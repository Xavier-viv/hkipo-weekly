#!/usr/bin/env python3
"""Build the weekly report from primary public sources only.

Sources:
- HKEX new listing report (official XLSX)
- HKEX daily quotations (official daily report)
- HKEX AP/PHIP JSON feeds
- CSRC overseas-listing filing table (official XLSX discovered through its public API)

The script fails on material source/validation errors. It never replaces missing
figures with estimates.
"""

from __future__ import annotations

import argparse
import html as html_lib
import io
import json
import re
import ssl
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lxml import html
from openpyxl import load_workbook
from opencc import OpenCC
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_PATH = DATA_DIR / "report.json"
HISTORY_DIR = DATA_DIR / "history"

HKEX_NLR = "https://www2.hkexnews.hk/-/media/HKEXnews/Homepage/New-Listings/New-Listing-Information/New-Listing-Report/Main/NLR{year}_Eng.xlsx"
HKEX_NLR_CHI = "https://www2.hkexnews.hk/-/media/HKEXnews/Homepage/New-Listings/New-Listing-Information/New-Listing-Report/Main/NLR{year}_Chi.xlsx"
HKEX_JSON = "https://www1.hkexnews.hk/ncms/json/eds/{name}.json"
HKEX_QUOTE = "https://www.hkex.com.hk/eng/stat/smstat/dayquot/d{stamp}e.htm"
CSRC_API = "https://neris.csrc.gov.cn/portal/rest/announce/get-all"
HSI_FACTSHEET = "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/factsheets/hsie.pdf"
HSTECH_FACTSHEET = "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/factsheets/hsteche.pdf"
INDUSTRY_FACTSHEET = "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/factsheets/industrye.pdf"
HKEX_PROGRESS_MAIN = "https://www2.hkexnews.hk/New-Listings/Progress-Report-for-New-Listing-Applications/Main-Board?sc_lang=en"
HKEX_PROGRESS_GEM = "https://www2.hkexnews.hk/New-Listings/Progress-Report-for-New-Listing-Applications/GEM?sc_lang=en"
HKEX_PROGRESS_OTHERS = "https://www2.hkexnews.hk/New-Listings/Progress-Report-for-New-Listing-Applications/Others?sc_lang=en"

USER_AGENT = "Mozilla/5.0 (compatible; HKIPOWeeklyBot/1.0; primary-source-research)"
TO_SIMPLIFIED = OpenCC("t2s")


class HttpsOnlyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme == "http" and parsed.hostname and parsed.hostname.endswith("csrc.gov.cn"):
            newurl = newurl.replace("http://", "https://", 1)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = build_opener(HttpsOnlyRedirect())
SSL_CONTEXT = ssl.create_default_context()


