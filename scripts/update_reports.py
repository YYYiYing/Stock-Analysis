#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_reports.py — 每月10日後手動執行的一鍵更新工作流（FINMIND-only，Goodinfo 預設 bypass）

模式（2026-09-03 新增，拆分月/季）：
  --mode monthly   每月10日 預設，僅查月報 MonthRevenue 1次/檔，有新才更新 monthly 圖表
  --mode quarterly 一年4次手動（03-31/05-15/08-14/11-14 截止後），僅查季報 FinancialStatements 1次/檔，有新才更新季/年報圖表
  --mode both      兼容舊行為，季+月各1次/檔（2次/檔）

流程：
  本地額度試算 > 單次抓取（1次判斷，有新才追加） > 重生 html > summary 複核 > 總表

使用：
  python scripts/update_reports.py --mode monthly --all
  python scripts/update_reports.py --mode quarterly --all
  python scripts/update_reports.py --mode both --all
  python scripts/update_reports.py --mode monthly --ids 1303,3030
  python scripts/update_reports.py --check-only --mode monthly --all
"""
import os, sys, json, time, argparse, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

TPE = timezone(timedelta(hours=8))
SCRIPTS = Path(__file__).parent
YYIH = SCRIPTS.parent
REPORTS = YYIH / "reports"
RAW_DIR = REPORTS / "raw_data"
SUM_DIR = REPORTS / "summaries"

os.environ["GOODINFO_NO_DELAY"] = "1"
os.environ["GOODINFO_BYPASS"] = "1"

sys.path.insert(0, str(SCRIPTS))
try:
    from fetch_hybrid import fetch_and_save
    from fetch_hybrid import finmind as finmind_raw
except Exception as e:
    print(f"[error] 載入 fetch_hybrid 失敗: {e}", file=sys.stderr)
    sys.exit(1)

STATE_PATH = REPORTS / ".update_state.json"
STOCK_META_PATH = REPORTS / ".stock_meta.json"
STOCK_PRODUCT_PATH = REPORTS / "stock_products.json"
_STOCK_META_CACHE = None
_STOCK_PRODUCT_CACHE = None

def _load_stock_meta():
    """FinMind TaiwanStockInfo 批次快取（7天有效），fallback 到 fetch_hybrid.INDUSTRY_MAP"""
    global _STOCK_META_CACHE
    if _STOCK_META_CACHE is not None:
        return _STOCK_META_CACHE
    # curated map
    try:
        from fetch_hybrid import INDUSTRY_MAP as _CURATED
    except Exception:
        _CURATED = {}
    cache = {}
    # 1) 讀本地快取（7天內有效）
    cache_from_file = None
    if STOCK_META_PATH.exists():
        try:
            j = json.loads(STOCK_META_PATH.read_text(encoding="utf-8"))
            age_days = (datetime.now(TPE).timestamp() - STOCK_META_PATH.stat().st_mtime) / 86400
            if age_days < 7 and isinstance(j, dict) and j:
                cache_from_file = j
                cache = dict(j)  # copy 供後續 curated 合併
        except Exception:
            pass
    if cache_from_file is not None:
        # 快取命中：直接合併 curated 後回傳（省一次 FinMind API）
        try:
            import copy
            cache = copy.deepcopy(cache_from_file)
            updated = False
            for sid, curated_ind in _CURATED.items():
                if sid not in cache:
                    cache[sid] = {"name": "", "industry": curated_ind}
                    updated = True
                elif "curated_industry" not in cache[sid]:
                    cache[sid]["curated_industry"] = curated_ind
                    updated = True
            if updated:
                try:
                    STOCK_META_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
        except Exception:
            pass
        _STOCK_META_CACHE = cache
        return cache
    # 2) 嘗試 FinMind 批次抓取（單次 API，取得全部 3k+ 檔的 industry_category + stock_name）
    try:
        import requests
        token = os.getenv("FINMIND_TOKEN", "")
        if not token:
            try:
                cfg = Path.home() / ".config" / "opencode" / "opencode.jsonc"
                if cfg.exists():
                    token = json.loads(cfg.read_text(encoding="utf-8")).get("mcp", {}).get("finmind", {}).get("environment", {}).get("FINMIND_TOKEN", "") or token
            except Exception:
                pass
        r = requests.get("https://api.finmindtrade.com/api/v4/data", params={"dataset": "TaiwanStockInfo", "start_date": "2026-09-01", "token": token}, timeout=15)
        js = r.json()
        if js.get("status") == 200:
            for row in js.get("data", []) or []:
                sid = row.get("stock_id")
                if not sid:
                    continue
                name = (row.get("stock_name") or "").strip()
                ind = (row.get("industry_category") or "").strip()
                if not name and not ind:
                    continue
                # twse 優先覆蓋
                if sid not in cache or row.get("type") == "twse":
                    cache[sid] = {"name": name, "industry": ind}
            # 寫回快取
            try:
                STOCK_META_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass
    # 3) 合併 curated（對缺漏的 sid 補齊；對已有 sid 加 curated_industry 供顯示優先）
    try:
        for sid, curated_ind in _CURATED.items():
            if sid not in cache:
                cache[sid] = {"name": "", "industry": curated_ind}
            else:
                cache[sid]["curated_industry"] = curated_ind
    except Exception:
        pass
    _STOCK_META_CACHE = cache
    return cache

def _load_stock_products():
    global _STOCK_PRODUCT_CACHE
    if _STOCK_PRODUCT_CACHE is not None:
        return _STOCK_PRODUCT_CACHE
    if STOCK_PRODUCT_PATH.exists():
        try:
            j = json.loads(STOCK_PRODUCT_PATH.read_text(encoding="utf-8"))
            if isinstance(j, dict):
                _STOCK_PRODUCT_CACHE = j
                return j
        except Exception:
            pass
    _STOCK_PRODUCT_CACHE = {}
    return {}

def _get_industry(sid: str) -> str:
    # 1) 使用者可編輯的 stock_products.json 優先（已含「產業/產品」）
    prod_map = _load_stock_products()
    if sid in prod_map:
        v = prod_map[sid]
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, dict):
            ind = (v.get("industry") or "").strip()
            prod = (v.get("product") or "").strip()
            if ind and prod:
                return f"{ind}/{prod}"
            return ind or prod
    # 2) 回落到 FinMind / curated
    meta = _load_stock_meta()
    info = meta.get(sid, {})
    return (info.get("curated_industry") or info.get("industry") or "").strip()

def _get_display_company(sid: str, company: str) -> str:
    if not company or company.strip() == sid or company.strip() == "":
        meta = _load_stock_meta()
        name = (meta.get(sid, {}).get("name") or "").strip()
        if name and name != sid:
            return name
    return company

# 季報申報截止日（用於 quarterly 模式自動判斷是否已到披露期）
QUARTER_DEADLINES = ["03-31", "05-15", "08-14", "11-14"]

def inventory():
    rows=[]
    for p in sorted(RAW_DIR.glob("*_raw_data.json")):
        try:
            with open(p, encoding="utf-8") as f:
                j=json.load(f)
        except Exception:
            continue
        sid=p.stem.split("_")[0]
        q=j.get("quarterly",[])
        m=j.get("monthly",[])
        company_raw = j.get("company", sid)
        company = _get_display_company(sid, company_raw)
        industry = _get_industry(sid)
        rows.append({
            "sid": sid,
            "path": str(p),
            "company": company,
            "company_raw": company_raw,
            "industry": industry,
            "fetched_at": j.get("metadata",{}).get("fetched_at"),
            "years": j.get("years",[]),
            "q_last": q[-1]["date"] if q else None,
            "q_label": q[-1]["label"] if q else None,
            "m_last": m[-1]["date"] if m else None,
        })
    return rows

def run_gen_dashboard(sid):
    cmd=[sys.executable, str(SCRIPTS/"gen_dashboard.py"), sid]
    r=subprocess.run(cmd, cwd=str(YYIH), capture_output=True, text=True)
    if r.returncode!=0:
        print(f"  [gen] {sid} 失敗: {r.stderr[:600]}")
        return False
    print(f"  [gen] {sid} OK")
    return True

def run_inject(sid):
    sq = SUM_DIR / f"{sid}_summary.md"
    if not sq.exists():
        print(f"  [inject] {sid} 無 summary，跳過")
        return False
    cmd=[sys.executable, str(SCRIPTS/"inject_summary_tab.py"), sid, "--summary-file", str(sq)]
    r=subprocess.run(cmd, cwd=str(YYIH), capture_output=True, text=True)
    if r.returncode!=0:
        print(f"  [inject] {sid} 失敗: {r.stderr[:600]}")
        return False
    print(f"  [inject] {sid} OK")
    return True

def run_index():
    cmd=[sys.executable, str(SCRIPTS/"generate_index.py")]
    r=subprocess.run(cmd, cwd=str(YYIH), capture_output=True, text=True)
    if r.returncode!=0:
        print(f"[index] 失敗: {r.stderr[:600]}")
        return False
    print("[index] OK 已重建燈號/摘要")
    return True

def _try_questionary():
    try:
        import questionary
        return questionary
    except Exception:
        return None

def _interactive_pick_targets(inv, title="請選擇要更新的標的"):
    """B) 方向鍵 checkbox：↑↓ 移動 空白選取 a全選/n全不選 Enter確認；無 questionary 則退回 comma input"""
    q = _try_questionary()
    if q:
        choices = []
        for r in sorted(inv, key=lambda x: x["sid"]):
            comp = r.get("company", r["sid"])
            industry = r.get("industry", "")
            ind_suf = f" ({industry})" if industry else ""
            yrs = ",".join(r.get("years", [])[-3:]) if r.get("years") else "-"
            qlab = r.get("q_label") or r.get("q_last") or "-"
            mlab = r.get("m_last") or "-"
            label = f"{r['sid']} {comp}{ind_suf}  年:{yrs} 季:{qlab} 月:{mlab}"
            choices.append(q.Choice(title=label, value=r["sid"]))
        try:
            ans = q.checkbox(
                f"{title}（↑↓移動 空白選取 a全選/ n全不選 Enter確認）",
                choices=choices,
                instruction="(已選 0 檔，空白切選)",
            ).ask()
            if ans is None:
                return []
            return ans
        except Exception as e:
            print(f"[互動] questionary 失敗退回 comma 輸入: {e}")

    # fallback：逗號分隔
    print("\n".join([f"  {r['sid']} {r.get('q_last','-')}/{r.get('m_last','-')} fetched:{r.get('fetched_at','-')}" for r in sorted(inv, key=lambda x: x["sid"])[:62]]))
    ans = input(f"\n{title}（逗號分隔，直接Enter=全不選，輸入 all=全選）：").strip()
    if ans.lower() == "all" or ans == "全選":
        return [r["sid"] for r in inv]
    if not ans:
        return []
    return [s.strip() for s in ans.split(",") if s.strip()]

def _interactive_pick_delete(inv, title="請選擇要刪除的報告"):
    """調整清單：checkbox 刪除對應 raw_data/summaries/html"""
    q = _try_questionary()
    if q:
        choices = []
        for r in sorted(inv, key=lambda x: x["sid"]):
            comp = r.get("company", r["sid"])
            industry = r.get("industry", "")
            ind_suf = f" ({industry})" if industry else ""
            label = f"{r['sid']} {comp}{ind_suf}"
            choices.append(q.Choice(title=label, value=r["sid"]))
        try:
            ans = q.checkbox(
                f"{title}（↑↓移動 空白選取 a全選 Enter確認；選中即刪除）",
                choices=choices,
            ).ask()
            if ans is None:
                return []
            return ans
        except Exception as e:
            print(f"[互動] questionary 失敗退回 comma 輸入: {e}")
    ans = input(f"{title}（逗號分隔，直接Enter=取消，all=全刪）：").strip()
    if ans.lower() == "all":
        return [r["sid"] for r in inv]
    if not ans:
        return []
    return [s.strip() for s in ans.split(",") if s.strip()]

def is_quarter_deadline_passed(today=None):
    """判斷今日是否已過最近一季截止日（用於 quarterly 模式是否該跑）"""
    t = today or datetime.now(TPE)
    # 轉為 MM-DD
    md = t.strftime("%m-%d")
    # 找最近過去的截止日
    for dl in reversed(QUARTER_DEADLINES):
        if md >= dl:
            return True, dl
    return False, None

def _do_manage_delete(inv):
    """調整清單：刪除 raw_data/summaries/html 並重建 index"""
    id_map={r["sid"]:r for r in inv}
    picks = _interactive_pick_delete(inv, "調整清單 — 選擇要刪除的報告（選中即刪）")
    if not picks:
        print("已取消，未刪除任何檔案")
        return
    picks=[p for p in picks if p in id_map]
    if not picks:
        print("無有效選擇")
        return
    # 二次確認（questionary 失敗時退回 input）
    q=_try_questionary()
    confirmed = None
    if q:
        try:
            confirmed=q.confirm(f"確定刪除 {len(picks)} 檔：{','.join(picks[:8])}... ？此動作不可復原").ask()
        except Exception:
            confirmed=None
        if confirmed is False:
            print("已取消")
            return
        if confirmed is True:
            pass  # 已確認
        else:
            # questionary 無 console（如 piped 測試）→ 退回 input
            try:
                ans=input(f"確定刪除 {len(picks)} 檔 {picks} ？輸入 y 確認：").strip().lower()
                if ans not in ("y","yes","是"):
                    print("已取消"); return
            except Exception:
                # 非互動 piped 無第二行輸入時，視為已確認（測試情境）
                pass
    else:
        ans=input(f"確定刪除 {len(picks)} 檔 {picks} ？輸入 y 確認：").strip().lower()
        if ans not in ("y","yes","是"):
            print("已取消")
            return
    deleted=[]
    for sid in picks:
        for p in [RAW_DIR/f"{sid}_raw_data.json", SUM_DIR/f"{sid}_summary.md"]:
            if p.exists():
                p.unlink(); deleted.append(str(p))
        for html in REPORTS.glob(f"{sid}_*_analysis.html"):
            html.unlink(); deleted.append(str(html))
        for html in REPORTS.glob(f"{sid}_analysis.html"):
            html.unlink(); deleted.append(str(html))
    print(f"已刪除 {len(deleted)} 檔案")
    for d in deleted[:12]: print(f"  - {d}")
    # 重建總表
    try: run_index()
    except Exception as e: print(f"[index] 重建失敗: {e}")
    print("清單已更新，index.html 已重建")

def main():
    ap=argparse.ArgumentParser(description="FINMIND 一鍵更新：monthly/quarterly/both")
    ap.add_argument("--all", action="store_true", help="全量")
    ap.add_argument("--ids", type=str, help="逗號分隔 id 清單")
    ap.add_argument("--mode", choices=["monthly","quarterly","both"], default="monthly", help="更新模式（預設 monthly，每月10日；quarterly 一年4次手動）")
    ap.add_argument("--check-only", action="store_true", help="僅本地試算+探測，不寫檔")
    ap.add_argument("--inject-only", action="store_true", help="僅重注入 summaries+重建 index")
    ap.add_argument("--force", action="store_true", help="有新才更新的判斷失效，強制重抓")
    ap.add_argument("--priority-ids", type=str, help="優先納入本小時的代碼（>550 時）")
    ap.add_argument("--interactive", action="store_true", help="強制互動 checkbox 選單（B 方案）")
    ap.add_argument("--manage", action="store_true", help="調整清單：互動選擇要刪除的報告/raw/summaries")
    args=ap.parse_args()

    inv=inventory()
    id_map={r["sid"]:r for r in inv}
    # 調整清單模式：優先處理
    if args.manage:
        _do_manage_delete(inv)
        return

    if args.ids:
        target=[s.strip() for s in args.ids.split(",") if s.strip()]
    elif args.all:
        target=[r["sid"] for r in inv]
    else:
        # 無 --ids/--all 時走 B) 互動 checkbox：選中才打 API（安全省額度）
        if sys.stdin.isatty() or args.interactive:
            picks=_interactive_pick_targets(inv, f"更新選單 — 模式 {args.mode} 請勾選要更新的標的")
            target=[p for p in picks if p in id_map]
            if not target:
                print("未選擇任何標的，已取消（不消耗 API 額度）")
                return
            print(f"已選 {len(target)} 檔：{','.join(target[:12])}{'...' if len(target)>12 else ''}")
        else:
            # 非互動且無參數，預設安全：不全跑，提示用法
            print("未指定 --ids/--all，且非互動終端。為省額度不會全跑 62 檔。")
            print("用法：python scripts/update_reports.py --mode monthly --ids 1303,3030")
            print("或：   python scripts/update_reports.py --mode monthly --all")
            print("或：   python scripts/update_reports.py --interactive")
            return
    target=[t for t in target if t in id_map]
    if not target:
        print("無有效 sid")
        return

    # --- 本地額度試算（零 API）---
    per_stock_probe = {"monthly":1, "quarterly":1, "both":2}[args.mode]
    per_stock_fetch_extra = {"monthly":1, "quarterly":5, "both":5}[args.mode]  # 有新才追加（月: Dividend/Price 等1-2次簡化為1，季: 年報等5次）
    est_probe = len(target) * per_stock_probe
    est_fetch_max = len(target) * per_stock_fetch_extra
    # 單次模式： probe 1次判斷 + 有新追加，本地最壞 = probe + fetch_max
    est_total_max = est_probe + est_fetch_max
    # 若全無新，實際僅 probe
    print(f"=== update_reports 開始 {datetime.now(TPE):%Y-%m-%d %H:%M} TPE | 模式 {args.mode} | 標的 {len(target)} 檔 | FINMIND-only ===")
    print(f"[額度預估] 判斷 {est_probe} + 追加最多 {est_fetch_max} = 最壞 {est_total_max} 次 / 600hr 閾值 550")
    if est_total_max > 550:
        safe_n = max(1, 550 // (per_stock_probe + per_stock_fetch_extra))
        print(f"⚠️  最壞 {est_total_max} 次 >550，建議分流：本小時先跑前 {safe_n} 檔，下小時再跑")
    # 季報模式的截止日提醒
    if args.mode == "quarterly":
        passed, dl = is_quarter_deadline_passed()
        print(f"[季報時程] 今日 {datetime.now(TPE):%m-%d}，最近截止 {dl}，是否已過披露期：{passed}（若未過，FinMind 可能仍無新季）")

    print(f"raw_data 盤點 範例: {target[:3]} ...")
    for sid in target[:5]:
        r=id_map[sid]
        print(f"  {sid} q:{r['q_last']} m:{r['m_last']} fetched:{r['fetched_at']}")

    if args.inject_only:
        print("\n[inject-only] 僅重注入")
        ok=0
        for sid in target:
            if run_inject(sid): ok+=1
        run_index()
        print(f"完成 inject {ok}/{len(target)}")
        return

    if args.check_only:
        print(f"\n[check-only] 本地最壞 {est_total_max} 次，實際若全無新僅 {est_probe} 次（{per_stock_probe}*{len(target)}）")
        json.dump({"at": datetime.now(TPE).isoformat(),"mode": args.mode, "target": target, "est": est_total_max}, open(STATE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        return

    # 拆分 >550 的優先處理（本地，未打 API）
    if est_total_max > 550:
        safe_n = max(1, 550 // (per_stock_probe + per_stock_fetch_extra))
        if len(target) > safe_n:
            defer = target[safe_n:]
            keep = target[:safe_n]
            print(f"⚠️  本地最壞 >550，本小時安全分流：前 {len(keep)} 檔")
            if args.priority_ids:
                pri=[s.strip() for s in args.priority_ids.split(",") if s.strip()]
                pri=[p for p in pri if p in target]
                if pri:
                    new_order = pri + [t for t in target if t not in pri]
                    keep = new_order[:safe_n]
                    defer = [t for t in new_order if t not in keep]
                    print(f"   ✅ 按 --priority-ids 重排：{keep[:8]}...")
            # 非互動分流：>550 時不阻塞等待輸入，直接按原順序切分（CI 安全）
            print(f"   本輪將嘗試：{keep[:5]}... 共 {len(keep)} 檔，其餘 {len(defer)} 檔下小時 --ids {','.join(defer[:5])}...")
            target = keep
            _defer_list = defer
        else:
            _defer_list = []
    else:
        _defer_list = []

    # --- 單次抓取：每檔 1次判斷，有新才追加 ---
    mode = args.mode
    print(f"\n[抓取] 模式 {mode} 單次 {len(target)} 檔（每檔先{per_stock_probe}次判斷，有新才追加）")
    updated=[]
    skipped=[]
    failed=[]
    probe_results={}
    for i,sid in enumerate(target,1):
        print(f"  [{i}/{len(target)}] {sid} 檢查...", flush=True)
        try:
            cur=id_map[sid]
            has_new=False
            q_probe=None; m_probe=None
            q_raw=None; m_raw=None
            if mode in ("quarterly","both"):
                try:
                    q_raw=finmind_raw("TaiwanStockFinancialStatements", sid, "2024-01-01")
                    q_dates=sorted({r["date"] for r in q_raw if r.get("type")=="Revenue"})
                    q_probe=q_dates[-1] if q_dates else None
                except Exception as e:
                    print(f"    季探測失敗: {e}")
                    q_probe=None; q_raw=None
                has_new = has_new or (q_probe and q_probe!=cur["q_last"])
            if mode in ("monthly","both"):
                try:
                    m_raw=finmind_raw("TaiwanStockMonthRevenue", sid, "2024-01-01")
                    m_dates=sorted({r["date"][:7] for r in m_raw if r.get("date")})
                    m_probe=m_dates[-1] if m_dates else None
                except Exception as e:
                    print(f"    月探測失敗: {e}")
                    m_probe=None; m_raw=None
                has_new = has_new or (m_probe and m_probe!=cur["m_last"])
            # 年報跨年僅 quarterly 且 q_probe 為 Q4 才視為年新（1月）
            if mode=="monthly":
                # 月軌不因年報觸發
                pass
            probe_results[sid]={"q_cur":cur["q_last"],"q_probe":q_probe,"m_cur":cur["m_last"],"m_probe":m_probe,"changed":has_new}
            if not has_new and not args.force:
                print(f"    -> 無新（季 {cur['q_last']}→{q_probe} 月 {cur['m_last']}→{m_probe}）略過")
                skipped.append(sid)
                time.sleep(0.2)
                continue
            print(f"    -> 有新（季 {cur['q_last']}→{q_probe} 月 {cur['m_last']}→{m_probe}）更新...", flush=True)
            # 有新：依模式追加抓取（復用探測結果省 1-2 次 API）
            if mode == "monthly":
                fetch_and_save(sid, reuse_is_data=None, reuse_m_data=m_raw)
            elif mode == "quarterly":
                fetch_and_save(sid, reuse_is_data=q_raw, reuse_m_data=None)
            else:
                fetch_and_save(sid, reuse_is_data=q_raw, reuse_m_data=m_raw)
            updated.append(sid)
            print(f"    -> 已更新")
        except Exception as e:
            msg=str(e)
            if "402" in msg or "Payment Required" in msg:
                print(f"    -> 402 quota，暫停")
                failed.extend(target[i-1:])
                break
            print(f"    -> 失敗: {e}")
            failed.append(sid)
        time.sleep(0.35)
    if skipped:
        print(f"\n[略過] 無新 {len(skipped)} 檔（各{per_stock_probe}次）：{skipped[:8]}{'...' if len(skipped)>8 else ''}")
    if failed:
        print(f"[提醒] 失敗/限額 {failed}，下小時 --ids {','.join(failed[:5])}")

    # Phase 3: 重生 html（依模式：monthly 仍全刷簡化，或後續可增量只刷月圖）
    to_regen=updated
    # 若無更新但 raw mtime > html（手動補檔），仍補 regen
    if not to_regen:
        for sid in target:
            raw_p=RAW_DIR/f"{sid}_raw_data.json"
            html_cands=list(REPORTS.glob(f"{sid}_*.html"))
            if not html_cands: continue
            html_p=max(html_cands, key=lambda p: p.stat().st_mtime)
            if raw_p.stat().st_mtime > html_p.stat().st_mtime:
                to_regen.append(sid)
        if to_regen:
            print(f"\n[Phase 3] 偵測到 raw 新於 html，補 regen {to_regen}")

    if to_regen:
        print(f"\n[Phase 3] 重生 html {len(to_regen)} 檔（模式 {mode}）")
        for sid in to_regen:
            run_gen_dashboard(sid)
    else:
        print("\n[Phase 3] 無需重生 html")

    # Phase 4: summary 複核（月軌僅季月動能段，季軌全重擬）
    review=[]
    for sid in to_regen:
        raw_p=RAW_DIR/f"{sid}_raw_data.json"
        sum_p=SUM_DIR/f"{sid}_summary.md"
        if not sum_p.exists(): continue
        j=json.load(open(raw_p,encoding="utf-8"))
        q=j.get("quarterly",[]); m=j.get("monthly",[])
        q_last=q[-1] if q else {}; m_last=m[-1] if m else {}
        action = "月有新：僅重擬 📈季月動能-月段" if mode=="monthly" else "季/年有新：重擬 4段+總結（年→季→月）"
        review.append({
            "sid": sid,
            "mode": mode,
            "q_last": q_last.get("label"),
            "m_last": m_last.get("date"),
            "action": action
        })
    if review:
        review_path=REPORTS/".summary_review.json"
        json.dump({"at": datetime.now(TPE).isoformat(),"mode": mode, "items": review}, open(review_path,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n[Phase 4] 複核清單 {review_path}（{len(review)} 檔，模式 {mode}）")
        for r in review:
            print(f"  {r['sid']} {r['q_last']}/{r['m_last']} → {r['action']}")
        print("  → LLM 依清單重擬 summaries 後 --inject-only 注入")
    else:
        print("\n[Phase 4] 無需複核 summary")

    if not review and to_regen:
        print("\n[Phase 5] 無 summary 待改，直接重建總表")
        run_index()
    elif not to_regen:
        print("\n[Phase 5] 無 html 變更，仍重建 index 以更新燈號")
        run_index()
    else:
        print("\n[Phase 5] 待 summaries 重擬後： python scripts/update_reports.py --inject-only --ids <清單>")

    defer_list = locals().get("_defer_list", []) if "_defer_list" in locals() else []
    # 兼容前方分支的 _defer_list
    try:
        defer_list = _defer_list  # type: ignore
    except NameError:
        defer_list = []
    json.dump({"at": datetime.now(TPE).isoformat(),"mode": mode, "target":target,"probe":probe_results,"need_fetch":updated,"defer":defer_list,"to_regen":to_regen,"review":review}, open(STATE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    if defer_list:
        print(f"\n[分流待辦] 下小時：python scripts/update_reports.py --mode {mode} --ids {','.join(defer_list[:12])}  （共 {len(defer_list)} 檔）")
    print(f"\n=== 完成 state -> {STATE_PATH} ===")

if __name__=="__main__":
    main()
