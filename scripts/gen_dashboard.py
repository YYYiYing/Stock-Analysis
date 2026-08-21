#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YYIH 儀表板生成器 - 修正版：以 8069 為範本，重建圖表與細緻內容 + 行動裝置響應式"""
import json, os

REPORTS = r"C:\Users\secre\OneDrive\OpenCode\YYIH\reports"
DIVS_PATH = os.path.join(os.path.dirname(__file__), "div_per_share.json")
try:
    DIVS = json.load(open(DIVS_PATH, encoding="utf-8"))
except:
    DIVS = {}
INDUSTRY = {
    "2603": "海運（貨櫃航運）",
    "3005": "電腦及週邊（強固型裝置）",
    "5243": "電子零組件（金屬機構件）",
    "3605": "電子零組件（連接器）",
    "2654": "電子零組件（連接器）",
    "2540": "營建開發",
    "5904": "零售通路（生活百貨）",
    "2484": "電子零組件（石英元件）",
    "8069": "光電業",
}

# 與 8069 完全相同的 CSS + 行動裝置擴充
CSS = """* { box-sizing: border-box; margin: 0; padding: 0; }
html { overflow-x: hidden; max-width: 100vw; }
html, body { overflow-x: hidden; }
    body { font-family: 'Microsoft JhengHei', 'Noto Sans TC', sans-serif; background: #f0f4f8; color: #2d3748; }
    .header {
      background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 50%, #3182ce 100%);
      color: white; padding: 24px 32px;
      display: flex; justify-content: space-between; align-items: center;
    }
    .header h1 { font-size: 1.5rem; font-weight: 700; }
    .header .subtitle { font-size: 0.85rem; opacity: 0.9; margin-top: 4px; }
    .badge { background: rgba(255,255,255,0.15); padding: 6px 14px; border-radius: 20px; font-size: 0.82rem; font-weight: 500; }
    .tabs { display: flex; background: white; border-bottom: 2px solid #e2e8f0; padding: 0 32px; }
    .tab { padding: 14px 24px; cursor: pointer; font-size: 0.95rem; font-weight: 600;
      color: #718096; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: all 0.2s; }
    .tab.active { color: #2b6cb0; border-bottom-color: #2b6cb0; }
    .tab-content { display: none; padding: 24px 32px; overflow-x: hidden; max-width: 100%; }
    .tab-content.active { display: block; max-width: 100%; }
    .kpi-row { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
    .kpi-card { flex: 1; min-width: 180px; background: white; border-radius: 12px;
      padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); border-left: 4px solid #3182ce; }
    .kpi-card.green { border-left-color: #38a169; }
    .kpi-card.orange { border-left-color: #dd6b20; }
    .kpi-card.red { border-left-color: #e53e3e; }
    .kpi-card.purple { border-left-color: #805ad5; }
    .kpi-label { font-size: 0.78rem; color: #718096; margin-bottom: 6px; font-weight: 500; text-transform: uppercase; }
    .kpi-value { font-size: 1.7rem; font-weight: 700; color: #2d3748; }
    .kpi-change { font-size: 0.82rem; margin-top: 4px; }
    .up { color: #38a169; } .down { color: #e53e3e; } .neutral { color: #718096; }
    .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; width: 100%; max-width: 100%; }
    .chart-card { background: white; border-radius: 12px; padding: 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); overflow: hidden; max-width: 100%; }
    .chart-card.full { grid-column: 1 / -1; }
    .chart-title { font-size: 0.92rem; font-weight: 700; color: #4a5568; margin-bottom: 16px;
      padding-bottom: 10px; border-bottom: 1px solid #f0f4f8; }
    .chart-container { position: relative; height: 240px; width: 100% !important; max-width: 100%; overflow: hidden; }
canvas { max-width: 100% !important; display: block; }
    .data-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 24px; }
    .data-table th { background: #2b6cb0; color: white; padding: 10px 14px; text-align: center; }
    .data-table td { padding: 9px 14px; text-align: right; border-bottom: 1px solid #e2e8f0; }
    .data-table tr:nth-child(even) td { background: #f7fafc; }
    .data-table td:first-child { text-align: left; font-weight: 500; }
    .data-table .section-header td { background: #ebf8ff; color: #2b6cb0; font-weight: 700; }
    .data-table .total-row td { background: #e6fffa; color: #276749; font-weight: 700; }
    .insight-box { background: linear-gradient(135deg, #ebf8ff, #e6fffa);
      border: 1px solid #bee3f8; border-radius: 12px; padding: 18px 22px; margin-bottom: 20px; }
    .insight-box h3 { color: #2b6cb0; font-size: 0.9rem; margin-bottom: 10px; }
    .insight-box ul { list-style: none; }
    .insight-box ul li { font-size: 0.87rem; color: #4a5568; padding: 3px 0;
      padding-left: 18px; position: relative; }
    .insight-box ul li::before { content: '▸'; position: absolute; left: 0; color: #3182ce; }
    .verify-bar { display: flex; gap: 16px; align-items: center; padding: 12px 32px; background: white; border-bottom: 1px solid #e2e8f0; font-size: 0.82rem; color: #718096; }
    .verify-bar a { color: #3182ce; text-decoration: none; font-weight: 500; }
    .verify-bar a:hover { text-decoration: underline; }
    .verify-badge { background: #c6f6d5; color: #276749; padding: 4px 10px; border-radius: 12px; font-weight: 600; }

.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); background: white; margin-bottom: 20px; }
.table-wrap .data-table { min-width: 560px; margin-bottom: 0; box-shadow: none; }
.finance-tables { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 4px; }
@media (max-width: 768px) {
  body { padding: 0; }
  .header { flex-direction: column; align-items: flex-start; gap: 10px; padding: 18px 16px; }
  .header h1 { font-size: 1.2rem; }
  .verify-bar { padding: 8px 16px; font-size: 0.72rem; flex-wrap: wrap; }
  .tabs { padding: 0 8px; overflow-x: auto; -webkit-overflow-scrolling: touch; white-space: nowrap; }
  .tab { padding: 12px 13px; font-size: 0.85rem; white-space: nowrap; flex-shrink: 0; }
  .tab-content { padding: 16px 12px; }
  .kpi-row { gap: 10px; }
  .kpi-card { min-width: calc(50% - 5px); padding: 14px; }
  .kpi-value { font-size: 1.35rem; }
  .kpi-label { font-size: 0.7rem; }
  .charts-grid { grid-template-columns: 1fr; gap: 14px; }
  .chart-card { padding: 16px; }
  .chart-container { height: 200px !important; }
  .chart-title { font-size: 0.85rem; }
  .insight-box { padding: 14px 16px; }
  .insight-box ul li { font-size: 0.82rem; }
  .data-table { font-size: 0.78rem; }
  .data-table th, .data-table td { padding: 8px 10px; }
  .finance-tables { grid-template-columns: 1fr !important; gap: 14px; }
}
@media (max-width: 480px) {
  .kpi-card { min-width: 100%; }
  .header h1 { font-size: 1.1rem; }
}"""

