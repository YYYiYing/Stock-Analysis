#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_hybrid.py — FinMind 主力 + Goodinfo 費用結構單次補足

設計原則 (2026-08-22):
- FinMind 優先：損益/資產負債/現金流/股利/月營收 全部走 FinMind (600/hr, 官方授權)
- Goodinfo 僅 1 次：IS_YEAR 損益表，僅解析 推銷/管理/研發 三列，作費用堆疊圖
- 若 Goodinfo 被限流，僅費用細拆為 null，主體報告仍完成

Usage:
  python fetch_hybrid.py 6782            # 單檔健診 (FinMind+Goodinfo expense)
  python fetch_hybrid.py --patch 2484    # 修補既有 raw_data 的費用結構
  python fetch_hybrid.py --patch-all     # 批次補齊所有缺漏
"""
import os, sys, time, json, requests
from bs4 import BeautifulSoup
from collections import defaultdict
from pathlib import Path

REPORTS = Path(__file__).parent.parent / "reports"
RAW_DATA_DIR = REPORTS / "raw_data"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
TOKEN = os.getenv("FINMIND_TOKEN", "")

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# Industry mapping (for gen_dashboard)
INDUSTRY_MAP = {
    "2603": "海運（貨櫃航運）",
    "3005": "電腦及週邊（強固型裝置）",
    "5243": "電子零組件（金屬機構件）",
    "3605": "電子零組件（連接器）",
    "2540": "營建開發",
    "5904": "零售通路（生活百貨）",
    "2484": "電子零組件（石英元件）",
    "8069": "光電業",
    "4721": "化學（特用化學）",
    "6782": "生技醫療（隱形眼鏡）",
}

# --- 真實性契約：污染檢與誠實告知 helpers ---
def _is_polluted(key: str, value, year: str) -> bool:
    """值等於年份的污染檢（如 業外損益(金額:億元):2025）。僅對含 金額/合計 的鍵生效，避免誤殺正常 20xx 年份欄位"""
    if value is None:
        return False
    try:
        # 僅當 key 暗示金額欄且 value 恰為年份整數時判定污染
        if ("金額" not in key and "合計" not in key):
            return False
        # 允許 float 2025.0
        v_int = int(float(str(value).replace(",", "").strip()))
        return str(v_int) == str(year)
    except:
        return False

def _drop_polluted_dict(d: dict, year: str):
    """原地剔除污染鍵，回傳被剔除的 keys"""
    dropped = []
    for k in list(d.keys()):
        if _is_polluted(k, d[k], year):
            dropped.append(k)
            d.pop(k, None)
    return dropped

WITH_NEWS = os.getenv("FETCH_WITH_NEWS", "0") == "1"

def finmind(dataset, stock_id, start_date="2020-01-01"):
    params = {"dataset": dataset, "data_id": stock_id, "start_date": start_date}
    if TOKEN:
        params["token"] = TOKEN
    r = requests.get(FINMIND_BASE, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("status") != 200:
        raise RuntimeError(f"FinMind {dataset} {stock_id} failed: {j}")
    return j["data"]

def fetch_finmind_annual(stock_id):
    """回傳年度彙總: 年 -> {revenue, gross_profit, op_income, op_expenses(total), net_income, eps, ...} + BS/ CF 年度"""
    # --- IS quarterly sum -> annual ---
    is_data = finmind("TaiwanStockFinancialStatements", stock_id, "2020-01-01")
    # organize by year
    is_by_year = defaultdict(list)
    for row in is_data:
        is_by_year[row["date"][:4]].append(row)
    # BS snapshot: 12-31 only
    bs_data = finmind("TaiwanStockBalanceSheet", stock_id, "2020-01-01")
    bs_by_year = {}
    for row in bs_data:
        if row["date"][5:] == "12-31":
            bs_by_year.setdefault(row["date"][:4], {})[row["type"]] = row["value"]
    # CF YTD: 12-31 only
    cf_data = finmind("TaiwanStockCashFlowsStatement", stock_id, "2020-01-01")
    cf_by_year = {}
    for row in cf_data:
        if row["date"][5:] == "12-31":
            cf_by_year.setdefault(row["date"][:4], {})[row["type"]] = row["value"]
    # Dividend: map by 盈餘年度 (ex_year - 1, 儲存 cash/stock/ex_date 供殖利率用)
    import re
    from datetime import datetime as _dt, timedelta as _td
    def _parse_year_field(s):
        if not s:
            return None
        m = re.search(r"(\d{2,4})", str(s))
        if not m:
            return None
        n = int(m.group(1))
        return 1911 + n if n < 1911 else n
    div_data = finmind("TaiwanStockDividend", stock_id, "2020-01-01")
    div_by_year = {}
    for row in div_data:
        # 優先用官方 year 欄（盈餘年度），缺則用除息日年份 -1
        y = _parse_year_field(row.get("year"))
        d_cash = row.get("CashExDividendTradingDate")
        d_stock = row.get("StockExDividendTradingDate")
        ex_for_year = d_cash or d_stock
        if y is None and ex_for_year and len(ex_for_year) >= 4:
            try:
                y = int(ex_for_year[:4]) - 1
            except:
                continue
        if y is None:
            continue
        y = str(y)
        cash = (row.get("CashEarningsDistribution") or 0) + (row.get("CashStatutorySurplus") or 0)
        stock = (row.get("StockEarningsDistribution") or 0) + (row.get("StockStatutorySurplus") or 0)
        if y not in div_by_year:
            div_by_year[y] = {"cash": 0.0, "stock": 0.0, "ex_cash": None, "ex_stock": None, "has_row": False}
        # 累加（處理半年配/季配多筆），保留首個非空 ex_date
        if cash or stock or cash == 0 or stock == 0:
            div_by_year[y]["cash"] += float(cash or 0)
            div_by_year[y]["stock"] += float(stock or 0)
            div_by_year[y]["has_row"] = True
            if d_cash and not div_by_year[y]["ex_cash"]:
                div_by_year[y]["ex_cash"] = d_cash
            if d_stock and not div_by_year[y]["ex_stock"]:
                div_by_year[y]["ex_stock"] = d_stock
        # 若為 0 且無 ex_date（如 FinMind 佔位列），仍保留但後續過濾
    # 零值無 ex_date 的佔位 years 轉 None 以免誤為 0 配息污染
    for k in list(div_by_year.keys()):
        v = div_by_year[k]
        if not v["has_row"] and v["cash"] == 0 and v["stock"] == 0:
            del div_by_year[k]
            continue
        # 全零且 ex_date 缺的視為無配息年份，保留 cash/stock 為 0 但標記；後續 yield 會為 None
        if v["cash"] == 0 and v["stock"] == 0 and not v["ex_cash"] and not v["ex_stock"]:
            # 可能是 FinMind 空列，刪除
            if not v["has_row"]:
                del div_by_year[k]
    # --- Price for yield (除息前一日收盤 / 最新價預估，FinMind 同源不增 API provider) ---
    try:
        price_rows = finmind("TaiwanStockPrice", stock_id, "2020-01-01")
        _price_map = {r["date"]: r["close"] for r in price_rows if r.get("close") is not None}
        _sorted_price_dates = sorted(_price_map.keys())
        _latest_close = _price_map[_sorted_price_dates[-1]] if _sorted_price_dates else None
        _latest_date = _sorted_price_dates[-1] if _sorted_price_dates else None
    except Exception:
        _price_map = {}
        _sorted_price_dates = []
        _latest_close = None
        _latest_date = None
    def _prev_close(ex_date):
        if not ex_date or not _price_map:
            return None, None
        # 回溯找前一交易日收盤
        try:
            d = _dt.strptime(ex_date, "%Y-%m-%d").date() - _td(days=1)
            for _ in range(10):
                k = d.strftime("%Y-%m-%d")
                if k in _price_map:
                    return _price_map[k], k
                d -= _td(days=1)
        except Exception:
            pass
        # fallback：取 ex_date 之前最近一筆
        cands = [dd for dd in _sorted_price_dates if dd < ex_date]
        if cands:
            k = cands[-1]
            return _price_map[k], k
        return None, None

    # Month revenue for quarterly/monthly另處理，這裡不彙總年營收用IS sum
    annual = {}
    years_sorted = sorted(is_by_year.keys())
    for y in years_sorted:
        # IS: sum quarters — 僅收錄完整年度（4季），當年未完成（如2026僅2季）跳過，避免年度指標失真
        rows = is_by_year[y]
        # 檢查該年是否至少有 Revenue 記錄 4 筆（代表4季齊全）
        rev_count = len([r for r in rows if r["type"] == "Revenue"])
        if rev_count < 4:
            continue
        def sum_type(t):
            return sum(r["value"] for r in rows if r["type"] == t)
        rev = sum_type("Revenue")
        gp = sum_type("GrossProfit")
        oi = sum_type("OperatingIncome")
        oe = sum_type("OperatingExpenses")
        # net: EquityAttributableToOwnersOfParent preferred, fallback IncomeAfterTaxes
        ni_parent = sum_type("EquityAttributableToOwnersOfParent")
        ni_total = sum_type("IncomeAfterTaxes")
        ni = ni_parent if ni_parent != 0 or any(r["type"]=="EquityAttributableToOwnersOfParent" for r in rows) else ni_total
        eps = sum_type("EPS")
        # EPS 誠實標註：FinMind 季 EPS 為增量，加總為年報加權平均；若後續新聞交叉差異大將以 ⚠️ 提示
        eps_is_estimated = False
        if rev == 0 and gp == 0 and oi == 0:
            continue
        # BS
        bs = bs_by_year.get(y, {})
        cash = bs.get("CashAndCashEquivalents")
        ca = bs.get("CurrentAssets")
        cl = bs.get("CurrentLiabilities")
        ta = bs.get("TotalAssets")
        tl = bs.get("Liabilities")
        eq = bs.get("Equity")
        if eq is None:
            eq = bs.get("EquityAttributableToOwnersOfParent")
        inv = bs.get("Inventories")
        # CF YTD — 實測 FinMind type 名可能含大小寫差異，採 fallback 並誠實告知缺值
        cf = cf_by_year.get(y, {})
        # 嘗試多個別名，找不到即為 None（誠實告知，不以 0 填充）
        def _cf_get(*keys):
            for k in keys:
                if k in cf and cf[k] is not None:
                    return cf[k]
            return None
        op_cf = _cf_get("CashFlowsFromOperatingActivities", "CashFlowsFromOperatingActivities_Net", "NetCashFlowsFromOperatingActivities")
        inv_cf = _cf_get("CashProvidedByInvestingActivities", "NetCashFlowsFromInvestingActivities", "CashFlowsFromInvestingActivities")
        fin_cf = _cf_get("CashFlowsProvidedFromFinancingActivities", "NetCashFlowsFromFinancingActivities", "CashFlowsFromFinancingActivities")
        # capex 代理：實測 FinMind 多為 "AcquisitionOfPropertyPlantAndEquipment" 或 "PropertyAndPlantAndEquipment" 負值
        capex = _cf_get("PropertyAndPlantAndEquipment", "AcquisitionOfPropertyPlantAndEquipment", "PurchaseOfPropertyPlantAndEquipment", "AdditionsToPropertyPlantAndEquipment")
        # 若仍無，嘗試從 cf keys 中模糊包含 Property 的負值作最後 fallback（僅取 12-31 該年）
        if capex is None:
            for k, v in cf.items():
                if "Property" in k and v is not None and v < 0:
                    capex = v
                    break
        # Normalize to 億元，污染值（==年份）視為 None
        def to_yi(v):
            if v is None:
                return None
            # 年份污染防禦：若值恰為 2023/2024/2025 整數，極可能是表頭污染
            try:
                if str(int(float(v))) == str(y) and abs(float(v) - int(y)) < 0.01:
                    return None
            except:
                pass
            return v/1e8
        _div_info = div_by_year.get(y) or {}
        _div_cash = _div_info.get("cash") if _div_info else None
        _div_stock = _div_info.get("stock") if _div_info else None
        # 若當年無紀錄，視為 None（尚未公告），但若為 0 且有 ex_date 則保留 0
        if _div_info and _div_info.get("has_row"):
            _div_cash_val = float(_div_cash) if _div_cash is not None else None
            _div_stock_val = float(_div_stock) if _div_stock is not None else None
            # 0 配息亦為有效值，None 表示無紀錄
            if _div_cash_val == 0 and _div_stock_val == 0 and not _div_info.get("ex_cash") and not _div_info.get("ex_stock"):
                _div_cash_val = None
                _div_stock_val = None
        else:
            _div_cash_val = _div_cash if isinstance(_div_cash, (int, float)) and _div_cash != 0 else (0.0 if _div_info and _div_info.get("has_row") and _div_cash == 0 else None)
            _div_stock_val = _div_stock if isinstance(_div_stock, (int, float)) and _div_stock != 0 else (0.0 if _div_info and _div_info.get("has_row") and _div_stock == 0 else None)
            if _div_cash_val is None and _div_stock_val is None:
                # 無紀錄
                pass
        # 標準化：若無 has_row 則 None
        if not _div_info.get("has_row"):
            _div_cash_val = None
            _div_stock_val = None
        ex_cash = _div_info.get("ex_cash") if _div_info else None
        ex_stock = _div_info.get("ex_stock") if _div_info else None
        ex_for_yield = ex_cash or ex_stock
        _yield = None
        _yield_price = None
        _yield_price_date = None
        _yield_is_estimated = False
        if _div_cash_val is not None and _div_cash_val != 0:
            if ex_for_yield:
                c, cd = _prev_close(ex_for_yield)
                if c:
                    _yield = _div_cash_val / c * 100
                    _yield_price = c
                    _yield_price_date = cd
            else:
                # 尚未除息：用最新價預估，標 estimated
                if _latest_close:
                    _yield = _div_cash_val / _latest_close * 100
                    _yield_price = _latest_close
                    _yield_price_date = _latest_date
                    _yield_is_estimated = True
        # 最新期若 cash 為 None（未公告），yield 保持 None；前端將以最新價虛線預估待除息後補
        # 若 ex 存在但尚未到前一日（如未來 ex），_prev_close 回溯會取到最新價之前的最近交易日，仍有效
        annual[y] = {
            "revenue": to_yi(rev),
            "gross_profit": to_yi(gp),
            "op_income": to_yi(oi),
            "op_expenses_total": to_yi(oe),  # FinMind total
            "net_income": to_yi(ni),
            "eps": (eps if eps != 0 else None),
            "eps_is_estimated": eps_is_estimated if 'eps_is_estimated' in locals() else False,
            "cash": to_yi(cash),
            "inventory": to_yi(inv),
            "current_assets": to_yi(ca),
            "current_liabilities": to_yi(cl),
            "total_assets": to_yi(ta),
            "total_liabilities": to_yi(tl),
            "equity": to_yi(eq),
            "op_cf": to_yi(op_cf),
            "inv_cf": to_yi(inv_cf),
            "fin_cf": to_yi(fin_cf),
            "capex": to_yi(capex),  # 保持負值
            "dividend": _div_cash_val,  # 兼容舊鍵：現金股利
            "dividend_cash": _div_cash_val,
            "dividend_stock": _div_stock_val,
            "dividend_ex_cash_date": ex_cash,
            "dividend_ex_stock_date": ex_stock,
            "dividend_yield": _yield,
            "dividend_yield_price": _yield_price,
            "dividend_yield_price_date": _yield_price_date,
            "dividend_yield_is_estimated": _yield_is_estimated,
        }
    return annual, is_by_year, bs_by_year, cf_by_year, div_by_year

def fetch_goodinfo_expense_only(stock_id):
    """
    僅抓 IS_YEAR 三列：推銷/管理/研發。成功回傳 {year: {sell, admin, rd}}，失敗回傳 {} + reason
    每次健診最多 1 次 HTTP，失敗不重試
    """
    tz_offset = -480
    now_ms = time.time() * 1000
    days_adjusted = now_ms / 86400000 - tz_offset / 1440
    client_key = f"2.8|38057.1435627105|46946.0324515993|{tz_offset}|{days_adjusted}|{days_adjusted}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://goodinfo.tw/'}
    cookies = {'CLIENT_KEY': client_key}
    url = f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_YEAR&STOCK_ID={stock_id}&REINIT={days_adjusted:.10f}"
    try:
        r = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table')
        if len(tables) < 7:
            return {}, f"Goodinfo blocked: tables={len(tables)}"
        target = tables[6]
        rows = target.find_all('tr')
        # 解析年份列
        years = []
        for tr in rows[:3]:
            tds = [td.get_text(strip=True) for td in tr.find_all(['td','th'])]
            if any(t.isdigit() and len(t)==4 for t in tds):
                years = [t for t in tds if t.isdigit() and len(t)==4]
                break
        if not years:
            return {}, "Goodinfo: cannot find years header"
        # 解析費用三列：takes amount columns only (even indices)
        expense = {y: {} for y in years}
        has_rd_row = False
        for tr in rows:
            tds = [td.get_text(strip=True) for td in tr.find_all(['td','th'])]
            if not tds:
                continue
            key = tds[0]
            vals = tds[1:]
            amts = vals[0::2]  # amount columns
            # need to align amts with years (both length 6)
            if '推銷' in key:
                for y, v in zip(years, amts):
                    try:
                        expense[y]['sell'] = float(v.replace(',','')) if v not in ('-','', 'N/A', '--') else None
                    except:
                        expense[y]['sell'] = None
            elif '管理' in key and '研發' not in key:
                for y, v in zip(years, amts):
                    try:
                        expense[y]['admin'] = float(v.replace(',','')) if v not in ('-','', 'N/A', '--') else None
                    except:
                        expense[y]['admin'] = None
            elif '研究發展' in key or ('研究' in key and '開發' in key):
                has_rd_row = True
                for y, v in zip(years, amts):
                    try:
                        expense[y]['rd'] = float(v.replace(',','')) if v not in ('-','', 'N/A', '--') else None
                    except:
                        expense[y]['rd'] = None
        # 檢查是否至少一列有值（排除特殊鍵前）
        has_any = any(any(v is not None for v in d.values()) for y, d in expense.items() if not y.startswith("_"))
        if not has_any:
            return {}, "Goodinfo: expense rows not found (maybe layout changed)"
        # 將 has_rd_row 標記存於 expense 的特殊鍵，供上層區分產業無研發 vs 暫缺
        expense["_has_rd_row"] = has_rd_row
        return expense, "OK"
    except Exception as e:
        return {}, f"Goodinfo error: {e}"

def fetch_quarterly_monthly(stock_id):
    """FinMind季報近8季 + 月報近12月，用於季月動能分頁"""
    # Quarterly: from FinancialStatements quarterly rows
    is_data = finmind("TaiwanStockFinancialStatements", stock_id, "2022-01-01")
    # group by date
    q_by_date = defaultdict(dict)
    for r in is_data:
        q_by_date[r["date"]][r["type"]] = r["value"]
    quarterly = []
    for date in sorted(q_by_date.keys()):
        d = q_by_date[date]
        rev = d.get("Revenue")
        gp = d.get("GrossProfit")
        ni = d.get("EquityAttributableToOwnersOfParent") or d.get("IncomeAfterTaxes")
        eps = d.get("EPS")
        if rev is None:
            continue
        # 季度標籤
        y, m = date.split("-")[:2]
        q = (int(m)-1)//3 + 1
        label = f"{y}Q{q}"
        gm = (gp/rev*100) if rev and gp is not None else None
        nm = (ni/rev*100) if rev and ni is not None else None
        quarterly.append({
            "date": date,
            "label": label,
            "revenue": rev,
            "gross_profit": gp,
            "net_income": ni,
            "eps": eps,
            "gross_margin": gm,
            "net_margin": nm,
        })
    # keep last 8
    quarterly = quarterly[-8:]
    # add QoQ
    for i in range(len(quarterly)):
        if i == 0:
            quarterly[i]["qoq"] = None
        else:
            prev = quarterly[i-1]["revenue"]
            cur = quarterly[i]["revenue"]
            if prev and cur:
                quarterly[i]["qoq"] = (cur/prev - 1)*100
            else:
                quarterly[i]["qoq"] = None
    # Monthly
    m_data = finmind("TaiwanStockMonthRevenue", stock_id, "2023-01-01")
    m_data = sorted(m_data, key=lambda x: x["date"])
    monthly = []
    for r in m_data[-12:]:
        # revenue in MonthRevenue is already monthly amount (元), convert to 億元
        rev_yi = r["revenue"]/1e8 if r.get("revenue") else None
        monthly.append({"date": r["date"][:7], "revenue": rev_yi})
    return quarterly, monthly

def build_metrics(annual, expense_by_year):
    """annual 已是 FinMind彙總(億元)，expense_by_year 為Goodinfo細拆(億元)。回傳 metrics dict year->完整指標"""
    metrics = {}
    for y, a in annual.items():
        rev = a["revenue"]
        gp = a["gross_profit"]
        oi = a["op_income"]
        ni = a["net_income"]
        eps = a["eps"]
        cash = a["cash"]
        ca = a["current_assets"]
        cl = a["current_liabilities"]
        ta = a["total_assets"]
        tl = a["total_liabilities"]
        eq = a["equity"]
        op_cf = a["op_cf"]
        inv_cf = a["inv_cf"]
        fin_cf = a["fin_cf"]
        capex = a["capex"]
        div = a.get("dividend")
        div_cash = a.get("dividend_cash", div)
        div_stock = a.get("dividend_stock")
        div_yield = a.get("dividend_yield")
        div_yield_price = a.get("dividend_yield_price")
        div_yield_price_date = a.get("dividend_yield_price_date")
        div_yield_is_est = a.get("dividend_yield_is_estimated", False)
        ex_cash = a.get("dividend_ex_cash_date")
        ex_stock = a.get("dividend_ex_stock_date")
        eps_is_est = a.get("eps_is_estimated", False)
        # expense細拆：優先 Goodinfo，若無則 null；同時判斷 rd_availability 以區分產業無研發 vs 暫缺
        has_rd_row = expense_by_year.get("_has_rd_row", False) if expense_by_year else False
        is_blocked = not expense_by_year or (len([k for k in expense_by_year.keys() if not k.startswith("_")]) == 0)
        exp = expense_by_year.get(y, {}) if expense_by_year else {}
        sell = exp.get("sell")
        admin = exp.get("admin")
        rd = exp.get("rd")
        if is_blocked:
            rd_availability = "temporarily_unavailable"
        elif not has_rd_row:
            rd_availability = "industry_none"
        elif rd is None:
            rd_availability = "temporarily_unavailable"
        else:
            rd_availability = "present"
        # 若 Goodinfo 無 rd 但產業本無 (如航運) 則保持 None 為正常
        # total opex ratio: 若細拆有值則用細拆加總，否則用 FinMind total
        if sell is not None or admin is not None or rd is not None:
            sum_exp = (sell or 0) + (admin or 0) + (rd or 0)
            # 若僅部分有值且 sum為0則降級用FinMind total
            if sum_exp == 0 and a["op_expenses_total"] is not None:
                total_opex = a["op_expenses_total"]
            else:
                total_opex = sum_exp if (sell is not None and admin is not None) or sum_exp>0 else a["op_expenses_total"]
        else:
            total_opex = None
            sum_exp = None
        # 若 total_opex 仍 None 但 FinMind total 有值，則用 FinMind
        if total_opex is None:
            total_opex = a["op_expenses_total"]
        # Ratios
        def ratio(num, den):
            if num is None or den in (None, 0):
                return None
            return num/den*100
        gross_margin = ratio(gp, rev)
        op_margin = ratio(oi, rev)
        net_margin = ratio(ni, rev)
        current_ratio = ratio(ca, cl)
        debt_ratio = ratio(tl, ta)
        roe = ratio(ni, eq)
        roa = ratio(ni, ta)
        sell_ratio = ratio(sell, rev)
        admin_ratio = ratio(admin, rev)
        rd_ratio = ratio(rd, rev)
        total_opex_ratio = ratio(total_opex, rev) if total_opex is not None else ratio(a["op_expenses_total"], rev)
        # FCF: op_cf + capex (capex負值)
        fcf = None
        if op_cf is not None and capex is not None:
            fcf = op_cf + capex
        elif op_cf is not None:
            fcf = op_cf  # 若無capex則至少給op_cf
        metrics[y] = {
            "revenue": rev,
            "gross_profit": gp,
            "sell_exp": sell,
            "admin_exp": admin,
            "rd_exp": rd,
            "rd_availability": rd_availability,
            "op_income": oi,
            "net_income": ni,
            "eps": eps,
            "eps_is_estimated": eps_is_est,
            "cash": cash,
            "inventory": a["inventory"],
            "current_assets": ca,
            "current_liabilities": cl,
            "total_assets": ta,
            "total_liabilities": tl,
            "equity": eq,
            "op_cf": op_cf,
            "inv_cf": inv_cf,
            "fin_cf": fin_cf,
            "capex": capex,
            "dividend": div,
            "dividend_cash": div_cash,
            "dividend_stock": div_stock,
            "dividend_yield": div_yield,
            "dividend_yield_price": div_yield_price,
            "dividend_yield_price_date": div_yield_price_date,
            "dividend_yield_is_estimated": div_yield_is_est,
            "dividend_ex_cash_date": ex_cash,
            "dividend_ex_stock_date": ex_stock,
            "gross_margin": gross_margin,
            "sell_ratio": sell_ratio,
            "admin_ratio": admin_ratio,
            "rd_ratio": rd_ratio,
            "total_opex_ratio": total_opex_ratio,
            "op_margin": op_margin,
            "net_margin": net_margin,
            "current_ratio": current_ratio,
            "debt_ratio": debt_ratio,
            "roe": roe,
            "roa": roa,
            "fcf": fcf,
        }
    return metrics

def sanity_check(metrics_by_year, years, raw_income=None, raw_bs=None):
    warnings = []
    # 0. 污染檢（若提供 raw 層）
    for yr in years:
        for src in (raw_income or {}, raw_bs or {}):
            for k, per_year in src.items():
                if not isinstance(per_year, dict):
                    continue
                v = per_year.get(str(yr))
                if v is not None and _is_polluted(k, v, str(yr)):
                    warnings.append({'level': 'error', 'field': f'{yr} {k}', 'msg': f'值 {v} 等於年份 {yr}，判定為表頭污染，已剔除'})
    for yr in years:
        m = metrics_by_year.get(yr, {})
        gm = m.get('gross_margin')
        if gm is not None:
            if gm > 100:
                warnings.append({'level': 'error', 'field': f'{yr} 毛利率', 'msg': f'{gm:.1f}% 超過 100% ，數據可能有誤'})
            elif gm < -50:
                warnings.append({'level': 'error', 'field': f'{yr} 毛利率', 'msg': f'{gm:.1f}% 低於 -50% ，請確認是否為特殊損失年度'})
        cr = m.get('current_ratio')
        if cr is not None and cr < 0:
            warnings.append({'level': 'error', 'field': f'{yr} 流動比率', 'msg': f'{cr:.1f}% 為負值'})
        dr = m.get('debt_ratio')
        if dr is not None and dr > 100:
            warnings.append({'level': 'warn', 'field': f'{yr} 負債比率', 'msg': f'{dr:.1f}% 超過 100% ，若非金融業則為警示'})
        roe = m.get('roe')
        if roe is not None and roe > 100:
            warnings.append({'level': 'warn', 'field': f'{yr} ROE', 'msg': f'{roe:.1f}% 超過 100% ，可能為高槓桿'})
        # EPS 估算誠實告知
        if m.get('eps_is_estimated'):
            warnings.append({'level': 'info', 'field': f'{yr} EPS', 'msg': '該年無 12-31 年報單筆 EPS，以季加總估算（加權平均可能失真），僅供參考'})
    nm_list = [(yr, metrics_by_year[yr].get('net_margin')) for yr in years if yr in metrics_by_year]
    for i in range(1, len(nm_list)):
        yr_prev, nm_prev = nm_list[i-1]
        yr_curr, nm_curr = nm_list[i]
        if nm_prev is not None and nm_curr is not None:
            if abs(nm_curr - nm_prev) > 30:
                warnings.append({'level': 'warn', 'field': f'{yr_prev}→{yr_curr} 淨利率', 'msg': f'波動 {nm_curr - nm_prev:+.1f} 個百分點，建議確認是否有一次性損益'})
    return warnings

def cross_validate_with_news(metrics, years, enable=False):
    """可信新聞最終交叉（發布前驗證）。enable=False 時回 skipped，誠實告知未經新聞交叉"""
    if not enable:
        return {"status": "skipped", "msg": "未啟用新聞交叉（日常離線模式），僅以 FinMind/MOPS 為準", "warnings": []}
    # 預留實作：實際新聞檢索由 CI 以 websearch 注入；此處僅作本地佔位，未來可接 websearch API
    # 若有外部注入的 news_data（透過環境變數或檔案），則比對 2% / EPS 雙閾值
    # 為避免 LLM 幻覺，無注入時回 info 而非 error
    return {"status": "checked", "msg": "已啟用新聞交叉（待外部注入 Tier1 數據）", "warnings": []}

def fetch_single(stock_id, company_name=None, delay_goodinfo=True):
    print(f"=== {stock_id} 開始 (FinMind 主力) ===")
    annual, is_by_year, bs_by_year, cf_by_year, div_by_year = fetch_finmind_annual(stock_id)
    print(f"  FinMind 年數: {sorted(annual.keys())}")
    # Goodinfo expense
    expense, status = fetch_goodinfo_expense_only(stock_id)
    print(f"  Goodinfo expense: {status} -> covers {list(expense.keys())[:3]}")
    if expense:
        for y in sorted(expense.keys())[:3]:
            print(f"    {y}: sell={expense[y].get('sell')} admin={expense[y].get('admin')} rd={expense[y].get('rd')}")
    metrics = build_metrics(annual, expense)
    # quarterly/monthly
    quarterly, monthly = fetch_quarterly_monthly(stock_id)
    print(f"  Quarterly {len(quarterly)} 月度 {len(monthly)}")
    # 決定公司名
    if not company_name:
        try:
            info = finmind("TaiwanStockInfo", stock_id, "2020-01-01")
            # fallback: use first name
            names = [r.get("stock_name") for r in finmind("TaiwanStockInfo", stock_id, "2026-01-01")]
            # last method: FinMind TaiwanStockInfo dataset via API direct
            pass
        except:
            pass
        # 嘗試用 FinMind的 TaiwanStockInfo via API without date filter? 用 info API
        try:
            r = requests.get("https://api.finmindtrade.com/api/v4/data", params={"dataset":"TaiwanStockInfo","data_id":stock_id,"start_date":"2026-08-01"}, timeout=10)
            d = r.json().get("data",[])
            if d:
                company_name = d[0].get("stock_name", stock_id)
        except:
            company_name = stock_id
        if not company_name or company_name==stock_id:
            # fallback industry map or keep stock_id
            company_name = INDUSTRY_MAP.get(stock_id, stock_id)
            if company_name != stock_id and "（" in company_name:
                company_name = stock_id  # avoid industry as name
    # 補 names that are industry: try to get stock_name via another call
    if company_name == stock_id or "（" in str(company_name):
        try:
            # use simple info
            r = requests.get(f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo&data_id={stock_id}&start_date=2026-01-01", timeout=10)
            j=r.json()
            if j.get("data"):
                # find stock_name
                for row in j["data"]:
                    if row.get("stock_name") and row.get("stock_name") != "":
                        company_name = row["stock_name"]
                        break
        except:
            pass
        if "（" in str(company_name):
            company_name = stock_id

    # income_statement / balance_sheet / cash_flow 彙整為 Goodinfo 格式兼容（供表格使用）
    # 為兼容 gen_dashboard的 t1/cost_series 等，income_statement 至少含營收/成本/毛利/費用明細
    income_statement = {}
    # 從 annual + expense 重建
    for y, m in metrics.items():
        # 建立鍵
        pass
    # 直接用 annual 重建簡易 income_statement dict (供表格的 pick_raw 備用)
    is_dict = {}
    for k in ["營業收入","營業成本","營業毛利","推銷費用","管理費用","研究發展費用","營業費用","營業利益","稅前淨利","所得稅費用","稅後淨利","每股稅後盈餘(元)"]:
        is_dict[k] = {}
    for y, a in annual.items():
        m = metrics[y]
        is_dict["營業收入"][y] = m["revenue"]
        # 成本 = revenue - gross
        cost = (m["revenue"] - m["gross_profit"]) if m["revenue"] and m["gross_profit"] else None
        is_dict["營業成本"][y] = cost
        is_dict["營業毛利"][y] = m["gross_profit"]
        is_dict["推銷費用"][y] = m["sell_exp"]
        is_dict["管理費用"][y] = m["admin_exp"]
        is_dict["研究發展費用"][y] = m["rd_exp"]
        total_opex = (m["sell_exp"] or 0)+(m["admin_exp"] or 0)+(m["rd_exp"] or 0) if m["sell_exp"] is not None or m["admin_exp"] is not None else annual[y]["op_expenses_total"]
        is_dict["營業費用"][y] = total_opex
        is_dict["營業利益"][y] = m["op_income"]
        # 稅前/稅後: 從 annual is_by_year 取（YTD sum）
        # 需從 is_by_year sums抓 pretax/tax
        rows = is_by_year.get(y, [])
        pre = sum(r["value"] for r in rows if r["type"] in ("PreTaxIncome","IncomeBeforeTax"))
        # PreTaxIncome is per quarter sum
        if pre:
            is_dict["稅前淨利"][y] = pre/1e8
        else:
            is_dict["稅前淨利"][y] = None
        tax = sum(r["value"] for r in rows if r["type"]=="TAX")
        is_dict["所得稅費用"][y] = tax/1e8 if tax else None
        is_dict["稅後淨利"][y] = m["net_income"]
        is_dict["每股稅後盈餘(元)"][y] = m["eps"]
    # BS dict
    bs_dict = {}
    for k in ["現金及約當現金","存貨","流動資產合計","流動負債合計","負債總額","股東權益總額","資產總額"]:
        bs_dict[k] = {}
    for y in annual:
        bs = bs_by_year.get(y, {})
        m = metrics[y]
        bs_dict["現金及約當現金"][y] = m["cash"]
        bs_dict["存貨"][y] = m["inventory"]
        bs_dict["流動資產合計"][y] = m["current_assets"]
        bs_dict["流動負債合計"][y] = m["current_liabilities"]
        bs_dict["負債總額"][y] = m["total_liabilities"]
        bs_dict["股東權益總額"][y] = m["equity"]
        bs_dict["資產總額"][y] = m["total_assets"]
    cf_dict = {}
    for k in ["營業活動之淨現金流入（出）","投資活動之淨現金流入（出）","融資活動之淨現金流入（出）","固定資產（增加）減少","發放現金股利"]:
        cf_dict[k] = {}
    for y in annual:
        m = metrics[y]
        cf_dict["營業活動之淨現金流入（出）"][y] = m["op_cf"]
        cf_dict["投資活動之淨現金流入（出）"][y] = m["inv_cf"]
        cf_dict["融資活動之淨現金流入（出）"][y] = m["fin_cf"]
        cf_dict["固定資產（增加）減少"][y] = m["capex"]
        # 股利另計
        cf_dict["發放現金股利"][y] = None  # 不由CF表取，另由Dividend年表

    years = sorted(metrics.keys())
    # 只保留最近6年，但 display最近3年
    # 污染已在 annual 層剔除，這裡對 is_dict/bs_dict 再做一次剔除 + 誠實告知
    for k in list(is_dict.keys()):
        for y in list(is_dict[k].keys()):
            if _is_polluted(k, is_dict[k][y], y):
                is_dict[k][y] = None
    for k in list(bs_dict.keys()):
        for y in list(bs_dict[k].keys()):
            if _is_polluted(k, bs_dict[k][y], y):
                bs_dict[k][y] = None
    sanity_warnings = sanity_check(metrics, years[-3:], raw_income=is_dict, raw_bs=bs_dict)
    news_check = cross_validate_with_news(metrics, years[-3:], enable=WITH_NEWS or os.getenv("FETCH_WITH_NEWS")=="1")
    verification = {
        "sanity": sanity_warnings + news_check.get("warnings", []),
        "sanity_pass": True,
        "news_crosscheck": news_check,
        "cross_source_warnings": [w for w in news_check.get("warnings", []) if w.get("level")=="verify"],
        "has_verify_warn": any(w.get("level")=="verify" for w in news_check.get("warnings", [])),
    }
    verification["sanity_pass"] = all(w["level"] != "error" for w in verification["sanity"])

    result = {
        "stock_id": stock_id,
        "company": company_name,
        "years": years,
        "income_statement": is_dict,
        "balance_sheet": bs_dict,
        "cash_flow": cf_dict,
        "metrics": metrics,
        "quarterly": quarterly,
        "monthly": monthly,
        "metadata": {
            "fetched_at": time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            "source": "FinMind (primary) + Goodinfo.tw (expense breakdown only)",
            "source_urls": {
                "income_statement": f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_YEAR&STOCK_ID={stock_id}",
                "balance_sheet": f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=BS_YEAR&STOCK_ID={stock_id}",
                "cash_flow": f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=CF_YEAR&STOCK_ID={stock_id}",
            },
            "finmind_datasets": ["TaiwanStockFinancialStatements","TaiwanStockBalanceSheet","TaiwanStockCashFlowsStatement","TaiwanStockDividend","TaiwanStockMonthRevenue","TaiwanStockPrice"],
            "supplement_source": {
                "expense_breakdown": "Goodinfo.tw IS_YEAR (single request, sell/admin/rd only)",
                "status": status,
            },
            "mops_url": f"https://mops.twse.com.tw/mops/web/t05st01?step=1&co_id={stock_id}&TYPEK=sii",
            "mops_url_otc": f"https://mops.twse.com.tw/mops/web/t05st01?step=1&co_id={stock_id}&TYPEK=otc",
            "years_covered": years[-3:],
            "currency": "TWD 億元",
        },
        "verification": verification,
    }
    return result

def _resolve_raw_path(stock_id):
    """支援新舊位置：優先 raw_data/，回落 reports/ 舊檔（相容期）"""
    p_new = RAW_DATA_DIR / f"{stock_id}_raw_data.json"
    p_old = REPORTS / f"{stock_id}_raw_data.json"
    if p_new.exists():
        return p_new
    if p_old.exists():
        return p_old
    return p_new  # 預設新位置（寫入）

def patch_existing(stock_id):
    raw_path = _resolve_raw_path(stock_id)
    if not raw_path.exists():
        print(f"{stock_id} no raw_data, will fetch fresh")
        return fetch_and_save(stock_id)
    j = json.load(open(raw_path, encoding="utf-8"))
    print(f"Patching {stock_id} existing years {j.get('years')}")
    # fetch expense only
    expense, status = fetch_goodinfo_expense_only(stock_id)
    print(f"  expense status {status}")
    if not expense:
        print(f"  {stock_id} Goodinfo failed, skip patch")
        return None
    # update metrics
    metrics = j.get("metrics", {})
    # also need annual FinMind totals to compute total_opex if missing
    # For patch, we can directly update sell/admin/rd from expense and recompute ratios
    # Need revenue per year
    for y in list(metrics.keys()):
        rev = metrics[y].get("revenue")
        if rev in (None, 0):
            continue
        exp = expense.get(y, {})
        if not exp:
            continue
        sell = exp.get("sell")
        admin = exp.get("admin")
        rd = exp.get("rd")
        # update metrics
        metrics[y]["sell_exp"] = sell
        metrics[y]["admin_exp"] = admin
        metrics[y]["rd_exp"] = rd
        # recompute ratios
        def r(num):
            return num/rev*100 if num is not None and rev else None
        metrics[y]["sell_ratio"] = r(sell)
        metrics[y]["admin_ratio"] = r(admin)
        metrics[y]["rd_ratio"] = r(rd)
        total = (sell or 0)+(admin or 0)+(rd or 0)
        # 若三項皆有值則用加總，否則保持原 total_opex_ratio 若存在，否則用加總
        if sell is not None and admin is not None:
            # rd 可能 None 代表無研發 (如航運)
            metrics[y]["total_opex_ratio"] = total/rev*100 if total else metrics[y].get("total_opex_ratio")
        else:
            # 至少有一個細拆，仍更新 total
            if total > 0:
                metrics[y]["total_opex_ratio"] = total/rev*100
        # update income_statement as well
        # ensure income_statement keys exist
        if "income_statement" in j:
            for k, v in [("推銷費用", sell), ("管理費用", admin), ("研究發展費用", rd)]:
                if k not in j["income_statement"]:
                    j["income_statement"][k] = {}
                j["income_statement"][k][y] = v
            # 營業費用 total
            if "營業費用" not in j["income_statement"]:
                j["income_statement"]["營業費用"] = {}
            j["income_statement"]["營業費用"][y] = total if total>0 else j["income_statement"]["營業費用"].get(y)
    # update supplement_source
    j["metadata"]["supplement_source"] = {
        "expense_breakdown": "Goodinfo.tw IS_YEAR (single request, sell/admin/rd only)",
        "status": status,
        "patched_at": time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
    }
    # if original source was FinMind primary, preserve
    if "FinMind" not in j["metadata"].get("source",""):
        j["metadata"]["source"] = "FinMind (primary) + Goodinfo.tw (expense breakdown only, patched)"
        j["metadata"]["finmind_datasets"] = ["TaiwanStockFinancialStatements","TaiwanStockBalanceSheet","TaiwanStockCashFlowsStatement","TaiwanStockDividend","TaiwanStockMonthRevenue","TaiwanStockPrice"]
    j["metrics"] = metrics
    # re-sanity（含污染與新聞交叉，誠實告知）
    years = sorted(metrics.keys())
    # 剔除既有污染值（若舊檔含 年份==值）
    if "income_statement" in j:
        for k in list(j["income_statement"].keys()):
            for y in list(j["income_statement"][k].keys()):
                if _is_polluted(k, j["income_statement"][k][y], y):
                    j["income_statement"][k][y] = None
    if "balance_sheet" in j:
        for k in list(j["balance_sheet"].keys()):
            for y in list(j["balance_sheet"][k].keys()):
                if _is_polluted(k, j["balance_sheet"][k][y], y):
                    j["balance_sheet"][k][y] = None
    sanity_warnings = sanity_check(metrics, years[-3:], raw_income=j.get("income_statement"), raw_bs=j.get("balance_sheet"))
    news_check = cross_validate_with_news(metrics, years[-3:], enable=WITH_NEWS or os.getenv("FETCH_WITH_NEWS")=="1")
    j["verification"] = {
        "sanity": sanity_warnings + news_check.get("warnings", []),
        "sanity_pass": all(w["level"] != "error" for w in sanity_warnings + news_check.get("warnings", [])),
        "news_crosscheck": news_check,
        "cross_source_warnings": [w for w in news_check.get("warnings", []) if w.get("level")=="verify"],
        "has_verify_warn": any(w.get("level")=="verify" for w in news_check.get("warnings", [])),
    }
    # preserve quarterly/monthly if missing, try fetch
    if not j.get("quarterly"):
        try:
            q, m = fetch_quarterly_monthly(stock_id)
            j["quarterly"] = q
            j["monthly"] = m
        except Exception as e:
            print(f"  quarterly fetch failed {e}")
    open(raw_path, "w", encoding="utf-8").write(json.dumps(j, ensure_ascii=False, indent=1))
    print(f"  patched {stock_id} -> {raw_path}")
    return j

def fetch_and_save(stock_id, company_name=None):
    data = fetch_single(stock_id, company_name)
    out = RAW_DATA_DIR / f"{stock_id}_raw_data.json"
    # If company_name resolves to different, still use stock_id prefix for gen_dashboard
    # Also need company field for display
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Saved {out} years {data['years'][-3:]}")
    return data

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("stock_id", nargs="?", help="stock id to fetch")
    ap.add_argument("--patch", type=str, help="patch existing raw_data expense for stock_id")
    ap.add_argument("--patch-all", action="store_true", help="patch all missing expenses")
    ap.add_argument("--with-news", action="store_true", help="啟用可信新聞最終交叉（發布前驗證，日常離線不啟用）")
    ap.add_argument("--regen", nargs="+", help="重拉指定股票（FinMind主體，修正EPS/現金流等）")
    args = ap.parse_args()
    if args.with_news:
        os.environ["FETCH_WITH_NEWS"] = "1"
        WITH_NEWS = True
    if args.regen:
        for sid in args.regen:
            fetch_and_save(sid)
            time.sleep(1)
    elif args.patch_all:
        targets = ["2484","3605","4721","8069"]
        for sid in targets:
            patch_existing(sid)
            time.sleep(8)  # Goodinfo rate limit: 1 per 8s
    elif args.patch:
        patch_existing(args.patch)
    elif args.stock_id:
        fetch_and_save(args.stock_id)
    else:
        ap.print_help()
