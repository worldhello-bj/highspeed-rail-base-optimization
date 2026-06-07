"""
问题三 — 综合敏感度分析
========================
系统性地分析关键参数对选址决策和净收益的影响：
1. 运价费率（EMU 4.5 + 捎带 3.0）
2. 需求水平（全局缩放）
3. 建设成本（全局缩放）
4. EMU 固定成本
5. 捎带能力上限
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
import copy
import time


def solve_problem3_with_params(rate_mult=1.0, demand_mult=1.0, cost_mult=1.0,
                                 emu_fixed_mult=1.0, pig_cap_mult=1.0,
                                 quiet=True):
    """运行参数调整后的问题三 MIP 模型，返回关键指标"""
    
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
    
    # 调整需求
    od_df['demand_t_per_day'] = od_df['demand_t_per_day'] * demand_mult
    od_list = od_df[od_df['demand_t_per_day'] > 0.01].copy().reset_index(drop=True)
    K = len(od_list)
    
    # 调整建设成本
    scale_df['construction_cost_yi'] = scale_df['construction_cost_yi'] * cost_mult
    
    # 参数（支持调整）
    EMU_CAP = utils.EMU_CAPACITY_T
    EMU_EDGE_CAP = utils.EMU_EDGE_CAP_T
    EMU_FIXED = utils.EMU_FIXED_COST * emu_fixed_mult
    EMU_VAR = utils.EMU_VAR_COST
    EMU_LOAD = utils.EMU_LOAD_COST
    EMU_RATE = utils.EMU_RATE * rate_mult
    EMU_STOP = utils.EMU_STOP_COST_FACTOR
    MGMT_COST = 20000
    LABOR_COST = 2000
    
    PIG_CAP = utils.PIGGY_CAPACITY_T * pig_cap_mult
    PIG_MAX = utils.PIGGY_MAX_TRAINS_PER_STATION
    PIG_NODE_CAP = PIG_CAP * PIG_MAX
    PIG_LOAD = utils.PIGGY_LOAD_COST
    PIG_RATE = utils.PIGGY_RATE * rate_mult
    
    TRANS_COST = utils.TRANSFER_COST
    
    # 建立模型（与 problem3.py 相同结构，简化版）
    model = gp.Model("Sensitivity")
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
    
    # 约束
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
            
            if i == orig:
                model.addConstr(unload_emu[i, idx] == 0)
            if i == dest:
                model.addConstr(load_emu[i, idx] == 0)
    
    for idx in range(K):
        for i in all_nodes:
            out_i = gp.quicksum(x[i, j, idx] for j in G.neighbors(i))
            in_i = gp.quicksum(x[j, i, idx] for j in G.neighbors(i))
            model.addConstr(load_emu[i, idx] <= out_i)
            model.addConstr(unload_emu[i, idx] <= in_i)
            model.addConstr(through[i, idx] >= in_i - unload_emu[i, idx])
    
    for idx, row in od_list.iterrows():
        orig, dest = row['from_code'], row['to_code']
        for i in all_nodes:
            if i != orig and i != dest:
                model.addConstr(transfer[i, idx] >= load_emu[i, idx])
    
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
    
    for i in candidates:
        ops = gp.quicksum(load_emu[i, idx] + unload_emu[i, idx] for idx in range(K))
        thru = gp.quicksum(through[i, idx] for idx in range(K))
        used = (ops + EMU_STOP * thru) / EMU_CAP
        avail = gp.quicksum(
            scale_df.loc[scale_df['scale_id'] == s, 'cargo_emu_capacity'].values[0] * z[i, s]
            for s in scale_df['scale_id']
        )
        model.addConstr(used <= avail)
    
    for u, v in arcs:
        model.addConstr(gp.quicksum(x[u, v, idx] for idx in range(K)) <= EMU_EDGE_CAP)
    
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
    base_var = mgmt_unit * gp.quicksum(load_emu[i, idx] + unload_emu[i, idx] for i in all_nodes for idx in range(K))
    
    emu_run = 0
    for u, v in arcs:
        d = G[u][v]['weight']
        uc = (EMU_FIXED + EMU_VAR * d) / EMU_CAP
        emu_run += uc * gp.quicksum(x[u, v, idx] for idx in range(K))
    
    emu_load_total = EMU_LOAD * gp.quicksum(load_emu[i, idx] + unload_emu[i, idx] for i in all_nodes for idx in range(K))
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
    
    # 提取结果
    n_built = sum(1 for i in candidates for s in scale_df['scale_id'] if z[i, s].x > 0.5)
    total_invest = sum(scale_df.loc[scale_df['scale_id'] == s, 'construction_cost_yi'].values[0]
                      for i in candidates for s in scale_df['scale_id'] if z[i, s].x > 0.5)
    
    total_sat = sum(sat[idx].x for idx in range(K))
    total_pig = sum(y_vars[idx].x for idx in range(K))
    total_emu = total_sat - total_pig
    total_demand = od_list['demand_t_per_day'].sum()
    
    # 判断是否全部选择改建小规模
    all_small = all(
        list(scale_df['scale_id'])[0] == s
        for i in candidates for s in scale_df['scale_id'] if z[i, s].x > 0.5
    ) if n_built > 0 else True
    
    return {
        'profit': model.ObjVal,
        'revenue': revenue.getValue(),
        'cost': total_cost.getValue(),
        'n_bases': n_built,
        'total_invest_yi': total_invest,
        'all_small_scale': all_small,
        'sat_tons': total_sat,
        'sat_pct': total_sat / total_demand * 100 if total_demand > 0 else 0,
        'emu_tons': total_emu,
        'pig_tons': total_pig,
        'emu_pct': total_emu / total_sat * 100 if total_sat > 0 else 0,
        'solve_time': model.Runtime,
    }


def run_sensitivity_analysis():
    """运行完整的敏感度分析"""
    print("=" * 70)
    print("  问题三：敏感度分析")
    print("=" * 70)
    
    # ── 基准情景 ──
    print("\n[1] 基准情景求解...")
    t0 = time.time()
    base = solve_problem3_with_params(rate_mult=1.0, demand_mult=1.0, cost_mult=1.0,
                                       emu_fixed_mult=1.0, pig_cap_mult=1.0, quiet=False)
    print(f"  基准: 净利={base['profit']:,.0f}元/日, {base['n_bases']}基地, "
          f"满足率={base['sat_pct']:.1f}%, 耗时={time.time()-t0:.1f}s")
    
    # ── 1. 运价费率敏感度 ──
    print("\n[2] 运价费率敏感度 (EMU + 捎带)...")
    rate_results = []
    for mult in [0.3, 0.5, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0]:
        r = solve_problem3_with_params(rate_mult=mult)
        if r:
            rate_results.append({'mult': mult, **r})
            print(f"  费率x{mult:.1f}: 净利={r['profit']:,.0f}, {r['n_bases']}基地, "
                  f"满足率={r['sat_pct']:.1f}%, EMU={r['emu_pct']:.0f}%")
    
    # ── 2. 需求水平敏感度 ──
    print("\n[3] 需求水平敏感度...")
    demand_results = []
    for mult in [0.3, 0.5, 0.7, 1.0, 1.3, 1.5, 2.0, 3.0, 5.0]:
        r = solve_problem3_with_params(demand_mult=mult)
        if r:
            demand_results.append({'mult': mult, **r})
            print(f"  需求x{mult:.1f}: 净利={r['profit']:,.0f}, {r['n_bases']}基地, "
                  f"满足率={r['sat_pct']:.1f}%, 全小规模={r['all_small_scale']}")
    
    # ── 3. 建设成本敏感度 ──
    print("\n[4] 建设成本敏感度...")
    cost_results = []
    for mult in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0]:
        r = solve_problem3_with_params(cost_mult=mult)
        if r:
            cost_results.append({'mult': mult, **r})
            print(f"  成本x{mult:.1f}: 净利={r['profit']:,.0f}, {r['n_bases']}基地, "
                  f"投资={r['total_invest_yi']:.1f}亿")
    
    # ── 4. EMU 固定成本敏感度 ──
    print("\n[5] EMU 固定成本敏感度 (50000元/列)...")
    emu_fixed_results = []
    for mult in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]:
        r = solve_problem3_with_params(emu_fixed_mult=mult)
        if r:
            emu_fixed_results.append({'mult': mult, **r})
            print(f"  EMU固定x{mult:.1f}: 净利={r['profit']:,.0f}, EMU={r['emu_pct']:.0f}%")
    
    # ── 5. 捎带能力敏感度 ──
    print("\n[6] 捎带能力敏感度 (6列/日/站)...")
    pig_cap_results = []
    for mult in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]:
        r = solve_problem3_with_params(pig_cap_mult=mult)
        if r:
            pig_cap_results.append({'mult': mult, **r})
            print(f"  捎带能力x{mult:.1f}: 净利={r['profit']:,.0f}, "
                  f"捎带={r['pig_tons']:.0f}t, EMU={r['emu_pct']:.0f}%")
    
    # ── 汇总保存 ──
    all_results = {
        'base': base,
        'rate': rate_results,
        'demand': demand_results,
        'cost': cost_results,
        'emu_fixed': emu_fixed_results,
        'pig_cap': pig_cap_results,
    }
    
    path = os.path.join(utils.OUTPUT_DIR, "problem3_sensitivity_full.json")
    with open(path, 'w', encoding='utf-8') as f:
        # Convert numpy types
        def convert(obj):
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            if isinstance(obj, dict): return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list): return [convert(v) for v in obj]
            return obj
        json.dump(convert(all_results), f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存至 problem3_sensitivity_full.json")
    
    # ── 打印汇总表 ──
    print("\n" + "=" * 70)
    print("【敏感度分析汇总】")
    print("=" * 70)
    
    print(f"\n{'参数':<16} {'变动':>8} {'净利(万/日)':>14} {'基地数':>8} {'满足率':>8} {'EMU%':>8} {'投资(亿)':>10}")
    print("-" * 76)
    
    print(f"{'基准情景':<16} {'1.0x':>8} {base['profit']/1e4:>14.1f} {base['n_bases']:>8} {base['sat_pct']:>8.1f} {base['emu_pct']:>8.1f} {base['total_invest_yi']:>10.2f}")
    
    # 关键转折点
    print(f"\n--- 运价费率 ---")
    for r in rate_results:
        marker = " <<<" if r['profit'] < 10000 else ""
        print(f"  {'费率':<14} {r['mult']:.1f}x {'->':>4} {r['profit']/1e4:>10.1f}万/日, "
              f"{r['n_bases']}站, 满足率{r['sat_pct']:.0f}%{marker}")
    
    print(f"\n--- 需求水平 ---")
    for r in demand_results:
        scale_info = ""
        if not r['all_small_scale']:
            scale_info = " [升级规模!]"
        print(f"  {'需求':<14} {r['mult']:.1f}x {'->':>4} {r['profit']/1e4:>10.1f}万/日, "
              f"{r['n_bases']}站, 满足率{r['sat_pct']:.0f}%{scale_info}")
    
    print(f"\n--- 建设成本 ---")
    for r in cost_results:
        print(f"  {'建设成本':<14} {r['mult']:.1f}x {'->':>4} {r['profit']/1e4:>10.1f}万/日, "
              f"{r['n_bases']}站, 投资{r['total_invest_yi']:.1f}亿")
    
    # 盈亏平衡点查找
    print(f"\n--- 关键盈亏平衡点 ---")
    
    # 费率盈亏平衡
    for r in rate_results:
        if r['profit'] > 0:
            bep_rate = r['mult']
    print(f"  运价费率盈亏平衡: 约 {bep_rate*100:.0f}% 基准费率 (EMU={4.5*bep_rate:.1f}, 捎带={3.0*bep_rate:.1f})")
    
    # 需求盈亏平衡
    for r in demand_results:
        if r['profit'] > 0:
            bep_demand = r['mult']
    print(f"  需求盈亏平衡: 约 {bep_demand*100:.0f}% 基准需求 ({1908.4*bep_demand:.0f}吨/日)")
    
    # 需求规模升级触发点
    for r in demand_results:
        if not r['all_small_scale']:
            print(f"  规模升级触发需求: 约 {r['mult']*100:.0f}% 基准需求 ({1908.4*r['mult']:.0f}吨/日), "
                  f"建设{r['n_bases']}站, 投资{r['total_invest_yi']:.1f}亿")


if __name__ == '__main__':
    run_sensitivity_analysis()