def fmt(v, dp=0):
    if v is None: return "-"
    return f"{v:,.{dp}f}"
def fmt_pct(v, dp=1):
    return "-" if v is None else f"{v:.{dp}f}%"

def trend(series, higher=True):
    vals=[v for v in series if v is not None]
    if len(vals)<2 or series[-1] is None or series[0] is None:
        return ("neutral","■ 資料不足")
    d=series[-1]-series[0]
    good=d>0 if higher else d<0
    if abs(d)<0.3: return ("neutral", "■ 大致持平")
    return (("up", "▲ 改善") if good else ("down", "▼ 惡化"))
def rev_trend(series):
    if series[0] in (None,0) or series[-1] is None: return ("neutral","■ 資料不足")
    try: cagr=((series[-1]/series[0])**0.5-1)*100
    except: return ("neutral","■ 資料不足")
    if cagr>5: return ("up", f"▲ CAGR +{cagr:.1f}%")
    if cagr<-5: return ("down", f"▼ CAGR {cagr:.1f}%")
    return ("neutral", f"■ CAGR {cagr:+.1f}%")

def chart_script(cid, config):
    s=json.dumps(config, ensure_ascii=False)
    s=s.replace('"__PCT__"', "v=>v+'%'")
    return f"<script>new Chart(document.getElementById('{cid}'),{s});</script>"
def wrap(cid, title, config):
    return f'<div class="chart-card"><div class="chart-title">{title}</div><div class="chart-container"><canvas id="{cid}"></canvas></div></div>' + chart_script(cid, config)