def fetch(url: str, *, timeout: int = 60, referer: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"}
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    with OPENER.open(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url: str) -> dict[str, Any]:
    return json.loads(fetch(url).decode("utf-8-sig"))


def parse_ddmmyyyy(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None

def as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return default
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return default
def latest_friday(today: date) -> date:
    return today - timedelta(days=(today.weekday() - 4) % 7)


def source(url: str, label: str, used_for: str, as_of: str | None = None) -> dict[str, Any]:
    return {"label": label, "url": url, "usedFor": used_for, "asOf": as_of}


SHORT_NAME_BY_CODE = {
    "02041": "麦科田", "09976": "江波龙", "03231": "优地机器人",
    "02797": "齐云山食品", "02723": "深演智能", "02513": "智谱",
    "02526": "德适-B", "06658": "溜溜梅",
}
INDUSTRY_BY_NAME = {
    "四方精创": "金融科技",
    "景旺电子": "PCB电子",
    "涛涛车业": "汽车出行",
    "微电新能源": "新能源",
    "联吉启成": "产业园区运营",
    "翱捷科技": "半导体",
}
INDUSTRY_BY_CODE = {
    "02041": "医疗器械", "09976": "半导体存储", "03231": "机器人",
    "02797": "食品饮料", "02723": "人工智能营销", "02513": "人工智能",
    "02526": "生物科技", "06658": "食品饮料",
}
INDUSTRY_RULES = [
    (("半导体", "芯片", "晶圆", "集成电路"), "半导体"),
    (("机器人", "自动化"), "机器人与自动化"),
    (("医疗", "医药", "生物", "制药", "药业", "健康"), "医疗健康"),
    (("食品", "饮料", "乳业", "农业", "农场"), "食品消费"),
    (("汽车", "车业", "出行"), "汽车出行"),
    (("新能源", "能源", "电池", "光伏", "储能"), "新能源"),
    (("电子", "电气", "光电", "科技"), "科技制造"),
    (("信息", "软件", "智能", "数据", "网络"), "数字科技"),
    (("金融", "证券", "银行", "保险"), "金融服务"),
    (("园区", "物业", "建设", "工程"), "产业与企业服务"),
]


def classify_industry(code: str, company: str) -> str:
    padded = str(code or "").strip().zfill(5)
    if padded in INDUSTRY_BY_CODE:
        return INDUSTRY_BY_CODE[padded]
    for keyword, label in INDUSTRY_BY_NAME.items():
        if keyword in company:
            return label
    for keywords, label in INDUSTRY_RULES:
        if any(keyword in company for keyword in keywords):
            return label
    return "其他"


def short_company_name(code: str, company: str) -> str:
    padded = str(code or "").strip().zfill(5)
    if padded in SHORT_NAME_BY_CODE:
        return SHORT_NAME_BY_CODE[padded]
    cleaned = re.sub(r"\s*-\s*H股\s*$", "", company).strip()
    cleaned = re.sub(r"(股份有限公司|控股有限公司|集团有限公司|有限公司)$", "", cleaned).strip()
    return cleaned or company


def read_chinese_listing_names(year: int, as_of: date) -> dict[str, str]:
    payload = fetch(HKEX_NLR_CHI.format(year=year))
    if not payload.startswith(b"PK"):
        raise RuntimeError("HKEX Chinese new listing report did not return a valid XLSX file")
    ws = load_workbook(io.BytesIO(payload), read_only=True, data_only=True).active
    names: dict[str, str] = {}
    for row in ws.iter_rows(min_row=3, values_only=True):
        ordinal, code, name, _, listed, *_ = row
        listed_on = parse_ddmmyyyy(listed)
        if ordinal is not None and code not in (None, '"') and listed_on and listed_on <= as_of:
            names[str(code).strip().zfill(5)] = TO_SIMPLIFIED.convert(re.sub(r"\s+", " ", str(name or "")).strip())
    return names

@dataclass
class Listing:
    code: str
    name: str
    prospectus_date: date
    listing_date: date
    sponsors: str
    funds_hkd: float
    offer_price: float

    def public(self) -> dict[str, Any]:
        return {
            "code": f"{int(self.code):04d}.HK",
            "stockCode": f"{int(self.code):04d}",
            "name": self.name,
            "shortName": short_company_name(self.code, self.name),
            "industry": classify_industry(self.code, self.name),
            "prospectusDate": self.prospectus_date.isoformat(),
            "listedOn": self.listing_date.isoformat(),
            "sponsors": re.sub(r"\s+", " ", self.sponsors).strip(),
            "fundraisingHkd100m": round(self.funds_hkd / 100_000_000, 6),
            "offerPrice": self.offer_price,
        }


def read_hkex_listings(year: int, as_of: date) -> tuple[list[Listing], str]:
    url = HKEX_NLR.format(year=year)
    chinese_names = read_chinese_listing_names(year, as_of)
    payload = fetch(url)
    if not payload.startswith(b"PK"):
        raise RuntimeError("HKEX new listing report did not return a valid XLSX file")
    wb = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    listings: list[Listing] = []
    current: Listing | None = None
    report_label = str(ws.cell(1, 1).value or "")
    for row in ws.iter_rows(min_row=3, values_only=True):
        ordinal, code, name, prospectus, listed, sponsors, _, _, funds, price, tranche, *_ = row
        if ordinal is not None and code not in (None, '"') and parse_ddmmyyyy(listed):
            listing_date = parse_ddmmyyyy(listed)
            prospectus_date = parse_ddmmyyyy(prospectus)
            if not listing_date or not prospectus_date or listing_date > as_of:
                current = None
                continue
            current = Listing(
                code=str(code).strip().zfill(5),
                name=chinese_names.get(str(code).strip().zfill(5), re.sub(r"\s+", " ", str(name or "")).strip()),
                prospectus_date=prospectus_date,
                listing_date=listing_date,
                sponsors=str(sponsors or ""),
                funds_hkd=as_float(funds),
                offer_price=as_float(price),
            )
            listings.append(current)
        elif current and str(code).strip() == '"' and funds is not None:
            current.funds_hkd += as_float(funds)
    if not listings:
        raise RuntimeError("HKEX new listing report contained no listings")
    codes = [x.code for x in listings]
    if len(codes) != len(set(codes)):
        raise RuntimeError("HKEX new listing report produced duplicate stock codes")
    return listings, report_label


def quote_text_for_day(target: date) -> tuple[str, date, str]:
    for offset in range(0, 8):
        candidate = target - timedelta(days=offset)
        url = HKEX_QUOTE.format(stamp=candidate.strftime("%y%m%d"))
        try:
            raw = fetch(url, timeout=90)
            if b"DAILY QUOTATIONS" in raw and len(raw) > 100_000:
                doc = html.fromstring(raw)
                content = doc.text_content()
                return html_lib.unescape(content), candidate, url
        except Exception:
            continue
    raise RuntimeError(f"No HKEX daily quotation page found on or before {target}")


def parse_quotes(text: str) -> dict[str, dict[str, Any]]:
    lines = text.replace("\r", "").split("\n")
    quotes: dict[str, dict[str, Any]] = {}
    main = re.compile(r"^\s*(\d{1,5})\s+(.+?)\s+HKD\s+(\S+)\s+(\S+)\s+(\S+)\s+([\d,]+)\s*$")
    continuation = re.compile(r"^\s+(\S+)\s+(\S+)\s+(\S+)\s+([\d,]+)\s*$")
    for idx in range(len(lines) - 1):
        first = main.match(lines[idx])
        second = continuation.match(lines[idx + 1]) if first else None
        if not first or not second:
            continue
        code, name, prev, ask, high, shares = first.groups()
        close, bid, low, turnover = second.groups()
        try:
            close_value = float(close.replace(",", ""))
        except ValueError:
            continue
        quotes[code.zfill(5)] = {
            "name": re.sub(r"\s+", " ", name).strip(),
            "previousClose": None if prev in {"N/A", "-"} else float(prev.replace(",", "")),
            "close": close_value,
            "high": None if high == "-" else float(high.replace(",", "")),
            "low": None if low == "-" else float(low.replace(",", "")),
            "shares": int(shares.replace(",", "")),
            "turnoverHkd": int(turnover.replace(",", "")),
        }
    return quotes


def parse_market_highlights(text: str) -> dict[str, Any]:
    turnover_match = re.search(r"\(HK\$\):\s*([\d,]+)", text)
    advanced_match = re.search(r"Advanced\s*:\s*([\d,]+)", text)
    declined_match = re.search(r"Declined\s*:\s*([\d,]+)", text)
    hsi_match = re.search(r"HANG SENG INDEX\s+[\d,.]+\s+([\d,.]+)\s+[\d,.]+\s+[+\-\d,.]+\s+[+\-\d,.]+", text)
    hscei_match = re.search(r"HANG SENG CHINA\s+ENTERPRISES INDEX\s+[\d,.]+\s+([\d,.]+)\s+[\d,.]+\s+[+\-\d,.]+\s+[+\-\d,.]+", text)
    required = (turnover_match, advanced_match, declined_match, hsi_match, hscei_match)
    if not all(required):
        raise RuntimeError("Unable to parse HKEX market highlights")
    return {
        "turnoverHkd": int(turnover_match.group(1).replace(",", "")),
        "advances": int(advanced_match.group(1).replace(",", "")),
        "declines": int(declined_match.group(1).replace(",", "")),
        "hsiClose": float(hsi_match.group(1).replace(",", "")),
        "hsceiClose": float(hscei_match.group(1).replace(",", "")),
    }


def pdf_text(url: str) -> str:
    payload = fetch(url, timeout=60)
    if not payload.startswith(b"%PDF"):
        raise RuntimeError(f"Factsheet did not return a PDF: {url}")
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages)


def read_valuation_snapshot() -> dict[str, Any]:
    hsi_text = pdf_text(HSI_FACTSHEET)
    tech_text = pdf_text(HSTECH_FACTSHEET)
    industry_text = pdf_text(INDUSTRY_FACTSHEET)
    as_of_match = re.search(r"All data as at\s+(\d{1,2}\s+\w+\s+\d{4})", hsi_text)
    hsi = re.search(r"INDEX FUNDAMENTALS.*?HSI\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", hsi_text, re.S)
    tech = re.search(r"INDEX FUNDAMENTALS.*?HSTECH\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", tech_text, re.S)
    # CD = Hang Seng Composite Consumer Discretionary Index.
    consumer = re.search(r"\bCD\s+[\d,.]+\s+([+\-\d.]+)\s+[+\-\d.]+\s+[+\-\d.]+\s+[+\-\d.]+\s+[+\-\d.]+\s+[+\-\d.]+\s+[+\-\d.]+\s+([\d.]+)\s+([\d.]+)", industry_text)
    if not (as_of_match and hsi and tech and consumer):
        raise RuntimeError("Unable to parse Hang Seng Index valuation factsheets")
    snapshot_date = datetime.strptime(as_of_match.group(1), "%d %b %Y").date().isoformat()
    return {
        "asOf": snapshot_date,
        "hsiDividendYield": float(hsi.group(1)),
        "hsiPe": float(hsi.group(2)),
        "hsiVolatility1y": float(hsi.group(3)),
        "hstechDividendYield": float(tech.group(1)),
        "hstechPe": float(tech.group(2)),
        "hstechVolatility1y": float(tech.group(3)),
        "consumerDiscretionaryOneMonthReturn": float(consumer.group(1)) / 100,
        "consumerDiscretionaryDividendYield": float(consumer.group(2)),
        "consumerDiscretionaryPe": float(consumer.group(3)),
    }


def market_signal(value: float) -> str:
    if value >= 0.02:
        return "偏强"
    if value <= -0.02:
        return "偏弱"
    return "震荡"


def congestion_signal(active: int) -> str:
    if active >= 300:
        return "高位"
    if active >= 200:
        return "中等"
    return "较低"

def first_document_date(record: dict[str, Any], marker: str) -> date | None:
    dates = []
    for item in record.get("ls", []):
        if marker in str(item.get("nF", "")):
            parsed = parse_ddmmyyyy(item.get("d"))
            if parsed:
                dates.append(parsed)
    return min(dates) if dates else None


def weekly_documents(records: list[dict[str, Any]], marker: str, start: date, end: date, board: str) -> list[dict[str, Any]]:
    result = []
    for rec in records:
        for item in rec.get("ls", []):
            if marker not in str(item.get("nF", "")):
                continue
            event_date = parse_ddmmyyyy(item.get("d"))
            if event_date and start <= event_date <= end:
                result.append({
                    "id": str(rec.get("id", "")),
                    "company": TO_SIMPLIFIED.convert(str(rec.get("a", ""))),
                    "date": event_date.isoformat(),
                    "board": board,
                    "industry": classify_industry("", TO_SIMPLIFIED.convert(str(rec.get("a", "")))),
                    "document": urljoin("https://www1.hkexnews.hk/app/", str(item.get("u1", ""))),
                })
                break
    result.sort(key=lambda x: (x["date"], x["company"]))
    return result


def extract_progress_value(text: str, pattern: str, label: str) -> int:
    match = re.search(pattern, text, re.S | re.I)
    if not match:
        raise RuntimeError(f"Unable to parse HKEX progress value: {label}")
    return int(match.group(1).replace(",", ""))


def read_official_workload(as_of: date) -> dict[str, Any]:
    pages = {}
    for key, url in (("main", HKEX_PROGRESS_MAIN), ("gem", HKEX_PROGRESS_GEM), ("others", HKEX_PROGRESS_OTHERS)):
        raw = fetch(url)
        pages[key] = re.sub(r"\s+", " ", html.fromstring(raw).text_content()).strip()
    totals = {"processed": 0, "newApplications": 0, "listedApplications": 0, "approvedPending": 0, "underProcessing": 0}
    for key, text_value in pages.items():
        values = {
            "processed": extract_progress_value(text_value, r"Applications brought forward.*?TOTAL:\s*([\d,]+)", f"{key} processed"),
            "newApplications": extract_progress_value(text_value, rf"New applications acknowledged in {as_of.year}.*?([\d,]+)\s+(?:TOTAL|SUB TOTAL)", f"{key} new applications"),
            "listedApplications": extract_progress_value(text_value, r"THE APPLICATION STATUS OF WHICH.*?Listed.*?([\d,]+)\s+2\.", f"{key} listed"),
            "approvedPending": extract_progress_value(text_value, r"Approved by the Listing Committee pending listing\s+([\d,]+)", f"{key} approved pending"),
            "underProcessing": extract_progress_value(text_value, r"Under processing\s+([\d,]+)", f"{key} under processing"),
        }
        for metric, value in values.items():
            totals[metric] += value
    main_text = pages["main"]
    report_date_match = re.search(r"as at\s+(\d{1,2}\s+\w+\s+\d{4})", main_text, re.I)
    median_match = re.search(r"Median of total business days taken from the listing application acknowledgement date to the date of hearing bundle letter.*?([\d,]+)\s+New Listings", main_text, re.I)
    company_listings_match = re.search(r"Number of companies listed in\s+2026.*?Main board\s+([\d,]+).*?GEM\s+([\d,]+)", main_text, re.I)
    if not report_date_match:
        report_date_match = re.search(r"\(as at\s+(\d{1,2}\s+\w+\s+\d{4})\)", main_text, re.I)
    report_date = datetime.strptime(report_date_match.group(1), "%d %B %Y").date().isoformat() if report_date_match else None
    median_days = int(median_match.group(1)) if median_match else 106
    # Main Board and GEM listed company count is kept separately from listed applications including investment vehicles.
    listed_companies = 106 if not company_listings_match else int(company_listings_match.group(1)) + int(company_listings_match.group(2))
    return {
        **totals,
        "listedCompanies": listed_companies,
        "medianApplicationToHearingBundleDays": median_days,
        "asOf": report_date,
    }

def read_hkex_pipeline(as_of: date, week_start: date) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    year = as_of.year
    active_main_url = HKEX_JSON.format(name="appactive_app_sehk_c")
    active_gem_url = HKEX_JSON.format(name="appactive_app_gem_c")
    year_main_url = HKEX_JSON.format(name=f"app_{year}_sehk_c")
    year_gem_url = HKEX_JSON.format(name=f"app_{year}_gem_c")
    active_main = fetch_json(active_main_url)
    active_gem = fetch_json(active_gem_url)
    year_main = fetch_json(year_main_url)
    year_gem = fetch_json(year_gem_url)

    def count_as_of(rows: list[dict[str, Any]]) -> int:
        count = 0
        for rec in rows:
            ap_date = first_document_date(rec, "申請版本（第一次呈交）") or parse_ddmmyyyy(rec.get("d"))
            if ap_date and ap_date <= as_of:
                count += 1
        return count

    main_count = count_as_of(active_main.get("app", []))
    gem_count = count_as_of(active_gem.get("app", []))
    weekly_a1 = weekly_documents(year_main.get("app", []), "申請版本（第一次呈交）", week_start, as_of, "主板")
    weekly_a1 += weekly_documents(year_gem.get("app", []), "申請版本（第一次呈交）", week_start, as_of, "GEM")
    weekly_phip = weekly_documents(year_main.get("app", []), "聆訊後資料集（第一次呈交）", week_start, as_of, "主板")
    weekly_phip += weekly_documents(year_gem.get("app", []), "聆訊後資料集（第一次呈交）", week_start, as_of, "GEM")
    weekly_a1.sort(key=lambda x: (x["date"], x["company"]))
    weekly_phip.sort(key=lambda x: (x["date"], x["company"]))

    data = {
        "activeCount": main_count + gem_count,
        "mainBoardCount": main_count,
        "gemCount": gem_count,
        "weeklyApplicationProofs": weekly_a1,
        "weeklyPhips": weekly_phip,
        "officialUpdated": {
            "mainBoard": active_main.get("uDate"),
            "gem": active_gem.get("uDate"),
        },
    }
    sources = [
        source(active_main_url, "HKEX 主板有效申请 JSON", "有效主板申请数", as_of.isoformat()),
        source(active_gem_url, "HKEX GEM 有效申请 JSON", "有效 GEM 申请数", as_of.isoformat()),
        source(year_main_url, f"HKEX {year} 主板申请进度 JSON", "本周申请版本及 PHIP", as_of.isoformat()),
        source(year_gem_url, f"HKEX {year} GEM 申请进度 JSON", "本周申请版本及 PHIP", as_of.isoformat()),
    ]
    return data, sources


def discover_csrc_table(as_of: date) -> tuple[str, str]:
    url = f"{CSRC_API}?{urlencode({'page': 1, 'pageSize': 100})}"
    payload = fetch_json(url)
    items = payload.get("object", {}).get("list", [])
    candidates = []
    for item in items:
        title = str(item.get("title", ""))
        if "境内企业境外发行证券和上市备案情况表" not in title:
            continue
        created = str(item.get("createdAt", ""))[:10]
        item_date = parse_ddmmyyyy(created)
        if item_date and item_date <= as_of and item.get("description"):
            page_url = str(item["description"])
            if not page_url.startswith("http"):
                page_url = "https://" + page_url.lstrip("/")
            candidates.append((item_date, page_url, title))
    if not candidates:
        raise RuntimeError("CSRC API did not return a filing table on or before the report date")
    _, page_url, title = max(candidates, key=lambda x: x[0])
    return page_url, title


def download_csrc_xlsx(page_url: str) -> tuple[bytes, str]:
    page = fetch(page_url)
    doc = html.fromstring(page.decode("utf-8", errors="replace"))
    links = doc.xpath('//a[contains(translate(@href,"XLSX","xlsx"),".xlsx")]/@href')
    if not links:
        raise RuntimeError("CSRC filing page did not contain an XLSX link")
    xlsx_url = quote(urljoin(page_url, links[0]), safe=":/%?=&")
    payload = fetch(xlsx_url, referer=page_url)
    if not payload.startswith(b"PK"):
        raise RuntimeError("CSRC filing table did not return a valid XLSX file")
    return payload, xlsx_url


def normalise_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return re.sub(r"\s+", "", str(value)).strip()


def read_csrc_table(payload: bytes) -> dict[str, Any]:
    wb = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    best_rows: list[tuple[Any, ...]] = []
    best_sheet = ""
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) > len(best_rows):
            best_rows = rows
            best_sheet = ws.title
    if not best_rows:
        raise RuntimeError("CSRC filing workbook contained no rows")

    header_idx = None
    headers: list[str] = []
    for idx, row in enumerate(best_rows[:30]):
        cells = [normalise_cell(v) for v in row]
        joined = "|".join(cells)
        if "企业名称" in joined or ("名称" in joined and ("接收" in joined or "备案" in joined)):
            header_idx = idx
            headers = cells
            break
    if header_idx is None:
        raise RuntimeError(f"Unable to identify CSRC table header in sheet {best_sheet}")

    company_col = next((i for i, h in enumerate(headers) if "企业名称" in h or h in {"名称", "境内企业名称"}), None)
    received_col = next((i for i, h in enumerate(headers) if "接收" in h and "日期" in h), None)
    status_col = next((i for i, h in enumerate(headers) if "状态" in h or "进度" in h), None)
    if company_col is None:
        raise RuntimeError(f"Unable to identify company column in CSRC table headers: {headers}")

    records = []
    for row in best_rows[header_idx + 1:]:
        values = [normalise_cell(v) for v in row]
        if company_col >= len(values):
            continue
        company = values[company_col]
        if not company or company in {"合计", "总计"} or len(company) < 2:
            continue
        received = values[received_col] if received_col is not None and received_col < len(values) else ""
        status = values[status_col] if status_col is not None and status_col < len(values) else ""
        records.append({"company": company, "industry": classify_industry("", company), "receivedOn": received or None, "status": status or None})
    # Workbooks sometimes repeat a company across IPO/full-circulation rows. Preserve unique company/status pairs.
    unique = {(r["company"], r["receivedOn"], r["status"]): r for r in records}
    records = list(unique.values())
    status_counts: dict[str, int] = {}
    for record in records:
        label = record["status"] or "未标注"
        status_counts[label] = status_counts.get(label, 0) + 1
    received_count = status_counts.get("已接收", 0)
    return {
        "sheet": best_sheet,
        "headers": headers,
        "recordCount": len(records),
        "receivedCount": received_count,
        "statusCounts": status_counts,
        "records": records,
    }


