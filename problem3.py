"""
问题 3：基地选址与规模优化 (MIP)
================================================================================
任务：
  在 12 个备选站点中选择建哪些基地、建什么规模，使得净收益最大。

核心决策：
  1. 选址：z[i,s] in {0,1} — 是否在站点 i 建设规模 s 的基地
  2. 货流分配：x[u,v,k] — EMU流, y[k] — 捎带直达流
  3. 中转：仅在有基地的站点允许货物在 EMU 之间换乘

约束关系：
  * 每个候选站最多建 1 个基地（4 种规模选 1 或都不建）
  * EMU 装卸操作只能在有基地的站点进行
  * 货物中转只能在有基地的站点进行
  * 基地处理能力 = 装卸列车 + 0.4*中途停靠列车
  * 线路通过能力：8列/日/区段（单向）
  * 捎带能力：6列/日/站（发出或到达）
  * 流量守恒：EMU + 捎带 = 满足的需求

目标函数（日均净收益）：
  收入 = 4.5*运距*EMU送达量 + 3.0*运距*捎带送达量
  成本 = 建设折旧 + 固定人工 + 操作变动费 + 列车运行费 + 装卸费 + 中转费
================================================================================
"""
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import utils
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np


def build_and_solve():
    """构建并求解基地选址 MIP 模型"""
    
    # ── 1. 数据准备 ─────────────────────────────────
    data = utils.load_data()
    od_df = data['od']
    stations_df = data['stations']
    scale_df = data['scale']
    
    code_to_name = dict(zip(stations_df['code'], stations_df['name']))
    main_stations = stations_df['code'].tolist()
    main_set = set(main_stations)
    
    # 候选基地站点
    candidates = stations_df[stations_df['is_candidate'] == 1]['code'].tolist()
    
    G = utils.build_railway_network()
    paths, dists = utils.get_shortest_paths(G, main_stations)
    
    # 有向边列表
    arcs = []
    for u, v in G.edges():
        arcs.append((u, v))
        arcs.append((v, u))
    
    all_nodes = list(G.nodes())
    
    # 有需求的 OD 列表
    od_list = od_df[od_df['demand_t_per_day'] > 0].copy().reset_index(drop=True)
    K = len(od_list)
    
    # ── 2. 模型参数 ─────────────────────────────────
    EMU_CAP = utils.EMU_CAPACITY_T           # 85 吨/列
    EMU_EDGE_CAP = utils.EMU_EDGE_CAP_T      # 680 吨/日
    EMU_FIXED = utils.EMU_FIXED_COST         # 50000 元/列
    EMU_VAR = utils.EMU_VAR_COST             # 116.6 元/km
    EMU_LOAD_COST = utils.EMU_LOAD_COST      # 144 元/吨
    EMU_RATE = utils.EMU_RATE                # 4.5 元/吨公里
    EMU_STOP = utils.EMU_STOP_COST_FACTOR    # 0.4
    MGMT_COST = 20000                        # 管理成本 元/列
    LABOR_COST = 2000                        # 单列人工 元/列
    
    PIG_CAP = utils.PIGGY_CAPACITY_T         # 8 吨/列
    PIG_MAX_TRAINS = utils.PIGGY_MAX_TRAINS_PER_STATION
    PIG_NODE_CAP = PIG_CAP * PIG_MAX_TRAINS  # 48 吨/日
    PIG_LOAD_COST = utils.PIGGY_LOAD_COST    # 120 元/吨
    PIG_RATE = utils.PIGGY_RATE              # 3.0 元/吨公里
    
    TRANS_COST = utils.TRANSFER_COST         # 2.52 元/吨次
    
    print(f"  候选基地: {len(candidates)} 个 ({', '.join(candidates)})")
    print(f"  OD 对数: {K}")
    print(f"  总需求: {od_list['demand_t_per_day'].sum():.1f} 吨/日")
    
    # ── 3. 建立模型 ─────────────────────────────────
    model = gp.Model("Base_Location_Scale")
    model.setParam('OutputFlag', 0)
    
    # === 3.1 选址决策变量 ===
    z = {}
    for i in candidates:
        for s in scale_df['scale_id']:
            z[i, s] = model.addVar(vtype=GRB.BINARY, name=f"z_{i}_{s}")
    
    for i in candidates:
        model.addConstr(
            gp.quicksum(z[i, s] for s in scale_df['scale_id']) <= 1,
            name=f"one_scale_{i}"
        )
    
    w = {}
    for i in all_nodes:
        if i in candidates:
            w[i] = gp.quicksum(z[i, s] for s in scale_df['scale_id'])
        else:
            w[i] = 0

    # === 3.2 货流决策变量 ===
    x = {}
    for idx in range(K):
        for u, v in arcs:
            x[u, v, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS,
                                        name=f"x_{u}_{v}_{idx}")
    
    y = {}
    for idx in range(K):
        y[idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name=f"y_{idx}")
    
    sat = {}
    for idx, row in od_list.iterrows():
        sat[idx] = model.addVar(lb=0, ub=row['demand_t_per_day'],
                                vtype=GRB.CONTINUOUS, name=f"sat_{idx}")
    
    load_emu = {}
    unload_emu = {}
    for idx in range(K):
        for i in all_nodes:
            load_emu[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS,
                                            name=f"load_{i}_{idx}")
            unload_emu[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS,
                                              name=f"unload_{i}_{idx}")
    
    through = {}
    for idx in range(K):
        for i in all_nodes:
            through[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS,
                                           name=f"thru_{i}_{idx}")
    
    transfer = {}
    for idx in range(K):
        for i in all_nodes:
            transfer[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS,
                                            name=f"tr_{i}_{idx}")
    
    model.update()
    
    # ── 4. 约束条件 ─────────────────────────────────
    
    # === 4.1 流量守恒 ===
    for idx, row in od_list.iterrows():
        orig = row['from_code']
        dest = row['to_code']
        
        for i in all_nodes:
            out_emu = gp.quicksum(x[i, j, idx] for j in G.neighbors(i))
            in_emu = gp.quicksum(x[j, i, idx] for j in G.neighbors(i))
            
            model.addConstr(
                out_emu - in_emu == load_emu[i, idx] - unload_emu[i, idx],
                name=f"emu_balance_{i}_{idx}"
            )
            
            net_pig = 0
            if i == orig:
                net_pig = y[idx]
            elif i == dest:
                net_pig = -y[idx]
            
            rhs = sat[idx] if i == orig else (-sat[idx] if i == dest else 0)
            model.addConstr(
                load_emu[i, idx] - unload_emu[i, idx] + net_pig == rhs,
                name=f"total_balance_{i}_{idx}"
            )
            
            # 关键约束：起点禁止卸车，终点禁止装车
            if i == orig:
                model.addConstr(unload_emu[i, idx] == 0,
                               name=f"no_unload_orig_{i}_{idx}")
            if i == dest:
                model.addConstr(load_emu[i, idx] == 0,
                               name=f"no_load_dest_{i}_{idx}")
    
    # === 4.2 装卸量与 EMU 流链接约束 ===
    for idx in range(K):
        for i in all_nodes:
            out_emu_i = gp.quicksum(x[i, j, idx] for j in G.neighbors(i))
            in_emu_i = gp.quicksum(x[j, i, idx] for j in G.neighbors(i))
            model.addConstr(load_emu[i, idx] <= out_emu_i,
                           name=f"load_le_out_{i}_{idx}")
            model.addConstr(unload_emu[i, idx] <= in_emu_i,
                           name=f"unload_le_in_{i}_{idx}")
    
    # === 4.3 通过流量定义 ===
    for idx in range(K):
        for i in all_nodes:
            in_emu = gp.quicksum(x[j, i, idx] for j in G.neighbors(i))
            model.addConstr(
                through[i, idx] >= in_emu - unload_emu[i, idx],
                name=f"through_def_{i}_{idx}"
            )
    
    # === 4.4 中转量定义 ===
    for idx, row in od_list.iterrows():
        orig = row['from_code']
        dest = row['to_code']
        for i in all_nodes:
            if i != orig and i != dest:
                model.addConstr(
                    transfer[i, idx] >= load_emu[i, idx],
                    name=f"transfer_def_{i}_{idx}"
                )
    
    # === 4.5 基地操作约束 ===
    BIG_M = 10000
    for idx in range(K):
        for i in all_nodes:
            if i in candidates:
                model.addConstr(
                    load_emu[i, idx] + unload_emu[i, idx] <= BIG_M * w[i],
                    name=f"base_ops_{i}_{idx}"
                )
            else:
                model.addConstr(load_emu[i, idx] == 0, name=f"no_load_{i}_{idx}")
                model.addConstr(unload_emu[i, idx] == 0, name=f"no_unload_{i}_{idx}")
    
    for idx in range(K):
        for i in all_nodes:
            if i in candidates:
                model.addConstr(
                    transfer[i, idx] <= BIG_M * w[i],
                    name=f"transfer_base_{i}_{idx}"
                )
            else:
                model.addConstr(transfer[i, idx] == 0, name=f"no_transfer_{i}_{idx}")
    
    # === 4.6 基地处理能力约束 ===
    for i in candidates:
        total_ops_tons = gp.quicksum(
            load_emu[i, idx] + unload_emu[i, idx] for idx in range(K)
        )
        total_thru_tons = gp.quicksum(through[i, idx] for idx in range(K))
        
        capacity_used = (total_ops_tons + EMU_STOP * total_thru_tons) / EMU_CAP
        
        capacity_available = gp.quicksum(
            scale_df.loc[scale_df['scale_id'] == s, 'cargo_emu_capacity'].values[0]
            * z[i, s]
            for s in scale_df['scale_id']
        )
        
        model.addConstr(capacity_used <= capacity_available, name=f"base_cap_{i}")
    
    # === 4.7 线路通过能力 ===
    for u, v in arcs:
        total_flow = gp.quicksum(x[u, v, idx] for idx in range(K))
        model.addConstr(total_flow <= EMU_EDGE_CAP, name=f"edge_{u}_{v}")
    
    # === 4.8 捎带车站能力 ===
    for i in main_stations:
        pig_out = gp.quicksum(y[idx] for idx, row in od_list.iterrows()
                              if row['from_code'] == i)
        pig_in = gp.quicksum(y[idx] for idx, row in od_list.iterrows()
                             if row['to_code'] == i)
        model.addConstr(pig_out <= PIG_NODE_CAP, name=f"pig_out_{i}")
        model.addConstr(pig_in <= PIG_NODE_CAP, name=f"pig_in_{i}")
    
    # ── 5. 目标函数 ─────────────────────────────────
    
    # === 5.1 收入 ===
    revenue = 0
    for idx, row in od_list.iterrows():
        orig = row['from_code']
        dest = row['to_code']
        d_od = dists[orig][dest]
        revenue += EMU_RATE * d_od * unload_emu[dest, idx]
        revenue += PIG_RATE * d_od * y[idx]
    
    # === 5.2 成本 ===
    
    # 5.2.1 建设成本 + 固定人工（日均）
    daily_fixed_cost = 0
    for i in candidates:
        for _, scale_row in scale_df.iterrows():
            s = scale_row['scale_id']
            build_yi = scale_row['construction_cost_yi']
            labor_wan = scale_row['fixed_labor_cost_wan']
            daily_build = build_yi * 1e8 / (utils.YEARS_AMORTIZATION * utils.DAYS_PER_YEAR)
            daily_labor = labor_wan * 1e4 / utils.DAYS_PER_YEAR
            daily_fixed_cost += (daily_build + daily_labor) * z[i, s]
    
    # 5.2.2 基地管理 + 单列人工
    mgmt_unit = (MGMT_COST + LABOR_COST) / EMU_CAP
    base_var_cost = mgmt_unit * gp.quicksum(
        load_emu[i, idx] + unload_emu[i, idx]
        for i in all_nodes for idx in range(K)
    )
    
    # 5.2.3 EMU 运行成本
    emu_run_cost = 0
    for u, v in arcs:
        dist = G[u][v]['weight']
        unit_cost = (EMU_FIXED + EMU_VAR * dist) / EMU_CAP
        edge_total = gp.quicksum(x[u, v, idx] for idx in range(K))
        emu_run_cost += unit_cost * edge_total
    
    # 5.2.4 EMU 装卸成本
    emu_load_total = EMU_LOAD_COST * gp.quicksum(
        load_emu[i, idx] + unload_emu[i, idx]
        for i in all_nodes for idx in range(K)
    )
    
    # 5.2.5 捎带装卸成本
    pig_cost = PIG_LOAD_COST * gp.quicksum(2 * y[idx] for idx in range(K))
    
    # 5.2.6 中转成本
    transfer_total = TRANS_COST * gp.quicksum(
        transfer[i, idx] for i in all_nodes for idx in range(K)
    )
    
    total_cost = (daily_fixed_cost + base_var_cost + emu_run_cost +
                  emu_load_total + pig_cost + transfer_total)
    
    net_profit = revenue - total_cost
    model.setObjective(net_profit, GRB.MAXIMIZE)
    
    # ── 6. 求解 ─────────────────────────────────────
    model.setParam('MIPGap', 0.03)
    model.setParam('TimeLimit', 600)
    model.setParam('Threads', 4)
    model.optimize()
    
    return model, locals()