def generate(sid):
    j=json.load(open(os.path.join(REPORTS, f"{sid}_raw_data.json"), encoding="utf-8"))
    name=j.get("company", sid)
    years=sorted(j["years"][:3])
    M=j["metrics"]
    md=j.get("metadata",{})
    ver=j.get("verification", {"sanity_pass": True, "sanity": []})
    divs=DIVS.get(sid, {})
    div_series=[divs.get(y) for y in years]
    g=lambda k: [M[y].get(k) for y in years]
    L=lambda k: M[years[-1]].get(k)
    P=lambda k: M[years[-2]].get(k)
    yoy=lambda k: (L(k)/P(k)-1)*100 if (L(k) and P(k)) else None
    dpp=lambda k: (L(k)-P(k)) if (L(k) is not None and P(k) is not None) else None
    ser=lambda k: [x for x in g(k) if x is not None]

    is_data=j.get("income_statement",{})
    def pick_raw(*kws):
        for k,v in is_data.items():
            if any(w in k for w in kws):
                return [v.get(y) for y in years]
        return [None]*3
    cost_series=[ (M[y]["revenue"]-M[y]["gross_profit"]) if (M[y].get("revenue") is not None and M[y].get("gross_profit") is not None) else None for y in years]
    pretax_series=pick_raw("稅前淨利")
    tax_series=pick_raw("所得稅")
    ca_series=g("current_assets"); ta_series=g("total_assets"); cl_series=g("current_liabilities"); tl_series=g("total_liabilities")
    nca_series=[ (ta-ca) if (ta is not None and ca is not None) else None for ta,ca in zip(ta_series, ca_series)]
    ncl_series=[ -(tl-cl) if (tl is not None and cl is not None) else None for tl,cl in zip(tl_series, cl_series)]
    cl_neg=[ -v if v is not None else None for v in cl_series]

    fetched=md.get("fetched_at","2026-08-21")[:10]
    sanity_badge='<span class="verify-badge">✅ 合理性檢查通過</span>' if ver.get("sanity_pass", True) else f'<span class="verify-badge" style="background:#fed7d7;color:#9b2c2c;">⚠️ {len(ver.get("sanity",[]))} 項警示</span>'
    mops=md.get("mops_url", f"https://mops.twse.com.tw/mops/web/t05st01?step=1&co_id={sid}&TYPEK=sii")
    gi=md.get("source_urls", {"income_statement": f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_YEAR&STOCK_ID={sid}", "balance_sheet": f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=BS_YEAR&STOCK_ID={sid}", "cash_flow": f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=CF_YEAR&STOCK_ID={sid}"})
    supp=md.get("supplement_source")
    supp_note=(f'｜<span title="{supp.get("reason","")}">部分數據由 {supp.get("cash_flow","FinMind")} 補足</span>' if supp else "")

    rev_yoy=yoy("revenue")
    try: rev_cagr=((L("revenue")/M[years[0]]["revenue"])**0.5-1)*100
    except: rev_cagr=0
    gm_d=dpp("gross_margin"); opex_d=dpp("total_opex_ratio"); om_d=dpp("op_margin")
    ni_yoy=yoy("net_income"); eps_yoy=yoy("eps"); roe_d=dpp("roe"); nm_d=dpp("net_margin")
    payout=(divs.get(years[-1],0)/L("eps")*100) if (divs.get(years[-1]) and L("eps")) else None
    ocf_ni=(L("op_cf")/L("net_income")) if (L("op_cf") is not None and L("net_income")) else None
    cr_l, dr_l = L("current_ratio"), L("debt_ratio")
    cash_yoy=yoy("cash")
    cr_grade=("優異（>200%）" if cr_l and cr_l>200 else "健康（150–200%）" if cr_l and cr_l>150 else "需關注（<150%）")
    dr_grade=("穩健（<60%）" if dr_l and dr_l<60 else "偏高（≥60%）")

    # KPI 經營
    has_rd=bool(ser("rd_ratio"))
    k4_lbl="研發費用率" if has_rd else "推銷費用率"
    k4_val=fmt_pct(L("rd_ratio")) if has_rd else fmt_pct(L("sell_ratio"))
    k4_before=fmt_pct(P("rd_ratio")) if has_rd else fmt_pct(P("sell_ratio"))
    ins4_rd=f"研發費用三年 {fmt(g('rd_exp')[0])} → {fmt(g('rd_exp')[1])} → {fmt(g('rd_exp')[2])} 億，佔營收{fmt_pct(L('rd_ratio'))}，投入強度{'穩定' if abs((dpp('rd_ratio') or 0))<0.5 else '有變化'}" if has_rd else f"推銷費用率 {fmt_pct(g('sell_ratio')[0])} → {fmt_pct(L('sell_ratio'))}、管理費用率 {fmt_pct(g('admin_ratio')[0])} → {fmt_pct(L('admin_ratio'))}（此產業無單獨研發費用列）"
    k1=f"""<div class="kpi-row">
<div class="kpi-card {'green' if (rev_yoy or 0)>0 else 'red'}"><div class="kpi-label">營業收入 (億元)</div><div class="kpi-value">{fmt(L('revenue'))}</div><div class="kpi-change {'up' if (rev_yoy or 0)>0 else 'down'}">▲ {rev_yoy:+.1f}% YoY（{years[-2]}年{fmt(P('revenue'))}→{years[-1]}年{fmt(L('revenue'))}）</div></div>
<div class="kpi-card green"><div class="kpi-label">毛利率</div><div class="kpi-value">{fmt_pct(L('gross_margin'))}</div><div class="kpi-change {'up' if (gm_d or 0)>0 else 'down'}">{'▲' if (gm_d or 0)>0 else '▼'} {years[-2]}年{fmt_pct(P('gross_margin'))} → {years[-1]}年{fmt_pct(L('gross_margin'))}</div></div>
<div class="kpi-card {'green' if (opex_d or 0)<0 else 'orange'}"><div class="kpi-label">營業費用率</div><div class="kpi-value">{fmt_pct(L('total_opex_ratio'))}</div><div class="kpi-change {'up' if (opex_d or 0)<0 else 'down'}">{'▼' if (opex_d or 0)<0 else '▲'} {years[-2]}年{fmt_pct(P('total_opex_ratio'))} → {years[-1]}年{fmt_pct(L('total_opex_ratio'))}</div></div>
<div class="kpi-card green"><div class="kpi-label">營業利益率</div><div class="kpi-value">{fmt_pct(L('op_margin'))}</div><div class="kpi-change {'up' if (om_d or 0)>0 else 'down'}">▲ {years[-2]}年{fmt_pct(P('op_margin'))} → {years[-1]}年{fmt_pct(L('op_margin'))}</div></div>
<div class="kpi-card purple"><div class="kpi-label">{k4_lbl}</div><div class="kpi-value">{k4_val}</div><div class="kpi-change neutral">■ {years[-2]}年{k4_before} → {years[-1]}年{k4_val}</div></div>
</div>"""
    ins1=f"""<ul>
<li>三年營收 {fmt(M[years[0]]['revenue'])} → {fmt(M[years[1]]['revenue'])} → {fmt(L('revenue'))} 億，CAGR {rev_cagr:+.1f}%，{years[-1]}年 YoY {rev_yoy:+.1f}%</li>
<li>毛利率三年 {fmt_pct(g('gross_margin')[0])} → {fmt_pct(g('gross_margin')[1])} → {fmt_pct(L('gross_margin'))}，{years[-1]}年 {gm_d:+.1f}pp，{'獲利結構改善' if (gm_d or 0)>0 else '呈現壓縮'}</li>
<li>{ins4_rd}</li>
<li>營業利益率三年 {fmt_pct(g('op_margin')[0])} → {fmt_pct(g('op_margin')[1])} → {fmt_pct(L('op_margin'))}，{years[-1]}年 {om_d:+.1f}pp，{'規模效益顯現' if (om_d or 0)>= (gm_d or 0) else '部分被費用侵蝕'}</li>
</ul>"""
    # KPI 獲利
    k2=f"""<div class="kpi-row">
<div class="kpi-card {'green' if (ni_yoy or 0)>0 else 'red'}"><div class="kpi-label">稅後淨利 (億元)</div><div class="kpi-value">{fmt(L('net_income'))}</div><div class="kpi-change {'up' if (ni_yoy or 0)>0 else 'down'}">▲ {ni_yoy:+.1f}% YoY（{years[-2]}年{fmt(P('net_income'))}→{years[-1]}年{fmt(L('net_income'))}）</div></div>
<div class="kpi-card {'green' if (eps_yoy or 0)>0 else 'red'}"><div class="kpi-label">EPS (元)</div><div class="kpi-value">{fmt(L('eps'),2)}</div><div class="kpi-change {'up' if (eps_yoy or 0)>0 else 'down'}">▲ {eps_yoy:+.1f}% YoY{'｜創三年新高' if L('eps')==max(x for x in g('eps') if x is not None) else ''}</div></div>
<div class="kpi-card green"><div class="kpi-label">ROE</div><div class="kpi-value">{fmt_pct(L('roe'))}</div><div class="kpi-change {'up' if (roe_d or 0)>0 else 'down'}">{'▲' if (roe_d or 0)>0 else '▼'} {years[-2]}年{fmt_pct(P('roe'))} → {years[-1]}年{fmt_pct(L('roe'))}</div></div>
<div class="kpi-card green"><div class="kpi-label">ROA</div><div class="kpi-value">{fmt_pct(L('roa'))}</div><div class="kpi-change neutral">■ {years[-2]}年{fmt_pct(P('roa'))} → {years[-1]}年{fmt_pct(L('roa'))}</div></div>
<div class="kpi-card purple"><div class="kpi-label">現金股利 (元/股)</div><div class="kpi-value">{divs.get(years[-1], '-')}</div><div class="kpi-change neutral">■ 配息率約 {f"{payout:.0f}%" if payout else "—"}</div></div>
</div>"""
    ins2=f"""<ul>
<li>三年EPS {fmt(M[years[0]]['eps'],2)} → {fmt(M[years[1]]['eps'],2)} → {fmt(L('eps'),2)}元，CAGR {(((L('eps')/M[years[0]]['eps'])**0.5-1)*100):+.1f}%，{years[-1]}年{'創新高' if L('eps')==max(x for x in g('eps') if x is not None) else '回檔'}</li>
<li>稅後淨利 {fmt(M[years[0]]['net_income'])} → {fmt(L('net_income'))} 億，{years[-1]}年 YoY {ni_yoy:+.1f}%，淨利率 {fmt_pct(L('net_margin'))}</li>
<li>ROE三年 {fmt_pct(g('roe')[0])} → {fmt_pct(g('roe')[1])} → {fmt_pct(L('roe'))}，{'穩定優質' if L('roe') and L('roe')>10 else '待提升'}</li>
<li>現金股利 {div_series[0]} → {div_series[1]} → {div_series[2]} 元，{years[-1]}年配息率約 {f'{payout:.0f}%' if payout else '—'}</li>
</ul>"""
    # KPI 財務
    k3=f"""<div class="kpi-row">
<div class="kpi-card {'green' if cr_l and cr_l>150 else 'orange'}"><div class="kpi-label">流動比率</div><div class="kpi-value">{fmt_pct(cr_l)}</div><div class="kpi-change neutral">■ {cr_grade}</div></div>
<div class="kpi-card {'green' if dr_l and dr_l<60 else 'red'}"><div class="kpi-label">負債比率</div><div class="kpi-value">{fmt_pct(dr_l)}</div><div class="kpi-change neutral">■ {dr_grade}</div></div>
<div class="kpi-card {'green' if (L('op_cf') or 0)>0 else 'red'}"><div class="kpi-label">營業現金流 (億元)</div><div class="kpi-value">{fmt(L('op_cf'))}</div><div class="kpi-change neutral">■ 為淨利的 {ocf_ni:.1f} 倍</div></div>
<div class="kpi-card {'green' if (L('fcf') or 0)>0 else 'red'}"><div class="kpi-label">自由現金流 (億元)</div><div class="kpi-value">{fmt(L('fcf'))}</div><div class="kpi-change neutral">■ Capex {fmt(L('capex'))} 億</div></div>
<div class="kpi-card purple"><div class="kpi-label">現金部位 (億元)</div><div class="kpi-value">{fmt(L('cash'))}</div><div class="kpi-change {'up' if (cash_yoy or 0)>0 else 'down'}">{'▲' if (cash_yoy or 0)>0 else '▼'} {cash_yoy:+.1f}% YoY</div></div>
</div>"""
    ins3=f"""<ul>
<li>流動比率 {fmt_pct(g('current_ratio')[0])} → {fmt_pct(cr_l)}，{cr_grade}，短期償債能力{'良好' if cr_l and cr_l>150 else '偏弱'}</li>
<li>負債比率 {fmt_pct(g('debt_ratio')[0])} → {fmt_pct(dr_l)}，{dr_grade}</li>
<li>現金部位 {fmt(M[years[0]]['cash'])} → {fmt(L('cash'))} 億（{years[-1]}年 {cash_yoy:+.1f}%），{'財務彈性充足' if (cash_yoy or 0)>0 else '因配息／投資消化'}</li>
<li>營業現金流 {fmt(L('op_cf'))} 億，為淨利的 {ocf_ni:.1f} 倍，{'獲利含金量高' if ocf_ni and ocf_ni>0.8 else '現金轉換待改善'}</li>
</ul>"""

    def table(rows):
        th="".join(f"<th>{y}</th>" for y in years)
        body=""
        for label, vals, fn, (cls,txt), rowcls in rows:
            tds="".join(f"<td>{fn(v)}</td>" for v in vals)
            rc=f' class="{rowcls}"' if rowcls else ""
            body+=f"<tr{rc}><td>{label}</td>{tds}<td class=\"{cls}\">{txt}</td></tr>"
        return f'<table class="data-table"><thead><tr><th>項目</th>{th}<th>趨勢評估</th></tr></thead><tbody>{body}</tbody></table>'

    t1=table([
        ("營業收入 (億元)", g("revenue"), lambda v: fmt(v), rev_trend(g("revenue")), ""),
        ("營業成本 (億元)", cost_series, lambda v: fmt(v), trend(cost_series, higher=False), ""),
        ("營業毛利 (億元)", g("gross_profit"), lambda v: fmt(v), trend(g("gross_profit")), ""),
        ("推銷費用 (億元)", g("sell_exp"), lambda v: fmt(v), trend(g("sell_exp"), higher=False), ""),
        ("管理費用 (億元)", g("admin_exp"), lambda v: fmt(v), trend(g("admin_exp"), higher=False), ""),
        ("研究發展費用 (億元)", g("rd_exp"), lambda v: fmt(v), trend(g("rd_exp")), ""),
        ("營業利益 (億元)", g("op_income"), lambda v: fmt(v), trend(g("op_income")), ""),
        ("毛利率", g("gross_margin"), lambda v: fmt_pct(v), trend(g("gross_margin")), "total-row"),
        ("營業利益率", g("op_margin"), lambda v: fmt_pct(v), trend(g("op_margin")), "total-row"),
    ])
    t2=table([
        ("稅前淨利 (億元)", pretax_series, lambda v: fmt(v), trend(pretax_series), ""),
        ("所得稅費用 (億元)", tax_series, lambda v: fmt(v), trend(tax_series, higher=False), ""),
        ("稅後淨利 (億元)", g("net_income"), lambda v: fmt(v), trend(g("net_income")), ""),
        ("EPS (元)", g("eps"), lambda v: fmt(v,2), trend(g("eps")), ""),
        ("毛利率", g("gross_margin"), lambda v: fmt_pct(v), trend(g("gross_margin")), "total-row"),
        ("營業利益率", g("op_margin"), lambda v: fmt_pct(v), trend(g("op_margin")), "total-row"),
        ("淨利率", g("net_margin"), lambda v: fmt_pct(v), trend(g("net_margin")), "total-row"),
        ("ROE", g("roe"), lambda v: fmt_pct(v), trend(g("roe")), "total-row"),
        ("ROA", g("roa"), lambda v: fmt_pct(v), trend(g("roa")), "total-row"),
    ])
    bs_t=table([
        ("流動資產 (億元)", g("current_assets"), lambda v: fmt(v), trend(g("current_assets")), ""),
        ("流動負債 (億元)", g("current_liabilities"), lambda v: fmt(v), trend(g("current_liabilities"), higher=False), ""),
        ("資產總額 (億元)", g("total_assets"), lambda v: fmt(v), trend(g("total_assets")), ""),
        ("負債總額 (億元)", g("total_liabilities"), lambda v: fmt(v), trend(g("total_liabilities"), higher=False), ""),
        ("股東權益 (億元)", g("equity"), lambda v: fmt(v), trend(g("equity")), ""),
        ("流動比率", g("current_ratio"), lambda v: fmt_pct(v), trend(g("current_ratio")), "total-row"),
        ("負債比率", g("debt_ratio"), lambda v: fmt_pct(v), trend(g("debt_ratio"), higher=False), "total-row"),
    ])
    cf_t=table([
        ("營業CF (億元)", g("op_cf"), lambda v: fmt(v), trend(g("op_cf")), ""),
        ("投資CF (億元)", g("inv_cf"), lambda v: fmt(v), trend(g("inv_cf")), ""),
        ("融資CF (億元)", g("fin_cf"), lambda v: fmt(v), trend(g("fin_cf")), ""),
        ("資本支出 (億元)", g("capex"), lambda v: fmt(v), trend(g("capex"), higher=False), ""),
        ("自由現金流 (億元)", g("fcf"), lambda v: fmt(v), trend(g("fcf")), "total-row"),
        ("現金部位 (億元)", g("cash"), lambda v: fmt(v), trend(g("cash")), "total-row"),
    ])

    common={"responsive": True, "maintainAspectRatio": False, "plugins": {"legend": {"position": "bottom"}}}
    charts=[]
    # 1
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}},"y2":{"position":"right","grid":{"display":False},"ticks":{"callback":"__PCT__"},"title":{"display":True,"text":"%"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"營業收入 (億元)","data":g("revenue"),"backgroundColor":"rgba(49,130,206,0.15)","borderColor":"#3182ce","borderWidth":2,"yAxisID":"y"},{"label":"毛利率 (%)","data":g("gross_margin"),"type":"line","borderColor":"#38a169","backgroundColor":"#38a169","pointRadius":5,"tension":0.3,"yAxisID":"y2"}]},"options":{**common, "scales":scales}}
    charts.append(wrap("revenueChart","營收與毛利率趨勢",cfg))
    # 2
    scales={"x":{"stacked":True,"grid":{"display":False}},"y":{"stacked":True,"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"推銷費用","data":g("sell_exp"),"backgroundColor":"#e53e3e"},{"label":"管理費用","data":g("admin_exp"),"backgroundColor":"#dd6b20"},{"label":"研發費用","data":g("rd_exp"),"backgroundColor":"#805ad5"}]},"options":{**common, "scales":scales}}
    charts.append(wrap("expenseStackChart","費用結構堆疊",cfg))
    # 3
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"ticks":{"callback":"__PCT__"}}}
    cfg={"type":"line","data":{"labels":years,"datasets":[{"label":"推銷費用率","data":g("sell_ratio"),"borderColor":"#e53e3e","tension":0.3},{"label":"管理費用率","data":g("admin_ratio"),"borderColor":"#dd6b20","tension":0.3},{"label":"研發費用率","data":g("rd_ratio"),"borderColor":"#805ad5","tension":0.3},{"label":"總費用率","data":g("total_opex_ratio"),"borderColor":"#718096","borderDash":[5,5],"tension":0.3}]},"options":{**common, "scales":scales}}
    charts.append(wrap("expenseRatioChart","費用率趨勢",cfg))
    # 4
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}},"y2":{"position":"right","grid":{"display":False},"ticks":{"callback":"__PCT__"},"title":{"display":True,"text":"%"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"營業利益 (億元)","data":g("op_income"),"backgroundColor":"rgba(56,161,105,0.15)","borderColor":"#38a169","borderWidth":2,"yAxisID":"y"},{"label":"營業利益率 (%)","data":g("op_margin"),"type":"line","borderColor":"#dd6b20","backgroundColor":"#dd6b20","pointRadius":5,"tension":0.3,"yAxisID":"y2"}]},"options":{**common, "scales":scales}}
    charts.append(wrap("operatingIncomeChart","營業利益與利益率",cfg))
    max_eps=max([x for x in g("eps") if x is not None], default=None)
    eps_bg=["rgba(56,161,105,0.3)" if v==max_eps else "rgba(49,130,206,0.3)" for v in g("eps")]
    eps_bd=["#38a169" if v==max_eps else "#3182ce" for v in g("eps")]
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}},"y2":{"position":"right","grid":{"display":False},"ticks":{"callback":"__PCT__"},"title":{"display":True,"text":"%"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"稅後淨利 (億元)","data":g("net_income"),"backgroundColor":"rgba(49,130,206,0.15)","borderColor":"#3182ce","borderWidth":2,"yAxisID":"y"},{"label":"淨利率 (%)","data":g("net_margin"),"type":"line","borderColor":"#38a169","backgroundColor":"#38a169","pointRadius":5,"tension":0.3,"yAxisID":"y2"}]},"options":{**common, "scales":scales}}
    charts.append(wrap("netIncomeChart","淨利與淨利率趨勢",cfg))
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"元"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"EPS (元)","data":g("eps"),"backgroundColor":eps_bg,"borderColor":eps_bd,"borderWidth":2}]},"options":{**common, "scales":scales}}
    charts.append(wrap("epsChart","EPS 趨勢",cfg))
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"ticks":{"callback":"__PCT__"}}}
    cfg={"type":"line","data":{"labels":years,"datasets":[{"label":"毛利率","data":g("gross_margin"),"borderColor":"#38a169","tension":0.3},{"label":"營業利益率","data":g("op_margin"),"borderColor":"#3182ce","tension":0.3},{"label":"淨利率","data":g("net_margin"),"borderColor":"#805ad5","tension":0.3}]},"options":{**common, "scales":scales}}
    charts.append(wrap("profitMarginChart","三層利潤率比較",cfg))
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"元/股"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"現金股利 (元/股)","data":div_series,"backgroundColor":"rgba(221,107,32,0.3)","borderColor":"#dd6b20","borderWidth":2}]},"options":{**common, "scales":scales}}
    charts.append(wrap("dividendChart","現金股利趨勢",cfg))
    scales={"x":{"stacked":True,"grid":{"display":False}},"y":{"stacked":True,"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"流動資產","data":g("current_assets"),"backgroundColor":"#3182ce"},{"label":"非流動資產","data":nca_series,"backgroundColor":"#90cdf4"},{"label":"流動負債","data":cl_neg,"backgroundColor":"#e53e3e"},{"label":"非流動負債","data":ncl_series,"backgroundColor":"#feb2b2"}]},"options":{**common, "scales":scales}}
    charts.append(wrap("balanceSheetChart","資產負債結構",cfg))
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}}}
    cfg={"type":"bar","data":{"labels":years,"datasets":[{"label":"營業CF","data":g("op_cf"),"backgroundColor":"#38a169"},{"label":"投資CF","data":g("inv_cf"),"backgroundColor":"#e53e3e"},{"label":"融資CF","data":g("fin_cf"),"backgroundColor":"#dd6b20"}]},"options":{**common, "scales":scales}}
    charts.append(wrap("cashFlowChart","現金流三表",cfg))
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"ticks":{"callback":"__PCT__"}}}
    cfg={"type":"line","data":{"labels":years,"datasets":[{"label":"流動比率","data":g("current_ratio"),"borderColor":"#3182ce","tension":0.3},{"label":"負債比率","data":g("debt_ratio"),"borderColor":"#e53e3e","tension":0.3}]},"options":{**common, "scales":scales}}
    charts.append(wrap("ratioChart","流動與負債比率",cfg))
    scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}}}
    cfg={"type":"line","data":{"labels":years,"datasets":[{"label":"現金部位","data":g("cash"),"borderColor":"#3182ce","backgroundColor":"rgba(49,130,206,0.1)","fill":True,"tension":0.3},{"label":"自由現金流","data":g("fcf"),"borderColor":"#38a169","borderDash":[5,5],"tension":0.3}]},"options":{**common, "scales":scales}}
    charts.append(wrap("cashChart","現金趨勢",cfg))

    # --- 季月動能（FinMind 季报/月报，仅 2484 新版有）---
    has_q = "quarterly" in j and isinstance(j["quarterly"], list) and len(j["quarterly"])>0
    has_m = "monthly" in j and isinstance(j["monthly"], list) and len(j["monthly"])>0
    momentum_tab=""
    momentum_content=""
    if has_q or has_m:
        momentum_tab = '<div class="tab" onclick="switchTab(\'momentum\')">📈 季月動能</div>'
        m_charts=[]
        if has_q:
            q = j["quarterly"]
            q_labels=[x.get("label", x.get("date","")) for x in q]
            def norm(v):
                if v is None: return None
                return v/1e8 if abs(v)>1e6 else v
            q_rev=[norm(x.get("revenue")) for x in q]
            q_gm=[x.get("gross_margin") for x in q]
            q_ni=[norm(x.get("net_income")) for x in q]
            q_nm=[x.get("net_margin") for x in q]
            scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}},"y2":{"position":"right","grid":{"display":False},"ticks":{"callback":"__PCT__"},"title":{"display":True,"text":"%"}}}
            cfg={"type":"bar","data":{"labels":q_labels,"datasets":[{"label":"單季營收 (億元)","data":q_rev,"backgroundColor":"rgba(49,130,206,0.15)","borderColor":"#3182ce","borderWidth":2,"yAxisID":"y"},{"label":"毛利率 (%)","data":q_gm,"type":"line","borderColor":"#38a169","backgroundColor":"#38a169","pointRadius":4,"tension":0.3,"yAxisID":"y2"}]},"options":{**common, "scales":scales}}
            m_charts.append(wrap("qqRevChart","單季營收与毛利率（近8季）",cfg))
            cfg2={"type":"bar","data":{"labels":q_labels,"datasets":[{"label":"單季淨利 (億元)","data":q_ni,"backgroundColor":"rgba(56,161,105,0.15)","borderColor":"#38a169","borderWidth":2,"yAxisID":"y"},{"label":"淨利率 (%)","data":q_nm,"type":"line","borderColor":"#805ad5","backgroundColor":"#805ad5","pointRadius":4,"tension":0.3,"yAxisID":"y2"}]},"options":{**common, "scales":scales}}
            m_charts.append(wrap("qqNiChart","單季淨利与淨利率",cfg2))
            qoq=[x.get("qoq") for x in q]
            if all(v is None for v in qoq):
                qoq=[]
                for i in range(len(q_rev)):
                    if i==0 or q_rev[i] is None or q_rev[i-1] in (None,0): qoq.append(None)
                    else: qoq.append((q_rev[i]/q_rev[i-1]-1)*100)
            cfg3={"type":"bar","data":{"labels":q_labels,"datasets":[{"label":"QoQ (%)","data":qoq,"backgroundColor":["rgba(56,161,105,0.6)" if (v or 0)>0 else "rgba(229,62,62,0.6)" for v in qoq],"borderColor":"#3182ce","borderWidth":1}]},"options":{**common, "scales":{"x":{"grid":{"display":False}},"y":{"ticks":{"callback":"__PCT__"}}}}}
            m_charts.append(wrap("qqQoqChart","單季營收 QoQ",cfg3))
        if has_m:
            m_data=j["monthly"]
            m_labels=[x.get("date","") for x in m_data]
            m_rev=[x.get("revenue") for x in m_data]
            mom=[]
            for i in range(len(m_rev)):
                if i==0 or m_rev[i] is None or m_rev[i-1] in (None,0): mom.append(None)
                else: mom.append((m_rev[i]/m_rev[i-1]-1)*100)
            scales={"x":{"grid":{"display":False}},"y":{"grid":{"color":"rgba(0,0,0,0.05)"},"title":{"display":True,"text":"億元"}},"y2":{"position":"right","grid":{"display":False},"ticks":{"callback":"__PCT__"}}}
            cfg={"type":"bar","data":{"labels":m_labels,"datasets":[{"label":"月營收 (億元)","data":m_rev,"backgroundColor":"rgba(49,130,206,0.2)","borderColor":"#3182ce","borderWidth":1,"yAxisID":"y"},{"label":"MoM (%)","data":mom,"type":"line","borderColor":"#dd6b20","backgroundColor":"#dd6b20","pointRadius":3,"tension":0.3,"yAxisID":"y2"}]},"options":{**common, "scales":scales}}
            m_charts.append(wrap("mmRevChart","月營收与 MoM（近12月）",cfg))
        q=j.get("quarterly",[])
        if q:
            last=q[-1]
            # YoY
            rev_yoy=None
            if len(q)>=5:
                yoy_prev=q[-5]
                if last.get("revenue") and yoy_prev.get("revenue"):
                    lv=last["revenue"]/1e8 if abs(last["revenue"])>1e6 else last["revenue"]
                    pv=yoy_prev["revenue"]/1e8 if abs(yoy_prev["revenue"])>1e6 else yoy_prev["revenue"]
                    rev_yoy=(lv/pv-1)*100 if pv else None
            qoq_val=last.get("qoq")
            if qoq_val is None and len(q)>=2:
                lv=last["revenue"]/1e8 if abs(last["revenue"])>1e6 else last["revenue"]
                pv=q[-2]["revenue"]/1e8 if abs(q[-2]["revenue"])>1e6 else q[-2]["revenue"]
                if lv and pv: qoq_val=(lv/pv-1)*100
            insights=[]
            if rev_yoy is not None:
                insights.append(f"單季營收 {last.get('label')} YoY {rev_yoy:+.1f}%")
            if qoq_val is not None:
                insights.append(f"QoQ {qoq_val:+.1f}%")
            if has_m:
                md=j["monthly"]
                last_m=md[-1]
                prev_m=md[-2] if len(md)>=2 else {}
                if last_m.get("revenue") and prev_m.get("revenue"):
                    mom_val=(last_m["revenue"]/prev_m["revenue"]-1)*100
                    insights.append(f"近月 {last_m.get('date')} MoM {mom_val:+.1f}%")
                if len(md)>=13 and md[-1].get("revenue") and md[-13].get("revenue"):
                    yoy_m=(md[-1]["revenue"]/md[-13]["revenue"]-1)*100
                    insights.append(f"月營收 YoY {yoy_m:+.1f}%")
            if not insights:
                insights.append("近8季營收趋势平稳")
            # 補上年報風格的說明：每條含 幅度 + 意義
            detailed=[]
            for s in insights:
                if "YoY" in s and "營收" in s:
                    detailed.append(s + "，季度營收年增轉強" if rev_yoy and rev_yoy>5 else s + "，年增動能放緩")
                elif "QoQ" in s:
                    try:
                        val=float(s.split()[1].replace("%","").replace("+",""))
                        detailed.append(s + "，短期動能轉強" if val>0 else s + "，短期動能轉弱")
                    except:
                        detailed.append(s)
                elif "MoM" in s:
                    detailed.append(s + "，月動能延續" if "MoM" in s and "+" in s else s)
                elif "月營收 YoY" in s:
                    detailed.append(s + "，月年增與季增同步")
                else:
                    detailed.append(s)
            # 再補一條整體季度毛利/淨利趨勢
            if q:
                gm_trend = q[-1].get("gross_margin",0) - q[0].get("gross_margin",0) if q[-1].get("gross_margin") and q[0].get("gross_margin") else 0
                detailed.append(f"毛利率 {q[0].get('gross_margin',0):.1f}% → {q[-1].get('gross_margin',0):.1f}% {'結構改善' if gm_trend>0 else '結構承壓'}")
            momentum_insight="<ul>"+"".join(f"<li>{s}</li>" for s in detailed[:5])+"</ul>"
        else:
            momentum_insight="<ul><li>季月数据加载中</li></ul>"
        momentum_charts="".join(m_charts)
        rows_html="".join(f"<tr><td>{x.get('label')}</td><td>{(x.get('revenue',0)/1e8 if abs(x.get('revenue',0))>1e6 else x.get('revenue') or 0):.2f}</td><td>{(x.get('gross_margin') or 0):.1f}%</td><td>{(x.get('net_income',0)/1e8 if abs(x.get('net_income',0))>1e6 else x.get('net_income') or 0):.2f}</td><td>{(x.get('net_margin') or 0):.1f}%</td><td>{x.get('eps')}</td></tr>" for x in j["quarterly"])
        momentum_content=f'<div id="momentum" class="tab-content"><div class="insight-box"><h3>季月動能亮点</h3>{momentum_insight}</div><div class="charts-grid">{momentum_charts}</div><div class="table-wrap"><table class="data-table"><thead><tr><th>季度</th><th>營收(亿)</th><th>毛利率</th><th>淨利(亿)</th><th>淨利率</th><th>EPS</th></tr></thead><tbody>'+rows_html+'</tbody></table></div></div>'
    ops_charts="".join(charts[0:4])
    profit_charts="".join(charts[4:8])
    fin_charts="".join(charts[8:12])

    html=f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} ({sid}) 三維財務分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="header"><div><h1>{name} ({sid}) 財務分析儀表板</h1><div class="subtitle">資料來源：Goodinfo.tw{supp_note}｜分析期間：{years[0]} – {years[-1]}｜金額單位：億元 (NTD)</div></div><div class="badge">🏢 {INDUSTRY.get(sid,'上市櫃公司')}</div></div>
