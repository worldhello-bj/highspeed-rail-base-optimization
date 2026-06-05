"""
高铁快运基地选址 — 公共工具模块
提供：网络构建、数据加载、最短路径计算、可视化辅助函数
"""
import networkx as nx
import pandas as pd
import numpy as np
import os

DATA_DIR = r"d:\高铁快运"

# ============================================================
# 常量定义
# ============================================================
EMU_CAPACITY_T = 85.0          # 货运动车组装载能力 (吨/列)
EMU_MAX_TRAINS_PER_EDGE = 8    # 每区段每日最多货运动车组列数
EMU_EDGE_CAP_T = EMU_CAPACITY_T * EMU_MAX_TRAINS_PER_EDGE  # 680 吨/日
EMU_FIXED_COST = 50000         # 固定成本 (元/列)
EMU_VAR_COST = 116.6           # 运行可变成本 (元/km)
EMU_LOAD_COST = 144            # 装卸成本 (元/吨)
EMU_RATE = 4.5                 # 运价费率 (元/吨公里)
EMU_STOP_COST_FACTOR = 0.4     # 中途停靠占用基地处理能力 (列)

PIGGY_CAPACITY_T = 8.0         # 确认车捎带装载能力 (吨/列)
PIGGY_MAX_TRAINS_PER_STATION = 6  # 每站每日最多捎带列数
PIGGY_LOAD_COST = 120          # 捎带装卸成本 (元/吨)
PIGGY_RATE = 3.0               # 捎带运价费率 (元/吨公里)

PASSENGER_PIGGY_CAPACITY_T = 2.7  # 载客列车捎带能力 (吨/列)

TRANSFER_COST = 2.52           # 中转成本 (元/吨次)

YEARS_AMORTIZATION = 20        # 建设成本摊销年限
DAYS_PER_YEAR = 365

# ============================================================
# 中间节点列表（非主站，仅用于路由）
# ============================================================
INTERMEDIATE_NODES = {
    'FL', 'WZ', 'XS', 'ES', 'XY', 'JM', 'TM', 'MC', 'LA',
    'CZ', 'YZ', 'TZ', 'TC', 'HH', 'JJ', 'AQ', 
    'WH_wuhu', 'HZ_huzhou', 'JX'
}


def build_railway_network():
    """
    根据PDF拓扑图构建完整高铁网络（无向图）。
    包含15个主站 + 19个中间路由节点，共34个节点。
    边权重为区间距离(km)。
    
    Returns
    -------
    G : nx.Graph
    """
    G = nx.Graph()
    
    # 全网44条边，距离单位：km
    edges = [
        # === 沪汉蓉通道（东西大动脉） ===
        ('SH', 'JX', 84),
        ('JX', 'HZ', 75),
        ('HZ', 'HZ_huzhou', 71),
        ('HZ_huzhou', 'NJ', 185),
        ('NJ', 'CZ', 34),
        ('CZ', 'HF', 112),
        ('HF', 'LA', 68),
        ('LA', 'MC', 174),
        ('MC', 'WH', 107),
        ('WH', 'TM', 110),
        ('TM', 'JM', 126),
        ('JM', 'YC', 70),
        ('YC', 'XS', 234),
        ('XS', 'WZ', 246),
        ('WZ', 'CQ', 245),
        ('CQ', 'CD', 292),
        # === 京广通道 ===
        ('WH', 'CS', 362),
        ('CS', 'HH', 332),
        ('HH', 'GY', 374),
        ('ZZ', 'WH', 536),
        # === 京沪通道 ===
        ('ZZ', 'XZ', 362),
        ('XZ', 'BB', 156),
        ('BB', 'CZ', 115),
        ('BB', 'HF', 130),
        ('CZ', 'NJ', 34),
        # === 沪通 ===
        ('NJ', 'YZ', 101),
        ('YZ', 'TZ', 45),
        ('TZ', 'NT', 90),
        ('NT', 'TC', 130),
        ('TC', 'SH', 33),
        # === 武九-昌九 ===
        ('WH', 'JJ', 223),
        ('JJ', 'NC', 135),
        ('JJ', 'AQ', 176),
        # === 宁安-合安 ===
        ('AQ', 'HF', 163),
        ('AQ', 'WH_wuhu', 172),
        ('WH_wuhu', 'NJ', 85),
        # === 沪昆通道 ===
        ('NC', 'CS', 342),
        # === 郑渝（经襄阳）===
        ('XY', 'ZZ', 389),
        ('XY', 'WH', 281),
        ('XS', 'XY', 189),
        # === 渝黔 ===
        ('CQ', 'GY', 345),
        # === 成贵 ===
        ('CD', 'GY', 648),
        # === 宜万补充 ===
        ('ES', 'YC', 234),
        ('FL', 'ES', 229),
        ('CQ', 'FL', 88),
    ]
    
    for u, v, w in edges:
        G.add_edge(u, v, weight=w)
        
    return G


