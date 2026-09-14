#!/usr/bin/env python3
"""Generate the shareable long PNG. The QR code always points to this site."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 3400
C = {
    "ruby": "#8b1a2b", "red": "#c41230", "burgundy": "#590d1a",
    "cream": "#fff7e9", "cream2": "#f3ddbd", "ivory": "#f5f2ef",
    "white": "#ffffff", "ink": "#182235", "muted": "#687487",
    "line": "#e4e7ec", "blue": "#405a7a", "green": "#078f6b",
}


def font_path(bold: bool) -> str:
    env_name = "POSTER_FONT_BOLD" if bold else "POSTER_FONT_REGULAR"
    candidates = [
        os.environ.get(env_name),
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("No suitable poster font found. Install Noto Sans CJK or set POSTER_FONT_REGULAR/BOLD.")


REGULAR = None
BOLD = None


def f(size: int, bold: bool = False):
    global REGULAR, BOLD
    if REGULAR is None:
        REGULAR, BOLD = font_path(False), font_path(True)
    return ImageFont.truetype(BOLD if bold else REGULAR, size)


def pct(value, digits=1):
    if value is None:
        return "—"
    return f"{'+' if value >= 0 else ''}{value * 100:.{digits}f}%"


def money(value):
    return f"HK${value:,.1f}亿"


def short_date(value):
    return value[5:].replace("-", ".")


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, size, fill=C["ink"], bold=False, anchor="la"):
    draw.text(xy, str(value), font=f(size, bold), fill=fill, anchor=anchor)


def fit_text(draw, value, box, size, fill=C["ink"], bold=False, max_lines=2, spacing=5):
    x1, y1, x2, _ = box
    chars = list(str(value))
    lines, line = [], ""
    font = f(size, bold)
    for char in chars:
        trial = line + char
        if draw.textlength(trial, font=font) > x2 - x1 and line:
            lines.append(line)
            line = char
        else:
            line = trial
    if line:
        lines.append(line)
    draw.multiline_text((x1, y1), "\n".join(lines[:max_lines]), font=font, fill=fill, spacing=spacing)


def vertical_gradient(image, top, bottom, y1, y2):
    top_rgb = tuple(int(top[i:i+2], 16) for i in (1, 3, 5))
    bottom_rgb = tuple(int(bottom[i:i+2], 16) for i in (1, 3, 5))
    for y in range(y1, y2):
        t = (y - y1) / max(1, y2 - y1 - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(top_rgb, bottom_rgb))
        ImageDraw.Draw(image).line((0, y, W, y), fill=color)


def generate(report, site_url, output):
    image = Image.new("RGB", (W, H), C["ivory"])
    draw = ImageDraw.Draw(image)
    vertical_gradient(image, C["burgundy"], C["red"], 0, 520)
    draw.ellipse((760, -320, 1280, 200), outline="#a85c68", width=2)
    text(draw, (68, 62), "HONG KONG IPO MARKET", 18, C["white"], True)
    text(draw, (68, 148), "港股市场", 64, C["white"], True)
    rr(draw, (48, 178, 770, 292), 0, C["cream"])
    text(draw, (72, 265), "审核动态周报", 88, "#711322", True)
    period = f"{short_date(report['meta']['weekStart'])}—{short_date(report['meta']['weekEnd'])}"
    text(draw, (68, 346), period, 38, C["white"], True)
    text(draw, (300, 345), f"数据截至 {report['meta']['asOf']}", 20, "#efd6db")
    draw.line((68, 382, 1012, 382), fill="#b96976", width=1)
    weekly = report["issuance"]["weekly"]
    headline = f"本周 {weekly['count']} 上市   {len(report['hkex']['weeklyPhips'])} 聆讯后资料集   {len(report['hkex']['weeklyApplicationProofs'])} 申请版本   {len(report['csrc']['weeklyNewReceived'])} 材料接收"
    text(draw, (68, 440), headline, 24, C["white"], True)
    qr = qrcode.make(site_url).convert("RGB").resize((96, 96))
    rr(draw, (852, 388, 1006, 506), 18, C["cream2"])
    rr(draw, (860, 396, 998, 498), 12, C["white"])
    image.paste(qr, (881, 399))
    text(draw, (929, 503), "扫描打开本站", 10, C["ruby"], True, "ma")

    y = 570
    def section(index, title_value, subtitle):
        nonlocal y
        rr(draw, (58, y, 124, y + 66), 17, C["ruby"])
        text(draw, (91, y + 42), index, 22, C["white"], True, "mm")
        text(draw, (146, y + 37), title_value, 38, C["ink"], True)
        text(draw, (146, y + 65), subtitle, 17, C["muted"])
        y += 105

    section("01", "发行上市情况", "港交所官方发行和行情数据")
    rr(draw, (58, y, 1022, y + 240), 24, C["white"], C["line"])
    text(draw, (84, y + 39), "本周新上市", 20, C["ruby"], True)
    text(draw, (988, y + 39), f"{weekly['count']}家", 18, C["ruby"], True, "ra")
    for label, x in zip(("公司", "募资额", "首日涨跌", "保荐人"), (84, 430, 620, 760)):
        text(draw, (x, y + 72), label, 13, C["muted"], True)
    for idx, item in enumerate(weekly["companies"]):
        yy = y + 112 + idx * 50
        if idx % 2 == 0:
            rr(draw, (72, yy - 28, 1008, yy + 14), 10, "#fffbfb")
        fit_text(draw, item["name"], (84, yy - 15, 405, yy + 15), 14, bold=True, max_lines=1)
        text(draw, (430, yy), money(item["fundraisingHkd100m"]), 15, bold=True)
        text(draw, (620, yy), pct(item["firstDayReturn"]), 16, C["red"] if item["firstDayReturn"] >= 0 else C["green"], True)
        fit_text(draw, item.get("sponsors") or "—", (760, yy - 15, 990, yy + 15), 12, C["muted"], max_lines=1)
    y += 270
    rr(draw, (58, y, 1022, y + 190), 24, C["white"], C["line"])
    text(draw, (84, y + 38), "年内概览", 20, C["ruby"], True)
    rr(draw, (84, y + 60, 362, y + 164), 16, C["ruby"])
    text(draw, (106, y + 91), "累计募资", 15, "#f0c9cf")
    text(draw, (106, y + 137), money(report["issuance"]["annual"]["fundraisingHkd100m"]), 28, C["white"], True)
    rr(draw, (382, y + 60, 602, y + 164), 16, "#fafbfc", C["line"])
    text(draw, (404, y + 91), "IPO / 介绍上市", 14, C["muted"])
    text(draw, (404, y + 137), f"{report['issuance']['annual']['count']}家", 30, C["ruby"], True)
    rr(draw, (622, y + 60, 998, y + 164), 16, "#fafbfc", C["line"])
    text(draw, (644, y + 88), "年内涨幅前五", 14, C["muted"], True)
    for idx, item in enumerate(report["issuance"]["annual"]["topPerformers"][:5]):
        text(draw, (644, y + 111 + idx * 16), f"{idx + 1}  {item['name'][:22]}", 11, bold=True)
        text(draw, (980, y + 111 + idx * 16), pct(item["latestReturn"]), 11, C["ruby"], True, "ra")
    y += 240

    section("02", "联交所审核动态", "有效申请及本周文件节点")
    rr(draw, (58, y, 508, y + 350), 24, C["white"], C["line"])
    text(draw, (84, y + 40), "有效申请", 18, C["ruby"], True)
    text(draw, (280, y + 175), report["hkex"]["activeCount"], 58, C["blue"], True, "mm")
    text(draw, (280, y + 215), "家", 18, C["muted"], True, "mm")
    text(draw, (110, y + 290), f"主板 {report['hkex']['mainBoardCount']}家", 18, C["blue"], True)
    text(draw, (318, y + 290), f"GEM {report['hkex']['gemCount']}家", 18, C["red"], True)
    for box_y, number, title_value, records in (
        (y, len(report["hkex"]["weeklyPhips"]), "本周聆讯后资料集", report["hkex"]["weeklyPhips"]),
        (y + 180, len(report["hkex"]["weeklyApplicationProofs"]), "本周申请版本", report["hkex"]["weeklyApplicationProofs"]),
    ):
        rr(draw, (530, box_y, 1022, box_y + 160), 24, C["white"], C["line"])
        text(draw, (562, box_y + 92), number, 50, C["ruby"], True)
        text(draw, (636, box_y + 52), title_value, 19, C["ruby"], True)
        fit_text(draw, " · ".join(x["company"] for x in records) or "暂无", (636, box_y + 77, 990, box_y + 145), 14, bold=True, max_lines=3)
    y += 410

    section("03", "中国证监会备案进度", "最新备案情况表时点数据")
    statuses = report["csrc"].get("statusCounts", {})
    stats = (("在表项目", report["csrc"]["recordCount"]), ("已接收", statuses.get("已接收", 0)), ("征求意见", statuses.get("征求意见", 0)), ("补充材料", statuses.get("补充材料", 0)))
    for idx, (label, value) in enumerate(stats):
        x = 58 + idx * 241
        rr(draw, (x, y, x + 224, y + 104), 17, C["ruby"])
        text(draw, (x + 18, y + 35), label, 14, "#f2cbd1")
        text(draw, (x + 18, y + 80), f"{value}家", 30, C["white"], True)
    y += 134
    rr(draw, (58, y, 558, y + 430), 24, C["white"], C["line"])
    text(draw, (84, y + 42), "当前状态分布", 20, C["ruby"], True)
    entries = sorted(statuses.items(), key=lambda x: x[1], reverse=True)
    maximum = max([v for _, v in entries] or [1])
    for idx, (label, value) in enumerate(entries):
        yy = y + 105 + idx * 76
        text(draw, (84, yy), label, 16, bold=True)
        rr(draw, (190, yy - 19, 470, yy + 5), 12, "#f0e5e7")
        rr(draw, (190, yy - 19, 190 + 280 * value / maximum, yy + 5), 12, C["ruby"])
        text(draw, (526, yy), f"{value}家", 16, C["ruby"], True, "ra")
    rr(draw, (580, y, 1022, y + 430), 24, C["white"], C["line"])
    text(draw, (606, y + 42), "本周新增接收", 20, C["ruby"], True)
    text(draw, (996, y + 42), f"{len(report['csrc']['weeklyNewReceived'])}家", 17, C["ruby"], True, "ra")
    for idx, item in enumerate(report["csrc"]["weeklyNewReceived"][:11]):
        text(draw, (606, y + 88 + idx * 30), item["company"][:26], 13, bold=True)
        text(draw, (994, y + 88 + idx * 30), item["receivedOn"], 12, C["muted"], anchor="ra")
    y += 485

    section("04", "严格数据来源", "仅使用港交所、中国证监会官方数据")
    for idx, item in enumerate(report["sources"][:8]):
        yy = y + idx * 62
        rr(draw, (58, yy, 1022, yy + 48), 12, C["white"], C["line"])
        text(draw, (78, yy + 30), item["label"], 14, bold=True)
        text(draw, (998, yy + 30), item.get("asOf") or "", 12, C["muted"], anchor="ra")
    draw.rectangle((0, 3290, W, H), fill=C["ink"])
    text(draw, (58, 3333), "港股市场审核动态周报 · VIVAIA THEME", 15, C["white"], True)
    text(draw, (58, 3365), "仅供信息参考，不构成投资建议", 12, "#aab4c5")
    text(draw, (1020, 3365), report["meta"]["asOf"], 12, "#aab4c5", anchor="ra")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "data" / "report.json"))
    parser.add_argument("--output", default=str(ROOT / "poster.png"))
    parser.add_argument("--site-url", required=True, help="Canonical URL encoded in the QR code")
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    generate(report, args.site_url, Path(args.output))
    print(json.dumps({"output": args.output, "siteUrl": args.site_url}, ensure_ascii=False))


if __name__ == "__main__":
    main()

