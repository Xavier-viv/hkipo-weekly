#!/usr/bin/env python3
"""Regression checks for automatic HKEX issue P/E extraction."""

from __future__ import annotations

from datetime import date

from fetch_data import Listing, derive_issue_pe_record, hkex_active_stock_ids


CASES = (
    ("06731", "本末科技", "2026-09-21", "2026-09-29", "NM（亏损）"),
    ("09607", "彤程新材", "2026-09-21", "2026-09-29", "46.2x"),
    ("03757", "罗博特科", "2026-09-21", "2026-09-29", "NM（亏损）"),
    ("03228", "景旺电子", "2026-09-21", "2026-09-29", "52.7x"),
    ("01256", "奕斯伟计算", "2026-09-28", "2026-10-09", "NM（亏损）"),
)


def main() -> None:
    stock_ids = hkex_active_stock_ids()
    for code, name, prospectus_date, listing_date, expected in CASES:
        listing = Listing(
            code=code,
            name=name,
            prospectus_date=date.fromisoformat(prospectus_date),
            listing_date=date.fromisoformat(listing_date),
            sponsors="",
            funds_hkd=1,
            offer_price=1,
        )
        actual = derive_issue_pe_record(listing, stock_ids[code])["display"]
        if actual != expected:
            raise RuntimeError(f"{code}: expected {expected}, got {actual}")
        print(f"{code}: {actual}")


if __name__ == "__main__":
    main()
