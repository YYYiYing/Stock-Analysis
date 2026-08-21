#!/usr/bin/env python3
"""
generate_index.py
掃描 reports/ 資料夾中的所有 *_analysis.html 檔案，自動生成 index.html
"""

import os
from pathlib import Path
from datetime import datetime

def get_stock_info(filename):
    """從檔名解析股票代碼和公司名稱"""
    # 檔名格式：{股票代碼}_{公司名}_analysis.html
    parts = filename.replace('_analysis.html', '').split('_', 1)
    if len(parts) == 2:
        stock_id, company_name = parts
        return stock_id, company_name
    return None, None

def generate_index_html(reports):
    """生成 index.html 內容"""
    report_rows = ""
    for stock_id, company_name, filename in reports:
        report_rows += f"""
        <tr>
            <td><a href="{filename}">{stock_id}</a></td>
            <td><a href="{filename}">{company_name}</a></td>
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
        body {{ 
            font-family: 'Microsoft JhengHei', 'Noto Sans TC', sans-serif; 
            background: #f0f4f8; 
            color: #2d3748;
            padding: 24px;
        }}
        .header {{
            background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 50%, #3182ce 100%);
            color: white; 
            padding: 32px; 
            border-radius: 12px; 
            margin-bottom: 24px;
        }}
        .header h1 {{ font-size: 1.8rem; margin-bottom: 8px; }}
        .header .subtitle {{ font-size: 0.9rem; opacity: 0.9; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .stats {{ 
            display: flex; 
            gap: 16px; 
            margin-bottom: 24px; 
        }}
        .stat-card {{
            flex: 1;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
            text-align: center;
        }}
        .stat-value {{ font-size: 2rem; font-weight: 700; color: #2b6cb0; }}
        .stat-label {{ font-size: 0.85rem; color: #718096; margin-top: 4px; }}
        table {{ 
            width: 100%; 
            background: white; 
            border-radius: 12px; 
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        }}
        th {{ 
            background: #2b6cb0; 
            color: white; 
            padding: 14px 20px; 
            text-align: left;
            font-weight: 600;
        }}
        td {{ 
            padding: 12px 20px; 
            border-bottom: 1px solid #e2e8f0;
        }}
        tr:hover td {{ background: #f7fafc; }}
        a {{ color: #3182ce; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .btn {{
            background: #3182ce;
            color: white;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.85rem;
        }}
        .btn:hover {{ background: #2b6cb0; text-decoration: none; }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #718096;
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>台股財務分析儀表板</h1>
            <div class="subtitle">自動生成的三維財務分析報告總覽｜最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(reports)}</div>
                <div class="stat-label">已分析個股</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>股票代碼</th>
                    <th>公司名稱</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>{report_rows}
            </tbody>
        </table>
        
        <div class="footer">
            資料來源：Goodinfo.tw｜分析期間：最近三年｜金額單位：億元 (NTD)
        </div>
    </div>
</body>
</html>"""

def main():
    reports_dir = Path('reports')
    if not reports_dir.exists():
        print("reports/ 資料夾不存在")
        return
    
    # 掃描所有 *_analysis.html 檔案
    reports = []
    for file in reports_dir.glob('*_analysis.html'):
        stock_id, company_name = get_stock_info(file.name)
        if stock_id and company_name:
            reports.append((stock_id, company_name, file.name))
    
    # 依照股票代碼排序
    reports.sort(key=lambda x: x[0])
    
    # 生成 index.html
    html_content = generate_index_html(reports)
    
    # 寫入檔案
    output_file = reports_dir / 'index.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"已生成 index.html，包含 {len(reports)} 個分析報告")

if __name__ == '__main__':
    main()