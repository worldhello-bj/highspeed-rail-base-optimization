"""
问题 4：列车开行方案设计
============================================================================
基于问题 3 的基地选址和货流分配结果，设计具体的列车服务网络。

方法：
  1. 对 EMU 边流进行路径拆解（贪心 + 流分解）
  2. 根据流量确定开行频率（列/日）
  3. 捎带模式直接按 OD 对开行
  4. 验证区间和车站能力
============================================================================
"""
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import networkx as nx
import numpy as np
import math
import utils
from collections import defaultdict


def decompose_emu_flows(G, x_df, main_stations):
    """将 EMU 边流量拆解为具体的列车路径。"""
    F = nx.DiGraph()
    for _, row in x_df.iterrows():
        if row['flow'] > 0.01:
            F.add_edge(row['u'], row['v'], flow=row['flow'])
    
    main_set = set(main_stations)
    routes = []
    
    max_iterations = 1000
    iteration = 0
    
    while F.number_of_edges() > 0 and iteration < max_iterations:
        iteration += 1
        
        start_node = None
        for n in list(F.nodes()):
            out_sum = sum(F[n][v]['flow'] for v in F.successors(n))
            in_sum = sum(F[u][n]['flow'] for u in F.predecessors(n))
            if out_sum > in_sum + 0.05:
                start_node = n
                break
        
        if start_node is None:
            max_f = 0
            for u, v in F.edges():
                if F[u][v]['flow'] > max_f:
                    max_f = F[u][v]['flow']
                    start_node = u
            if start_node is None:
                break
        
        path = [start_node]
        visited = {start_node}
        curr = start_node
        min_flow = float('inf')
        
        while True:
            successors = list(F.successors(curr))
            valid = [(v, F[curr][v]['flow']) for v in successors if v not in visited]
            
            if not valid:
                break
            
            next_node, f = max(valid, key=lambda x: x[1])
            min_flow = min(min_flow, f)
            path.append(next_node)
            visited.add(next_node)
            curr = next_node
            
            out_sum = sum(F[curr][v]['flow'] for v in F.successors(curr))
            in_sum = sum(F[u][curr]['flow'] for u in F.predecessors(curr))
            if in_sum > out_sum + 0.05 and curr in main_set:
                break
            
            if len(path) > 20:
                break
        
        if len(path) < 2:
            for u in list(F.nodes()):
                if F.degree(u) == 0:
                    F.remove_node(u)
            continue
        
        if min_flow <= 0.01:
            min_flow = 0.01
        
        trains = max(1, int(np.ceil(min_flow / utils.EMU_CAPACITY_T)))
        main_stops = [n for n in path if n in main_set]
        dist = utils.get_route_distance(G, path)
        
        routes.append({
            'path': path, 'main_stops': main_stops,
            'flow': min_flow, 'trains': trains, 'distance': dist
        })
        
        for k in range(len(path) - 1):
            u, v = path[k], path[k+1]
            if F.has_edge(u, v):
                F[u][v]['flow'] -= min_flow
                if F[u][v]['flow'] < 0.01:
                    F.remove_edge(u, v)
        
        to_remove = [n for n in list(F.nodes()) if F.degree(n) == 0]
        for n in to_remove:
            F.remove_node(n)
    
    return routes


