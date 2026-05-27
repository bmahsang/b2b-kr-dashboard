import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open("godo_b2b_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

daily = data["daily_sales"]
customers = data["customers"]
customer_sales = data["customer_sales"]
products = data["product_sales"][:50]
orders = data["orders"]

# Build customer map with sales data
cust_map = {}
for c in customers:
    key = c["member_id"]
    cust_map[key] = {**c, "total_sales": 0, "order_count": 0, "last_order_date": None}

for cs in customer_sales:
    key = cs["member_id"]
    if key in cust_map:
        cust_map[key]["total_sales"] = cs["total_sales"]
        cust_map[key]["order_count"] = cs["order_count"]
        cust_map[key]["last_order_date"] = cs["last_order_date"]
    else:
        cust_map[key] = {
            "member_id": cs["member_id"], "name": cs["name"],
            "grade": cs.get("grade", ""),
            "total_sales": cs["total_sales"],
            "order_count": cs["order_count"],
            "last_order_date": cs["last_order_date"]
        }

now = datetime.now()

# RFM-based segment classification (no login data for godomall)
def classify(c):
    has_order = c["order_count"] > 0
    sales = c["total_sales"]
    last_order = c.get("last_order_date", "")

    days_since_order = 999
    if last_order:
        try:
            lo = datetime.strptime(last_order[:10], "%Y-%m-%d")
            days_since_order = (now - lo).days
        except:
            pass

    if has_order and days_since_order <= 14 and c["order_count"] >= 5 and sales >= 2000000:
        return "champion"
    elif has_order and days_since_order <= 30 and c["order_count"] >= 3:
        return "loyal"
    elif has_order and days_since_order <= 60:
        return "promising"
    elif has_order and days_since_order <= 120 and c["order_count"] >= 2:
        return "atrisk"
    elif has_order and days_since_order <= 180:
        return "dormant"
    elif has_order and days_since_order > 180:
        return "lost"
    elif not has_order:
        return "lost"
    else:
        return "promising"

for key in cust_map:
    cust_map[key]["segment"] = classify(cust_map[key])

buyer_list = sorted(cust_map.values(), key=lambda x: -x["total_sales"])

# Stats
seg_counts = defaultdict(int)
for b in buyer_list:
    seg_counts[b["segment"]] += 1

# Prepare JSON for embedding
dashboard_data = {
    "crawl_meta": data["crawl_meta"],
    "daily_sales": daily,
    "buyers": [{
        "id": b["member_id"],
        "name": b.get("name", ""),
        "grade": b.get("grade", ""),
        "segment": b["segment"],
        "total_sales": b["total_sales"],
        "order_count": b["order_count"],
        "last_order": (b.get("last_order_date", "") or "")[:10],
    } for b in buyer_list],
    "products": [{
        "name": p["product_name"],
        "code": p["product_code"],
        "orders": p["order_count"],
        "qty": p["total_qty"],
        "amount": p["total_amount"],
    } for p in products],
    "segment_counts": dict(seg_counts),
}

data_json = json.dumps(dashboard_data, ensure_ascii=False)
print(f"Data prepared: {len(buyer_list)} buyers, {len(daily)} days, {len(products)} products")
print(f"Segments: {dict(seg_counts)}")

# Generate HTML
html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BiteMe KR B2B Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root {{
  --navy:#0f1923;--navy-mid:#1a2736;--sidebar-w:220px;
  --accent:#4a90d9;--accent-hover:#3a7bc8;--accent-bg:rgba(74,144,217,0.08);
  --danger:#ef4444;--danger-bg:rgba(239,68,68,0.08);
  --warning:#f59e0b;--warning-bg:rgba(245,158,11,0.08);
  --success:#22c55e;--success-bg:rgba(34,197,94,0.08);
  --purple:#8b5cf6;--purple-bg:rgba(139,92,246,0.08);
  --bg:#f1f5f9;--card:#fff;--text:#1e293b;--text2:#64748b;--text3:#94a3b8;
  --border:#e2e8f0;--radius:12px;
  --shadow:0 1px 3px rgba(0,0,0,0.04),0 1px 2px rgba(0,0,0,0.06);
  --font:'Pretendard','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;display:flex}}

.sidebar{{width:var(--sidebar-w);background:var(--navy);color:#cbd5e1;position:fixed;top:0;left:0;bottom:0;display:flex;flex-direction:column;z-index:200}}
.sidebar-hdr{{padding:18px 16px 14px;border-bottom:1px solid rgba(255,255,255,0.06)}}
.sidebar-logo{{font-size:18px;font-weight:800;color:#fff}}.sidebar-logo span{{color:var(--accent)}}
.sidebar-sub{{font-size:10px;color:#475569;margin-top:2px;letter-spacing:.5px}}
.sidebar-nav{{flex:1;padding:10px 0;overflow-y:auto}}
.nav-sec{{padding:8px 16px 4px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#475569}}
.nav-item{{display:flex;align-items:center;gap:8px;padding:8px 16px;font-size:12px;cursor:pointer;border-left:3px solid transparent;color:#94a3b8;transition:.2s}}
.nav-item:hover{{background:rgba(255,255,255,.04);color:#e2e8f0}}
.nav-item.active{{background:rgba(74,144,217,.1);color:#fff;border-left-color:var(--accent)}}
.nav-item .badge{{margin-left:auto;background:var(--danger);color:#fff;font-size:9px;font-weight:700;padding:2px 6px;border-radius:8px}}
.sidebar-ft{{padding:12px 16px;border-top:1px solid rgba(255,255,255,.06);font-size:10px;color:#475569}}

.main{{margin-left:var(--sidebar-w);flex:1;min-height:100vh}}
.topbar{{background:var(--card);border-bottom:1px solid var(--border);padding:0 24px;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}}
.topbar h2{{font-size:15px;font-weight:700}}
.topbar-meta{{font-size:11px;color:var(--text3)}}
.topbar-r{{display:flex;align-items:center;gap:10px}}
.btn{{padding:6px 14px;border-radius:8px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid var(--border);background:#fff;color:var(--text);transition:.2s;display:inline-flex;align-items:center;gap:5px;white-space:nowrap}}
.btn:hover{{background:var(--bg)}}.btn-primary{{background:var(--accent);color:#fff;border-color:var(--accent)}}.btn-sm{{padding:4px 9px;font-size:10px}}

.content{{padding:20px 24px}}
.kpi-row{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:18px}}
.kpi{{background:var(--card);border-radius:var(--radius);padding:16px 18px;box-shadow:var(--shadow);border:1px solid var(--border);border-top:3px solid var(--accent)}}
.kpi.green{{border-top-color:var(--success)}}.kpi.amber{{border-top-color:var(--warning)}}.kpi.red{{border-top-color:var(--danger)}}.kpi.purple{{border-top-color:var(--purple)}}
.kpi-label{{font-size:10px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
.kpi-val{{font-size:24px;font-weight:800;letter-spacing:-.5px}}
.kpi-sub{{display:flex;align-items:center;gap:5px;margin-top:6px;font-size:11px}}
.chg{{font-weight:700;padding:2px 6px;border-radius:4px;font-size:10px}}
.chg.up{{color:var(--success);background:var(--success-bg)}}.chg.down{{color:var(--danger);background:var(--danger-bg)}}
.kpi-desc{{color:var(--text3);font-size:10px}}

.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}}
.grid-73{{display:grid;grid-template-columns:7fr 3fr;gap:14px;margin-bottom:18px}}
.card{{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);border:1px solid var(--border);overflow:hidden}}
.card-hdr{{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}}
.card-hdr h3{{font-size:13px;font-weight:700}}.card-hdr .meta{{font-size:10px;color:var(--text3)}}
.card-body{{padding:18px}}.card-body.np{{padding:0}}
.chart-w{{position:relative;height:260px}}
.chart-sm{{position:relative;height:200px}}

.seg-item{{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:8px;background:var(--bg);margin-bottom:6px;cursor:pointer;transition:.2s}}
.seg-item:hover{{background:#e2e8f0}}
.seg-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.seg-info{{flex:1}}.seg-name{{font-size:12px;font-weight:600}}.seg-desc{{font-size:10px;color:var(--text3)}}
.seg-ct{{font-size:15px;font-weight:800;text-align:right}}.seg-pct{{font-size:10px;color:var(--text3)}}

.ins{{padding:12px 14px;border-radius:8px;border-left:4px solid;margin-bottom:8px}}
.ins.high{{border-color:var(--danger);background:var(--danger-bg)}}.ins.med{{border-color:var(--warning);background:var(--warning-bg)}}
.ins.opp{{border-color:var(--success);background:var(--success-bg)}}.ins.low{{border-color:var(--accent);background:var(--accent-bg)}}
.ins-badge{{font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;color:#fff}}
.ins.high .ins-badge{{background:var(--danger)}}.ins.med .ins-badge{{background:var(--warning)}}.ins.opp .ins-badge{{background:var(--success)}}
.ins-title{{font-size:12px;font-weight:700;margin:4px 0 2px}}.ins-desc{{font-size:11px;color:var(--text2);line-height:1.5}}

table{{width:100%;border-collapse:collapse}}
thead th{{padding:8px 12px;text-align:left;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;color:var(--text3);background:#fafbfc;border-bottom:1px solid var(--border);white-space:nowrap}}
tbody td{{padding:8px 12px;font-size:12px;border-bottom:1px solid #f1f5f9}}
tbody tr:hover{{background:#f8fafc}}

.badge{{display:inline-block;padding:2px 8px;border-radius:5px;font-size:10px;font-weight:700}}
.badge-d{{background:var(--danger-bg);color:var(--danger)}}.badge-w{{background:var(--warning-bg);color:#d97706}}
.badge-s{{background:var(--success-bg);color:#16a34a}}.badge-i{{background:var(--accent-bg);color:var(--accent)}}
.badge-p{{background:var(--purple-bg);color:var(--purple)}}.badge-m{{background:var(--bg);color:var(--text3)}}
.pri{{font-weight:800;font-size:10px;padding:2px 7px;border-radius:4px;color:#fff}}
.pri.p0{{background:var(--danger)}}.pri.p1{{background:var(--warning)}}.pri.p2{{background:var(--accent)}}

.tabs{{display:flex;border-bottom:2px solid var(--border);padding:0 18px;flex-wrap:wrap}}
.tab{{padding:10px 14px;font-size:12px;font-weight:600;color:var(--text3);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:.2s;white-space:nowrap}}
.tab:hover{{color:var(--text)}}.tab.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.tab .tb{{margin-left:4px;font-size:9px;background:var(--bg);padding:1px 5px;border-radius:3px}}

.search-input{{padding:6px 10px 6px 30px;border:1px solid var(--border);border-radius:7px;font-size:11px;outline:none;width:180px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85zm-5.242.656a5 5 0 1 1 0-10 5 5 0 0 1 0 10z'/%3E%3C/svg%3E") no-repeat 8px center}}
.search-input:focus{{border-color:var(--accent)}}
.fg{{display:flex;flex-direction:column;gap:2px}}.fg label{{font-size:10px;color:var(--text3);font-weight:600;letter-spacing:.3px}}
.f-sel{{padding:4px 6px;border:1px solid var(--border);border-radius:5px;font-size:11px;background:var(--card);color:var(--text);width:48px}}
.f-inp{{padding:4px 8px;border:1px solid var(--border);border-radius:5px;font-size:11px;width:72px;outline:none;background:var(--card);color:var(--text)}}.f-inp:focus{{border-color:var(--accent)}}
.f-u{{font-size:10px;color:var(--text3);align-self:center}}
.preset{{padding:6px 14px;border-radius:10px;font-size:11px;border:1px solid var(--border);background:var(--card);cursor:pointer;color:var(--text2);transition:all .15s;line-height:1.4}}
.preset:hover{{border-color:var(--accent);color:var(--accent)}}.preset.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.preset .p-desc{{font-size:9px;opacity:.65;font-weight:400;display:block}}.preset.active .p-desc{{opacity:.85}}
.filter-count{{font-size:11px;color:var(--accent);font-weight:600}}

.strip{{background:linear-gradient(135deg,var(--navy),var(--navy-mid));color:#fff;border-radius:var(--radius);padding:14px 24px;margin-bottom:18px;display:flex;align-items:center;gap:0;font-size:13px;line-height:1.5;flex-wrap:wrap}}
.strip strong{{color:var(--accent)}}
.strip-item{{padding:0 14px}}.strip-item:first-child{{padding-left:0}}
.strip-sep{{color:#475569;font-size:11px;user-select:none}}
.strip-sub{{font-size:11px;color:#94a3b8;margin-left:4px}}

.month-sel{{padding:5px 10px;border:1px solid var(--border);border-radius:7px;font-size:12px;font-weight:600;outline:none;background:#fff}}
.month-sel:focus{{border-color:var(--accent)}}
.detail-kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}}
.detail-table{{max-height:500px;overflow-y:auto}}

@media(max-width:1200px){{.kpi-row{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:1024px){{.grid-2,.grid-73{{grid-template-columns:1fr}}.kpi-row{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:768px){{.sidebar{{display:none}}.main{{margin-left:0}}.kpi-row{{grid-template-columns:1fr}}}}
::-webkit-scrollbar{{width:5px}}::-webkit-scrollbar-thumb{{background:#cbd5e1;border-radius:3px}}

.lang-toggle{{display:flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;font-size:11px;font-weight:600}}
.lang-btn{{padding:5px 10px;cursor:pointer;background:#fff;color:var(--text3);border:none;transition:.2s;display:flex;align-items:center;gap:3px}}
.lang-btn:first-child{{border-right:1px solid var(--border)}}
.lang-btn:hover{{background:var(--bg)}}
.lang-btn.active{{background:var(--accent);color:#fff}}
</style>
</head>
<body>

<aside class="sidebar">
  <div class="sidebar-hdr"><div class="sidebar-logo">Bite<span>Me</span> KR</div><div class="sidebar-sub">B2B Sales Intelligence</div></div>
  <nav class="sidebar-nav" id="sidebarNav"></nav>
  <div class="sidebar-ft">
    <div style="margin-top:3px">Powered by Claude Code</div>
  </div>
</aside>

<div class="main">
  <div class="topbar">
    <div><h2 id="topTitle"></h2><span class="topbar-meta" id="topMeta"></span></div>
    <div class="topbar-r">
      <span id="crawlTime" style="font-size:11px;color:#94a3b8;margin-right:12px"></span>
      <button class="btn" onclick="exportCSV()">CSV</button>
    </div>
  </div>
  <div class="content">
    <div id="pageDash">
      <div class="strip" id="summaryStrip"></div>
      <div class="kpi-row" id="kpiRow"></div>
      <div class="grid-73">
        <div class="card"><div class="card-hdr"><h3 id="hdrTrend"></h3><div class="meta" id="hdrTrendMeta"></div></div><div class="card-body"><div class="chart-w"><canvas id="salesChart"></canvas></div></div></div>
        <div class="card"><div class="card-hdr"><h3 id="hdrSeg"></h3><div class="meta" id="totalBuyers"></div></div><div class="card-body"><div class="chart-sm"><canvas id="segChart"></canvas></div><div id="segList" style="margin-top:12px"></div></div></div>
      </div>
      <div class="grid-2">
        <div class="card"><div class="card-hdr"><h3 id="hdrInsight"></h3><div class="meta" id="insCnt"></div></div><div class="card-body" id="insCards"></div></div>
        <div class="card" id="actionCard"><div class="card-hdr"><h3 id="hdrAction"></h3></div><div class="card-body np" id="actionBody"></div></div>
      </div>
    </div>
    <div id="pageSku" style="display:none">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
        <div class="lang-toggle" id="skuPeriodToggle">
          <button class="lang-btn active" data-period="all" onclick="setSkuPeriod('all')">전체</button>
          <button class="lang-btn" data-period="month" onclick="setSkuPeriod('month')">월간</button>
          <button class="lang-btn" data-period="week" onclick="setSkuPeriod('week')">주간</button>
        </div>
        <select class="month-sel" id="skuMonthSelect" onchange="renderSKU()" style="display:none"></select>
        <span style="color:var(--text3);font-size:11px" id="skuPeriodLabel"></span>
        <div style="flex:1"></div>
        <div class="lang-toggle" id="skuSortToggle">
          <button class="lang-btn active" data-sort="orders" onclick="setSkuSort('orders')">수주건수</button>
          <button class="lang-btn" data-sort="qty" onclick="setSkuSort('qty')">수량</button>
          <button class="lang-btn" data-sort="amount" onclick="setSkuSort('amount')">매출액</button>
        </div>
      </div>
      <div class="card">
        <div class="card-hdr"><h3 id="hdrSku"></h3><div class="meta" id="hdrSkuMeta"></div></div>
        <div class="card-body np" style="max-height:calc(100vh - 220px);overflow-y:auto">
          <table><thead id="skuThead"></thead><tbody id="skuTbody"></tbody></table>
        </div>
      </div>
    </div>
    <div id="pageBuyers" style="display:none">
      <div class="card" id="buyerCard">
        <div class="tabs" id="btabs"></div>
        <div id="filterPanel" style="padding:12px 18px;border-bottom:1px solid var(--border);background:var(--bg)">
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px" id="filterPresets"></div>
          <div id="filterControls" style="display:none">
            <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:end">
              <div class="fg"><label>수주 건수</label><div style="display:flex;gap:4px"><select id="fOrdOp" class="f-sel"><option value="gte">&ge;</option><option value="lte">&le;</option><option value="eq">=</option></select><input type="number" id="fOrdVal" class="f-inp" placeholder="3"><span class="f-u">건</span></div></div>
              <div class="fg"><label>수주 총액</label><div style="display:flex;gap:4px"><select id="fSalesOp" class="f-sel"><option value="gte">&ge;</option><option value="lte">&le;</option></select><input type="number" id="fSalesVal" class="f-inp" placeholder="500000"><span class="f-u">원</span></div></div>
              <div class="fg"><label>최종 수주</label><div style="display:flex;gap:4px"><select id="fLastOp" class="f-sel"><option value="lte">&le;</option><option value="gte">&ge;</option></select><input type="number" id="fLastDays" class="f-inp" placeholder="30"><span class="f-u">일 전</span></div></div>
              <button class="btn btn-primary btn-sm" onclick="applyFilter()">검색</button>
              <button class="btn btn-sm" onclick="clearFilter()">초기화</button>
            </div>
          </div>
        </div>
        <div id="buyerToolbar" style="padding:10px 18px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:center"></div>
        <div style="max-height:calc(100vh - 280px);overflow-y:auto">
          <table><thead id="buyerThead"></thead><tbody id="buyerTbody"></tbody></table>
        </div>
      </div>
    </div>
    <div id="pageDetail" style="display:none">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <select class="month-sel" id="monthSelect" onchange="renderDetail()"></select>
        <div class="lang-toggle">
          <button class="lang-btn active" id="btnDaily" onclick="setDetailMode('daily')">일간</button>
          <button class="lang-btn" id="btnWeekly" onclick="setDetailMode('weekly')">주간</button>
        </div>
        <button class="btn btn-sm" onclick="exportMonthCSV()">월간 CSV</button>
      </div>
      <div class="detail-kpi-row" id="detailKpiRow"></div>
      <div class="card" style="margin-bottom:18px"><div class="card-hdr"><h3>매출 차트</h3></div><div class="card-body"><div class="chart-w"><canvas id="detailChart"></canvas></div></div></div>
      <div class="card"><div class="card-hdr"><h3>명세</h3></div><div class="card-body np detail-table"><table><thead id="detailThead"></thead><tbody id="detailTbody"></tbody></table></div></div>
    </div>
  </div>
</div>

<script>
const D = {data_json};

const SEG_COLORS = {{champion:'#22c55e',loyal:'#3b82f6',promising:'#8b5cf6',atrisk:'#f59e0b',dormant:'#ef4444',lost:'#94a3b8'}};
const SEG_LABELS = {{champion:'Champion',loyal:'Loyal',promising:'Promising',atrisk:'At Risk',dormant:'Dormant',lost:'Lost'}};
const SEG_BADGE = {{champion:'badge-s',loyal:'badge-i',promising:'badge-p',atrisk:'badge-w',dormant:'badge-d',lost:'badge-m'}};
const SEG_DESC = {{champion:'고빈도 고단가 VIP',loyal:'정기 구매 리피터',promising:'유망 고객',atrisk:'구매 빈도 감소',dormant:'장기 미주문',lost:'이탈'}};
let curSeg = 'all';
let curPage = 'dash';
let salesChart, segChart, detailChartInst;
let selMonth='';
let detailMode='daily';
let skuPeriod='all';
let skuSort='orders';

function fmtKRW(n) {{
  if(n>=100000000) return (n/100000000).toFixed(1)+'억';
  if(n>=10000) return Math.round(n/10000).toLocaleString()+'만';
  return n.toLocaleString();
}}

function fmtFull(n) {{ return n.toLocaleString()+'원'; }}

const ct = D.crawl_meta.crawled_at.slice(0,16).replace('T',' ');
document.getElementById('crawlTime').textContent = '최종 업데이트: '+ct;

const ds = D.daily_sales;
function getMonday(dateStr){{const[y,m,d]=dateStr.split('-').map(Number);const dt=new Date(Date.UTC(y,m-1,d));const day=dt.getUTCDay();const diff=day===0?-6:1-day;dt.setUTCDate(dt.getUTCDate()+diff);return dt.toISOString().slice(0,10);}}
function addDays(dateStr,n){{const[y,m,d]=dateStr.split('-').map(Number);const dt=new Date(Date.UTC(y,m-1,d+n));return dt.toISOString().slice(0,10);}}

const latestDate=ds.length?ds[0].date:new Date().toISOString().slice(0,10);
const mondayStr=getMonday(latestDate);
const prevMondayStr=addDays(mondayStr,-7);
const prevSundayStr=addDays(prevMondayStr,6);
const thisWeek=ds.filter(d=>d.date>=mondayStr&&d.date<=latestDate);
const prevWeek=ds.filter(d=>d.date>=prevMondayStr&&d.date<=prevSundayStr);
const sum7=thisWeek.reduce((s,d)=>s+d.total_sales,0);
const sump7=prevWeek.reduce((s,d)=>s+d.total_sales,0);
const wow=sump7?((sum7-sump7)/sump7*100).toFixed(1):'0';
const ord7=thisWeek.reduce((s,d)=>s+d.order_count,0);
const ordp7=prevWeek.reduce((s,d)=>s+d.order_count,0);
const wowOrd=ordp7?((ord7-ordp7)/ordp7*100).toFixed(1):'0';
const aov=ord7?Math.round(sum7/ord7):0;
const aovp=ordp7?Math.round(sump7/ordp7):0;
const wowAov=aovp?((aov-aovp)/aovp*100).toFixed(1):'0';
const weekStart=mondayStr.slice(5).replace('-','/').replace(/^0/,'');
const weekEnd=latestDate.slice(5).replace('-','/').replace(/^0/,'');
const curYM=latestDate.slice(0,7);
const thisMonth=ds.filter(d=>d.date.startsWith(curYM));
const monthSum=thisMonth.reduce((s,d)=>s+d.total_sales,0);
const monthOrd=thisMonth.reduce((s,d)=>s+d.order_count,0);
const curDay=parseInt(latestDate.slice(8,10));
const prevYM=(()=>{{const[y,m]=curYM.split('-').map(Number);const pm=m===1?12:m-1;const py=m===1?y-1:y;return py+'-'+String(pm).padStart(2,'0');}})();
const prevMonthSame=ds.filter(d=>d.date.startsWith(prevYM)&&parseInt(d.date.slice(8,10))<=curDay);
const prevMonthSum=prevMonthSame.reduce((s,d)=>s+d.total_sales,0);
const mom=prevMonthSum?((monthSum-prevMonthSum)/prevMonthSum*100).toFixed(1):'0';

const segs = ['champion','loyal','promising','atrisk','dormant','lost'];
let activeBuyers, activeRate, dormantCt, atriskCt, segCts;

function recompute() {{
  const sc = {{}};
  segs.forEach(s=>sc[s]=0);
  D.buyers.forEach(b=>sc[b.segment]=(sc[b.segment]||0)+1);
  D.segment_counts = sc;
  dormantCt = sc.dormant||0;
  atriskCt = sc.atrisk||0;
  activeBuyers = D.buyers.filter(b=>['champion','loyal','promising'].includes(b.segment)).length;
  activeRate = D.buyers.length ? (activeBuyers/D.buyers.length*100).toFixed(1) : '0';
  segCts = segs.map(s=>sc[s]||0);
}}
recompute();

/* ===== Render functions ===== */
function renderNav() {{
  document.getElementById('sidebarNav').innerHTML = `
    <div class="nav-sec">Dashboard</div>
    <div class="nav-item ${{curPage==='dash'?'active':''}}" onclick="showPage('dash')"><span>&#x1f4ca;</span> 매출 대시보드</div>
    <div class="nav-item ${{curPage==='detail'?'active':''}}" onclick="showPage('detail')"><span>&#x1f4cb;</span> 매출 상세</div>
    <div class="nav-item" onclick="goToDash('insCards')"><span>&#x1f4a1;</span> 인사이트<span class="badge" id="navInsight">0</span></div>
    <div class="nav-sec">회원 관리</div>
    <div class="nav-item ${{curPage==='buyers'?'active':''}}" onclick="showPage('buyers')"><span>&#x1f465;</span> 전체 회원 <span class="badge" id="navTotal">${{D.buyers.length}}</span></div>
    <div class="nav-sec">매출 분석</div>
    <div class="nav-item ${{curPage==='sku'?'active':''}}" onclick="showPage('sku')"><span>&#x1f4e6;</span> 상품 랭킹</div>
    <div class="nav-item" onclick="goToDash('actionCard')"><span>&#x1f3af;</span> 액션 플랜<span class="badge" id="navAction">3</span></div>`;
}}

function renderTopbar() {{
  const titles = {{dash:'매출 대시보드',buyers:'전체 회원',detail:'매출 상세',sku:'상품 랭킹'}};
  document.getElementById('topTitle').textContent = titles[curPage]||'매출 대시보드';
  document.getElementById('topMeta').textContent = '고도몰 B2B — 실데이터';
}}

function showPage(page) {{
  curPage = page;
  ['pageDash','pageBuyers','pageDetail','pageSku'].forEach(id=>document.getElementById(id).style.display='none');
  const pageMap={{dash:'pageDash',buyers:'pageBuyers',detail:'pageDetail',sku:'pageSku'}};
  document.getElementById(pageMap[page]||'pageDash').style.display='';
  if(page==='detail') renderDetail();
  if(page==='sku') renderSKU();
  renderNav();
  renderTopbar();
  window.scrollTo({{top:0,behavior:'smooth'}});
}}

function goToDash(elId) {{
  if(curPage!=='dash') showPage('dash');
  setTimeout(()=>{{const el=document.getElementById(elId);if(el)el.scrollIntoView({{behavior:'smooth',block:'center'}})}},80);
}}

function renderKPI() {{
  document.getElementById('kpiRow').innerHTML = [
    {{l:'주간 매출',v:fmtFull(sum7),c:wow,d:weekStart+'~'+weekEnd+' vs 전주',cl:''}},
    {{l:'수주 건수',v:ord7+'건',c:wowOrd,d:'vs 전주',cl:'green'}},
    {{l:'평균 수주액',v:fmtFull(aov),c:wowAov,d:'vs 전주',cl:'purple'}},
    {{l:'Active Rate',v:activeRate+'%',c:null,d:activeBuyers+'/'+D.buyers.length+'사',cl:'green'}},
    {{l:'대응 필요',v:(dormantCt+atriskCt)+'사',c:null,d:'At Risk '+atriskCt+' / Dormant '+dormantCt,cl:'red'}},
  ].map(k=>`<div class="kpi ${{k.cl}}"><div class="kpi-label">${{k.l}}</div><div class="kpi-val">${{k.v}}</div><div class="kpi-sub">${{k.c!==null?`<span class="chg ${{parseFloat(k.c)>=0?'up':'down'}}">${{parseFloat(k.c)>=0?'+':''}}${{k.c}}%</span>`:''}} <span class="kpi-desc">${{k.d}}</span></div></div>`).join('');
}}

function renderSummary() {{
  const wowStr = (parseFloat(wow)>=0?'+':'')+wow+'%';
  const momStr = (parseFloat(mom)>=0?'+':'')+mom+'%';
  const ym = curYM.split('-')[1].replace(/^0/,'');
  document.getElementById('summaryStrip').innerHTML = `<span class="strip-item">&#x1f4c5; ${{weekStart}}~${{weekEnd}}</span><span class="strip-sep">|</span><span class="strip-item">주간 <strong>${{fmtFull(sum7)}}</strong> <span class="strip-sub">전주비 ${{wowStr}}</span></span><span class="strip-sep">|</span><span class="strip-item">${{ym}}월 <strong>${{fmtFull(monthSum)}}</strong> <span class="strip-sub">전월 동기비 ${{momStr}}</span></span><span class="strip-sep">|</span><span class="strip-item">&#x26a0;&#xfe0f; At Risk <strong style="color:#f59e0b">${{atriskCt}}</strong>사 / Dormant <strong style="color:#ef4444">${{dormantCt}}</strong>사</span>`;
}}

function renderHeaders() {{
  document.getElementById('hdrTrend').textContent = '일별 매출 추이';
  document.getElementById('hdrTrendMeta').textContent = '최근 14일 + 전 14일 비교';
  document.getElementById('hdrSeg').textContent = '세그먼트 분포';
  document.getElementById('totalBuyers').textContent = D.buyers.length + '사';
  document.getElementById('hdrInsight').textContent = '자동 인사이트';
  document.getElementById('hdrAction').textContent = '액션 플랜';
}}

function renderSalesChart() {{
  const ctx = document.getElementById('salesChart').getContext('2d');
  const last14 = ds.slice(0,14).reverse();
  const prev14 = ds.slice(14,28).reverse();
  if(salesChart) salesChart.destroy();
  salesChart = new Chart(ctx,{{
    type:'bar',
    data:{{
      labels:last14.map(d=>d.date.slice(5)),
      datasets:[
        {{label:'매출',data:last14.map(d=>d.total_sales),backgroundColor:'rgba(74,144,217,0.7)',borderRadius:4,order:2}},
        {{label:'전 14일',data:prev14.map(d=>d.total_sales),backgroundColor:'rgba(74,144,217,0.15)',borderRadius:4,order:3}},
        {{label:'수주 수',data:last14.map(d=>d.order_count),type:'line',borderColor:'#22c55e',backgroundColor:'transparent',tension:0.3,yAxisID:'y1',pointRadius:3,order:1}},
      ]
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{display:true,position:'top',labels:{{font:{{size:10}},usePointStyle:true}}}},
        tooltip:{{callbacks:{{label:function(ctx){{return ctx.dataset.label+': '+(ctx.dataset.yAxisID==='y1'?ctx.raw+'건':fmtFull(ctx.raw))}}}}}}}},
      scales:{{
        y:{{beginAtZero:true,ticks:{{font:{{size:10}},callback:v=>fmtKRW(v)}}}},
        y1:{{position:'right',beginAtZero:true,grid:{{display:false}},ticks:{{font:{{size:10}}}}}},
        x:{{ticks:{{font:{{size:10}}}}}}
      }}
    }}
  }});
}}

function renderSegChart() {{
  const ctx = document.getElementById('segChart').getContext('2d');
  if(segChart) segChart.destroy();
  segChart = new Chart(ctx,{{
    type:'doughnut',
    data:{{labels:segs.map(s=>SEG_LABELS[s]),datasets:[{{data:segCts,backgroundColor:segs.map(s=>SEG_COLORS[s]),borderWidth:2,borderColor:'#fff'}}]}},
    options:{{responsive:true,maintainAspectRatio:false,cutout:'65%',plugins:{{legend:{{display:false}}}},onClick:(e,el)=>{{if(el.length){{switchSeg(segs[el[0].index])}}}}}}
  }});
}}

function renderSegList() {{
  document.getElementById('segList').innerHTML = segs.map((s,i)=>`<div class="seg-item" onclick="switchSeg('${{s}}')"><div class="seg-dot" style="background:${{SEG_COLORS[s]}}"></div><div class="seg-info"><div class="seg-name">${{SEG_LABELS[s]}}</div><div class="seg-desc">${{SEG_DESC[s]}}</div></div><div><div class="seg-ct">${{segCts[i]}}</div><div class="seg-pct">${{D.buyers.length?(segCts[i]/D.buyers.length*100).toFixed(0):0}}%</div></div></div>`).join('');
}}

function renderInsights() {{
  const ins = [];
  if(parseFloat(wow)<-10) ins.push({{cls:'high',badge:'HIGH',title:'주간 매출 전주비 '+wow+'% 급락',desc:'최근 7일 매출이 전주 대비 크게 감소했습니다. 주요 거래처 주문 현황을 확인하고 즉시 팔로업이 필요합니다.'}});
  else if(parseFloat(wow)<-3) ins.push({{cls:'med',badge:'MEDIUM',title:'매출 소폭 감소 추세 ('+wow+'%)',desc:'전주 대비 소폭 감소. 주문 건수와 객단가 변동을 개별 확인하세요.'}});
  else if(parseFloat(wow)>15) ins.push({{cls:'opp',badge:'OPPORTUNITY',title:'매출 호조 +'+wow+'%',desc:'전주 대비 대폭 증가. 성장 요인을 파악하고 횡전개를 검토하세요.'}});
  if(dormantCt>=3) ins.push({{cls:'high',badge:'HIGH',title:'Dormant '+dormantCt+'사 — 재활성화 시급',desc:'장기 미주문 고객이 '+dormantCt+'사 있습니다. 재활성화 메일/특별 오퍼로 구매 전환을 유도하세요.'}});
  if(atriskCt>=2) ins.push({{cls:'high',badge:'HIGH',title:'At Risk '+atriskCt+'사 감지',desc:'구매 빈도가 감소하고 있는 고객이 '+atriskCt+'사 있습니다. 1:1 전화 팔로업과 특별 할인 쿠폰 배포를 권장합니다.'}});
  const td = ds[0];
  if(td && ds[1]) {{
    const dod = ((td.total_sales-ds[1].total_sales)/(ds[1].total_sales||1)*100).toFixed(1);
    if(parseFloat(dod)>30) ins.push({{cls:'opp',badge:'OPPORTUNITY',title:'당일 매출 급증 +'+dod+'% (전일비)',desc:'오늘 '+fmtFull(td.total_sales)+'으로 전일 대비 대폭 증가.'}});
  }}
  ins.push({{cls:'low',badge:'INFO',title:'전체 회원 '+D.buyers.length+'사, 상품 '+D.products.length+'SKU',desc:'데이터는 '+D.crawl_meta.crawled_at.slice(0,10)+' 시점 기준입니다.'}});
  document.getElementById('insCnt').textContent = ins.length+'건 감지';
  const highCt = ins.filter(i=>i.cls==='high').length;
  const ni = document.getElementById('navInsight'); if(ni) ni.textContent = highCt;
  document.getElementById('insCards').innerHTML = ins.map(i=>`<div class="ins ${{i.cls}}"><div style="display:flex;justify-content:space-between;align-items:center"><span class="ins-badge">${{i.badge}}</span></div><div class="ins-title">${{i.title}}</div><div class="ins-desc">${{i.desc}}</div></div>`).join('');
}}

function renderActions() {{
  const acts = [];
  if(atriskCt>0) acts.push({{p:'p0',seg:'At Risk',act:atriskCt+'사 1:1 전화 팔로업 + 특별 할인 쿠폰 배포',own:'영업'}});
  if(dormantCt>0) acts.push({{p:'p0',seg:'Dormant',act:dormantCt+'사 재활성화 메일(한정 오퍼)',own:'마케팅'}});
  const lostCt = D.segment_counts.lost||0;
  if(lostCt>0) acts.push({{p:'p1',seg:'Lost',act:lostCt+'사 win-back 캠페인',own:'마케팅'}});
  document.getElementById('actionBody').innerHTML = `<table><thead><tr><th>우선도</th><th>대상</th><th>액션</th><th>담당</th></tr></thead><tbody>${{acts.map(a=>`<tr><td><span class="pri ${{a.p}}">${{a.p.toUpperCase()}}</span></td><td><span class="badge ${{a.seg==='At Risk'?'badge-w':(a.seg==='Dormant'?'badge-d':'badge-m')}}">${{a.seg}}</span></td><td style="font-size:11px">${{a.act}}</td><td style="font-size:11px">${{a.own}}</td></tr>`).join('')}}</tbody></table>`;
}}

/* ===== Buyers ===== */
let activePreset=null;
const PRESETS = {{
  p1:{{ label:'고가치 휴면', desc:'200만+, 60일+ 미주문', filters:{{ salesOp:'gte',salesVal:2000000,lastOp:'gte',lastDays:60 }} }},
  p2:{{ label:'이탈 징후', desc:'3건+, 60일+ 미주문', filters:{{ ordOp:'gte',ordVal:3,lastOp:'gte',lastDays:60 }} }},
  p3:{{ label:'VIP 케어', desc:'500만+, 30일+ 미주문', filters:{{ salesOp:'gte',salesVal:5000000,lastOp:'gte',lastDays:30 }} }},
}};

function daysSince(dateStr){{
  if(!dateStr) return 9999;
  const then=new Date(dateStr.slice(0,10));
  return Math.floor((new Date()-then)/86400000);
}}

function cmpOp(op,val,target){{
  if(op==='gte') return target>=val;
  if(op==='lte') return target<=val;
  if(op==='eq') return target===val;
  return true;
}}

function applyPreset(key){{
  if(activePreset===key){{ clearFilter(); return; }}
  activePreset=key;
  const p=PRESETS[key];
  const f=p.filters;
  document.getElementById('filterControls').style.display='block';
  document.getElementById('fOrdVal').value=f.ordVal!==undefined?f.ordVal:'';
  document.getElementById('fOrdOp').value=f.ordOp||'gte';
  document.getElementById('fSalesVal').value=f.salesVal||'';
  document.getElementById('fSalesOp').value=f.salesOp||'gte';
  document.getElementById('fLastDays').value=f.lastDays||'';
  document.getElementById('fLastOp').value=f.lastOp||'lte';
  applyFilter();
}}

function toggleCustom(){{
  activePreset='custom';
  document.getElementById('filterControls').style.display='block';
  renderPresetBtns();
}}

function applyFilter(){{
  renderPresetBtns();
  renderBuyers();
}}

function clearFilter(){{
  activePreset=null;
  document.getElementById('filterControls').style.display='none';
  ['fOrdVal','fSalesVal','fLastDays'].forEach(id=>document.getElementById(id).value='');
  renderPresetBtns();
  renderBuyers();
}}

function getFilteredBuyers(){{
  let list = curSeg==='all' ? D.buyers : D.buyers.filter(b=>b.segment===curSeg);
  const el = document.getElementById('bSearch');
  const q = el ? el.value.toLowerCase() : '';
  if(q) list = list.filter(b=>(b.name+b.id+b.grade).toLowerCase().includes(q));
  const ordVal=document.getElementById('fOrdVal').value;
  const salesVal=document.getElementById('fSalesVal').value;
  const lastDays=document.getElementById('fLastDays').value;
  if(ordVal!=='') list=list.filter(b=>cmpOp(document.getElementById('fOrdOp').value,+ordVal,b.order_count));
  if(salesVal) list=list.filter(b=>cmpOp(document.getElementById('fSalesOp').value,+salesVal,b.total_sales));
  if(lastDays) list=list.filter(b=>cmpOp(document.getElementById('fLastOp').value,+lastDays,daysSince(b.last_order)));
  return list;
}}

function renderPresetBtns(){{
  const keys=Object.keys(PRESETS);
  document.getElementById('filterPresets').innerHTML = keys.map(k=>`<div class="preset ${{activePreset===k?'active':''}}" onclick="applyPreset('${{k}}')">${{PRESETS[k].label}}<span class="p-desc">${{PRESETS[k].desc}}</span></div>`).join('')+`<div class="preset ${{activePreset==='custom'?'active':''}}" onclick="toggleCustom()">커스텀</div>`;
}}

function renderBuyerTabs() {{
  document.getElementById('btabs').innerHTML = `
    <div class="tab ${{curSeg==='all'?'active':''}}" onclick="switchSeg('all')">전체 회원<span class="tb">${{D.buyers.length}}</span></div>
    ${{segs.map(s=>`<div class="tab ${{curSeg===s?'active':''}}" onclick="switchSeg('${{s}}')">${{SEG_LABELS[s]}}<span class="tb">${{D.segment_counts[s]||0}}</span></div>`).join('')}}`;
  renderPresetBtns();
  document.getElementById('buyerToolbar').innerHTML = `<input class="search-input" id="bSearch" placeholder="회원명/ID 검색..." oninput="renderBuyers()"><span class="filter-count" id="filterCount"></span><div style="flex:1"></div><button class="btn btn-sm" onclick="exportBuyers()">CSV 출력</button>`;
}}

function renderBuyers() {{
  const list = getFilteredBuyers();
  const fc = document.getElementById('filterCount');
  if(fc) fc.textContent = list.length!==D.buyers.length ? list.length+'사 해당' : '';
  document.getElementById('buyerThead').innerHTML = `<tr><th>회원명</th><th>회원ID</th><th>등급</th><th>세그먼트</th><th>수주 총액</th><th>수주 건수</th><th>최종 수주</th></tr>`;
  document.getElementById('buyerTbody').innerHTML = list.slice(0,200).map(b=>`<tr><td style="font-weight:600">${{b.name}}</td><td style="font-size:11px;color:var(--text3)">${{b.id}}</td><td><span class="badge badge-i">${{b.grade||'-'}}</span></td><td><span class="badge ${{SEG_BADGE[b.segment]}}">${{SEG_LABELS[b.segment]}}</span></td><td style="text-align:right;font-weight:600">${{fmtFull(b.total_sales)}}</td><td style="text-align:center">${{b.order_count}}건</td><td style="font-size:11px">${{b.last_order||'-'}}</td></tr>`).join('');
}}

function switchSeg(seg) {{
  curSeg = seg;
  if(curPage!=='buyers') showPage('buyers');
  renderBuyerTabs();
  renderBuyers();
}}

/* ===== SKU ===== */
function setSkuPeriod(p){{
  skuPeriod=p;
  document.querySelectorAll('#skuPeriodToggle .lang-btn').forEach(b=>b.classList.toggle('active',b.dataset.period===p));
  document.getElementById('skuMonthSelect').style.display=p==='month'?'':'none';
  renderSKU();
}}
function setSkuSort(s){{
  skuSort=s;
  document.querySelectorAll('#skuSortToggle .lang-btn').forEach(b=>b.classList.toggle('active',b.dataset.sort===s));
  renderSKU();
}}

function renderSKU() {{
  let prods = [...D.products];
  prods.sort((a,b)=>b[skuSort]-a[skuSort]);
  document.getElementById('hdrSku').textContent = '상품 랭킹';
  document.getElementById('hdrSkuMeta').textContent = prods.length+'SKU';
  document.getElementById('skuThead').innerHTML = `<tr><th>#</th><th>상품명</th><th>품번</th><th>수주건수</th><th>총수량</th><th>총액</th></tr>`;
  document.getElementById('skuTbody').innerHTML = prods.map((p,i)=>`<tr><td style="color:var(--text3)">${{i+1}}</td><td style="font-weight:600;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{p.name}}</td><td style="font-size:11px;color:var(--text3)">${{p.code}}</td><td style="text-align:center">${{p.orders}}</td><td style="text-align:center">${{p.qty}}</td><td style="text-align:right;font-weight:600">${{fmtFull(p.amount)}}</td></tr>`).join('');
}}

/* ===== Detail ===== */
function setDetailMode(m) {{
  detailMode=m;
  document.getElementById('btnDaily').classList.toggle('active',m==='daily');
  document.getElementById('btnWeekly').classList.toggle('active',m==='weekly');
  renderDetail();
}}

function renderDetail() {{
  const months = [...new Set(ds.map(d=>d.date.slice(0,7)))].sort().reverse();
  const sel = document.getElementById('monthSelect');
  if(!selMonth || !months.includes(selMonth)) selMonth = months[0]||'';
  sel.innerHTML = months.map(m=>`<option value="${{m}}" ${{m===selMonth?'selected':''}}>${{m}}</option>`).join('');
  selMonth = sel.value;

  const mData = ds.filter(d=>d.date.startsWith(selMonth)).sort((a,b)=>a.date.localeCompare(b.date));
  const mTotal = mData.reduce((s,d)=>s+d.total_sales,0);
  const mOrd = mData.reduce((s,d)=>s+d.order_count,0);
  const mAvg = mData.length ? Math.round(mTotal/mData.length) : 0;

  const[py,pm] = selMonth.split('-').map(Number);
  const prevM = py+'-'+String(pm===1?12:pm-1).padStart(2,'0');
  const prevData = ds.filter(d=>d.date.startsWith(pm===1?(py-1)+'-12':prevM));
  const prevTotal = prevData.reduce((s,d)=>s+d.total_sales,0);
  const momD = prevTotal?((mTotal-prevTotal)/prevTotal*100).toFixed(1):'0';

  document.getElementById('detailKpiRow').innerHTML = [
    {{l:'월간 매출 합계',v:fmtFull(mTotal),d:'vs 전월 '+(parseFloat(momD)>=0?'+':'')+momD+'%'}},
    {{l:'월간 수주 건수',v:mOrd+'건',d:mData.length+'일 영업'}},
    {{l:'일평균 매출',v:fmtFull(mAvg),d:''}},
    {{l:'영업일수',v:mData.length+'일',d:''}},
  ].map(k=>`<div class="kpi"><div class="kpi-label">${{k.l}}</div><div class="kpi-val">${{k.v}}</div><div class="kpi-sub"><span class="kpi-desc">${{k.d}}</span></div></div>`).join('');

  let chartData, chartLabels;
  if(detailMode==='weekly') {{
    const wk={{}};
    mData.forEach(d=>{{const w=getMonday(d.date);if(!wk[w])wk[w]={{sales:0,orders:0,days:0}};wk[w].sales+=d.total_sales;wk[w].orders+=d.order_count;wk[w].days++;}});
    const weeks=Object.keys(wk).sort();
    chartLabels=weeks.map(w=>w.slice(5));
    chartData=weeks.map(w=>wk[w]);
  }} else {{
    chartLabels=mData.map(d=>d.date.slice(5));
    chartData=mData;
  }}

  const ctx = document.getElementById('detailChart').getContext('2d');
  if(detailChartInst) detailChartInst.destroy();
  detailChartInst = new Chart(ctx,{{
    type:'bar',
    data:{{
      labels:chartLabels,
      datasets:[
        {{label:'매출',data:chartData.map(d=>d.total_sales||d.sales),backgroundColor:'rgba(74,144,217,0.7)',borderRadius:4}},
        {{label:'수주 수',data:chartData.map(d=>d.order_count||d.orders),type:'line',borderColor:'#22c55e',backgroundColor:'transparent',tension:0.3,yAxisID:'y1',pointRadius:3}},
      ]
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      plugins:{{legend:{{position:'top',labels:{{font:{{size:10}},usePointStyle:true}}}}}},
      scales:{{y:{{beginAtZero:true,ticks:{{callback:v=>fmtKRW(v),font:{{size:10}}}}}},y1:{{position:'right',beginAtZero:true,grid:{{display:false}},ticks:{{font:{{size:10}}}}}},x:{{ticks:{{font:{{size:10}}}}}}}}
    }}
  }});

  document.getElementById('detailThead').innerHTML = `<tr><th>날짜</th><th>매출액</th><th>수주 건수</th><th>평균 수주액</th><th>상품 종수</th><th>수량</th></tr>`;
  document.getElementById('detailTbody').innerHTML = mData.slice().reverse().map(d=>`<tr><td>${{d.date}}</td><td style="text-align:right;font-weight:600">${{fmtFull(d.total_sales)}}</td><td style="text-align:center">${{d.order_count}}</td><td style="text-align:right">${{fmtFull(d.avg_order||0)}}</td><td style="text-align:center">${{d.product_kinds||0}}</td><td style="text-align:center">${{d.product_total_qty||0}}</td></tr>`).join('');
}}

/* ===== CSV Export ===== */
function exportCSV() {{
  let csv = '날짜,수주건수,수주총액,평균수주액\\n';
  ds.forEach(d=>csv+=`${{d.date}},${{d.order_count}},${{d.total_sales}},${{d.avg_order||0}}\\n`);
  downloadCSV(csv, 'biteme_kr_b2b_daily.csv');
}}

function exportBuyers() {{
  const list = getFilteredBuyers();
  let csv = '회원명,회원ID,등급,세그먼트,수주총액,수주건수,최종수주\\n';
  list.forEach(b=>csv+=`"${{b.name}}",${{b.id}},${{b.grade||''}},${{b.segment}},${{b.total_sales}},${{b.order_count}},${{b.last_order||''}}\\n`);
  downloadCSV(csv, 'biteme_kr_b2b_buyers.csv');
}}

function exportMonthCSV() {{
  const mData = ds.filter(d=>d.date.startsWith(selMonth));
  let csv = '날짜,수주건수,수주총액,평균수주액,상품종수,수량\\n';
  mData.forEach(d=>csv+=`${{d.date}},${{d.order_count}},${{d.total_sales}},${{d.avg_order||0}},${{d.product_kinds||0}},${{d.product_total_qty||0}}\\n`);
  downloadCSV(csv, `biteme_kr_b2b_${{selMonth}}.csv`);
}}

function downloadCSV(csv, filename) {{
  const bom = '\\uFEFF';
  const blob = new Blob([bom+csv], {{type:'text/csv;charset=utf-8;'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}}

/* ===== Init ===== */
function renderAll() {{
  renderNav();
  renderTopbar();
  renderKPI();
  renderSummary();
  renderHeaders();
  renderSalesChart();
  renderSegChart();
  renderSegList();
  renderInsights();
  renderActions();
  renderBuyerTabs();
  renderBuyers();
}}
renderAll();
</script>
</body>
</html>'''

with open("biteme-kr-b2b-dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Dashboard HTML: {len(html):,} chars written to biteme-kr-b2b-dashboard.html")