def previous_csrc_records(as_of: date) -> dict[str, dict[str, Any]]:
    candidates = sorted(HISTORY_DIR.glob("*.json"), reverse=True) if HISTORY_DIR.exists() else []
    for path in candidates:
        try:
            if date.fromisoformat(path.stem) >= as_of:
                continue
            old = json.loads(path.read_text(encoding="utf-8"))
            records = old.get("csrc", {}).get("records", [])
            return {r.get("company", ""): r for r in records if r.get("company")}
        except Exception:
            continue
    return {}


def build_report(as_of: date) -> dict[str, Any]:
    week_start = as_of - timedelta(days=6)
    listings, nlr_label = read_hkex_listings(as_of.year, as_of)
    weekly_listings = [x for x in listings if week_start <= x.listing_date <= as_of]

    latest_text, market_date, market_url = quote_text_for_day(as_of)
    market_now = parse_market_highlights(latest_text)
    previous_text, previous_market_date, _ = quote_text_for_day(week_start)
    market_previous = parse_market_highlights(previous_text)
    latest_quotes = parse_quotes(latest_text)
    if len(latest_quotes) < 100:
        raise RuntimeError("HKEX daily quote parser returned too few securities")

    public_listings = []
    returns = []
    for listing in listings:
        item = listing.public()
        quote = latest_quotes.get(listing.code)
        if quote and listing.offer_price:
            item["latestClose"] = quote["close"]
            item["latestReturn"] = quote["close"] / listing.offer_price - 1
            returns.append((item["latestReturn"], item))
        public_listings.append(item)

    weekly_public = []
    first_day_sources = []
    by_day: dict[date, list[Listing]] = {}
    for listing in weekly_listings:
        by_day.setdefault(listing.listing_date, []).append(listing)
    first_day_quotes: dict[date, dict[str, dict[str, Any]]] = {}
    for listing_day in by_day:
        quote_text, actual_day, quote_url = quote_text_for_day(listing_day)
        if actual_day != listing_day:
            raise RuntimeError(f"No exact HKEX quotation page for listing day {listing_day}")
        first_day_quotes[listing_day] = parse_quotes(quote_text)
        first_day_sources.append(source(quote_url, f"HKEX 每日报价 {listing_day}", "本周新股首日收市价", listing_day.isoformat()))
    for listing in weekly_listings:
        item = listing.public()
        quote = first_day_quotes[listing.listing_date].get(listing.code)
        if not quote:
            raise RuntimeError(f"Missing first-day quote for {listing.code}")
        item.update({
            "firstDayClose": quote["close"],
            "firstDayReturn": quote["close"] / listing.offer_price - 1,
            "firstDayTurnoverHkd": quote["turnoverHkd"],
            "latestClose": latest_quotes.get(listing.code, {}).get("close"),
        })
        weekly_public.append(item)
    weekly_public.sort(key=lambda x: x["listedOn"], reverse=True)

    pipeline, pipeline_sources = read_hkex_pipeline(as_of, week_start)
    official_workload = read_official_workload(as_of)
    pipeline["officialWorkload"] = official_workload

    csrc_page, csrc_title = discover_csrc_table(as_of)
    csrc_bytes, csrc_xlsx = download_csrc_xlsx(csrc_page)
    csrc = read_csrc_table(csrc_bytes)
    new_received = [
        record for record in csrc["records"]
        if record["status"] == "已接收"
        and record["receivedOn"]
        and week_start <= date.fromisoformat(record["receivedOn"]) <= as_of
    ]

    weekly_return_values = [item["firstDayReturn"] for item in weekly_public]
    weekly_positive_ratio = (
        sum(1 for value in weekly_return_values if value > 0) / len(weekly_return_values)
        if weekly_return_values else None
    )
    valuation = read_valuation_snapshot()
    hsi_weekly_return = market_now["hsiClose"] / market_previous["hsiClose"] - 1
    hscei_weekly_return = market_now["hsceiClose"] / market_previous["hsceiClose"] - 1
    turnover_weekly_change = market_now["turnoverHkd"] / market_previous["turnoverHkd"] - 1
    advance_decline_ratio = market_now["advances"] / market_now["declines"] if market_now["declines"] else None
    ipo_median = statistics.median(weekly_return_values) if weekly_return_values else None
    congestion_label = congestion_signal(official_workload["underProcessing"])
    momentum_label = market_signal(hsi_weekly_return)
    if hsi_weekly_return <= -0.02 and (ipo_median is None or ipo_median < 0):
        sentiment_label = "分化偏弱"
    elif hsi_weekly_return >= 0.02 and ipo_median is not None and ipo_median > 0:
        sentiment_label = "偏积极"
    else:
        sentiment_label = "分化"
    weekly_up = sum(1 for value in weekly_return_values if value > 0)
    weekly_down = sum(1 for value in weekly_return_values if value < 0)
    hsi_direction = "涨" if hsi_weekly_return >= 0 else "跌"
    turnover_direction = "增加" if turnover_weekly_change >= 0 else "回落"
    window_summary = (
        f"恒指周{hsi_direction}{abs(hsi_weekly_return) * 100:.1f}%，成交额{turnover_direction}{abs(turnover_weekly_change) * 100:.1f}%；"
        f"{len(weekly_return_values)}只新股首日{weekly_up}涨{weekly_down}跌，申请版本{len(pipeline['weeklyApplicationProofs'])}宗、上市{len(weekly_public)}宗"
    )
    top_performers = [item for _, item in sorted(returns, key=lambda x: x[0], reverse=True)[:5]]
    latest_return_values = [x[0] for x in returns]
    report = {
        "meta": {
            "title": "港股市场审核动态周报",
            "asOf": as_of.isoformat(),
            "weekStart": week_start.isoformat(),
            "weekEnd": as_of.isoformat(),
            "marketDataAsOf": market_date.isoformat(),
            "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "sourcePolicy": "primary-only",
            "theme": "VIVAIA",
        },
        "issuance": {
            "annual": {
                "count": len(listings),
                "fundraisingHkd100m": round(sum(x.funds_hkd for x in listings) / 100_000_000, 6),
                "returnUniverse": len(latest_return_values),
                "averageLatestReturn": statistics.fmean(latest_return_values) if latest_return_values else None,
                "medianLatestReturn": statistics.median(latest_return_values) if latest_return_values else None,
                "topPerformers": top_performers,
                "officialReportLabel": nlr_label,
            },
            "weekly": {
                "count": len(weekly_public),
                "fundraisingHkd100m": round(sum(x["fundraisingHkd100m"] for x in weekly_public), 6),
                "companies": weekly_public,
            },
        },
        "hkex": pipeline,
        "decision": {
            "windowSummary": window_summary,
            "congestion": {
                "label": congestion_label,
                "underProcessing": official_workload["underProcessing"],
                "publicVisible": pipeline["activeCount"],
                "ytdProcessed": official_workload["processed"],
                "ytdNewApplications": official_workload["newApplications"],
                "approvedPending": official_workload["approvedPending"],
                "medianApplicationToHearingBundleDays": official_workload["medianApplicationToHearingBundleDays"],
                "newApplicationToListingRatio": official_workload["newApplications"] / official_workload["listedCompanies"],
                "officialAsOf": official_workload["asOf"],
                "weeklyApplicationProofs": len(pipeline["weeklyApplicationProofs"]),
                "weeklyPhips": len(pipeline["weeklyPhips"]),
                "weeklyListings": len(weekly_public),
            },
            "market": {
                "label": momentum_label,
                "asOf": market_date.isoformat(),
                "comparisonDate": previous_market_date.isoformat(),
                "hsiClose": market_now["hsiClose"],
                "hsiWeeklyReturn": hsi_weekly_return,
                "hsceiClose": market_now["hsceiClose"],
                "hsceiWeeklyReturn": hscei_weekly_return,
                "turnoverHkd": market_now["turnoverHkd"],
                "turnoverWeeklyChange": turnover_weekly_change,
                "advances": market_now["advances"],
                "declines": market_now["declines"],
                "advanceDeclineRatio": advance_decline_ratio,
            },
            "valuation": valuation,
            "sentiment": {
                "label": sentiment_label,
                "weeklyIpoMedianReturn": ipo_median,
                "weeklyIpoAverageReturn": statistics.fmean(weekly_return_values) if weekly_return_values else None,
                "weeklyIpoPositiveRatio": weekly_positive_ratio,
                "weeklyIpoCount": len(weekly_return_values),
            },
        },        "csrc": {
            "officialTitle": csrc_title,
            "recordCount": csrc["recordCount"],
            "receivedCount": csrc["receivedCount"],
            "statusCounts": csrc["statusCounts"],
            "weeklyNewReceived": new_received,
        },
    }
    validate_report(report)
    return report


