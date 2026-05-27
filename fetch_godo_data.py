"""
고도몰 OpenHub API에서 B2B 주문 데이터를 직접 조회하여 JSON으로 변환.

API: https://openhub.godo.co.kr/godomall5/order/Order_Search.php
인증: partner_key + key (환경변수)
응답: XML
"""
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

try:
    import requests
except ImportError:
    print("ERROR: requests 패키지가 필요합니다. pip install requests")
    sys.exit(1)

API_URL = "https://openhub.godo.co.kr/godomall5/order/Order_Search.php"
PARTNER_KEY = os.environ.get("GODO_PARTNER_KEY", "JUY0JUM1cCU1RSVBNDYlQUNu")
API_KEY = os.environ.get("GODO_API_KEY", "JTI1JURCJTJDJURCJTdEbCVFQiVEM3IlMjd4SyUwNiVFNFQlQTclMjVMdlklQTJCJUUxJUU5JTBFJUJDLiVENCUxRUtHJUM0JTE0a2MlMjU=")


def log(msg):
    print(f"[fetch] {msg}", flush=True)


def clean_xml(data):
    if not data:
        return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', data)


def parse_num(s):
    if not s:
        return 0
    s = s.strip().replace(",", "").replace("'", "")
    try:
        return int(float(s))
    except ValueError:
        return 0


def fetch_orders(start_date, end_date):
    """고도몰 OpenHub API 호출 (하루 단위)."""
    payload = {
        "partner_key": PARTNER_KEY,
        "key": API_KEY,
        "startDate": start_date,
        "endDate": end_date,
        "dateType": "order",
    }
    try:
        resp = requests.post(API_URL, data=payload, timeout=30)
        if resp.status_code == 200:
            return clean_xml(resp.text)
        else:
            log(f"  API {resp.status_code} for {start_date}")
            return None
    except Exception as e:
        log(f"  API error for {start_date}: {e}")
        return None


def parse_xml_orders(xml_text):
    """XML 응답에서 주문 데이터 파싱 (Apps Script 로직 그대로 재현)."""
    if not xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log(f"  XML parse error: {e}")
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
        use_deposit = parse_num(order.findtext("useDeposit", "0"))
        use_mileage = parse_num(order.findtext("useMileage", "0"))
        total_goods_dc = parse_num(order.findtext("totalGoodsDcPrice", "0"))
        total_member_dc = parse_num(order.findtext("totalMemberDcPrice", "0"))
        total_coupon_goods_dc = parse_num(order.findtext("totalCouponGoodsDcPrice", "0"))
        total_coupon_order_dc = parse_num(order.findtext("totalCouponOrderDcPrice", "0"))
        total_coupon_delivery_dc = parse_num(order.findtext("totalCouponDeliveryDcPrice", "0"))
        total_delivery = parse_num(order.findtext("totalDeliveryCharge", "0"))
        settle_price = parse_num(order.findtext("settlePrice", "0"))

        # 배송비 맵
        delivery_map = {}
        for ddata in order.findall("orderDeliveryData"):
            dsno = ddata.findtext("sno", "")
            charge = parse_num(ddata.findtext("deliveryCharge", "0"))
            if dsno:
                delivery_map[dsno] = charge

        # 본상품
        for g in order.findall("orderGoodsData"):
            price = parse_num(g.findtext("goodsPrice", "0"))
            opt_price = parse_num(g.findtext("optionPrice", "0"))
            dsno = g.findtext("orderDeliverySno", "")

            order_lines.append({
                "order_no": order_no,
                "member_name": order_name,
                "member_id": mem_id,
                "order_date": order_date[:10] if len(order_date) >= 10 else order_date,
                "grade": mem_group,
                "item_no": g.findtext("sno", ""),
                "status": g.findtext("orderStatus", ""),
                "product_code": g.findtext("goodsNo", ""),
                "product_name": g.findtext("goodsNm", ""),
                "qty": parse_num(g.findtext("goodsCnt", "0")),
                "price": price,
                "option_price": opt_price,
                "price_with_option": price + opt_price,
                "total_order_amount": settle_price,
                "delivery_fee": delivery_map.get(dsno, 0),
                "total_delivery_fee": total_delivery,
                "deposit_used": use_deposit,
                "mileage_used": use_mileage,
                "goods_discount": total_goods_dc,
                "member_discount": total_member_dc,
                "payment_date": payment_dt[:10] if len(payment_dt) >= 10 else payment_dt,
            })

        # 추가상품
        for a in order.findall("addGoodsData"):
            price = parse_num(a.findtext("goodsPrice", "0"))
            dsno = a.findtext("orderDeliverySno", "")

            order_lines.append({
                "order_no": order_no,
                "member_name": order_name,
                "member_id": mem_id,
                "order_date": order_date[:10] if len(order_date) >= 10 else order_date,
                "grade": mem_group,
                "item_no": a.findtext("sno", ""),
                "status": a.findtext("orderStatus", ""),
                "product_code": a.findtext("goodsNo", ""),
                "product_name": a.findtext("goodsNm", ""),
                "qty": parse_num(a.findtext("goodsCnt", "0")),
                "price": price,
                "option_price": 0,
                "price_with_option": price,
                "total_order_amount": settle_price,
                "delivery_fee": delivery_map.get(dsno, 0),
                "total_delivery_fee": total_delivery,
                "deposit_used": use_deposit,
                "mileage_used": use_mileage,
                "goods_discount": total_goods_dc,
                "member_discount": total_member_dc,
                "payment_date": payment_dt[:10] if len(payment_dt) >= 10 else payment_dt,
            })

    return order_lines


