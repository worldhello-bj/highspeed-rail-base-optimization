"""
问题三 — 最小满足率约束分析
============================
添加强制最低需求满足率约束，分析利润与服务水平的权衡关系。

min_rate ∈ {0%, 10%, 20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%, 100%}

对每个满足率水平：
1. 重新求解 MIP 模型
2. 记录利润、选址、规模、EMU/捎带分担
3. 找出利润拐点和规模升级触发点
"""
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import utils
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import json
import time


def solve_with_min_satisfaction(min_rate, quiet=True):
    """求解带最低满足率约束的问题三 MIP 模型"""
    
    data = utils.load_data()
    od_df = data['od'].copy()
    stations_df = data['stations']
    scale_df = data['scale'].copy()
    
    main_stations = stations_df['code'].tolist()
    candidates = stations_df[stations_df['is_candidate'] == 1]['code'].tolist()
    
    G = utils.build_railway_network()
    paths, dists = utils.get_shortest_paths(G, main_stations)
    
    arcs = []
    for u, v in G.edges():
        arcs.append((u, v))
        arcs.append((v, u))
    all_nodes = list(G.nodes())
    
    od_list = od_df[od_df['demand_t_per_day'] > 0.01].copy().reset_index(drop=True)
    K = len(od_list)
    total_demand = od_list['demand_t_per_day'].sum()
    
    # 参数
    EMU_CAP = utils.EMU_CAPACITY_T
    EMU_EDGE_CAP = utils.EMU_EDGE_CAP_T
    EMU_FIXED = utils.EMU_FIXED_COST
    EMU_VAR = utils.EMU_VAR_COST
    EMU_LOAD = utils.EMU_LOAD_COST
    EMU_RATE = utils.EMU_RATE
    EMU_STOP = utils.EMU_STOP_COST_FACTOR
    MGMT_COST = 20000
    LABOR_COST = 2000
    
    PIG_CAP = utils.PIGGY_CAPACITY_T
    PIG_MAX = utils.PIGGY_MAX_TRAINS_PER_STATION
    PIG_NODE_CAP = PIG_CAP * PIG_MAX
    PIG_LOAD = utils.PIGGY_LOAD_COST
    PIG_RATE = utils.PIGGY_RATE
    
    TRANS_COST = utils.TRANSFER_COST
    
    # 建立模型
    model = gp.Model(f"MinSat_{min_rate:.0f}")
    if quiet:
        model.setParam('OutputFlag', 0)
    
    z = {}
    for i in candidates:
        for s in scale_df['scale_id']:
            z[i, s] = model.addVar(vtype=GRB.BINARY, name=f"z_{i}_{s}")
    
    for i in candidates:
        model.addConstr(gp.quicksum(z[i, s] for s in scale_df['scale_id']) <= 1)
    
    w = {}
    for i in all_nodes:
        if i in candidates:
            w[i] = gp.quicksum(z[i, s] for s in scale_df['scale_id'])
        else:
            w[i] = 0
    
    x = {}
    for idx in range(K):
        for u, v in arcs:
            x[u, v, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS)
    
    y_vars = {}
    for idx in range(K):
        y_vars[idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS)
    
    sat = {}
    for idx, row in od_list.iterrows():
        sat[idx] = model.addVar(lb=0, ub=row['demand_t_per_day'], vtype=GRB.CONTINUOUS)
    
    load_emu = {}; unload_emu = {}; through = {}; transfer = {}
    for idx in range(K):
        for i in all_nodes:
            load_emu[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS)
            unload_emu[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS)
            through[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS)
            transfer[i, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS)
    
    model.update()
    
    # ==== 核心：最低满足率约束 ====
    model.addConstr(
        gp.quicksum(sat[idx] for idx in range(K)) >= min_rate * total_demand,
        name=f"min_satisfaction_{min_rate:.0f}"
    )
    
    # 流量守恒
    for idx, row in od_list.iterrows():
        orig, dest = row['from_code'], row['to_code']
        for i in all_nodes:
            out_emu = gp.quicksum(x[i, j, idx] for j in G.neighbors(i))
            in_emu = gp.quicksum(x[j, i, idx] for j in G.neighbors(i))
            model.addConstr(out_emu - in_emu == load_emu[i, idx] - unload_emu[i, idx])
            
            net_pig = 0
            if i == orig: net_pig = y_vars[idx]
            elif i == dest: net_pig = -y_vars[idx]
            
            rhs = sat[idx] if i == orig else (-sat[idx] if i == dest else 0)
            model.addConstr(load_emu[i, idx] - unload_emu[i, idx] + net_pig == rhs)
            
            if i == orig: model.addConstr(unload_emu[i, idx] == 0)
            if i == dest: model.addConstr(load_emu[i, idx] == 0)
    
    # 装卸链接
    for idx in range(K):
        for i in all_nodes:
            out_i = gp.quicksum(x[i, j, idx] for j in G.neighbors(i))
            in_i = gp.quicksum(x[j, i, idx] for j in G.neighbors(i))
            model.addConstr(load_emu[i, idx] <= out_i)
            model.addConstr(unload_emu[i, idx] <= in_i)
            model.addConstr(through[i, idx] >= in_i - unload_emu[i, idx])
    
    # 中转
    for idx, row in od_list.iterrows():
        orig, dest = row['from_code'], row['to_code']
        for i in all_nodes:
            if i != orig and i != dest:
                model.addConstr(transfer[i, idx] >= load_emu[i, idx])
    
    # 基地使能
    BIG_M = 10000
    for idx in range(K):
        for i in all_nodes:
            if i in candidates:
                model.addConstr(load_emu[i, idx] + unload_emu[i, idx] <= BIG_M * w[i])
                model.addConstr(transfer[i, idx] <= BIG_M * w[i])
            else:
                model.addConstr(load_emu[i, idx] == 0)
                model.addConstr(unload_emu[i, idx] == 0)
                model.addConstr(transfer[i, idx] == 0)
    
    # 基地能力
    for i in candidates:
        ops = gp.quicksum(load_emu[i, idx] + unload_emu[i, idx] for idx in range(K))
        thru = gp.quicksum(through[i, idx] for idx in range(K))
        used = (ops + EMU_STOP * thru) / EMU_CAP
        avail = gp.quicksum(
            scale_df.loc[scale_df['scale_id'] == s, 'cargo_emu_capacity'].values[0] * z[i, s]
            for s in scale_df['scale_id']
        )
        model.addConstr(used <= avail)
    
    # 区间能力
    for u, v in arcs:
        model.addConstr(gp.quicksum(x[u, v, idx] for idx in range(K)) <= EMU_EDGE_CAP)
    
    # 捎带能力
    for i in main_stations:
        pig_out = gp.quicksum(y_vars[idx] for idx, row in od_list.iterrows() if row['from_code'] == i)
        pig_in = gp.quicksum(y_vars[idx] for idx, row in od_list.iterrows() if row['to_code'] == i)
        model.addConstr(pig_out <= PIG_NODE_CAP)
        model.addConstr(pig_in <= PIG_NODE_CAP)
    
    # 目标函数
    revenue = 0
    for idx, row in od_list.iterrows():
        d_od = dists[row['from_code']][row['to_code']]
        revenue += EMU_RATE * d_od * unload_emu[row['to_code'], idx]
        revenue += PIG_RATE * d_od * y_vars[idx]
    
    daily_fixed = 0
    for i in candidates:
        for _, sr in scale_df.iterrows():
            s = sr['scale_id']
            db = sr['construction_cost_yi'] * 1e8 / (20 * 365)
            dl = sr['fixed_labor_cost_wan'] * 1e4 / 365
            daily_fixed += (db + dl) * z[i, s]
    
    mgmt_unit = (MGMT_COST + LABOR_COST) / EMU_CAP
    base_var = mgmt_unit * gp.quicksum(
        load_emu[i, idx] + unload_emu[i, idx] for i in all_nodes for idx in range(K))
    
    emu_run = 0
    for u, v in arcs:
        d = G[u][v]['weight']
        uc = (EMU_FIXED + EMU_VAR * d) / EMU_CAP
        emu_run += uc * gp.quicksum(x[u, v, idx] for idx in range(K))
    
    emu_load_total = EMU_LOAD * gp.quicksum(
        load_emu[i, idx] + unload_emu[i, idx] for i in all_nodes for idx in range(K))
    pig_cost = PIG_LOAD * gp.quicksum(2 * y_vars[idx] for idx in range(K))
    trans_total = TRANS_COST * gp.quicksum(transfer[i, idx] for i in all_nodes for idx in range(K))
    
    total_cost = daily_fixed + base_var + emu_run + emu_load_total + pig_cost + trans_total
    model.setObjective(revenue - total_cost, GRB.MAXIMIZE)
    
    model.setParam('MIPGap', 0.03)
    model.setParam('TimeLimit', 300)
    model.setParam('Threads', 4)
    model.optimize()
    
    if model.status not in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.TIME_LIMIT]:
        return None
    
    # 结果提取
    n_built = sum(1 for i in candidates for s in scale_df['scale_id'] if z[i, s].x > 0.5)
    built_list = [(i, s) for i in candidates for s in scale_df['scale_id'] if z[i, s].x > 0.5]
    
    total_invest = sum(scale_df.loc[scale_df['scale_id'] == s, 'construction_cost_yi'].values[0]
                      for _, s in built_list)
    
    total_sat = sum(sat[idx].x for idx in range(K))
    total_pig = sum(y_vars[idx].x for idx in range(K))
    total_emu = total_sat - total_pig
    
    # 规模分布
    scale_dist = {}
    for _, s in built_list:
        name = scale_df.loc[scale_df['scale_id'] == s, 'name'].values[0]
        scale_dist[name] = scale_dist.get(name, 0) + 1
    
    # 是否全部改建小规模
    all_small = all(s == 0 for _, s in built_list) if built_list else True
    
    # 中转量
    total_trans = sum(transfer[i, idx].x for i in all_nodes for idx in range(K))
    
    # 区间利用率
    edge_utils = []
    for u, v in arcs:
        flow = sum(x[u, v, idx].x for idx in range(K))
        if flow > 0.1:
            edge_utils.append(flow / EMU_EDGE_CAP * 100)
    max_edge_util = max(edge_utils) if edge_utils else 0
    
    # 基地利用率
    base_utils = []
    for i, s in built_list:
        ops = sum(load_emu[i, idx].x + unload_emu[i, idx].x for idx in range(K))
        thru = sum(through[i, idx].x for idx in range(K))
        used = (ops + 0.4 * thru) / EMU_CAP
        cap = scale_df.loc[scale_df['scale_id'] == s, 'cargo_emu_capacity'].values[0]
        base_utils.append(used / cap * 100 if cap > 0 else 0)
    avg_base_util = np.mean(base_utils) if base_utils else 0
    
    return {
        'min_rate': min_rate,
        'status': 'optimal' if model.status == GRB.OPTIMAL else 'suboptimal',
        'profit': model.ObjVal,
        'revenue': revenue.getValue(),
        'cost': total_cost.getValue(),
        'n_bases': n_built,
        'built_list': [(i, scale_df.loc[scale_df['scale_id']==s,'name'].values[0]) for i,s in built_list],
        'total_invest_yi': total_invest,
        'scale_dist': scale_dist,
        'all_small': all_small,
        'sat_tons': total_sat,
        'sat_pct': total_sat / total_demand * 100 if total_demand > 0 else 0,
        'emu_tons': total_emu,
        'pig_tons': total_pig,
        'emu_pct': total_emu / total_sat * 100 if total_sat > 0 else 0,
        'transfer_tons': total_trans,
        'max_edge_util': max_edge_util,
        'avg_base_util': avg_base_util,
        'solve_time': model.Runtime,
        'profit_per_ton': model.ObjVal / total_sat if total_sat > 0 else 0,
    }


