#!/usr/bin/env python3
"""
clover_export.py — Export full Clover order history (with itemized receipt
detail) to CSV for a date range, using your own merchant API token.

Why this exists: Clover's dashboard "Transactions" export gives you payments
but NOT line items. This pulls orders WITH line items, payments, discounts,
refunds, and customer info via the REST API, and writes two joinable CSVs.

------------------------------------------------------------------------------
SETUP (one time)
------------------------------------------------------------------------------
1. In your Clover dashboard, turn on two-factor auth (required for tokens).
2. Settings (gear) -> View all settings -> Business Operations -> API tokens
   -> Get Started. Grant READ on: Orders, Payments, Customers, Inventory.
   -> Create Token. Copy the token string.
3. Find your Merchant ID (mId): it's in the dashboard URL, and under
   Account & Setup. It's a ~13-char alphanumeric string.

------------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------------
  # Simplest: just run it. It will ask for your token, Merchant ID, and dates.
  python3 clover_export.py

  # Or pass the dates on the command line:
  python3 clover_export.py --start 2025-01-01 --end 2025-12-31

  # Repeat users can preset credentials as environment variables to skip the
  # prompts (optional):
  export CLOVER_API_TOKEN="paste-your-token-here"
  export CLOVER_MERCHANT_ID="yourMerchantId"

  # Whole ranges are auto-chunked into <=90-day windows for you.

  # Options:
  #   --outdir DIR     where to write CSVs (default: ./clover_export_<timestamp>)
  #   --region us|eu|la   (default: us -> api.clover.com)
  #   --tz  TIMEZONE   local tz for date boundaries & output (default America/Chicago)
  #   --format split|single|both   (default: split)

Outputs (depend on --format):
  split  (default): orders.csv      one row per order  (summary + payment + customer)
                    line_items.csv  one row per line item (join to orders on order_id)
  single:           report.csv      denormalized - one row per line item with ALL the
                                    order/payment/customer columns repeated; orders with
                                    no line items still get one row (item_* blank)
  both:             all three files

No third-party packages required — standard library only.
"""

import argparse
import contextlib
import csv
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None

REGION_HOSTS = {
    "us": "https://api.clover.com",
    "eu": "https://api.eu.clover.com",
    "la": "https://api.la.clover.com",
}

# Clover caps time-filtered order queries to a 90-day window per request.
WINDOW_DAYS = 90
PAGE_LIMIT = 1000            # max Clover allows
REQUEST_PAUSE = 0.2         # seconds between requests, be polite to rate limits
MAX_RETRIES = 5

# Fields to expand so each order carries its full receipt.
EXPAND = "lineItems,lineItems.modifications,discounts,payments,refunds,credits,customers"


def cents(v):
    """Clover stores money in integer cents. Return dollars (float) or ''."""
    if v is None or v == "":
        return ""
    try:
        return round(int(v) / 100.0, 2)
    except (ValueError, TypeError):
        return ""


def ms_to_local(ms, tz):
    if ms in (None, ""):
        return ""
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
        return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ""


