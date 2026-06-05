"""
问题 1：货流最短路与全有全无分配
============================================================================
任务：
  1. 假设全部使用货运动车组模式运输
  2. 计算每支 OD 在铁路网络中的最短路径
  3. 将 OD 需求全部沿最短路径分配（全有全无法）
  4. 判断各区段货流量是否超过线路通过能力（8列/日 = 680吨/日）

分析要点：
  - 路网有 34 个节点（15 主站 + 19 中间路由节点）
  - 主站间最短路径经过的中间节点也需要考虑在区间流量中
  - 单向分析：对每条有向边分别统计流量
  - 识别瓶颈区段并给出扩容建议
============================================================================
"""
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import utils
import pandas as pd
import numpy as np
from collections import defaultdict
import networkx as nx


def analyze_network_structure(G, main_stations):
    """分析路网基本结构"""
    print("-" * 60)
    print("【路网结构分析】")
    print(f"  总节点数: {G.number_of_nodes()} (主站: {len(main_stations)}, 中间节点: {G.number_of_nodes() - len(main_stations)})")
    print(f"  总边数: {G.number_of_edges()}")
    
    print(f"\n  各主站连接度（相邻主站数，含经中间节点连接）:")
    Gc = utils.build_contracted_network(G)
    for node in sorted(main_stations):
        degree = Gc.degree(node)
        neighbors = sorted(Gc.neighbors(node))
        print(f"    {node}: 连接 {degree} 个主站 -- {', '.join(neighbors)}")


