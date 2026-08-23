#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_summary_tab.py — 為 *_analysis.html 注入第5頁「白話總結」

設計原則：
- 純版面注入，不動任何數據 (revenue/metrics/charts/tables 皆不改)
- 冪等：若已存在 id="summary" 的 tab-content 與對應 tab 頭則覆寫而非重複
- 支援單檔與批次，summary 來自外部 md/txt 檔或 --text

Usage:
  python scripts/inject_summary_tab.py 2540 --summary-file reports/summaries/2540_summary.md
  python scripts/inject_summary_tab.py 2540 --text "白話總結內文..."
  python scripts/inject_summary_tab.py --all --summary-dir reports/summaries
  python scripts/inject_summary_tab.py 2540 --remove
"""
import argparse
import re
import os
from pathlib import Path

REPORTS = Path(__file__).parent.parent / "reports"

TAB_HEADER_HTML = '<div class="tab" onclick="switchTab(\'summary\')" data-tab="summary">💬 白話總結</div>'

def load_summary_text(args, sid):
    if args.text:
        return args.text
    if args.summary_file:
        p = Path(args.summary_file)
        if not p.exists():
            raise FileNotFoundError(f"summary_file not found: {p}")
        return p.read_text(encoding="utf-8")
    if args.summary_dir:
        candidates = [
            Path(args.summary_dir) / f"{sid}_summary.md",
            Path(args.summary_dir) / f"{sid}_summary.txt",
            Path(args.summary_dir) / f"{sid}.md",
        ]
        for c in candidates:
            if c.exists():
                return c.read_text(encoding="utf-8")
        raise FileNotFoundError(f"No summary file for {sid} in {args.summary_dir}")
    # try default location
    default = REPORTS / "summaries" / f"{sid}_summary.md"
    if default.exists():
        return default.read_text(encoding="utf-8")
    raise ValueError(f"需提供 --text 或 --summary-file 或 --summary-dir，或存在 {default}")

def md_to_html(md_text):
    """極簡 md→html：保留段落、▸ 列表、**粗體**、換行"""
    import html
    lines = md_text.strip().split("\n")
    html_parts = []
    in_ul = False
    for raw in lines:
        line = raw.strip()
        if not line:
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            continue
        # heading
        if line.startswith("### "):
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            html_parts.append(f"<h4 style='color:#2b6cb0;margin:16px 0 8px;font-size:0.92rem;'>{html.escape(line[4:].strip())}</h4>")
            continue
        if line.startswith("## "):
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            html_parts.append(f"<h3 style='color:#1a365d;margin:18px 0 10px;font-size:1rem;border-bottom:1px solid #e2e8f0;padding-bottom:6px;'>{html.escape(line[3:].strip())}</h3>")
            continue
        # list
        if line.startswith("- ") or line.startswith("▸ ") or line.startswith("* "):
            if not in_ul:
                html_parts.append("<ul style='list-style:none;padding:0;margin:0 0 12px;'>")
                in_ul = True
            content = line[2:].strip()
            content = html.escape(content)
            content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", content)
            html_parts.append(f"<li style='font-size:0.88rem;color:#4a5568;padding:4px 0 4px 18px;position:relative;'><span style='position:absolute;left:0;color:#3182ce;'>▸</span>{content}</li>")
            continue
        # numbered list 1. 
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            if not in_ul:
                html_parts.append("<ul style='list-style:none;padding:0;margin:0 0 12px;'>")
                in_ul = True
            content = html.escape(m.group(1))
            content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", content)
            html_parts.append(f"<li style='font-size:0.88rem;color:#4a5568;padding:4px 0 4px 18px;position:relative;'><span style='position:absolute;left:0;color:#3182ce;'>▸</span>{content}</li>")
            continue
        # paragraph
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        esc = html.escape(line)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        html_parts.append(f"<p style='font-size:0.88rem;color:#4a5568;line-height:1.7;margin:0 0 10px;'>{esc}</p>")
    if in_ul:
        html_parts.append("</ul>")
    return "\n".join(html_parts)

def build_summary_content(summary_html_inner):
    return f"""<div id="summary" class="tab-content">