def main():
    print("=" * 60)
    print("  问题 4：列车开行方案设计")
    print("=" * 60)
    
    try:
        x_df = pd.read_csv(os.path.join(utils.OUTPUT_DIR, "problem3_x_flow.csv"))
        y_df = pd.read_csv(os.path.join(utils.OUTPUT_DIR, "problem3_y_flow.csv"))
    except FileNotFoundError:
        print("请先运行 problem3.py 生成货流数据。")
        return
    
    data = utils.load_data()
    stations_df = data['stations']
    code_to_name = dict(zip(stations_df['code'], stations_df['name']))
    main_stations = stations_df['code'].tolist()
    
    G = utils.build_railway_network()
    _, dists = utils.get_shortest_paths(G, main_stations)
    
    print(f"\n  加载 EMU 边流: {len(x_df)} 条有向边")
    print(f"  加载捎带 OD 流: {len(y_df)} 条 OD 对")
    
    # ── EMU 列车路径拆解 ────────────────────────────
    print(f"\n{'-'*60}")
    print(f"【货运动车组开行方案】")
    
    emu_routes = decompose_emu_flows(G, x_df, main_stations)
    print(f"\n  共拆解出 {len(emu_routes)} 条 EMU 运行线")
    
    emu_routes.sort(key=lambda r: r['trains'], reverse=True)
    
    total_emu_trains = 0
    total_emu_flow = 0
    
    print(f"\n  {'#':<4} {'路径':<45} {'列车/日':>8} {'吨/日':>10} {'距离km':>8}")
    print(f"  {'-'*4} {'-'*45} {'-'*8} {'-'*10} {'-'*8}")
    
    for rank, route in enumerate(emu_routes[:30], 1):
        path_str = ' -> '.join([code_to_name.get(n, n) for n in route['main_stops']])
        if len(path_str) > 42:
            path_str = path_str[:39] + '...'
        print(f"  {rank:<4} {path_str:<45} {route['trains']:>8} {route['flow']:>10.1f} {route['distance']:>8.0f}")
        total_emu_trains += route['trains']
        total_emu_flow += route['flow']
    
    if len(emu_routes) > 30:
        for route in emu_routes[30:]:
            total_emu_trains += route['trains']
            total_emu_flow += route['flow']
        print(f"  ... (共 {len(emu_routes)} 条，其余省略)")
    
    print(f"\n  EMU 合计: {total_emu_trains} 列/日, {total_emu_flow:.1f} 吨/日")
    
    # ── 捎带列车开行方案 ────────────────────────────
    print(f"\n{'-'*60}")
    print(f"【捎带列车开行方案 (确认车 8 吨/列)】")
    
    y_df_sorted = y_df.sort_values('flow', ascending=False)
    
    print(f"\n  {'#':<4} {'出发':<8} {'到达':<8} {'吨/日':>10} {'列/日':>8} {'距离km':>8}")
    print(f"  {'-'*4} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*8}")
    
    total_pig_trains = 0
    total_pig_flow = 0
    
    for rank, (_, row) in enumerate(y_df_sorted.iterrows(), 1):
        i, j, flow = row['i'], row['j'], row['flow']
        trains = math.ceil(flow / utils.PIGGY_CAPACITY_T)
        dist = dists[i][j]
        i_name = code_to_name.get(i, i)
        j_name = code_to_name.get(j, j)
        
        if rank <= 20:
            print(f"  {rank:<4} {i_name:<8} {j_name:<8} {flow:>10.1f} {trains:>8} {dist:>8.0f}")
        
        total_pig_trains += trains
        total_pig_flow += flow
    
    print(f"\n  捎带合计: {total_pig_trains} 列/日, {total_pig_flow:.1f} 吨/日")
    
    # ── 区间能力校核 ────────────────────────────────
    print(f"\n{'-'*60}")
    print(f"【区间能力校核】")
    
    edge_trains = defaultdict(int)
    for route in emu_routes:
        path = route['path']
        tr = route['trains']
        for k in range(len(path) - 1):
            edge_trains[(path[k], path[k+1])] += tr
    
    max_edge_trains = max(edge_trains.values()) if edge_trains else 0
    exceed_edges = [(u, v, t) for (u, v), t in edge_trains.items() if t > utils.EMU_MAX_TRAINS_PER_EDGE]
    
    if exceed_edges:
        print(f"  [!] 有 {len(exceed_edges)} 个区间超过 8 列/日限制:")
        for u, v, t in sorted(exceed_edges, key=lambda x: x[2], reverse=True)[:10]:
            u_name = code_to_name.get(u, u)
            v_name = code_to_name.get(v, v)
            print(f"    {u_name} -> {v_name}: {t} 列/日 (超限 +{t - 8})")
    else:
        print(f"  [OK] 所有区间 EMU 列车数 <= 8 列/日，最大: {max_edge_trains} 列/日")
    
    # ── 车站能力校核 ────────────────────────────────
    print(f"\n【车站能力校核】")
    station_trains = defaultdict(float)
    for route in emu_routes:
        path = route['path']
        tr = route['trains']
        for node in path:
            if node in main_stations:
                if node == path[0] or node == path[-1]:
                    station_trains[node] += tr * 1.0
                else:
                    station_trains[node] += tr * 0.4
    
    for node in sorted(main_stations):
        t = station_trains.get(node, 0)
        if t > 0:
            node_name = code_to_name.get(node, node)
            print(f"  {node_name}({node}): 等效占用 {t:.1f} 列/日")
    
    # ── 总结 ────────────────────────────────────────
    print(f"\n{'-'*60}")
    print(f"【问题 4 总结】")
    print(f"  1. 共设计 {len(emu_routes)} 条 EMU 运行线，{total_emu_trains} 列/日")
    print(f"  2. 共设计 {len(y_df)} 条捎带线，{total_pig_trains} 列/日")
    print(f"  3. 列车总开行: {total_emu_trains + total_pig_trains} 列/日")
    print(f"  4. 最大区间负荷: {max_edge_trains} 列/日")


if __name__ == '__main__':
    main()