def local_day_bounds(date_str, tz):
    """Return (start_ms, end_ms) covering the full local day(s) in a range."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.replace(tzinfo=tz)


def to_ms(dt):
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def http_get_json(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            if e.code == 401:
                sys.exit("ERROR 401 Unauthorized — check CLOVER_API_TOKEN and its "
                         "permissions.\n" + body)
            if e.code == 404:
                sys.exit("ERROR 404 Not Found — check CLOVER_MERCHANT_ID and --region.\n"
                         + body)
            if e.code == 429 or 500 <= e.code < 600:
                wait = min(2 ** attempt, 30)
                sys.stderr.write(f"  HTTP {e.code}, retry {attempt}/{MAX_RETRIES} "
                                 f"in {wait}s...\n")
                time.sleep(wait)
                last_err = e
                continue
            sys.exit(f"ERROR HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            wait = min(2 ** attempt, 30)
            sys.stderr.write(f"  Network error ({e.reason}), retry {attempt}/"
                             f"{MAX_RETRIES} in {wait}s...\n")
            time.sleep(wait)
            last_err = e
    sys.exit(f"ERROR: gave up after {MAX_RETRIES} retries. Last error: {last_err}")


def fetch_orders_window(host, mid, token, start_ms, end_ms):
    """Yield every order in [start_ms, end_ms], paging until exhausted."""
    offset = 0
    while True:
        params = [
            ("filter", f"createdTime>={start_ms}"),
            ("filter", f"createdTime<={end_ms}"),
            ("expand", EXPAND),
            ("limit", PAGE_LIMIT),
            ("offset", offset),
            ("orderBy", "createdTime ASC"),
        ]
        url = (f"{host}/v3/merchants/{mid}/orders?"
               + urllib.parse.urlencode(params, doseq=True))
        data = http_get_json(url, token)
        elements = data.get("elements", []) if isinstance(data, dict) else []
        for o in elements:
            yield o
        if len(elements) < PAGE_LIMIT:
            return
        offset += PAGE_LIMIT
        time.sleep(REQUEST_PAUSE)


def summarize_payments(order):
    pays = (order.get("payments") or {}).get("elements", []) or []
    total_paid = sum(int(p.get("amount") or 0) for p in pays)
    total_tip = sum(int(p.get("tipAmount") or 0) for p in pays)
    total_tax = sum(int(p.get("taxAmount") or 0) for p in pays)
    tenders, cards, last4s = [], [], []
    for p in pays:
        tender = (p.get("tender") or {}).get("label")
        if tender:
            tenders.append(tender)
        ct = p.get("cardTransaction") or {}
        if ct.get("cardType"):
            cards.append(ct["cardType"])
        if ct.get("last4"):
            last4s.append(ct["last4"])
    return {
        "payment_count": len(pays),
        "amount_paid": cents(total_paid),
        "tip": cents(total_tip),
        "tax_paid": cents(total_tax),
        "tenders": "; ".join(tenders),
        "card_types": "; ".join(cards),
        "card_last4": "; ".join(last4s),
    }


EMPTY_CUST = {"customer_name": "", "customer_email": "", "customer_phone": ""}


def _customer_record(c):
    """Flatten a full Clover customer object into our output fields.
    Clover stores names as firstName + lastName (there is no combined `name`
    field); email/phone require expand=emailAddresses,phoneNumbers."""
    name = " ".join(x for x in [c.get("firstName"), c.get("lastName")] if x).strip()
    emails = (c.get("emailAddresses") or {}).get("elements", []) or []
    phones = (c.get("phoneNumbers") or {}).get("elements", []) or []
    return {
        "customer_name": name,
        "customer_email": "; ".join(e.get("emailAddress", "") for e in emails),
        "customer_phone": "; ".join(p.get("phoneNumber", "") for p in phones),
    }


def build_customer_index(host, mid, token):
    """Fetch every customer once -> {id: {name,email,phone}}.

    Orders embed only a customer *reference* (id + href), so names and contact
    info must be resolved from the dedicated /customers endpoint.
    """
    index = {}
    offset = 0
    while True:
        params = [
            ("expand", "emailAddresses,phoneNumbers"),
            ("limit", PAGE_LIMIT),
            ("offset", offset),
        ]
        url = (f"{host}/v3/merchants/{mid}/customers?"
               + urllib.parse.urlencode(params, doseq=True))
        data = http_get_json(url, token)
        els = data.get("elements", []) if isinstance(data, dict) else []
        for c in els:
            cid = c.get("id")
            if cid:
                index[cid] = _customer_record(c)
        if len(els) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(REQUEST_PAUSE)
    return index


def summarize_customer(order, cust_index):
    custs = (order.get("customers") or {}).get("elements", []) or []
    if not custs:
        return dict(EMPTY_CUST)
    c = custs[0]
    cid = c.get("id")
    if cid and cid in cust_index:
        return dict(cust_index[cid])
    # Fallback in case a payload ever embeds the fields directly.
    return _customer_record(c)


def refund_total(order):
    refs = (order.get("refunds") or {}).get("elements", []) or []
    return sum(int(r.get("amount") or 0) for r in refs)


ORDER_COLS = [
    "order_id", "created_local", "modified_local", "state", "order_type",
    "currency", "order_total", "amount_paid", "tip", "tax_paid",
    "refund_total", "payment_count", "tenders", "card_types", "card_last4",
    "customer_name", "customer_email", "customer_phone",
    "employee", "note", "line_item_count",
]

LINE_COLS = [
    "order_id", "created_local", "line_item_id", "name", "price",
    "quantity_unitQty", "note", "modifications", "line_discounts",
    "printed", "refunded", "exchanged",
]


def line_rows(order, created_local):
    items = (order.get("lineItems") or {}).get("elements", []) or []
    for li in items:
        mods = (li.get("modifications") or {}).get("elements", []) or []
        mod_str = "; ".join(
            f"{m.get('name','')}"
            + (f" (+{cents(m.get('amount'))})" if m.get("amount") else "")
            for m in mods
        )
        discs = (li.get("discounts") or {}).get("elements", []) or []
        disc_str = "; ".join(
            f"{d.get('name','')}"
            + (f" (-{cents(d.get('amount'))})" if d.get("amount") else "")
            for d in discs
        )
        yield {
            "order_id": order.get("id", ""),
            "created_local": created_local,
            "line_item_id": li.get("id", ""),
            "name": li.get("name", ""),
            "price": cents(li.get("price")),
            "quantity_unitQty": li.get("unitQty", ""),
            "note": li.get("note", ""),
            "modifications": mod_str,
            "line_discounts": disc_str,
            "printed": li.get("printed", ""),
            "refunded": li.get("refunded", ""),
            "exchanged": li.get("exchanged", ""),
        }


def build_order_row(order, tz, cust_index):
    """One order-level row (ORDER_COLS), shared by every output format."""
    items = (order.get("lineItems") or {}).get("elements", []) or []
    row = {
        "order_id": order.get("id", ""),
        "created_local": ms_to_local(order.get("createdTime"), tz),
        "modified_local": ms_to_local(order.get("modifiedTime"), tz),
        "state": order.get("state", ""),
        "order_type": (order.get("orderType") or {}).get("label", ""),
        "currency": order.get("currency", ""),
        "order_total": cents(order.get("total")),
        "refund_total": cents(refund_total(order)),
        "employee": (order.get("employee") or {}).get("name", ""),
        "note": order.get("note", ""),
        "line_item_count": len(items),
    }
    row.update(summarize_payments(order))
    row.update(summarize_customer(order, cust_index))
    return row


# Denormalized report: every order column, plus the line-item columns (prefixed
# item_ so they don't collide with order-level `note`/`name`), one row per line
# item. Orders with no line items still emit one row (item_* left blank).
ITEM_COLS_DENORM = [
    "item_id", "item_name", "item_price", "item_qty_unitQty", "item_note",
    "item_modifications", "item_line_discounts",
    "item_printed", "item_refunded", "item_exchanged",
]
EMPTY_ITEM = {k: "" for k in ITEM_COLS_DENORM}
DENORM_COLS = ORDER_COLS + ITEM_COLS_DENORM


def _item_fields(line_row):
    """Map a line_rows() dict onto the prefixed denormalized item columns."""
    return {
        "item_id": line_row["line_item_id"],
        "item_name": line_row["name"],
        "item_price": line_row["price"],
        "item_qty_unitQty": line_row["quantity_unitQty"],
        "item_note": line_row["note"],
        "item_modifications": line_row["modifications"],
        "item_line_discounts": line_row["line_discounts"],
        "item_printed": line_row["printed"],
        "item_refunded": line_row["refunded"],
        "item_exchanged": line_row["exchanged"],
    }


def _resolve_date(value, label):
    """Validate a CLI-supplied date, or ask for one interactively."""
    if value:
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            sys.exit(f"'{value}' is not a valid date. Use the format 2025-01-31.")
    while True:
        val = input(f"Enter the {label} date (YYYY-MM-DD), e.g. 2025-01-01: ").strip()
        try:
            datetime.strptime(val, "%Y-%m-%d")
            return val
        except ValueError:
            print("  That's not a valid date. Please type it like 2025-01-31.")


def main():
    ap = argparse.ArgumentParser(description="Export Clover orders + itemized "
                                             "receipts to CSV.")
    ap.add_argument("--start", help="start date YYYY-MM-DD (inclusive); prompts if omitted")
    ap.add_argument("--end", help="end date YYYY-MM-DD (inclusive); prompts if omitted")
    ap.add_argument("--outdir", default=None, help="output directory")
    ap.add_argument("--region", default="us", choices=REGION_HOSTS.keys())
    ap.add_argument("--tz", default="America/Chicago", help="local timezone")
    ap.add_argument("--format", default="split", choices=["split", "single", "both"],
                    help="split = orders.csv + line_items.csv (default); "
                         "single = one denormalized report.csv (one row per line "
                         "item, all columns repeated); both = all three files.")
    args = ap.parse_args()

    # Credentials: use environment variables if present, otherwise ask.
    # (getpass hides the token so it isn't shown on screen or saved in history.)
    token = os.environ.get("CLOVER_API_TOKEN")
    if not token:
        token = getpass.getpass("Paste your Clover API token (it won't show as you type): ").strip()
    mid = os.environ.get("CLOVER_MERCHANT_ID")
    if not mid:
        mid = input("Enter your Clover Merchant ID: ").strip()
    if not token or not mid:
        sys.exit("A Clover API token and Merchant ID are both required.")

    if ZoneInfo is None:
        sys.exit("Python 3.9+ required (needs zoneinfo).")
    tz = ZoneInfo(args.tz)
    host = REGION_HOSTS[args.region]

    start = _resolve_date(args.start, "START")
    end = _resolve_date(args.end, "END")
    start_dt = local_day_bounds(start, tz)
    # end is inclusive: go to the very end of that local day
    end_dt = local_day_bounds(end, tz) + timedelta(days=1) - timedelta(milliseconds=1)
    if end_dt < start_dt:
        sys.exit("The end date is before the start date.")

    outdir = args.outdir or f"clover_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(outdir, exist_ok=True)
    orders_path = os.path.join(outdir, "orders.csv")
    lines_path = os.path.join(outdir, "line_items.csv")
    report_path = os.path.join(outdir, "report.csv")

    want_split = args.format in ("split", "both")
    want_single = args.format in ("single", "both")

    sys.stderr.write("Building customer index (names/email/phone)...\n")
    cust_index = build_customer_index(host, mid, token)
    sys.stderr.write(f"  {len(cust_index)} customers loaded.\n")

    n_orders = 0
    n_lines = 0
    seen_ids = set()

    with contextlib.ExitStack() as stack:
        ow = lw = dw = None
        if want_split:
            of = stack.enter_context(open(orders_path, "w", newline="", encoding="utf-8"))
            lf = stack.enter_context(open(lines_path, "w", newline="", encoding="utf-8"))
            ow = csv.DictWriter(of, fieldnames=ORDER_COLS)
            lw = csv.DictWriter(lf, fieldnames=LINE_COLS)
            ow.writeheader()
            lw.writeheader()
        if want_single:
            rf = stack.enter_context(open(report_path, "w", newline="", encoding="utf-8"))
            dw = csv.DictWriter(rf, fieldnames=DENORM_COLS)
            dw.writeheader()

        # Walk the range in <=90-day windows.
        win_start = start_dt
        while win_start <= end_dt:
            win_end = min(win_start + timedelta(days=WINDOW_DAYS) - timedelta(milliseconds=1),
                          end_dt)
            s_ms, e_ms = to_ms(win_start), to_ms(win_end)
            sys.stderr.write(f"Window {win_start.date()} -> {win_end.date()} ...\n")

            for order in fetch_orders_window(host, mid, token, s_ms, e_ms):
                oid = order.get("id")
                if oid in seen_ids:      # windows are disjoint, but be safe
                    continue
                seen_ids.add(oid)

                order_row = build_order_row(order, tz, cust_index)
                lrows = list(line_rows(order, order_row["created_local"]))
                n_orders += 1
                n_lines += len(lrows)

                if ow is not None:
                    ow.writerow(order_row)
                    for lr in lrows:
                        lw.writerow(lr)
                if dw is not None:
                    if lrows:
                        for lr in lrows:
                            dw.writerow({**order_row, **_item_fields(lr)})
                    else:
                        # Keep orders with no line items in the report.
                        dw.writerow({**order_row, **EMPTY_ITEM})

            win_start = win_end + timedelta(milliseconds=1)
            time.sleep(REQUEST_PAUSE)

    sys.stderr.write(f"\nDone. {n_orders} orders, {n_lines} line items.\n")
    if want_split:
        print(orders_path)
        print(lines_path)
    if want_single:
        print(report_path)


if __name__ == "__main__":
    main()