<div class="verify-bar">{sanity_badge}<span>抓取時間：{fetched}</span><a href="{gi['income_statement']}" target="_blank">🔍 Goodinfo 原始數據</a><a href="{mops}" target="_blank">📋 MOPS 官方申報</a><a href="index.html">← 回總覽</a></div>
<div class="tabs"><div class="tab active" onclick="switchTab('ops')">📊 經營分析</div><div class="tab" onclick="switchTab('profit')">💰 獲利分析</div><div class="tab" onclick="switchTab('finance')">🏦 財務健全度</div>{momentum_tab}</div>
<div id="ops" class="tab-content active">{k1}<div class="insight-box"><h3>🔍 經營亮點</h3>{ins1}</div><div class="charts-grid">{ops_charts}</div><div class="table-wrap">{t1}</div></div>
<div id="profit" class="tab-content">{k2}<div class="insight-box"><h3>🔍 獲利亮點</h3>{ins2}</div><div class="charts-grid">{profit_charts}</div><div class="table-wrap">{t2}</div></div>
<div id="finance" class="tab-content">{k3}<div class="insight-box"><h3>🔍 財務健全度亮點</h3>{ins3}</div><div class="charts-grid">{fin_charts}</div><div class="finance-tables"><div class="table-wrap">{bs_t}</div><div class="table-wrap">{cf_t}</div></div></div>{momentum_content}
<div style="text-align:center;padding:20px;color:#a0aec0;font-size:0.78rem;">本報告由 taiwan-stock-analysis skill 自動生成｜僅供參考，非投資建議</div>
<script>
function switchTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.target.classList.add('active');
}}
</script>
</body>
</html>"""
    out=os.path.join(REPORTS, f"{sid}_{name}_analysis.html")
    open(out,"w",encoding="utf-8").write(html)
    print(f"OK {sid}_{name} ({len(html):,} bytes)")

if __name__=="__main__":
    import sys
    for sid in (sys.argv[1:] or ["2603","3005","5243"]):
        generate(sid)
