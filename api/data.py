"""
Vercel serverless function: Godo OpenHub API -> dashboard JSON.
14-day batch fetch, 5-min in-memory cache (Fluid Compute).
"""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict
from http.server import BaseHTTPRequestHandler

import requests as req_lib

API_URL = "https://openhub.godo.co.kr/godomall5/order/Order_Search.php"
PARTNER_KEY = os.environ.get("GODO_PARTNER_KEY", "JUY0JUM1cCU1RSVBNDYlQUNu")
API_KEY = os.environ.get("GODO_API_KEY", "JTI1JURCJTJDJURCJTdEbCVFQiVEM3IlMjd4SyUwNiVFNFQlQTclMjVMdlklQTJCJUUxJUU5JTBFJUJDLiVENCUxRUtHJUM0JTE0a2MlMjU=")
CACHE_TTL = 300
DAYS_BACK = 180
BATCH_DAYS = 14
PRODUCT_DAILY_CUTOFF_DAYS = 60

_cache = {"json": None, "ts": 0}


def clean_xml(data):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', data) if data else ""


def parse_num(s):
    if not s:
        return 0
    s = s.strip().replace(",", "").replace("'", "")
    try:
        return int(float(s))
    except ValueError:
        return 0


def fetch_orders(start_date, end_date):
    payload = {
        "partner_key": PARTNER_KEY,
        "key": API_KEY,
        "startDate": start_date,
        "endDate": end_date,
        "dateType": "payment",
    }
    try:
        resp = req_lib.post(API_URL, data=payload, timeout=30)
        if resp.status_code == 200:
            return clean_xml(resp.text)
    except Exception:
        pass
    return None


def parse_xml_orders(xml_text):
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    return_el = root.find("return")
    if return_el is None:
        return []

    order_lines = []
    for order in return_el.findall("order_data"):
        order_no = order.findtext("orderNo", "")
        order_info = order.find("orderInfoData")
        order_name = order_info.findtext("orderName", "") if order_info is not None else ""
        mem_id = order.findtext("memId", "")
        order_date = order.findtext("orderDate", "")
        mem_group = order.findtext("memGroupNm", "")
        payment_dt = order.findtext("paymentDt", "")
        settle_price = parse_num(order.findtext("settlePrice", "0"))

        delivery_map = {}
        for ddata in order.findall("orderDeliveryData"):
            dsno = ddata.findtext("sno", "")
            charge = parse_num(ddata.findtext("deliveryCharge", "0"))
            if dsno:
                delivery_map[dsno] = charge

        for g in order.findall("orderGoodsData"):
            price = parse_num(g.findtext("goodsPrice", "0"))
            opt_price = parse_num(g.findtext("optionPrice", "0"))
            order_lines.append({
                "order_no": order_no,
                "member_name": order_name,
                "member_id": mem_id,
                "order_date": order_date[:10] if len(order_date) >= 10 else order_date,
                "grade": mem_group,
                "product_code": g.findtext("goodsNo", ""),
                "product_name": g.findtext("goodsNm", ""),
                "qty": parse_num(g.findtext("goodsCnt", "0")),
                "price_with_option": price + opt_price,
                "total_order_amount": settle_price,
                "payment_date": payment_dt[:10] if len(payment_dt) >= 10 else payment_dt,
                "payment_hour": int(payment_dt[11:13]) if len(payment_dt) >= 13 and payment_dt[11:13].isdigit() else -1,
            })

        for a in order.findall("addGoodsData"):
            price = parse_num(a.findtext("goodsPrice", "0"))
            order_lines.append({
                "order_no": order_no,
                "member_name": order_name,
                "member_id": mem_id,
                "order_date": order_date[:10] if len(order_date) >= 10 else order_date,
                "grade": mem_group,
                "product_code": a.findtext("goodsNo", ""),
                "product_name": a.findtext("goodsNm", ""),
                "qty": parse_num(a.findtext("goodsCnt", "0")),
                "price_with_option": price,
                "total_order_amount": settle_price,
                "payment_date": payment_dt[:10] if len(payment_dt) >= 10 else payment_dt,
                "payment_hour": int(payment_dt[11:13]) if len(payment_dt) >= 13 and payment_dt[11:13].isdigit() else -1,
            })

    return order_lines