def analyze_results(model, ctx):
    """分析并打印求解结果"""
    
    z = ctx['z']; sat = ctx['sat']; y = ctx['y']; x = ctx['x']
    load_emu = ctx['load_emu']; unload_emu = ctx['unload_emu']
    through = ctx['through']; transfer = ctx['transfer']
    
    od_list = ctx['od_list']; scale_df = ctx['scale_df']
    stations_df = ctx['stations_df']; candidates = ctx['candidates']
    all_nodes = ctx['all_nodes']; arcs = ctx['arcs']
    main_stations = ctx['main_stations']
    dists = ctx['dists']; code_to_name = ctx['code_to_name']
    
    EMU_CAP = utils.EMU_CAPACITY_T; EMU_EDGE_CAP = utils.EMU_EDGE_CAP_T
    
    if model.status not in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.TIME_LIMIT]:
        print(f"\n求解失败。状态码: {model.status}")
        return
    
    status_str = ('最优解' if model.status == GRB.OPTIMAL else 
                  ('次优解' if model.status == GRB.SUBOPTIMAL else '时间限制'))
    
    print(f"\n{'='*60}")
    print(f"  问题 3：基地选址与规模优化结果")
    print(f"  求解状态: {status_str} | 目标值: {model.ObjVal:,.2f} 元/日")
    print(f"{'='*60}")
    
    # ── 选址结果 ──
    print(f"\n【选址决策】")
    built = []
    for i in candidates:
        for _, sr in scale_df.iterrows():
            s = sr['scale_id']
            if z[i, s].x > 0.5:
                name = code_to_name.get(i, i)
                scale_name = sr['name']
                cap = sr['cargo_emu_capacity']
                build_yi = sr['construction_cost_yi']
                built.append((i, s, name, scale_name, cap, build_yi))
                print(f"  [+] {name}({i}) -- {scale_name} | "
                      f"处理能力: {cap}列/日 | 建设成本: {build_yi:.3f}亿元")
    
    if not built:
        print(f"  [-] 未选择建设任何基地")
    
    not_built = [i for i in candidates if all(z[i, s].x < 0.5 for s in scale_df['scale_id'])]
    if not_built:
        print(f"\n  未建基地的候选站: {', '.join(not_built)}")
    
    # ── 财务汇总 ──
    print(f"\n【财务汇总（日均）】")
    daily_fixed_val = ctx['daily_fixed_cost'].getValue()
    base_var_val = ctx['base_var_cost'].getValue()
    emu_run_val = ctx['emu_run_cost'].getValue()
    emu_load_val = ctx['emu_load_total'].getValue()
    pig_cost_val = ctx['pig_cost'].getValue()
    transfer_val = ctx['transfer_total'].getValue()
    revenue_val = ctx['revenue'].getValue()
    total_cost_val = ctx['total_cost'].getValue()
    
    print(f"  运输收入:         {revenue_val:>15,.2f} 元/日")
    print(f"  成本合计:         {total_cost_val:>15,.2f} 元/日")
    print(f"    建设折旧:       {daily_fixed_val:>15,.2f}")
    print(f"    基地操作费:     {base_var_val:>15,.2f}")
    print(f"    EMU 运行费:     {emu_run_val:>15,.2f}")
    print(f"    EMU 装卸费:     {emu_load_val:>15,.2f}")
    print(f"    捎带装卸费:     {pig_cost_val:>15,.2f}")
    print(f"    中转费:         {transfer_val:>15,.2f}")
    print(f"  日均净利润:       {model.ObjVal:>15,.2f} 元/日")
    print(f"  年化净利润:       {model.ObjVal * 365 / 1e8:>15.2f} 亿元/年")
    
    # ── 货流统计 ──
    K = len(od_list)
    total_demand = od_list['demand_t_per_day'].sum()
    total_sat = sum(sat[idx].x for idx in range(K))
    total_pig = sum(y[idx].x for idx in range(K))
    total_emu = total_sat - total_pig
    total_trans = sum(transfer[i, idx].x for i in all_nodes for idx in range(K))
    
    print(f"\n【货流统计】")
    print(f"  总需求:           {total_demand:>15.1f} 吨/日")
    print(f"  满足量:           {total_sat:>15.1f} 吨/日 ({total_sat/total_demand*100:.1f}%)")
    if total_sat > 0:
        print(f"    EMU 承运:       {total_emu:>15.1f} 吨/日 ({total_emu/total_sat*100:.1f}%)")
        print(f"    捎带承运:       {total_pig:>15.1f} 吨/日 ({total_pig/total_sat*100:.1f}%)")
    print(f"  总中转量:         {total_trans:>15.1f} 吨/日")
    
    # ── 基地负荷 ──
    print(f"\n【基地负荷分析】")
    for i, s, name, scale_name, cap, _ in built:
        ops = sum(load_emu[i, idx].x + unload_emu[i, idx].x for idx in range(K))
        thru = sum(through[i, idx].x for idx in range(K))
        used_trains = (ops + 0.4 * thru) / EMU_CAP
        util = used_trains / cap * 100 if cap > 0 else 0
        bar = '#' * int(util / 5) + '-' * (20 - int(util / 5))
        print(f"  {name}({i}): 装卸{ops:.0f}t 通过{thru:.0f}t | "
              f"占用{used_trains:.1f}/{cap}列 {bar} {util:.0f}%")
    
    # ── 瓶颈区段 ──
    print(f"\n【区段利用率 TOP-10】")
    edge_util = []
    for u, v in arcs:
        flow = sum(x[u, v, idx].x for idx in range(K))
        if flow > 1:
            util = flow / EMU_EDGE_CAP * 100
            edge_util.append((u, v, flow, util))
    edge_util.sort(key=lambda t: t[3], reverse=True)
    
    for rank, (u, v, flow, util) in enumerate(edge_util[:10], 1):
        u_name = code_to_name.get(u, u)
        v_name = code_to_name.get(v, v)
        bar = '#' * int(util / 5) + '-' * (20 - int(util / 5))
        print(f"  {rank:>2}. {u_name}->{v_name}: {flow:>8.1f}t {bar} {util:.0f}%")
    
    # ── 保存货流数据 ──
    x_res = []
    for u, v in arcs:
        total_x = sum(x[u, v, idx].x for idx in range(K))
        if total_x > 0.01:
            x_res.append({'u': u, 'v': v, 'flow': total_x})
    pd.DataFrame(x_res).to_csv(r"d:\高铁快运\problem3_x_flow.csv", index=False)
    
    y_res = []
    for idx in range(K):
        y_val = y[idx].x
        if y_val > 0.01:
            row = od_list.iloc[idx]
            y_res.append({'i': row['from_code'], 'j': row['to_code'], 'flow': y_val})
    pd.DataFrame(y_res).to_csv(r"d:\高铁快运\problem3_y_flow.csv", index=False)
    
    print(f"\n  货流数据已保存: problem3_x_flow.csv, problem3_y_flow.csv")
    
    # ── 结论 ──
    n_built = len(built)
    total_invest = sum(bi for _,_,_,_,_,bi in built)
    print(f"\n{'─'*60}")
    print(f"【问题 3 结论】")
    print(f"  1. 共建设 {n_built} 个基地，分别为: "
          f"{', '.join([code_to_name.get(i,i) for i,_,_,_,_,_ in built])}")
    print(f"  2. 总建设投资: {total_invest:.3f} 亿元 (日均折旧 {daily_fixed_val:,.0f} 元)")
    print(f"  3. 日均净利润 {model.ObjVal:,.0f} 元，年化 {model.ObjVal*365/1e8:.2f} 亿元")
    if total_sat > 0:
        print(f"  4. 需求满足率 {total_sat/total_demand*100:.1f}%，"
              f"EMU 占比 {total_emu/total_sat*100:.0f}%，捎带占比 {total_pig/total_sat*100:.0f}%")
        print(f"  5. 中转率 {total_trans/total_sat*100:.1f}%（每吨货物平均中转次数）")


def main():
    print("=" * 60)
    print("  问题 3：基地选址与规模优化 (MIP)")
    print("=" * 60)
    
    model, ctx = build_and_solve()
    analyze_results(model, ctx)


if __name__ == '__main__':
    main()