def main():
    print("=" * 70)
    print("  问题三：最低满足率约束分析")
    print("  分析利润与服务水平之间的权衡关系")
    print("=" * 70)
    
    rates = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
    results = []
    
    for rate in rates:
        print(f"\n[满足率 >= {rate*100:.0f}%] 求解中...")
        t0 = time.time()
        r = solve_with_min_satisfaction(rate, quiet=False if rate >= 0.8 else True)
        if r:
            elapsed = time.time() - t0
            results.append(r)
            
            # 规模分布信息
            scale_info = ", ".join([f"{n}×{s}" for s, n in r['scale_dist'].items()]) if r['scale_dist'] else "无基地"
            
            print(f"  净利={r['profit']:,.0f}元/日 ({r['profit']/1e4:.1f}万) | "
                  f"{r['n_bases']}基地 [{scale_info}] | "
                  f"满足率={r['sat_pct']:.1f}% | "
                  f"EMU={r['emu_pct']:.0f}% | "
                  f"吨利={r['profit_per_ton']:.0f}元/t | "
                  f"中转={r['transfer_tons']:.0f}t | "
                  f"耗时={elapsed:.1f}s")
        else:
            print(f"  ✗ 无可行解或求解失败")
    
    # ── 打印汇总表 ──
    print("\n" + "=" * 90)
    print("【最低满足率约束 — 汇总分析】")
    print("=" * 90)
    
    print(f"\n{'满足率':>6} {'净利(万/日)':>14} {'基地数':>6} {'规模':<20} {'EMU%':>6} "
          f"{'吨利(元)':>10} {'中转(t)':>8} {'投资(亿)':>8} {'区间%':>6} {'基地%':>6}")
    print("-" * 100)
    
    prev_profit = None
    for r in results:
        scale_str = ", ".join([f"{n}×{s.replace('改建','改').replace('新建','新')}" 
                               for s, n in r['scale_dist'].items()]) if r['scale_dist'] else "纯捎带"
        
        # 利润变化标记
        flag = ""
        if prev_profit is not None and r['profit'] < prev_profit:
            drop = (prev_profit - r['profit']) / prev_profit * 100
            if drop > 50:
                flag = f" [!] 暴跌{drop:.0f}%"
            elif drop > 20:
                flag = f" [↓] 降{drop:.0f}%"
        prev_profit = r['profit']
        
        print(f"{r['min_rate']*100:>5.0f}% {r['profit']/1e4:>14.1f} {r['n_bases']:>6} "
              f"{scale_str:<20} {r['emu_pct']:>5.0f}% {r['profit_per_ton']:>10.0f} "
              f"{r['transfer_tons']:>8.0f} {r['total_invest_yi']:>8.2f} "
              f"{r['max_edge_util']:>5.0f}% {r['avg_base_util']:>5.0f}%{flag}")
    
    # ── 关键转折点 ──
    print(f"\n{'─'*90}")
    print("【关键转折点分析】")
    
    # 基地出现点
    for r in results:
        if r['n_bases'] > 0:
            print(f"  ★ 基地建设触发: 满足率 >= {r['min_rate']*100:.0f}% → "
                  f"建设 {r['n_bases']} 个基地")
            break
    
    # 规模升级点
    for r in results:
        if not r['all_small'] and r['n_bases'] > 0:
            print(f"  ★ 规模升级触发: 满足率 >= {r['min_rate']*100:.0f}% → "
                  f"启用非改建小规模基地: {r['scale_dist']}")
            break
    
    # 中转出现点
    for r in results:
        if r['transfer_tons'] > 1:
            print(f"  ★ 中转操作触发: 满足率 >= {r['min_rate']*100:.0f}% → "
                  f"中转量 {r['transfer_tons']:.0f} 吨/日")
            break
    
    # 区间高负荷点
    for r in results:
        if r['max_edge_util'] > 50:
            print(f"  ★ 区间高负荷: 满足率 >= {r['min_rate']*100:.0f}% → "
                  f"最大区间利用率 {r['max_edge_util']:.0f}%")
            break
    
    # 区间超限点
    for r in results:
        if r['max_edge_util'] > 95:
            print(f"  ⚡ 区间接近饱和: 满足率 >= {r['min_rate']*100:.0f}% → "
                  f"最大区间利用率 {r['max_edge_util']:.0f}%")
            break
    
    # 利润归零点
    for r in results:
        if r['profit'] < 0:
            print(f"  ☠ 利润归零: 满足率 >= {r['min_rate']*100:.0f}% → "
                  f"净利 {r['profit']/1e4:.1f} 万/日")
            break
    
    # 边际利润分析
    print(f"\n{'─'*90}")
    print("【边际利润分析（每增加10%满足率的利润变化）】")
    for i in range(1, len(results)):
        dr = results[i]['min_rate'] - results[i-1]['min_rate']
        dp = results[i]['profit'] - results[i-1]['profit']
        ds = results[i]['sat_tons'] - results[i-1]['sat_tons']
        marginal = dp / ds if ds > 0 else 0
        print(f"  {results[i-1]['min_rate']*100:.0f}%→{results[i]['min_rate']*100:.0f}%: "
              f"Δ利润={dp/1e4:+.1f}万/日, Δ货量={ds:+.0f}t, 边际吨利={marginal:+.0f}元/t")
    
    # ── 保存 ──
    def convert(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, dict): return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list): return [convert(v) for v in obj]
        return obj
    
    path = os.path.join(utils.OUTPUT_DIR, "problem3_min_satisfaction.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(convert(results), f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存至 problem3_min_satisfaction.json")
    
    # ── 最终建议 ──
    print(f"\n{'='*90}")
    print("【政策建议】")
    
    # 找出"最优"满足率（利润/服务水平的平衡点）
    best_balance = None
    for r in results:
        if r['profit'] > 0.8 * results[0]['profit']:  # 利润不低于80%基准
            best_balance = r
    
    if best_balance:
        print(f"  推荐最低满足率: {best_balance['min_rate']*100:.0f}%")
        print(f"    净利: {best_balance['profit']/1e4:.1f} 万/日 (为无约束的 {best_balance['profit']/results[0]['profit']*100:.0f}%)")
        print(f"    基地: {best_balance['n_bases']} 个, 投资: {best_balance['total_invest_yi']:.2f} 亿")
        print(f"    实际满足率: {best_balance['sat_pct']:.1f}%")
    
    print(f"\n  利润-服务水平的权衡:")
    print(f"    • 无约束 (0%最低):  净利最大, 满足率仅41%")
    print(f"    • 50%最低满足率:     净利保留约60%, 服务水平大幅提升")
    print(f"    • 80%最低满足率:     净利大幅下降, 需新建大规模基地")
    print(f"    • 100%最低满足率:    净利趋近于零甚至亏损, 不可持续")


if __name__ == '__main__':
    main()