def crawl_all():
    end = datetime.now()
    start = end - timedelta(days=DAYS_BACK)
    all_lines = []
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=BATCH_DAYS - 1), end)
        xml = fetch_orders(
            current.strftime("%Y-%m-%d 00:00:00"),
            chunk_end.strftime("%Y-%m-%d 23:59:59"),
        )
        if xml:
            all_lines.extend(parse_xml_orders(xml))
        current = chunk_end + timedelta(days=1)
        time.sleep(0.2)
    return all_lines


def build_dashboard(order_lines):
    now = datetime.now()
    cutoff = (now - timedelta(days=PRODUCT_DAILY_CUTOFF_DAYS)).strftime("%Y-%m-%d")

    orders_by_no = {}
    for line in order_lines:
        ono = line["order_no"]
        if ono not in orders_by_no:
            orders_by_no[ono] = {
                "order_no": ono,
                "member_name": line["member_name"],
                "member_id": line["member_id"],
                "grade": line["grade"],
                "total_amount": line["total_order_amount"],
                "payment_date": line["payment_date"],
                "order_date": line["order_date"],
                "payment_hour": line.get("payment_hour", -1),
                "products": [],
            }
        orders_by_no[ono]["products"].append({
            "product_code": line["product_code"],
            "product_name": line["product_name"],
            "qty": line["qty"],
            "price_with_option": line["price_with_option"],
        })

    # daily_sales
    daily_map = defaultdict(lambda: {"order_count": 0, "product_codes": set(), "total_qty": 0, "amounts": []})
    for o in orders_by_no.values():
        dt = o["payment_date"] or o["order_date"]
        if not dt or dt < "2000-01-01":
            continue
        d = daily_map[dt]
        d["order_count"] += 1
        d["amounts"].append(o["total_amount"])
        for p in o["products"]:
            d["product_codes"].add(p["product_code"])
            d["total_qty"] += p["qty"]

    daily_sales = sorted([{
        "date": dt,
        "order_count": d["order_count"],
        "product_kinds": len(d["product_codes"]),
        "product_total_qty": d["total_qty"],
        "avg_order": round(sum(d["amounts"]) / len(d["amounts"])) if d["amounts"] else 0,
        "total_sales": sum(d["amounts"]),
    } for dt, d in daily_map.items()], key=lambda x: x["date"], reverse=True)

    # customers
    cust_map = defaultdict(lambda: {"orders": set(), "total_sales": 0, "last": "", "first": "9999-12-31", "name": "", "grade": ""})
    for o in orders_by_no.values():
        mid = o["member_id"]
        if not mid:
            continue
        c = cust_map[mid]
        c["name"] = o["member_name"]
        c["grade"] = o["grade"]
        c["orders"].add(o["order_no"])
        c["total_sales"] += o["total_amount"]
        pay_dt = o["payment_date"] or o["order_date"]
        if not pay_dt or pay_dt < "2000-01-01":
            continue
        if pay_dt > c["last"]:
            c["last"] = pay_dt
        if pay_dt < c["first"]:
            c["first"] = pay_dt

    def classify(order_count, total_sales, last_order):
        days = 999
        if last_order:
            try:
                days = (now - datetime.strptime(last_order[:10], "%Y-%m-%d")).days
            except Exception:
                pass
        if order_count > 0 and days <= 14 and order_count >= 5 and total_sales >= 2000000:
            return "champion"
        if order_count > 0 and days <= 30 and order_count >= 3:
            return "loyal"
        if order_count > 0 and days <= 60:
            return "promising"
        if order_count > 0 and days <= 120 and order_count >= 2:
            return "atrisk"
        if order_count > 0 and days <= 180:
            return "dormant"
        return "lost"

    buyers = sorted([{
        "id": mid,
        "name": c["name"],
        "grade": c["grade"],
        "segment": classify(len(c["orders"]), c["total_sales"], c["last"]),
        "total_sales": c["total_sales"],
        "order_count": len(c["orders"]),
        "last_order": c["last"][:10] if c["last"] else "",
        "first_order": c["first"][:10] if c["first"] != "9999-12-31" else "",
    } for mid, c in cust_map.items()], key=lambda x: -x["total_sales"])

    seg_counts = defaultdict(int)
    for b in buyers:
        seg_counts[b["segment"]] += 1

    # orders list
    orders = [{"d": o["payment_date"] or o["order_date"], "m": o["member_id"], "a": o["total_amount"]}
              for o in orders_by_no.values()
              if (o.get("payment_date") or o.get("order_date", "")) >= "2000-01-01"]

    # hourly
    hourly_map = defaultdict(lambda: defaultdict(lambda: {"c": 0, "s": 0}))
    for o in orders_by_no.values():
        dt = o["payment_date"] or o["order_date"]
        h = o.get("payment_hour", -1)
        if not dt or dt < "2000-01-01" or h < 0:
            continue
        hourly_map[dt][h]["c"] += 1
        hourly_map[dt][h]["s"] += o["total_amount"]

    hourly = []
    for dt in sorted(hourly_map):
        for h in range(24):
            d = hourly_map[dt].get(h)
            if d:
                hourly.append({"d": dt, "h": h, "s": d["s"], "c": d["c"]})

    # product_daily (60-day cutoff)
    pd_map = defaultdict(lambda: {"name": "", "orders": set(), "qty": 0, "amount": 0})
    for line in order_lines:
        pcode = line["product_code"]
        pay_dt = line["payment_date"] or line["order_date"]
        if not pcode or not pay_dt or pay_dt < cutoff:
            continue
        key = (pay_dt, pcode)
        p = pd_map[key]
        p["name"] = line["product_name"]
        p["orders"].add(line["order_no"])
        p["qty"] += line["qty"]
        p["amount"] += line["price_with_option"] * max(line["qty"], 1)

    product_daily = [{"d": k[0], "c": k[1], "n": p["name"][:30], "o": len(p["orders"]), "q": p["qty"], "a": p["amount"]}
                     for k, p in pd_map.items()]

    # products top 50
    prod_map = defaultdict(lambda: {"name": "", "orders": set(), "qty": 0, "amount": 0})
    for line in order_lines:
        pcode = line["product_code"]
        if not pcode:
            continue
        p = prod_map[pcode]
        p["name"] = line["product_name"]
        p["orders"].add(line["order_no"])
        p["qty"] += line["qty"]
        p["amount"] += line["price_with_option"] * max(line["qty"], 1)

    products = sorted([{"name": p["name"], "code": pc, "orders": len(p["orders"]), "qty": p["qty"], "amount": p["amount"]}
                       for pc, p in prod_map.items()], key=lambda x: -x["amount"])[:50]

    return {
        "crawl_meta": {"crawled_at": now.isoformat(), "source": "godomall-openhub-api-live"},
        "daily_sales": daily_sales,
        "buyers": buyers,
        "products": products,
        "segment_counts": dict(seg_counts),
        "orders": orders,
        "hourly": hourly,
        "product_daily": product_daily,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        now = time.time()
        if _cache["json"] and (now - _cache["ts"]) < CACHE_TTL:
            body = _cache["json"]
        else:
            lines = crawl_all()
            data = build_dashboard(lines)
            body = json.dumps(data, ensure_ascii=False)
            _cache["json"] = body
            _cache["ts"] = time.time()

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
