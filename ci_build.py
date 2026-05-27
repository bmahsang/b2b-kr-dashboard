"""Post-build: copies dashboard HTML to index.html and injects auth gate."""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

AUTH_PW = os.environ.get("DASHBOARD_PASSWORD", "biteme2026!")

AUTH_GATE = f'''<div id="authGate" style="position:fixed;inset:0;z-index:9999;background:#0f1923;display:flex;align-items:center;justify-content:center">
<div style="text-align:center">
<div style="font-size:24px;font-weight:800;color:#fff;margin-bottom:4px">Bite<span style="color:#4a90d9">Me</span> KR</div>
<div style="font-size:11px;color:#475569;margin-bottom:24px;letter-spacing:.5px">B2B Sales Intelligence</div>
<div><input type="password" id="authPw" placeholder="Password" autocomplete="off" style="padding:10px 16px;border:1px solid #334155;border-radius:8px;background:#1a2736;color:#fff;font-size:14px;width:240px;outline:none;text-align:center" onkeydown="if(event.key==='Enter')checkAuth()"></div>
<button onclick="checkAuth()" style="margin-top:12px;padding:8px 36px;background:#4a90d9;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;letter-spacing:.3px">Login</button>
<div id="authErr" style="color:#ef4444;font-size:11px;margin-top:10px;min-height:16px"></div>
</div>
</div>
<script>
function checkAuth(){{var p=document.getElementById('authPw').value;if(p==='{AUTH_PW}'){{document.getElementById('authGate').remove();sessionStorage.setItem('bkr_auth','1');}}else{{document.getElementById('authErr').textContent='\\ube44\\ubc00\\ubc88\\ud638\\uac00 \\ud2c0\\ub9bd\\ub2c8\\ub2e4';document.getElementById('authPw').value='';}}}}
if(sessionStorage.getItem('bkr_auth')==='1'){{var g=document.getElementById('authGate');if(g)g.remove();}}
else{{document.getElementById('authPw').focus();}}
</script>'''

with open("biteme-kr-b2b-dashboard.html", "r", encoding="utf-8") as f:
    html = f.read()

html = html.replace("<body>", f"<body>\n{AUTH_GATE}", 1)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"index.html generated ({len(html):,} bytes) with auth gate")