def crawl_date_range(start, end):
    """날짜 범위를 하루씩 순회하며 API 호출."""
    all_lines = []
    current = start
    while current <= end:
        day_start = current.strftime("%Y-%m-%d 00:00:00")
        day_end = current.strftime("%Y-%m-%d 23:59:59")

        xml = fetch_orders(day_start, day_end)
        if xml:
            lines = parse_xml_orders(xml)
            log(f"  {current.strftime('%Y-%m-%d')}: {len(lines)} lines")
            all_lines.extend(lines)
        else:
            log(f"  {current.strftime('%Y-%m-%d')}: no data")

        current += timedelta(days=1)
        time.sleep(0.3)

    return all_lines


def aggregate(order_lines):
    """주문 라인 → 일별매출/고객별/상품별/주문목록 집계."""
    # 주문번호별 중복 제거 (총 주문금액은 주문 단위)
    orders_by_no = {}
    for line in order_lines:
        ono = line["order_no"]
        if ono not in orders_by_no:
            orders_by_no[ono] = {
                "order_no": ono,
                "member_name": line["member_name"],
                "member_id": line["member_id"],
                "order_date": line["order_date"],
                "grade": line["grade"],
                "status": line["status"],
                "total_amount": line["total_order_amount"],
                "payment_date": line["payment_date"],
                "products": [],
            }
        orders_by_no[ono]["products"].append({
            "product_code": line["product_code"],
            "product_name": line["product_name"],
            "qty": line["qty"],
            "price_with_option": line["price_with_option"],
        })

    # === daily_sales ===
    daily_map = defaultdict(lambda: {"order_count": 0, "product_codes": set(), "total_qty": 0, "amounts": []})
    for ono, order in orders_by_no.items():
        dt = order["order_date"]
        if not dt:
            continue
        d = daily_map[dt]
        d["order_count"] += 1
        d["amounts"].append(order["total_amount"])
        for p in order["products"]:
            d["product_codes"].add(p["product_code"])
            d["total_qty"] += p["qty"]

    daily_sales = []
    for dt in sorted(daily_map.keys(), reverse=True):
        d = daily_map[dt]
        amounts = d["amounts"]
        total = sum(amounts)
        daily_sales.append({
            "date": dt,
            "order_count": d["order_count"],
            "product_kinds": len(d["product_codes"]),
            "product_total_qty": d["total_qty"],
            "min_order": min(amounts) if amounts else 0,
            "max_order": max(amounts) if amounts else 0,
            "avg_order": round(total / len(amounts)) if amounts else 0,
            "total_sales": total,
        })

    # === customer_sales ===
    cust_map = defaultdict(lambda: {"orders": set(), "total_sales": 0, "last_order_date": "", "name": "", "grade": ""})
    for ono, order in orders_by_no.items():
        mid = order["member_id"]
        if not mid:
            continue
        c = cust_map[mid]
        c["name"] = order["member_name"]
        c["grade"] = order["grade"]
        c["orders"].add(ono)
        c["total_sales"] += order["total_amount"]
        if order["order_date"] > c["last_order_date"]:
            c["last_order_date"] = order["order_date"]

    customer_sales = []
    for mid, c in cust_map.items():
        customer_sales.append({
            "member_id": mid,
            "name": c["name"],
            "grade": c["grade"],
            "order_count": len(c["orders"]),
            "total_sales": c["total_sales"],
            "last_order_date": c["last_order_date"],
        })

    customers = [{"member_id": mid, "name": c["name"], "grade": c["grade"]} for mid, c in cust_map.items()]

    # === product_sales ===
    prod_map = defaultdict(lambda: {"name": "", "orders": set(), "total_qty": 0, "total_amount": 0})
    for line in order_lines:
        pcode = line["product_code"]
        if not pcode:
            continue
        p = prod_map[pcode]
        p["name"] = line["product_name"]
        p["orders"].add(line["order_no"])
        p["total_qty"] += line["qty"]
        p["total_amount"] += line["price_with_option"] * max(line["qty"], 1)

    product_sales = sorted(
        [{"product_name": p["name"], "product_code": pcode, "order_count": len(p["orders"]),
          "total_qty": p["total_qty"], "total_amount": p["total_amount"]}
         for pcode, p in prod_map.items()],
        key=lambda x: -x["total_amount"]
    )

    # === orders list ===
    orders_list = sorted(
        [{"order_number": ono, "member_name": o["member_name"], "member_id": o["member_id"],
          "order_date": o["order_date"], "total_amount": o["total_amount"], "status": o["status"],
          "grade": o["grade"], "payment_date": o["payment_date"], "item_count": len(o["products"])}
         for ono, o in orders_by_no.items()],
        key=lambda x: x["order_date"], reverse=True
    )

    return {
        "daily_sales": daily_sales,
        "customers": customers,
        "customer_sales": customer_sales,
        "product_sales": product_sales,
        "orders": orders_list,
    }