def get_main_station_set():
    """返回15个主站代码集合"""
    return {'SH', 'NT', 'HZ', 'NJ', 'HF', 'BB', 'XZ', 
            'WH', 'CS', 'NC', 'ZZ', 'YC', 'CQ', 'GY', 'CD'}


def build_contracted_network(G):
    """
    构建仅包含15个主站的缩略网络。
    任意两个相邻主站间的距离 = 它们之间路径上的总距离。
    
    Returns
    -------
    Gc : nx.Graph  缩略图（只有15个主站）
    """
    main_set = get_main_station_set()
    Gc = nx.Graph()
    for u in main_set:
        Gc.add_node(u)
    
    # 对每对相邻主站（在原图中直接相连且路径上无其他主站），
    # 计算它们之间的实际线路距离
    paths_all = dict(nx.all_pairs_dijkstra_path(G, weight='weight'))
    dists_all = dict(nx.all_pairs_dijkstra_path_length(G, weight='weight'))
    
    for u in main_set:
        for v in main_set:
            if u >= v:
                continue
            path = paths_all[u][v]
            # 检查路径上是否只有端点两个主站
            intermediates = [n for n in path[1:-1] if n in main_set]
            if len(intermediates) == 0:
                # 直接连接（仅经过中间节点）
                Gc.add_edge(u, v, weight=dists_all[u][v])
    
    return Gc


def load_data():
    """
    加载所有 CSV 数据。
    
    Returns
    -------
    dict with keys: 'od', 'stations', 'scale', 'train'
    """
    od_df = pd.read_csv(os.path.join(DATA_DIR, 'od_demand.csv'))
    stations_df = pd.read_csv(os.path.join(DATA_DIR, 'stations.csv'))
    scale_df = pd.read_csv(os.path.join(DATA_DIR, 'base_scale_params.csv'))
    train_df = pd.read_csv(os.path.join(DATA_DIR, 'train_params.csv'))
    
    return {
        'od': od_df,
        'stations': stations_df,
        'scale': scale_df,
        'train': train_df
    }


def get_shortest_paths(G, stations_list):
    """
    计算给定站点列表两两之间的最短路径及距离。
    
    Parameters
    ----------
    G : nx.Graph
    stations_list : list of str
    
    Returns
    -------
    paths : dict[dict[list]]
        paths[u][v] = [u, ..., v]  最短路径节点序列
    dists : dict[dict[float]]
        dists[u][v] = 最短距离(km)
    """
    paths = {}
    dists = {}
    for u in stations_list:
        paths[u] = {}
        dists[u] = {}
        for v in stations_list:
            if u == v:
                paths[u][v] = [u]
                dists[u][v] = 0
            else:
                try:
                    paths[u][v] = nx.shortest_path(G, source=u, target=v, weight='weight')
                    dists[u][v] = nx.shortest_path_length(G, source=u, target=v, weight='weight')
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    paths[u][v] = []
                    dists[u][v] = float('inf')
    return paths, dists


def get_route_distance(G, route):
    """计算一条路线（节点序列）的总距离"""
    total = 0
    for i in range(len(route) - 1):
        total += G[route[i]][route[i+1]]['weight']
    return total


def get_edge_between_main_stations(G, u, v):
    """
    获取两个主站之间的线路距离（经过中间节点）。
    如果 u, v 在 G 中直接相邻或通过中间节点相连，返回实际距离。
    """
    try:
        return nx.shortest_path_length(G, source=u, target=v, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return float('inf')


def compute_od_demand_matrix(od_df):
    """
    构建 OD 需求矩阵（15×15）。
    
    Returns
    -------
    demand : np.ndarray  shape (15, 15)
        demand[i][j] = 从主站i到主站j的日需求(吨)
    idx_to_code : dict
    code_to_idx : dict
    """
    stations_df = pd.read_csv(os.path.join(DATA_DIR, 'stations.csv'))
    codes = stations_df['code'].tolist()
    code_to_idx = {c: i for i, c in enumerate(codes)}
    n = len(codes)
    demand = np.zeros((n, n))
    
    for _, row in od_df.iterrows():
        i = code_to_idx[row['from_code']]
        j = code_to_idx[row['to_code']]
        demand[i][j] += row['demand_t_per_day']
    
    return demand, {i: c for i, c in enumerate(codes)}, code_to_idx


if __name__ == '__main__':
    # 快速测试
    G = build_railway_network()
    print(f"全网节点数: {G.number_of_nodes()}")
    print(f"全网边数: {G.number_of_edges()}")
    
    Gc = build_contracted_network(G)
    print(f"缩略图节点数: {Gc.number_of_nodes()}")
    print(f"缩略图边数: {Gc.number_of_edges()}")
    
    main_stations = sorted(get_main_station_set())
    paths, dists = get_shortest_paths(G, main_stations)
    print(f"\n最短路径示例 (SH -> CD):")
    print(f"  路径: {' → '.join(paths['SH']['CD'])}")
    print(f"  距离: {dists['SH']['CD']} km")

