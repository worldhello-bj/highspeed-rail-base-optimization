"""
问题 2：最小费用最大流分配
============================================================================
任务：
  1. 考虑线路通过能力（8列/日/区段）和车站办理能力约束
  2. 最小费用最大流原则分配 OD 货流
  3. 可使用货运动车组 + 捎带模式（确认车 8吨/列）
  4. 求最大可承运货流量及对应的最小费用分配方案

模型设计：
  - 货运动车组流 x[u,v,k]：商品 k 在有向边 (u,v) 上通过 EMU 运输的量
  - 捎带流 y[k]：商品 k 通过捎带模式从起点直达终点的量
  - 目标：最大化总满足量（主），最小化总费用（次）
  - 约束：线路通过能力、车站捎带能力、流量守恒
============================================================================
"""
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import utils
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np


def main():
    print("=" * 60)
    print("  问题 2：最小费用最大流分配（EMU + 捎带）")
    print("=" * 60)
    
    # ── 1. 加载数据 ─────────────────────────────────
    data = utils.load_data()
    od_df = data['od']
    stations_df = data['stations']
    code_to_name = dict(zip(stations_df['code'], stations_df['name']))
    main_stations = stations_df['code'].tolist()
    main_set = set(main_stations)
    
    G = utils.build_railway_network()
    paths, dists = utils.get_shortest_paths(G, main_stations)
    
    od_list = od_df[od_df['demand_t_per_day'] > 0].copy().reset_index(drop=True)
    K = len(od_list)
    
    arcs = []
    for u, v in G.edges():
        arcs.append((u, v))
        arcs.append((v, u))
    
    nodes = list(G.nodes())
    
    print(f"\n  OD 对数: {K}")
    print(f"  网络节点: {len(nodes)} (主站: {len(main_stations)})")
    print(f"  有向边数: {len(arcs)}")
    print(f"  总需求: {od_list['demand_t_per_day'].sum():.1f} 吨/日")
    
    # ── 2. 参数 ─────────────────────────────────────
    EMU_CAP = utils.EMU_CAPACITY_T
    EMU_EDGE_CAP = utils.EMU_EDGE_CAP_T
    EMU_FIXED = utils.EMU_FIXED_COST
    EMU_VAR = utils.EMU_VAR_COST
    EMU_LOAD = utils.EMU_LOAD_COST
    
    PIG_CAP = utils.PIGGY_CAPACITY_T
    PIG_MAX_TRAINS = utils.PIGGY_MAX_TRAINS_PER_STATION
    PIG_NODE_CAP_TONS = PIG_CAP * PIG_MAX_TRAINS
    PIG_LOAD = utils.PIGGY_LOAD_COST
    
    # ── 3. 建立优化模型 ─────────────────────────────
    model = gp.Model("MCMF_Problem2")
    model.setParam('OutputFlag', 0)
    
    x = {}
    for idx in range(K):
        for u, v in arcs:
            x[u, v, idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name=f"x_{u}_{v}_{idx}")
    
    y = {}
    for idx in range(K):
        y[idx] = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name=f"y_{idx}")
    
    sat = {}
    for idx, row in od_list.iterrows():
        sat[idx] = model.addVar(lb=0, ub=row['demand_t_per_day'], vtype=GRB.CONTINUOUS, name=f"sat_{idx}")
    
    model.update()
    
    # ── 4. 约束条件 ─────────────────────────────────
    for idx, row in od_list.iterrows():
        orig = row['from_code']
        dest = row['to_code']
        
        for i in nodes:
            out_emu = gp.quicksum(x[i, j, idx] for j in G.neighbors(i))
            in_emu = gp.quicksum(x[j, i, idx] for j in G.neighbors(i))
            net_emu = out_emu - in_emu
            
            net_pig = 0
            if i == orig:
                net_pig = y[idx]
            elif i == dest:
                net_pig = -y[idx]
            
            total_net = net_emu + net_pig
            
            if i == orig:
                model.addConstr(total_net == sat[idx], name=f"flow_orig_{idx}_{i}")
            elif i == dest:
                model.addConstr(total_net == -sat[idx], name=f"flow_dest_{idx}_{i}")
            else:
                model.addConstr(total_net == 0, name=f"flow_mid_{idx}_{i}")
    
    for u, v in arcs:
        total_emu = gp.quicksum(x[u, v, idx] for idx in range(K))
        model.addConstr(total_emu <= EMU_EDGE_CAP, name=f"edge_cap_{u}_{v}")
    
    for i in main_stations:
        pig_out = gp.quicksum(y[idx] for idx, row in od_list.iterrows() if row['from_code'] == i)
        pig_in = gp.quicksum(y[idx] for idx, row in od_list.iterrows() if row['to_code'] == i)
        model.addConstr(pig_out <= PIG_NODE_CAP_TONS, name=f"pig_out_{i}")
        model.addConstr(pig_in <= PIG_NODE_CAP_TONS, name=f"pig_in_{i}")
    
    # ── 5. 目标函数 ─────────────────────────────────
    emu_run_cost = 0
    for u, v in arcs:
        dist = G[u][v]['weight']
        unit_run_cost = (EMU_FIXED + EMU_VAR * dist) / EMU_CAP
        edge_flow = gp.quicksum(x[u, v, idx] for idx in range(K))
        emu_run_cost += unit_run_cost * edge_flow
    
    emu_load_cost = gp.quicksum(EMU_LOAD * 2 * (sat[idx] - y[idx]) for idx in range(K))
    pig_cost = gp.quicksum(PIG_LOAD * 2 * y[idx] for idx in range(K))
    
    total_cost = emu_run_cost + emu_load_cost + pig_cost
    total_satisfied = gp.quicksum(sat[idx] for idx in range(K))
    
    max_possible_cost = od_list['demand_t_per_day'].sum() * 3000 * 10
    M = max_possible_cost * 2
    model.setObjective(M * total_satisfied - total_cost, GRB.MAXIMIZE)
    
    # ── 6. 求解 ─────────────────────────────────────
    model.setParam('MIPGap', 0.001)
    model.optimize()
    
    # ── 7. 结果分析 ─────────────────────────────────
    if model.status in [GRB.OPTIMAL, GRB.SUBOPTIMAL]:
        total_demand = od_list['demand_t_per_day'].sum()
        total_sat_val = total_satisfied.getValue()
        total_cost_val = total_cost.getValue()
        emu_run_val = emu_run_cost.getValue()
        emu_load_val = emu_load_cost.getValue()
        pig_cost_val = pig_cost.getValue()
        
        print(f"\n{'-'*60}")
        print(f"【求解结果】状态: {'最优解' if model.status == GRB.OPTIMAL else '次优解'}")
        print(f"{'-'*60}")
        print(f"  总需求量:       {total_demand:>12.1f} 吨/日")
        print(f"  最大满足量:     {total_sat_val:>12.1f} 吨/日")
        print(f"  满足率:         {total_sat_val/total_demand*100:>11.1f}%")
        print(f"  未满足量:       {total_demand - total_sat_val:>12.1f} 吨/日")
        print(f"")
        print(f"  总费用:         {total_cost_val:>12.2f} 元/日")
        print(f"    - EMU 运行费:  {emu_run_val:>12.2f} 元/日")
        print(f"    - EMU 装卸费:  {emu_load_val:>12.2f} 元/日")
        print(f"    - 捎带装卸费:  {pig_cost_val:>12.2f} 元/日")
        
        emu_tonnage = 0
        pig_tonnage = 0
        for idx in range(K):
            sat_val = sat[idx].x
            y_val = y[idx].x
            emu_tonnage += (sat_val - y_val)
            pig_tonnage += y_val
        
        if total_sat_val > 0:
            print(f"")
            print(f"  货运动车组承运: {emu_tonnage:>12.1f} 吨/日 ({emu_tonnage/total_sat_val*100:.1f}%)")
            print(f"  捎带模式承运:   {pig_tonnage:>12.1f} 吨/日 ({pig_tonnage/total_sat_val*100:.1f}%)")
            
            avg_cost_per_ton = total_cost_val / total_sat_val
            avg_revenue = 0
            for idx, row in od_list.iterrows():
                orig = row['from_code']
                dest = row['to_code']
                d = dists[orig][dest]
                sat_val = sat[idx].x
                y_val = y[idx].x
                avg_revenue += 4.5 * d * (sat_val - y_val) + 3.0 * d * y_val
            avg_revenue_per_ton = avg_revenue / total_sat_val
            print(f"")
            print(f"  平均吨成本:     {avg_cost_per_ton:>12.2f} 元/吨")
            print(f"  平均吨收入:     {avg_revenue_per_ton:>12.2f} 元/吨")
            print(f"  吨均毛利:       {avg_revenue_per_ton - avg_cost_per_ton:>12.2f} 元/吨")
        
        print(f"\n{'-'*60}")
        print(f"【区段利用率 TOP-10】")
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
        
        unsat_ods = []
        for idx, row in od_list.iterrows():
            shortfall = row['demand_t_per_day'] - sat[idx].x
            if shortfall > 0.5:
                unsat_ods.append((row['from_code'], row['to_code'], row['demand_t_per_day'], sat[idx].x, shortfall))
        unsat_ods.sort(key=lambda t: t[4], reverse=True)
        
        if unsat_ods:
            print(f"\n【未满足需求 TOP-10（受能力限制）】")
            for rank, (o, d, demand, s, short) in enumerate(unsat_ods[:10], 1):
                print(f"  {rank:>2}. {o}->{d}: 需求 {demand:.1f}, 满足 {s:.1f}, 缺口 {short:.1f} 吨/日")
    else:
        print(f"\n求解失败。状态码: {model.status}")
    
    print(f"\n结论: 即使引入捎带模式，部分大运量OD仍可能受限于线路通过能力。")
    print(f"这需要在问题3中通过合理的基地选址和中转来进一步提升运能。")


if __name__ == '__main__':
    main()