def main():
    output_path = os.environ.get("OUTPUT_JSON", "godo_b2b_data.json")

    # 조회 기간: 기본 180일 (환경변수로 조정 가능)
    days_back = int(os.environ.get("CRAWL_DAYS", "180"))
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    # 증분 모드: 기존 데이터가 있으면 최근 데이터만 갱신
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_dates = {d["date"] for d in existing.get("daily_sales", [])}
        if existing_dates:
            latest = max(existing_dates)
            incremental_start = datetime.strptime(latest, "%Y-%m-%d") - timedelta(days=3)
            start_date = incremental_start
            log(f"Incremental mode: from {start_date.strftime('%Y-%m-%d')} (latest={latest})")
    else:
        existing = None

    log(f"Crawling {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} ({(end_date-start_date).days} days)")

    all_lines = crawl_date_range(start_date, end_date)
    log(f"Total: {len(all_lines)} order lines")

    if not all_lines and not existing:
        log("ERROR: No data fetched and no existing data")
        sys.exit(1)

    result = aggregate(all_lines)

    # 기존 데이터와 병합
    if existing:
        existing_date_map = {d["date"]: d for d in existing.get("daily_sales", [])}
        for d in result["daily_sales"]:
            existing_date_map[d["date"]] = d
        result["daily_sales"] = sorted(existing_date_map.values(), key=lambda x: x["date"], reverse=True)

    result["crawl_meta"] = {
        "crawled_at": datetime.now().isoformat(),
        "source": "godomall-openhub-api",
        "mode": "incremental" if existing else "full",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log(f"\n=== DONE ===")
    log(f"Daily: {len(result['daily_sales'])}, Customers: {len(result['customers'])}, "
        f"Products: {len(result['product_sales'])}, Orders: {len(result['orders'])}")
    log(f"Saved to {output_path} ({os.path.getsize(output_path):,} bytes)")


if __name__ == "__main__":
    main()
