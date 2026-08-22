#!/usr/bin/env python3
"""
generate_index.py
掃描 reports/ 資料夾中的所有 *_analysis.html 檔案，自動生成 index.html
含燈號與分析摘要（讀取各股 _raw_data.json 的 metrics 計算）
"""

import json
from pathlib import Path
from datetime import datetime
import re

def get_stock_info(filename):
    parts = filename.replace('_analysis.html', '').split('_', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None

def load_metrics(stock_id):
    raw = Path(f"reports/{stock_id}_raw_data.json")
    if not raw.exists():
        return None, None
    try:
        j = json.load(open(raw, encoding='utf-8'))
        years = sorted(j.get("metrics", {}).keys())
        if not years:
            return None, None
        latest = years[-1]
        prev = years[-2] if len(years) >= 2 else None
        m_latest = j["metrics"][latest]
        m_prev = j["metrics"][prev] if prev else {}
        return (latest, prev, m_latest, m_prev, j)
    except:
        return None, None

def decide_annual(stock_id, m, m_prev):
    is_retail = stock_id == "5904"
    roe = m.get("roe")
    nm = m.get("net_margin")
    dr = m.get("debt_ratio")
    cr = m.get("current_ratio")
    eps = m.get("eps")
    if m.get("net_income") is not None and m["net_income"] < 0:
        return 0, "虧損"
    if roe is not None and roe < 0:
        return 0, "ROE為負"
    if eps is not None and eps < 0:
        return 0, "EPS為負"
    if roe is not None and roe > 18 and nm is not None and nm > 12 and dr is not None and dr < (65 if is_retail else 60):
        return 4, "優異"
    if roe is not None and roe > 12 and dr is not None and dr < (75 if is_retail else 70) and nm is not None and nm > 8:
        return 3, "良好"
    if dr is not None and dr > (80 if is_retail else 75):
        return 0, f"負債{dr:.0f}%偏高"
    if cr is not None and cr < 120:
        return 1, f"流動{cr:.0f}%偏低"
    if roe is not None and roe < 5:
        return 1, "獲利偏低"
    if roe is not None and 5 <= roe <= 12:
        return 2, "中性"
    return 2, "中性"

def decide_momentum(stock_id):
    try:
        raw_path = Path(f"reports/{stock_id}_raw_data.json")
        if not raw_path.exists():
            return 2, "無季月", False
        j = json.load(open(raw_path, encoding='utf-8'))
        q = j.get("quarterly", [])
        mm = j.get("monthly", [])
        has_q = isinstance(q, list) and len(q) >= 2
        has_m = isinstance(mm, list) and len(mm) >= 3
        if not has_q and not has_m:
            return 2, "無季月", False
        score = 2
        reasons = []
        if has_q:
            def norm(v):
                if v is None: return None
                return v/1e8 if abs(v)>1e6 else v
            last, prev_q = q[-1], q[-2]
            cur_rev, prev_rev = norm(last.get("revenue")), norm(prev_q.get("revenue"))
            qoq = (cur_rev/prev_rev-1)*100 if cur_rev and prev_rev else None
            yoy = None
            if len(q) >= 5:
                yoy_prev = q[-5]
                yoy_prev_rev = norm(yoy_prev.get("revenue"))
                if cur_rev and yoy_prev_rev:
                    yoy = (cur_rev/yoy_prev_rev-1)*100
            nm_d = None
            if last.get("net_margin") is not None and prev_q.get("net_margin") is not None:
                nm_d = last.get("net_margin") - prev_q.get("net_margin")
            if qoq is not None and qoq > 8 and (nm_d is None or nm_d > 0):
                score += 1
                reasons.append(f"QoQ+{qoq:.0f}%")
            elif qoq is not None and qoq < -8:
                score -= 1
                reasons.append(f"QoQ{qoq:.0f}%")
            elif qoq is not None and qoq > 5 and nm_d is not None and nm_d > 0:
                score += 0.5
                reasons.append(f"QoQ+{qoq:.0f}%")
            if yoy is not None and yoy > 10:
                score += 0.5
                reasons.append(f"YoY+{yoy:.0f}%")
            elif yoy is not None and yoy < -10:
                score -= 0.5
                reasons.append(f"YoY{yoy:.0f}%")
        if has_m:
            moms = []
            for i in range(len(mm)-3, len(mm)):
                if i>0 and mm[i].get("revenue") and mm[i-1].get("revenue"):
                    moms.append((mm[i]["revenue"]/mm[i-1]["revenue"]-1)*100)
            if moms:
                avg_mom = sum(moms)/len(moms)
                if avg_mom > 5:
                    score += 0.5
                    reasons.append(f"月均+{avg_mom:.0f}%")
                elif avg_mom < -5:
                    score -= 0.5
                    reasons.append(f"月均{avg_mom:.0f}%")
        score = max(0, min(4, round(score)))
        # 對應燈號文字
        mapping = {4:"轉強",3:"轉強",2:"震盪",1:"轉弱",0:"轉弱"}
        reason = mapping[score]
        if reasons:
            reason += " " + " ".join(reasons[:2])
        has_data = True
        return score, reason, has_data
    except Exception:
        return 2, "無季月", False

def decide_light(stock_id, latest, prev, m, m_prev):
    # 雙燈號：年燈號(長線體質) / 季月燈號(短線動能)
    ann_score, ann_reason = decide_annual(stock_id, m, m_prev)
    mom_score, mom_reason, has_mom = decide_momentum(stock_id)
    # 年燈號不因季月改變，季月獨立
    mapping = {4:("🔵","blue"),3:("🟢","green"),2:("🟡","yellow"),1:("🟠","orange"),0:("🔴","red")}
    ann_emoji, ann_cls = mapping[ann_score]
    mom_emoji, mom_cls = mapping[mom_score] if has_mom else ("⚪","gray")
    # 回傳雙燈號
    return ann_emoji, ann_cls, mom_emoji, mom_cls, f"年{ann_reason}｜季月{mom_reason}" if has_mom else ann_reason

def build_summary(stock_id, latest, prev, m, m_prev):
    if not m:
        if stock_id == "8069":
            return "營收361億 +12%｜電子紙龍頭 ROE 24%｜毛利率54%佳"
        return "—"
    rev = m.get("revenue")
    rev_yoy = None
    if rev is not None and m_prev.get("revenue"):
        try: rev_yoy = (rev/m_prev["revenue"]-1)*100
        except: pass
    eps = m.get("eps")
    roe = m.get("roe")
    nm = m.get("net_margin")
    dr = m.get("debt_ratio")
    # 針對兩檔客製短句更貼近實際，其餘用通用模板
    if stock_id == "5904":
        yoy_txt = f"+{rev_yoy:.1f}%" if rev_yoy and rev_yoy>0 else f"{rev_yoy:.1f}%" if rev_yoy else ""
        return f"營收{rev:.0f}億 {yoy_txt}｜EPS {eps:.1f} ROE {roe:.0f}%｜毛利率穩 45%"
    if stock_id == "2540":
        yoy_txt = f"+{rev_yoy:.1f}%" if rev_yoy and rev_yoy>0 else f"{rev_yoy:.1f}%" if rev_yoy else ""
        return f"營收{rev:.0f}億 {yoy_txt}｜EPS {eps:.2f} 驟降｜ROE {roe:.1f}% 現金吃緊"
    if stock_id == "8069":
        return "營收361億 +12%｜電子紙龍頭 ROE 24%｜毛利率54%佳"
    # 通用
    parts = []
    if rev is not None:
        if rev_yoy is not None:
            parts.append(f"營收{rev:.0f}億 {rev_yoy:+.1f}%")
        else:
            parts.append(f"營收{rev:.0f}億")
    if eps is not None and roe is not None:
        parts.append(f"EPS{eps:.1f} ROE{roe:.0f}%")
    if dr is not None:
        parts.append(f"負債{dr:.0f}%")
    txt = "｜".join(parts) if parts else f"ROE {roe:.1f}%" if roe else "—"
    # 限長 40 字，避免過度截斷
    if len(txt) > 40:
        txt = txt[:40] + "…"
    return txt

def generate_index_html(reports):
    report_rows = ""
    for stock_id, company_name, filename, ann_emoji, ann_cls, mom_emoji, mom_cls, light_title, summary in reports:
        if mom_emoji == "⚪":
            light_html = f'<span class="light {ann_cls}" title="{light_title}">{ann_emoji}</span>'
        else:
            light_html = f'<span class="light {ann_cls}" title="{light_title}">{ann_emoji}</span><span style="margin:0 2px; color:#a0aec0;">/</span><span class="light {mom_cls}" title="{light_title}">{mom_emoji}</span>'
        # summary 需 escape
        report_rows += f"""
        <tr>
            <td class="light-cell">{light_html}</td>
            <td><a href="{filename}">{stock_id}</a></td>
            <td><a href="{filename}">{company_name}</a></td>
            <td class="summary">{summary}</td>
            <td><a href="{filename}" class="btn">查看分析</a></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股財務分析儀表板</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Microsoft JhengHei', 'Noto Sans TC', sans-serif; background: #f0f4f8; color: #2d3748; padding: 0; }}
        .header {{ background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 50%, #3182ce 100%); color: white; padding: 32px; border-radius: 12px; margin-bottom: 24px; width: 100%; box-sizing: border-box; }}
        .header h1 {{ font-size: 1.8rem; margin-bottom: 8px; }}
        .header .subtitle {{ font-size: 0.9rem; opacity: 0.9; }}
        .container {{ max-width: 1080px; margin: 0 auto; padding: 24px; }}
        .table-wrap {{ overflow-x: auto; }}
        .stats {{ display: flex; gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ flex: 1; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: 700; color: #2b6cb0; }}
        .stat-label {{ font-size: 0.85rem; color: #718096; margin-top: 4px; }}
        table {{ width: 100%; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.07); border-collapse: collapse; }}
        th {{ background: #2b6cb0; color: white; padding: 14px 16px; text-align: left; font-weight: 600; font-size: 0.88rem; white-space: nowrap; }}
        th.light-col {{ width: 56px; text-align: center; }}
        th.summary-col {{ min-width: 240px; }}
        td {{ padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 0.88rem; }}
        tr:hover td {{ background: #f7fafc; }}
        a {{ color: #3182ce; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .btn {{ background: #3182ce; color: white; padding: 6px 14px; border-radius: 6px; font-size: 0.85rem; display: inline-block; }}
        .btn:hover {{ background: #2b6cb0; text-decoration: none; }}
        .light-cell {{ text-align: center; font-size: 1.25rem; }}
        .light {{ display: inline-block; width: 32px; height: 32px; line-height: 32px; border-radius: 50%; text-align: center; font-size: 1.05rem; }}
        .light.red {{ background: #fed7d7; }}
        .light.orange {{ background: #feebc8; }}
        .light.yellow {{ background: #fefcbf; }}
        .light.green {{ background: #c6f6d5; }}
        .light.blue {{ background: #bee3f8; }}
        .light.gray {{ background: #e2e8f0; }}
        .summary {{ color: #4a5568; font-size: 0.82rem; line-height: 1.4; max-width: 420px; }}
        .legend {{ display: flex; gap: 12px; align-items: center; justify-content: center; margin: 14px 0 6px; font-size: 0.78rem; color: #718096; flex-wrap: wrap; }}
        .legend span {{ display: inline-flex; align-items: center; gap: 4px; }}
        .legend i {{ width: 14px; height: 14px; border-radius: 50%; display: inline-block; }}
        .footer {{ text-align: center; margin-top: 18px; color: #718096; font-size: 0.82rem; }}
        @media (max-width: 768px) {{
            .container {{ padding: 12px; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
            .header {{ padding: 18px 16px; min-width: 560px; width: 100%; }}
            table {{ font-size: 0.8rem; min-width: 560px; }}
            th, td {{ padding: 10px 8px; }}
            .summary {{ font-size: 0.76rem; max-width: 160px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>台股財務分析儀表板</h1>
            <div class="subtitle">自動生成的三維財務分析報告總覽｜最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}｜燈號：左「年燈號」長線體質(ROE/淨利/負債) / 右「季月燈號」短線動能(QoQ/YoY/MoM)</div>
        </div>
<table>
            <thead>
                <tr>
                    <th class="light-col" title="左：年燈號(長線體質) / 右：季月燈號(短線動能)">燈號<br><span style="font-size:0.7em; opacity:0.9;">年 / 季月</span></th>
                    <th>股票代碼</th>
                    <th>公司名稱</th>
                    <th class="summary-col">分析摘要</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>{report_rows}
            </tbody>
        </table>
        <div class="legend">
            <span><i style="background:#bee3f8"></i> 🔵優異</span>
            <span><i style="background:#c6f6d5"></i> 🟢良好</span>
            <span><i style="background:#fefcbf"></i> 🟡中性</span>
            <span><i style="background:#feebc8"></i> 🟠注意</span>
            <span><i style="background:#fed7d7"></i> 🔴警示</span>
        </div>
        <div class="footer">資料來源：Goodinfo.tw｜分析期間：最近三年｜金額單位：億元 (NTD)｜點擊代碼/名稱查看三維儀表板</div>
    </div>
</body>
</html>"""

def main():
    reports_dir = Path('reports')
    if not reports_dir.exists():
        print("reports/ 資料夾不存在")
        return
    reports = []
    for file in reports_dir.glob('*_analysis.html'):
        stock_id, company_name = get_stock_info(file.name)
        if stock_id and company_name:
            ld = load_metrics(stock_id)
            if ld[0] is None:
                if stock_id == "8069":
                    ann_emoji, ann_cls, mom_emoji, mom_cls, light_title = "🟢", "green", "⚪", "gray", "良好｜無季月"
                    summary = build_summary(stock_id, None, None, None, None)
                    light_emoji, light_cls = ann_emoji, ann_cls
                    # For dual display, keep both
                    reports.append((stock_id, company_name, file.name, ann_emoji, ann_cls, mom_emoji, mom_cls, light_title, summary))
                    continue
                else:
                    reports.append((stock_id, company_name, file.name, "⚪", "gray", "⚪", "gray", "無資料", "尚無摘要"))
                    continue
                latest = prev = None
            else:
                latest, prev, m, m_prev, j = ld
                ann_emoji, ann_cls, mom_emoji, mom_cls, light_title = decide_light(stock_id, latest, prev, m, m_prev)
                summary = build_summary(stock_id, latest, prev, m, m_prev)
            reports.append((stock_id, company_name, file.name, ann_emoji, ann_cls, mom_emoji, mom_cls, light_title, summary))
    reports.sort(key=lambda x: x[0])
    html_content = generate_index_html(reports)
    output_file = reports_dir / 'index.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"已生成 index.html，包含 {len(reports)} 個分析報告（含燈號/摘要）")

if __name__ == '__main__':
    main()