<div class="insight-box" style="background:linear-gradient(135deg,#fffbeb,#fefcbf);border-color:#fbd38d;">
<h3>💬 白話總結 — 給非財務背景的一頁讀懂</h3>
<div style="font-size:0.82rem;color:#744210;margin-bottom:12px;">以下為 AI 閱讀本報告 4 頁（季月動能／經營／獲利／財務）後，以白話整合的解讀，數據皆來自 FinMind/MOPS，僅做翻譯不新增數據。</div>
</div>
{summary_html_inner}
<div style="text-align:center;padding:12px;color:#a0aec0;font-size:0.75rem;margin-top:8px;">本總結由 AI 依報告數據生成，僅為白話解讀，非投資建議 · 數據來源見頁首 MOPS/Goodinfo 連結</div>
</div>"""

def inject_one(html_path: Path, summary_text: str):
    html = html_path.read_text(encoding="utf-8")
    summary_inner = md_to_html(summary_text)
    summary_block = build_summary_content(summary_inner)

    # --- 1. 處理 tab 頭 ---
    # 移除舊的 summary tab 頭（冪等）
    html = re.sub(r'<div class="tab"[^>]*data-tab="summary"[^>]*>.*?</div>', '', html)
    # 也移除舊的 onclick summary（兼容舊版無 data-tab）
    html = re.sub(r'<div class="tab"[^>]*onclick="switchTab\(\'summary\'\)"[^>]*>.*?</div>', '', html)

    # 在財務健全度 tab 後插入新 tab 頭
    finance_tab_pattern = r"(<div class=\"tab\"[^>]*onclick=\"switchTab\('finance'\)\"[^>]*>.*?</div>)"
    if re.search(finance_tab_pattern, html):
        html = re.sub(finance_tab_pattern, r"\1" + TAB_HEADER_HTML, html, count=1)
    else:
        # fallback: 在 </div>\n<div id="momentum" 前的 tabs 區塊末尾插入
        html = html.replace("</div>\n<div id=\"momentum\"", TAB_HEADER_HTML + "\n<div id=\"momentum\"")
        # 另一 fallback: 直接在 <div class=\"tabs\"> 內末尾
        if TAB_HEADER_HTML not in html:
            html = html.replace('<div class="tabs">', '<div class="tabs">' + TAB_HEADER_HTML, 1)

    # --- 2. 處理 tab 內容 ---
    # 移除舊的 summary tab-content
    html = re.sub(r'<div id="summary" class="tab-content">.*?</div>\s*(?=<div style="text-align:center)', '', html, flags=re.DOTALL)
    # 更寬鬆的移除（若 footer 樣式不同）
    if '<div id="summary"' in html:
        html = re.sub(r'<div id="summary" class="tab-content">.*?</div>\s*(?=<script>)', '', html, flags=re.DOTALL)
        # 最終暴力移除殘留
        if '<div id="summary"' in html:
            # 找 id=summary 到下一個 <div style="text-align:center;padding:20px 或 <script>
            html = re.sub(r'<div id="summary".*?</div>\s*<div style="text-align:center', '<div style="text-align:center', html, flags=re.DOTALL)

    # 在 finance tab-content 後插入 summary
    finance_block_pattern = r'(<div id="finance" class="tab-content">.*?</div>)\s*(<div style="text-align:center)'
    m = re.search(finance_block_pattern, html, flags=re.DOTALL)
    if m:
        html = html.replace(m.group(0), m.group(1) + "\n" + summary_block + "\n" + m.group(2), 1)
    else:
        # fallback: 在 </div>\n<div style="text-align:center;padding:20px 之前插入
        html = html.replace('<div style="text-align:center;padding:20px', summary_block + '\n<div style="text-align:center;padding:20px', 1)

    html_path.write_text(html, encoding="utf-8")
    print(f"OK injected summary tab -> {html_path.name} ({len(html):,} bytes)")
    return html_path

def remove_one(html_path: Path):
    html = html_path.read_text(encoding="utf-8")
    orig_len = len(html)
    html = re.sub(r'<div class="tab"[^>]*data-tab="summary"[^>]*>.*?</div>', '', html)
    html = re.sub(r'<div class="tab"[^>]*onclick="switchTab\(\'summary\'\)"[^>]*>.*?</div>', '', html)
    html = re.sub(r'<div id="summary" class="tab-content">.*?</div>\s*(?=<div style="text-align:center)', '', html, flags=re.DOTALL)
    if '<div id="summary"' in html:
        html = re.sub(r'<div id="summary".*?</div>\s*(?=<script>)', '', html, flags=re.DOTALL)
    html_path.write_text(html, encoding="utf-8")
    print(f"OK removed summary tab -> {html_path.name} ({orig_len:,} -> {len(html):,} bytes)")

def resolve_reports(sids):
    if sids:
        paths = []
        for sid in sids:
            matches = list(REPORTS.glob(f"{sid}_*_analysis.html"))
            if not matches:
                print(f"WARN no report for {sid}")
                continue
            paths.extend(matches)
        return paths
    return list(REPORTS.glob("*_analysis.html"))

def main():
    ap = argparse.ArgumentParser(description="注入第5頁白話總結")
    ap.add_argument("sids", nargs="*", help="stock ids e.g. 2540")
    ap.add_argument("--all", action="store_true", help="批次處理全部 reports")
    ap.add_argument("--summary-file", type=str, help="白話稿檔案路徑 (md/txt)")
    ap.add_argument("--summary-dir", type=str, help="白話稿目錄，內含 {sid}_summary.md")
    ap.add_argument("--text", type=str, help="直接傳入白話稿文字")
    ap.add_argument("--remove", action="store_true", help="移除第5頁")
    args = ap.parse_args()

    if args.remove:
        targets = resolve_reports(args.sids) if args.sids else list(REPORTS.glob("*_analysis.html"))
        for p in targets:
            if '<div id="summary"' in p.read_text(encoding="utf-8"):
                remove_one(p)
            else:
                print(f"SKIP {p.name} 無第5頁")
        return

    if args.all:
        sids = None
        # --all 時若有提供 summary-dir/text/summary-file 則批量用同樣邏輯，否則逐檔找預設 summaries/{sid}_summary.md
        if args.text or args.summary_file:
            # 單一稿套用到全部（少用）
            paths = resolve_reports(None)
            for p in paths:
                sid = p.name.split("_")[0]
                txt = args.text or Path(args.summary_file).read_text(encoding="utf-8")
                inject_one(p, txt)
            return
        # 逐檔找對應稿
        paths = resolve_reports(None)
        for p in paths:
            sid = p.name.split("_")[0]
            try:
                txt = load_summary_text(args, sid)
            except Exception as e:
                print(f"SKIP {p.name}: {e}")
                continue
            inject_one(p, txt)
        return

    if not args.sids:
        ap.print_help()
        return

    for sid in args.sids:
        paths = list(REPORTS.glob(f"{sid}_*_analysis.html"))
        if not paths:
            print(f"WARN no report for {sid}")
            continue
        try:
            txt = load_summary_text(args, sid)
        except Exception as e:
            print(f"ERROR {sid}: {e}")
            continue
        for p in paths:
            inject_one(p, txt)

if __name__ == "__main__":
    main()
