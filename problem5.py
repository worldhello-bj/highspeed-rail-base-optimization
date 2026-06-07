"""
问题 5：大周期商业盈亏平衡与财务健康度可行性评估
================================================================================
基于问题 3 的选址规模结果，进行 20 年全生命周期财务核算。

分析内容：
  1. 投资概况（建设成本、固定人工）
  2. 日常运营收支（收入、各项成本）
  3. 盈亏平衡分析（回收期、盈亏平衡货量、盈亏平衡运价）
  4. NPV 净现值（折现率 5%）
  5. IRR 内部收益率
  6. 敏感性分析（需求波动、运价波动、建设成本波动）
================================================================================
"""
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import utils
import json


def main():
    print("=" * 60)
    print("  问题 5：盈亏平衡与财务可行性评估")
    print("=" * 60)
    
    data = utils.load_data()
    stations_df = data['stations']
    scale_df = data['scale']
    code_to_name = dict(zip(stations_df['code'], stations_df['name']))
    
    G = utils.build_railway_network()
    main_stations = stations_df['code'].tolist()
    _, dists = utils.get_shortest_paths(G, main_stations)
    
    x_df = pd.read_csv(os.path.join(utils.OUTPUT_DIR, "problem3_x_flow.csv"))
    y_df = pd.read_csv(os.path.join(utils.OUTPUT_DIR, "problem3_y_flow.csv"))
    
    EMU_CAP = utils.EMU_CAPACITY_T
    EMU_FIXED = utils.EMU_FIXED_COST
    EMU_VAR = utils.EMU_VAR_COST
    EMU_LOAD = utils.EMU_LOAD_COST
    EMU_RATE = utils.EMU_RATE
    PIG_CAP = utils.PIGGY_CAPACITY_T
    PIG_LOAD = utils.PIGGY_LOAD_COST
    PIG_RATE = utils.PIGGY_RATE
    TRANS_COST = utils.TRANSFER_COST
    MGMT_COST = 20000
    LABOR_COST = 2000
    
    # 从 problem3_x_flow 动态推断建成基地
    emu_active = set()
    for _, row in x_df.iterrows():
        emu_active.add(row['u'])
        emu_active.add(row['v'])
    
    candidates_all = set(stations_df[stations_df['is_candidate'] == 1]['code'].tolist())
    BUILT_BASES = sorted(candidates_all & emu_active)
    if not BUILT_BASES:
        BUILT_BASES = ['WH', 'CS', 'NC', 'ZZ', 'CQ', 'GY', 'CD']
    
    SCALE_ID = 0
    
    n_bases = len(BUILT_BASES)
    build_cost_per_base = scale_df.loc[scale_df['scale_id'] == SCALE_ID, 'construction_cost_yi'].values[0]
    labor_per_base = scale_df.loc[scale_df['scale_id'] == SCALE_ID, 'fixed_labor_cost_wan'].values[0]
    
    total_investment = n_bases * build_cost_per_base * 1e8
    annual_fixed_labor = n_bases * labor_per_base * 1e4
    
    YEARS = utils.YEARS_AMORTIZATION
    DAYS = utils.DAYS_PER_YEAR
    DISCOUNT_RATE = 0.05
    
    print(f"\n{'-'*60}")
    print(f"【投资概况】")
    print(f"  建设基地数:     {n_bases} 个（全部改建小规模）")
    print(f"  基地列表:       {', '.join([code_to_name.get(b, b) for b in BUILT_BASES])}")
    print(f"  单基地投资:     {build_cost_per_base:.3f} 亿元")
    print(f"  总投资额:       {build_cost_per_base * n_bases:.3f} 亿元 = {total_investment/1e8:.2f} 亿元")
    print(f"  年均固定人工:   {annual_fixed_labor/1e4:.1f} 万元/年")
    
    # ── 日均运营收支 ────────────────────────────────
    print(f"\n{'-'*60}")
    print(f"【日均运营收支核算】")
    
    daily_depreciation = total_investment / (YEARS * DAYS)
    daily_fixed_labor = annual_fixed_labor / DAYS
    daily_fixed_total = daily_depreciation + daily_fixed_labor
    
    total_revenue = 0.0
    emu_revenue = 0.0
    pig_revenue = 0.0
    
    for _, row in y_df.iterrows():
        i, j, flow = row['i'], row['j'], row['flow']
        if i in main_stations and j in main_stations:
            dist = dists[i][j]
            pig_revenue += PIG_RATE * dist * flow
    
    for _, row in x_df.iterrows():
        u, v, flow = row['u'], row['v'], row['flow']
        if G.has_edge(u, v):
            dist = G[u][v]['weight']
            emu_revenue += EMU_RATE * dist * flow
    
    total_revenue = emu_revenue + pig_revenue
    
    emu_run_cost = 0.0
    for _, row in x_df.iterrows():
        u, v, flow = row['u'], row['v'], row['flow']
        if G.has_edge(u, v):
            dist = G[u][v]['weight']
            unit_cost = (EMU_FIXED + EMU_VAR * dist) / EMU_CAP
            emu_run_cost += unit_cost * flow
    
    emu_total_flow = x_df['flow'].sum() if len(x_df) > 0 else 0
    avg_edges = max(3.0, emu_total_flow / max(1, sum(y_df['flow']) * 0.12))
    emu_total_handled = emu_total_flow / avg_edges
    emu_load_cost = EMU_LOAD * emu_total_handled * 2
    
    pig_total_tons = y_df['flow'].sum() if len(y_df) > 0 else 0
    pig_cost = PIG_LOAD * pig_total_tons * 2
    
    base_var_cost = (MGMT_COST + LABOR_COST) * emu_total_handled * 2 / EMU_CAP
    
    transfer_tons = emu_total_handled * 0.30
    transfer_cost = TRANS_COST * transfer_tons
    
    daily_total_cost = (daily_fixed_total + base_var_cost + emu_run_cost + 
                        emu_load_cost + pig_cost + transfer_cost)
    daily_net_profit = total_revenue - daily_total_cost
    
    print(f"  运输收入:       {total_revenue:>15,.2f} 元/日")
    print(f"    EMU 收入:     {emu_revenue:>15,.2f}")
    print(f"    捎带收入:     {pig_revenue:>15,.2f}")
    print(f"  运营成本:       {daily_total_cost:>15,.2f} 元/日")
    print(f"    建设折旧:     {daily_depreciation:>15,.2f}")
    print(f"    固定人工:     {daily_fixed_labor:>15,.2f}")
    print(f"    基地操作费:   {base_var_cost:>15,.2f}")
    print(f"    EMU 运行费:   {emu_run_cost:>15,.2f}")
    print(f"    EMU 装卸费:   {emu_load_cost:>15,.2f}")
    print(f"    捎带装卸费:   {pig_cost:>15,.2f}")
    print(f"    中转费:       {transfer_cost:>15,.2f}")
    print(f"  日均净利润:     {daily_net_profit:>15,.2f} 元/日")
    
    # ── 盈亏平衡 ────────────────────────────────────
    annual_net_profit = daily_net_profit * DAYS
    payback_years = total_investment / annual_net_profit if annual_net_profit > 0 else float('inf')
    payback_months = payback_years * 12
    
    print(f"\n{'='*60}")
    print(f"【盈亏平衡分析】")
    print(f"  年净利润:       {annual_net_profit/1e8:>10.2f} 亿元/年")
    print(f"  总投资回收期:   {payback_years:>10.2f} 年 = {payback_months:.1f} 个月")
    print(f"  ROI:            {(annual_net_profit/total_investment*100):>10.1f}%/年")
    
    # ── NPV ─────────────────────────────────────────
    print(f"\n{'-'*60}")
    print(f"【20年净现值(NPV)分析 (折现率 {DISCOUNT_RATE*100:.0f}%)】")
    
    npv = -total_investment
    cumulative_cf = -total_investment
    cash_flows = []
    
    for yr in range(1, YEARS + 1):
        cf = annual_net_profit
        discounted_cf = cf / ((1 + DISCOUNT_RATE) ** yr)
        npv += discounted_cf
        cumulative_cf += cf
        cash_flows.append({'year': yr, 'cash_flow': cf, 'discounted': discounted_cf, 'cumulative': cumulative_cf})
    
    print(f"  初始投资:       {-total_investment/1e8:>10.2f} 亿元")
    print(f"  20年NPV:        {npv/1e8:>10.2f} 亿元")
    print(f"  20年累计现金流: {cumulative_cf/1e8:>10.2f} 亿元")
    
    print(f"\n  {'年份':<8} {'现金流(亿元)':>14} {'折现(亿元)':>14} {'累计(亿元)':>14}")
    print(f"  {'-'*8} {'-'*14} {'-'*14} {'-'*14}")
    print(f"  {'0':<8} {'':>14} {'':>14} {-total_investment/1e8:>14.2f}")
    for cf in cash_flows:
        if cf['year'] <= 5 or cf['year'] % 5 == 0:
            print(f"  {cf['year']:<8} {cf['cash_flow']/1e8:>14.2f} {cf['discounted']/1e8:>14.2f} {cf['cumulative']/1e8:>14.2f}")
    
    def npv_at_rate(r):
        return -total_investment + sum(annual_net_profit / ((1 + r) ** yr) for yr in range(1, YEARS + 1))
    
    lo, hi = 0.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if npv_at_rate(mid) > 0:
            lo = mid
        else:
            hi = mid
    irr = (lo + hi) / 2
    print(f"\n  IRR: {irr*100:.1f}%")
    
    # ── 盈亏平衡点 ──────────────────────────────────
    print(f"\n{'-'*60}")
    print(f"【盈亏平衡点分析】")
    
    total_tons = emu_total_handled + pig_total_tons
    daily_var_cost = base_var_cost + emu_run_cost + emu_load_cost + pig_cost + transfer_cost
    avg_revenue_per_ton = total_revenue / total_tons if total_tons > 0 else 0
    avg_var_per_ton = daily_var_cost / total_tons if total_tons > 0 else 0
    contribution_margin = avg_revenue_per_ton - avg_var_per_ton
    
    bep_tons = daily_fixed_total / contribution_margin if contribution_margin > 0 else float('inf')
    bep_ratio = bep_tons / total_tons * 100 if total_tons > 0 else 0
    
    emu_tkm = emu_revenue / EMU_RATE if emu_revenue > 0 else 0
    pig_tkm = pig_revenue / PIG_RATE if pig_revenue > 0 else 0
    
    print(f"  日均固定成本:   {daily_fixed_total:>12,.2f} 元/日")
    print(f"  平均吨收入:     {avg_revenue_per_ton:>12.2f} 元/吨")
    print(f"  平均吨变动成本: {avg_var_per_ton:>12.2f} 元/吨")
    print(f"  边际贡献:       {contribution_margin:>12.2f} 元/吨")
    print(f"  盈亏平衡日货量: {bep_tons:>12.1f} 吨/日 (实际 {total_tons:.0f} 吨/日, {bep_ratio:.1f}%)")
    if emu_tkm > 0:
        bep_emu_rate = (daily_total_cost - pig_revenue) / emu_tkm
        if bep_emu_rate > 0:
            print(f"  盈亏平衡EMU运价: {bep_emu_rate:>12.2f} 元/吨公里 (当前: {EMU_RATE})")
    else:
        print(f"  盈亏平衡EMU运价: N/A (捎带收入已覆盖全部成本)")
    
    # ── 敏感性分析 ──────────────────────────────────
    print(f"\n{'='*60}")
    print(f"【敏感性分析】")
    
    print(f"\n  7.1 需求波动对年净利润的影响：")
    scenarios = [-0.4, -0.2, -0.1, 0.0, 0.1, 0.2, 0.4]
    print(f"  {'需求变动':<10} {'年净利润(亿)':>14} {'NPV(亿)':>12} {'回收期(年)':>12}")
    for sc in scenarios:
        adj = 1 + sc
        adj_rev = total_revenue * adj
        adj_var = daily_var_cost * adj
        adj_tc = daily_fixed_total + adj_var
        adj_p = adj_rev - adj_tc
        adj_annual = adj_p * DAYS
        adj_pb = total_investment / adj_annual if adj_annual > 0 else float('inf')
        adj_npv = -total_investment + sum(adj_annual / ((1+DISCOUNT_RATE)**yr) for yr in range(1, YEARS+1))
        pb_str = f"{adj_pb:.2f}" if adj_pb < 100 else "N/A"
        print(f"  {sc:+.0%}         {adj_annual/1e8:>14.2f} {adj_npv/1e8:>12.2f} {pb_str:>12}")
    
    print(f"\n  7.2 EMU运价波动对年净利润的影响：")
    rate_sc = [-0.3, -0.15, -0.05, 0.0, 0.05, 0.15, 0.3]
    print(f"  {'费率变动':<10} {'年净利润(亿)':>14} {'NPV(亿)':>12} {'回收期(年)':>12}")
    for sc in rate_sc:
        adj = 1 + sc
        adj_rev = emu_revenue * adj + pig_revenue
        adj_p = adj_rev - daily_total_cost
        adj_annual = adj_p * DAYS
        adj_pb = total_investment / adj_annual if adj_annual > 0 else float('inf')
        adj_npv = -total_investment + sum(adj_annual / ((1+DISCOUNT_RATE)**yr) for yr in range(1, YEARS+1))
        pb_str = f"{adj_pb:.2f}" if adj_pb < 100 else "N/A"
        print(f"  {sc:+.0%}         {adj_annual/1e8:>14.2f} {adj_npv/1e8:>12.2f} {pb_str:>12}")
    
    print(f"\n  7.3 建设成本波动对回收期的影响：")
    cost_sc = [-0.3, -0.15, 0.0, 0.15, 0.3]
    print(f"  {'成本变动':<10} {'总投资(亿)':>14} {'回收期(年)':>12} {'NPV(亿)':>12}")
    for sc in cost_sc:
        adj_invest = total_investment * (1 + sc)
        adj_daily_depr = adj_invest / (YEARS * DAYS)
        adj_fixed = adj_daily_depr + daily_fixed_labor
        adj_tc = adj_fixed + daily_var_cost
        adj_p = total_revenue - adj_tc
        adj_annual = adj_p * DAYS
        adj_pb = adj_invest / adj_annual if adj_annual > 0 else float('inf')
        adj_npv = -adj_invest + sum(adj_annual / ((1+DISCOUNT_RATE)**yr) for yr in range(1, YEARS+1))
        pb_str = f"{adj_pb:.2f}" if adj_pb < 100 else "N/A"
        print(f"  {sc:+.0%}         {adj_invest/1e8:>14.2f} {pb_str:>12} {adj_npv/1e8:>12.2f}")
    
    # ── 保存 ────────────────────────────────────────
    results = {
        'n_bases': n_bases,
        'total_investment_yi': total_investment / 1e8,
        'daily_revenue': total_revenue,
        'daily_total_cost': daily_total_cost,
        'daily_net_profit': daily_net_profit,
        'annual_net_profit_yi': annual_net_profit / 1e8,
        'payback_months': payback_months,
        'npv_20yr_yi': npv / 1e8,
        'irr': irr,
        'bep_tons_per_day': bep_tons,
        'roi_annual': annual_net_profit / total_investment * 100,
    }
    with open(os.path.join(utils.OUTPUT_DIR, "problem5_results.json"), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存至 problem5_results.json")
    
    # ── 结论 ────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"【问题 5 最终结论】")
    print(f"  1. 项目总投资 {total_investment/1e8:.2f} 亿元，全部为改建小规模基地")
    print(f"  2. 日均净利润 {daily_net_profit:,.0f} 元，年化 {annual_net_profit/1e8:.2f} 亿元")
    print(f"  3. 投资回收期 {payback_months:.1f} 个月，ROI {annual_net_profit/total_investment*100:.1f}%/年")
    print(f"  4. 20年NPV = {npv/1e8:.1f} 亿元，IRR = {irr*100:.1f}%")
    print(f"  5. 盈亏平衡日货量 {bep_tons:.0f} 吨 (占实际 {bep_ratio:.1f}%)")
    if total_tons > 0:
        print(f"  6. 安全边际: {(total_tons - bep_tons)/total_tons*100:.1f}%")


if __name__ == '__main__':
    main()