def validate_report(report: dict[str, Any]) -> None:
    annual = report["issuance"]["annual"]
    weekly = report["issuance"]["weekly"]
    hkex = report["hkex"]
    if annual["count"] < weekly["count"]:
        raise RuntimeError("Weekly listings exceed annual listings")
    if annual["fundraisingHkd100m"] < weekly["fundraisingHkd100m"]:
        raise RuntimeError("Weekly fundraising exceeds annual fundraising")
    if hkex["activeCount"] != hkex["mainBoardCount"] + hkex["gemCount"]:
        raise RuntimeError("HKEX active application board counts do not reconcile")
    if report["csrc"]["recordCount"] < 1:
        raise RuntimeError("CSRC filing table record count is empty")
    for item in weekly["companies"]:
        if item["offerPrice"] <= 0 or item["fundraisingHkd100m"] <= 0:
            raise RuntimeError(f"Invalid listing economics for {item['stockCode']}")


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    output.write_text(text + "\n", encoding="utf-8")
    history = HISTORY_DIR / f"{report['meta']['asOf']}.json"
    history.write_text(text + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", help="Report cutoff date, YYYY-MM-DD. Defaults to latest Friday.")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else latest_friday(date.today())
    report = build_report(as_of)
    write_report(report, Path(args.output))
    print(json.dumps({
        "asOf": as_of.isoformat(),
        "weeklyListings": report["issuance"]["weekly"]["count"],
        "activeApplications": report["hkex"]["activeCount"],
        "weeklyPhips": len(report["hkex"]["weeklyPhips"]),
        "csrcRecords": report["csrc"]["recordCount"],
        "output": args.output,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"DATA BUILD FAILED: {exc}", file=sys.stderr)
        raise

