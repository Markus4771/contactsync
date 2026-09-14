from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from contactsync import __version__

router = APIRouter(tags=["devices-ui"])


@router.get("/devices", response_class=HTMLResponse)
def devices_page() -> str:
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Geräte · ContactSync</title><style>
body{{font-family:system-ui;margin:0;background:#f3f5f7;color:#17202a}}header{{background:#17202a;color:#fff;padding:20px 5vw}}main{{padding:24px 5vw}}.card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 2px 12px #0001;margin-bottom:18px}}input,select,button{{padding:9px;margin:4px;border:1px solid #ccd3d9;border-radius:7px}}button{{cursor:pointer}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #e7ebee;text-align:left;vertical-align:top}}a{{color:#1769aa}}.ok{{font-weight:700}}.warn{{font-weight:700}}.crit{{font-weight:700}}.muted{{color:#68737d}}.details{{white-space:nowrap}}
</style></head><body><header><h1>Geräte & Monitoring</h1><div>ContactSync Professional {__version__}</div></header><main>
<div class='card'><a href='/'>Dashboard</a> · <a href='/customers'>Kundenstamm</a> · <a href='/docs'>REST-API</a><h2>Filter</h2>
<input id='q' placeholder='Host, IP, MAC, Kunde...'><input id='customer' placeholder='Kundennummer'>
<select id='rmm'><option value=''>RMM: alle</option><option value='online'>online</option><option value='offline'>offline</option><option value='unknown'>unknown</option></select>
<select id='monitoring'><option value=''>Checkmk: alle</option><option value='up'>up</option><option value='down'>down</option><option value='unreachable'>unreachable</option><option value='pending'>pending</option><option value='unmonitored'>nicht überwacht</option></select>
<button onclick='loadDevices()'>Aktualisieren</button></div>
<div class='card'><h2>Geräte</h2><table><thead><tr><th>Kunde</th><th>Gerät</th><th>RMM</th><th>GLPI</th><th>Checkmk</th><th>Services</th><th></th></tr></thead><tbody id='rows'></tbody></table></div>
<div class='card' id='detail' style='display:none'><h2 id='detailTitle'>Details</h2><div id='detailBody'></div></div>
<script>
function esc(v){{return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function badgeState(s){{return s||'nicht überwacht'}}
async function loadDevices(){{const p=new URLSearchParams();if(q.value)p.set('q',q.value);if(customer.value)p.set('customer_number',customer.value);if(rmm.value)p.set('online_status',rmm.value);if(monitoring.value)p.set('monitoring_state',monitoring.value);const res=await fetch('/api/v1/devices?'+p.toString());const data=await res.json();rows.innerHTML=data.map(d=>`<tr><td>${{esc(d.customer_number||'')}}<br><span class='muted'>${{esc(d.customer_name||'')}}</span></td><td><strong>${{esc(d.hostname)}}</strong><br><span class='muted'>${{esc(d.ip_address||'')}} ${{esc(d.operating_system||'')}}</span></td><td>${{esc(d.online_status)}}<br><span class='muted'>Agent: ${{esc(d.agent_status)}}</span></td><td>${{esc(d.glpi_asset_id||'—')}}</td><td>${{esc(badgeState(d.monitoring_state_label))}}<br><span class='muted'>${{esc(d.checkmk_site||'')}}</span></td><td>OK ${{d.services_ok||0}} · WARN ${{d.services_warn||0}} · CRIT ${{d.services_crit||0}} · UNK ${{d.services_unknown||0}}</td><td class='details'><button onclick='showDevice(${{d.id}})'>Details</button></td></tr>`).join('')}}
async function showDevice(id){{const res=await fetch('/api/v1/devices/'+id);const d=await res.json();detail.style.display='block';detailTitle.textContent=d.hostname+' – Details';const services=(d.monitoring_services||[]).map(s=>`<tr><td>${{esc(s.description)}}</td><td>${{esc(s.state_label)}}</td><td>${{esc(s.plugin_output||'')}}</td><td>${{esc(s.last_check||'')}}</td></tr>`).join('');detailBody.innerHTML=`<p><strong>Kunde:</strong> ${{esc(d.customer_number||'')}} ${{esc(d.customer_name||'')}}</p><p><strong>RMM:</strong> ${{esc(d.online_status)}} / Agent ${{esc(d.agent_status)}} · <strong>GLPI:</strong> ${{esc(d.glpi_asset_id||'—')}} · <strong>Checkmk:</strong> ${{esc(badgeState(d.monitoring_state_label))}}</p><p><strong>Letzter Check:</strong> ${{esc(d.monitoring_last_check||'—')}}</p><h3>Checkmk Services</h3><table><thead><tr><th>Service</th><th>Status</th><th>Ausgabe</th><th>Letzter Check</th></tr></thead><tbody>${{services||'<tr><td colspan="4">Keine Monitoring-Services vorhanden.</td></tr>'}}</tbody></table>`;detail.scrollIntoView({{behavior:'smooth'}})}}
loadDevices();
</script></main></body></html>"""
