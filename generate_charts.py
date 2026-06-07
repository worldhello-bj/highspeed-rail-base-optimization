import os
import math
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import networkx as nx
import utils

# 动态注册 Windows 中文字体，防止中文乱码与警告
font_registered = False
for f_name in ['msyh.ttc', 'simsun.ttc', 'simhei.ttf']:
    f_path = os.path.join(r'C:\Windows\Fonts', f_name)
    if os.path.exists(f_path):
        try:
            fm.fontManager.addfont(f_path)
            font_name = fm.FontProperties(fname=f_path).get_name()
            plt.rcParams['font.sans-serif'] = [font_name]
            font_registered = True
            print(f"成功注册字体：{font_name}")
            break
        except Exception as e:
            print(f"注册字体 {f_name} 失败: {e}")

if not font_registered:
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'Arial']

plt.rcParams['axes.unicode_minus'] = False

def main():
    print("重新生成图表...")
    
    # 建立目录
    output_dir = os.path.join(utils.IMAGES_DIR)
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 加载网络与需求
    G = utils.build_railway_network()
    data = utils.load_data()
    od_df = data['od']
    stations_df = data['stations']
    
    name_map = dict(zip(stations_df['code'], stations_df['name']))
    main_stations = stations_df['code'].tolist()
    
    # === 图表 1：问题一关键区段断面货流量 ===
    paths, dists = utils.get_shortest_paths(G, main_stations)
    edge_flow = {}
    
    for idx, row in od_df.iterrows():
        src = row['from_code']
        dst = row['to_code']
        demand = row['demand_t_per_day']
        if demand <= 0:
            continue
        path = paths[src][dst]
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge_flow[(u, v)] = edge_flow.get((u, v), 0) + demand
            
    # 挑选流量最高的前 10 个区段
    sorted_edges = sorted(edge_flow.items(), key=lambda x: x[1], reverse=True)[:10]
    
    labels = []
    flows = []
    for (u, v), flow in sorted_edges:
        u_name = name_map.get(u, u)
        v_name = name_map.get(v, v)
        labels.append(f"{u_name}→{v_name}")
        flows.append(flow)
        
    plt.figure(figsize=(10, 5), dpi=300)
    bars = plt.bar(labels, flows, color='#1f77b4', width=0.55, edgecolor='black', alpha=0.85)
    plt.axhline(y=680, color='red', linestyle='--', linewidth=1.5, label='日最大通过能力上限 (680吨/日)')
    
    # 数值标注
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, height + 10, f"{height:.1f}t", ha='center', va='bottom', fontsize=8.5, fontweight='bold')
        
    plt.title('问题一：路网前 10 位关键断面货流量及能力校核', fontsize=12, fontweight='bold', pad=15)
    plt.xlabel('区段名称', fontsize=10, fontweight='bold', labelpad=10)
    plt.ylabel('断面货流量 (吨/日)', fontsize=10, fontweight='bold', labelpad=10)
    plt.grid(axis='y', linestyle=':', alpha=0.6)
    plt.ylim(0, 800)
    plt.legend(loc='upper right', frameon=True)
    plt.tight_layout()
    chart1_path = os.path.join(output_dir, 'section_flows.png')
    plt.savefig(chart1_path, bbox_inches='tight')
    plt.close()
    print(f"图表 1 已生成：{chart1_path}")
    
    # === 图表 2：问题二货流模式分担比例饼图 ===
    plt.figure(figsize=(6, 6), dpi=300)
    mode_labels = ['货运动车组模式', '载客动车组捎带模式']
    shares = [1548.4, 360.0]
    colors = ['#2c3e50', '#18bc9c']
    explode = (0.05, 0)
    
    plt.pie(shares, explode=explode, labels=mode_labels, autopct='%1.1f%%',
            startangle=140, colors=colors, shadow=False, 
            textprops={'fontsize': 11, 'fontweight': 'bold'})
    plt.title('问题二：不同快运运营模式货流量分担比例', fontsize=12, fontweight='bold', pad=15)
    plt.tight_layout()
    chart2_path = os.path.join(output_dir, 'mode_split.png')
    plt.savefig(chart2_path, bbox_inches='tight')
    plt.close()
    print(f"图表 2 已生成：{chart2_path}")
    
    # === 图表 3：问题三选址站点基地级别与日处理货流 ===
    try:
        x_df = pd.read_csv(os.path.join(utils.OUTPUT_DIR, "problem3_x_flow.csv"))
        node_emu_flow = {}
        for idx, row in x_df.iterrows():
            u, v, flow = row['u'], row['v'], row['flow']
            node_emu_flow[u] = node_emu_flow.get(u, 0) + flow
            node_emu_flow[v] = node_emu_flow.get(v, 0) + flow
            
        selected_bases = ['CD', 'CQ', 'GY', 'WH', 'CS', 'NC', 'NJ', 'HZ', 'SH']
        base_flows = [node_emu_flow.get(b, 0) for b in selected_bases]
        base_names = [name_map.get(b, b) for b in selected_bases]
        
        plt.figure(figsize=(10, 5), dpi=300)
        x_ticks = np.arange(len(selected_bases))
        
        bars = plt.bar(x_ticks, base_flows, color='#8e44ad', width=0.5, edgecolor='black', alpha=0.8, label='货运动车组实际处理量 (吨/日)')
        plt.axhline(y=85, color='orange', linestyle='--', linewidth=1.5, label='改建小规模能力上限 (85吨/日)')
        
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, height + 1.5, f"{height:.1f}t", ha='center', va='bottom', fontsize=8.5, fontweight='bold')
            
        plt.xticks(x_ticks, base_names, fontsize=9, fontweight='bold')
        plt.title('问题三：各选址基地实际货流量与设计能力校核', fontsize=12, fontweight='bold', pad=15)
        plt.xlabel('选址建设基地站点', fontsize=10, fontweight='bold', labelpad=10)
        plt.ylabel('实际日处理量 (吨/日)', fontsize=10, fontweight='bold', labelpad=10)
        plt.grid(axis='y', linestyle=':', alpha=0.6)
        plt.ylim(0, 105)
        plt.legend(loc='upper right', frameon=True)
        plt.tight_layout()
        chart3_path = os.path.join(output_dir, 'base_workloads.png')
        plt.savefig(chart3_path, bbox_inches='tight')
        plt.close()
        print(f"图表 3 已生成：{chart3_path}")
    except Exception as e:
        print(f"图表 3 生成失败: {e}")
    
    # === 图表 4：问题五 敏感性分析（龙卷风图）===
    try:
        path = os.path.join(utils.OUTPUT_DIR, "problem5_sensitivity.json")
        with open(path, 'r', encoding='utf-8') as f:
            sens_data = json.load(f)
        
        fig, axes = plt.subplots(1, 3, figsize=(16, 5), dpi=300)
        
        # 4a: 需求敏感性
        ax = axes[0]
        demand_changes = [d['change']*100 for d in sens_data['demand_scenarios']]
        demand_profits = [d['annual_profit_yi'] for d in sens_data['demand_scenarios']]
        colors_d = ['#e74c3c' if x < 0 else '#27ae60' for x in demand_changes]
        bars = ax.bar(range(len(demand_changes)), demand_profits, color=colors_d, edgecolor='black', alpha=0.8)
        ax.set_xticks(range(len(demand_changes)))
        ax.set_xticklabels([f'{x:+.0f}%' for x in demand_changes])
        ax.axhline(y=demand_profits[3], color='blue', linestyle='--', linewidth=1, label=f'基准: {demand_profits[3]:.2f}亿')
        for bar, val in zip(bars, demand_profits):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.1, f'{val:.2f}', ha='center', fontsize=7)
        ax.set_title('需求波动对年净利润的影响', fontsize=11, fontweight='bold')
        ax.set_ylabel('年净利润 (亿元)', fontsize=9)
        ax.legend(fontsize=7)
        ax.grid(axis='y', linestyle=':', alpha=0.5)
        
        # 4b: 费率敏感性
        ax = axes[1]
        rate_changes = [d['change']*100 for d in sens_data['rate_scenarios']]
        rate_profits = [d['annual_profit_yi'] for d in sens_data['rate_scenarios']]
        colors_r = ['#e74c3c' if x < 0 else '#27ae60' for x in rate_changes]
        bars = ax.bar(range(len(rate_changes)), rate_profits, color=colors_r, edgecolor='black', alpha=0.8)
        ax.set_xticks(range(len(rate_changes)))
        ax.set_xticklabels([f'{x:+.0f}%' for x in rate_changes])
        ax.axhline(y=rate_profits[3], color='blue', linestyle='--', linewidth=1, label=f'基准: {rate_profits[3]:.2f}亿')
        for bar, val in zip(bars, rate_profits):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.1, f'{val:.2f}', ha='center', fontsize=7)
        ax.set_title('运价费率波动对年净利润的影响', fontsize=11, fontweight='bold')
        ax.set_ylabel('年净利润 (亿元)', fontsize=9)
        ax.legend(fontsize=7)
        ax.grid(axis='y', linestyle=':', alpha=0.5)
        
        # 4c: 成本敏感性
        ax = axes[2]
        cost_changes = [d['change']*100 for d in sens_data['cost_scenarios']]
        cost_payback = [d['payback_years'] for d in sens_data['cost_scenarios']]
        colors_c = ['#e74c3c' if x > 0 else '#27ae60' for x in cost_changes]
        bars = ax.bar(range(len(cost_changes)), cost_payback, color=colors_c, edgecolor='black', alpha=0.8)
        ax.set_xticks(range(len(cost_changes)))
        ax.set_xticklabels([f'{x:+.0f}%' for x in cost_changes])
        ax.axhline(y=cost_payback[2], color='blue', linestyle='--', linewidth=1, label=f'基准: {cost_payback[2]:.2f}年')
        for bar, val in zip(bars, cost_payback):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02, f'{val:.2f}', ha='center', fontsize=7)
        ax.set_title('建设成本波动对回收期的影响', fontsize=11, fontweight='bold')
        ax.set_ylabel('投资回收期 (年)', fontsize=9)
        ax.legend(fontsize=7)
        ax.grid(axis='y', linestyle=':', alpha=0.5)
        
        plt.tight_layout()
        chart4_path = os.path.join(output_dir, 'sensitivity_analysis.png')
        plt.savefig(chart4_path, bbox_inches='tight')
        plt.close()
        print(f"图表 4 已生成：{chart4_path}")
    except Exception as e:
        print(f"图表 4 生成失败: {e}")
    
    # === 图表 5：问题六 多式联运成本对比 ===
    try:
        path = os.path.join(utils.OUTPUT_DIR, "problem6_results.json")
        with open(path, 'r', encoding='utf-8') as f:
            comp_data = json.load(f)
        
        cost_table = comp_data['cost_table']
        distances = [c['distance'] for c in cost_table]
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), dpi=300)
        
        # 5a: 三种运输模式成本曲线
        ax = axes[0]
        hsr_costs = [c['高铁快运（货_costs'] if '高铁快运（货_costs' in c else c.get('高铁快运（货_cost', 0)/10000 for c in cost_table]
        
        # 从cost_table提取成本
        hsr_cost_vals = []
        air_cost_vals = []
        truck_cost_vals = []
        for c in cost_table:
            for k, v in c.items():
                if '高铁' in k and 'cost' in k and 'unit' not in k:
                    hsr_cost_vals.append(v/10000)
                elif '航空' in k and 'cost' in k and 'unit' not in k:
                    air_cost_vals.append(v/10000)
                elif '公路' in k and 'cost' in k and 'unit' not in k:
                    truck_cost_vals.append(v/10000)
        
        ax.plot(distances, hsr_cost_vals, 'o-', color='#2c3e50', linewidth=2, markersize=6, label='高铁快运（货运动车组）')
        ax.plot(distances, air_cost_vals, 's-', color='#e74c3c', linewidth=2, markersize=6, label='航空货运')
        ax.plot(distances, truck_cost_vals, '^-', color='#27ae60', linewidth=2, markersize=6, label='公路卡车')
        ax.set_xlabel('运输距离 (km)', fontsize=10, fontweight='bold')
        ax.set_ylabel('总运输成本 (万元/200吨)', fontsize=10, fontweight='bold')
        ax.set_title('问题六：三种运输模式成本-距离曲线对比', fontsize=11, fontweight='bold')
        ax.legend(fontsize=8, loc='upper left')
        ax.grid(True, linestyle=':', alpha=0.6)
        
        # 标注盈亏平衡距离
        be_air = comp_data['breakeven_hsr_air_km']
        be_truck = comp_data['breakeven_hsr_truck_km']
        if be_truck > 0 and be_truck < 5000:
            ax.axvline(x=be_truck, color='green', linestyle='--', alpha=0.5, linewidth=1)
            ax.text(be_truck+20, ax.get_ylim()[1]*0.9, f'{be_truck:.0f}km', fontsize=7, color='green')
        if be_air > 0 and be_air < 5000:
            ax.axvline(x=be_air, color='red', linestyle='--', alpha=0.5, linewidth=1)
            ax.text(be_air+20, ax.get_ylim()[1]*0.7, f'{be_air:.0f}km', fontsize=7, color='red')
        
        # 5b: 雷达图
        ax = axes[1]
        radar_scores = comp_data['radar_scores']
        radar_dims = comp_data['radar_dimensions']
        
        angles = np.linspace(0, 2*np.pi, len(radar_dims), endpoint=False).tolist()
        angles += angles[:1]
        
        ax = plt.subplot(1, 2, 2, projection='polar')
        colors_radar = ['#2c3e50', '#e74c3c', '#27ae60']
        for idx, (mode_name, scores_list) in enumerate(radar_scores.items()):
            values = scores_list + scores_list[:1]
            ax.fill(angles, values, alpha=0.1, color=colors_radar[idx])
            ax.plot(angles, values, 'o-', linewidth=2, color=colors_radar[idx], label=mode_name[:10], markersize=5)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(radar_dims, fontsize=9)
        ax.set_ylim(0, 10)
        ax.set_yticks([2, 4, 6, 8, 10])
        ax.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=7)
        ax.set_title('多式联运综合竞争力雷达图', fontsize=11, fontweight='bold', pad=20)
        ax.legend(fontsize=7, loc='upper right', bbox_to_anchor=(1.3, 1.1))
        
        plt.tight_layout()
        chart5_path = os.path.join(output_dir, 'modal_competition.png')
        plt.savefig(chart5_path, bbox_inches='tight')
        plt.close()
        print(f"图表 5 已生成：{chart5_path}")
    except Exception as e:
        print(f"图表 5 生成失败: {e}")
        import traceback
        traceback.print_exc()
        
    print("图表重新生成完毕！")

if __name__ == '__main__':
    main()