def main():
    print("=" * 60)
    print("  问题 1：货流最短路与全有全无分配")
    print("=" * 60)
    
    # ── 1. 加载数据 ─────────────────────────────────
    data = utils.load_data()
    od_df = data['od']
    stations_df = data['stations']
    code_to_name = dict(zip(stations_df['code'], stations_df['name']))
    main_stations = sorted(stations_df['code'].tolist())
    
    G = utils.build_railway_network()
    analyze_network_structure(G, main_stations)
    
    paths, dists = utils.get_shortest_paths(G, main_stations)
    
    # ── 2. 全有全无分配 ──────────────────────────────
    print("\n" + "-" * 60)
    print("【全有全无分配 -- OD需求沿最短路径分配】")
    
    edge_flow = defaultdict(float)
    edge_flow_undirected = defaultdict(float)
    od_path_details = []
    
    total_demand_all = 0.0
    total_ton_km = 0.0
    
    for _, row in od_df.iterrows():
        src = row['from_code']
        dst = row['to_code']
        demand = row['demand_t_per_day']
        total_demand_all += demand
        
        path = paths[src][dst]
        dist = dists[src][dst]
        
        if demand > 0:
            total_ton_km += demand * dist
            
        od_path_details.append({
            'from': src, 'to': dst,
            'demand': demand,
            'distance': dist,
            'path': ' -> '.join(path),
            'n_intermediate': len(path) - 2
        })
        
        for k in range(len(path) - 1):
            u, v = path[k], path[k+1]
            edge_flow[(u, v)] += demand
            edge_key = tuple(sorted([u, v]))
            edge_flow_undirected[edge_key] += demand
    
    print(f"\n  总需求处理量: {total_demand_all:.1f} 吨/日")
    print(f"  总周转量: {total_ton_km:,.0f} 吨·公里/日")
    print(f"  平均运距: {total_ton_km/total_demand_all:.0f} km" if total_demand_all > 0 else "")
    
    # ── 3. 瓶颈区段识别 ──────────────────────────────
    print("\n" + "-" * 60)
    print("【区段能力校核】")
    print(f"  货运动车组限值: {utils.EMU_MAX_TRAINS_PER_EDGE} 列/日 * {utils.EMU_CAPACITY_T} 吨/列 = {utils.EMU_EDGE_CAP_T} 吨/日")
    
    sorted_edges = sorted(edge_flow.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n  {'排名':<6} {'区段':<20} {'方向':<6} {'流量(吨/日)':>12} {'饱和度':>10} {'状态'}")
    print(f"  {'-'*6} {'-'*20} {'-'*6} {'-'*12} {'-'*10} {'-'*10}")
    
    exceed_count = 0
    high_load_count = 0
    critical_edges = []
    
    for rank, ((u, v), flow) in enumerate(sorted_edges[:30], 1):
        sat = flow / utils.EMU_EDGE_CAP_T * 100
        status = "[OK] 正常"
        if sat > 100:
            status = "[!] 超限!"
            exceed_count += 1
            critical_edges.append((u, v, flow, sat))
        elif sat > 80:
            status = "[*] 关注"
            high_load_count += 1
        
        u_name = code_to_name.get(u, u)
        v_name = code_to_name.get(v, v)
        print(f"  {rank:<6} {u_name + '->' + v_name:<20} ->{'':>4} {flow:>12.1f} {sat:>9.1f}% {status}")
    
    print(f"\n  -- 汇总 --")
    print(f"  超限区段数: {exceed_count} (饱和度>100%)")
    print(f"  高负荷区段数: {high_load_count} (饱和度80%-100%)")
    print(f"  正常区段数: {len(edge_flow) - exceed_count - high_load_count}")
    
    if critical_edges:
        print(f"\n  [!] 超限区段详情（需要增加运力或分流）:")
        for u, v, flow, sat in critical_edges:
            u_name = code_to_name.get(u, u)
            v_name = code_to_name.get(v, v)
            needed_trains = np.ceil(flow / utils.EMU_CAPACITY_T)
            extra_trains = needed_trains - utils.EMU_MAX_TRAINS_PER_EDGE
            print(f"    {u_name} -> {v_name}: 需要 {needed_trains:.0f} 列/日 (超限 +{extra_trains:.0f} 列)")
    
    # ── 4. 全网关键断面排名 ──────────────────────────
    print(f"\n" + "-" * 60)
    print("【全网 TOP-10 高负荷断面（无向合计）】")
    sorted_undirected = sorted(edge_flow_undirected.items(), key=lambda x: x[1], reverse=True)
    for rank, (edge, flow) in enumerate(sorted_undirected[:10], 1):
        u, v = edge
        u_name = code_to_name.get(u, u)
        v_name = code_to_name.get(v, v)
        sat = flow / (utils.EMU_EDGE_CAP_T * 2) * 100
        print(f"  {rank:>2}. {u_name} <-> {v_name}: {flow:.1f} 吨/日 (双向饱和度 {sat:.1f}%)")
    
    # ── 5. OD 距离分布统计 ──────────────────────────
    print(f"\n" + "-" * 60)
    print("【OD 距离分布统计】")
    dist_bins = [0, 300, 500, 800, 1000, 1500, 2000, 99999]
    dist_labels = ['0-300', '300-500', '500-800', '800-1000', '1000-1500', '1500-2000', '2000+']
    dist_counts = [0] * len(dist_labels)
    dist_demand = [0] * len(dist_labels)
    
    for detail in od_path_details:
        d = detail['distance']
        for i, (lo, hi) in enumerate(zip(dist_bins[:-1], dist_bins[1:])):
            if lo <= d < hi:
                dist_counts[i] += 1
                dist_demand[i] += detail['demand']
                break
    
    print(f"  {'距离段':<12} {'OD对数':>8} {'需求占比':>10} {'累计需求(吨)':>14}")
    for i, label in enumerate(dist_labels):
        pct = dist_demand[i] / total_demand_all * 100 if total_demand_all > 0 else 0
        print(f"  {label:<12} {dist_counts[i]:>8} {pct:>9.1f}% {dist_demand[i]:>14.1f}")
    
    print(f"\n  结论: 全有全无分配下，部分核心区段（如沪宁、京广等）可能超限。")
    print(f"  这说明了引入捎带模式分流和优化分配的必要性（-> 问题2）。")


if __name__ == '__main__':
    main()
