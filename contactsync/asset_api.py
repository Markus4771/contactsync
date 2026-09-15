from __future__ import annotations
import html, sqlite3
from typing import Any
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from contactsync.asset_core import asset_query, asset_summary, get_asset, init_asset_schema
from contactsync.asset_matching import auto_link_safe_matches, detect_duplicates, ensure_asset_links_schema, link_devices, reject_match, unlink_device
router=APIRouter(tags=['assets'])

class AssetMetadataUpdate(BaseModel):
    asset_tag:str|None=None; location:str|None=None; responsible_person:str|None=None
    lifecycle_status:str=Field(default='active',pattern='^(active|stock|repair|retired|lost)$')
    purchase_date:str|None=None; warranty_until:str|None=None; notes:str|None=None
class AssetLinkRequest(BaseModel): primary_device_id:int; linked_device_id:int
class AssetRejectRequest(BaseModel): left_device_id:int; right_device_id:int; reason:str='manual'

def _db():
    from contactsync.main import DB_PATH,DATA_DIR
    DATA_DIR.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); init_asset_schema(c); ensure_asset_links_schema(c); return c

def _e(v): return html.escape(str(v or '-'))

@router.get('/api/v1/assets')
def list_assets(customer_number:str|None=None,status:str|None=None,q:str|None=None)->dict[str,Any]:
    sql=asset_query()+' WHERE 1=1'; params=[]
    if customer_number: sql+=' AND d.customer_number=?'; params.append(customer_number)
    if status: sql+=" AND COALESCE(a.lifecycle_status,'active')=?"; params.append(status)
    if q: term=f'%{q}%'; sql+=' AND (d.hostname LIKE ? OR d.serial_number LIKE ? OR d.mac_address LIKE ? OR d.glpi_asset_id LIKE ? OR a.asset_tag LIKE ? OR c.name LIKE ?)'; params.extend([term]*6)
    with _db() as c: return {'summary':asset_summary(c),'assets':[dict(r) for r in c.execute(sql+' ORDER BY c.name COLLATE NOCASE,d.hostname COLLATE NOCASE',params)]}

@router.get('/api/v1/assets/duplicates')
def asset_duplicates():
    with _db() as c: d=detect_duplicates(c); return {'count':len(d),'duplicates':d}
@router.post('/api/v1/assets/auto-link')
def asset_auto_link():
    with _db() as c: r=auto_link_safe_matches(c); c.commit(); return r
@router.post('/api/v1/assets/link')
def asset_link(p:AssetLinkRequest):
    try:
        with _db() as c: link_devices(c,p.primary_device_id,p.linked_device_id); c.commit(); return {'ok':True}
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
@router.post('/api/v1/assets/reject')
def asset_reject(p:AssetRejectRequest):
    with _db() as c: reject_match(c,p.left_device_id,p.right_device_id,p.reason); c.commit(); return {'ok':True}
@router.delete('/api/v1/assets/link/{linked_device_id}')
def asset_unlink(linked_device_id:int):
    with _db() as c:
        if not unlink_device(c,linked_device_id): raise HTTPException(404,'Asset-Verknüpfung nicht gefunden')
        c.commit(); return {'ok':True}

@router.post('/assets/link')
def ui_link(primary_device_id:int=Form(...),linked_device_id:int=Form(...)):
    with _db() as c: link_devices(c,primary_device_id,linked_device_id); c.commit()
    return RedirectResponse('/assets',303)
@router.post('/assets/reject')
def ui_reject(left_device_id:int=Form(...),right_device_id:int=Form(...)):
    with _db() as c: reject_match(c,left_device_id,right_device_id,'GUI: nicht identisch'); c.commit()
    return RedirectResponse('/assets',303)
@router.post('/assets/unlink')
def ui_unlink(linked_device_id:int=Form(...)):
    with _db() as c: unlink_device(c,linked_device_id); c.commit()
    return RedirectResponse('/assets',303)

@router.get('/api/v1/assets/{device_id}')
def asset_detail(device_id:int):
    with _db() as c:
        a=get_asset(c,device_id)
        if not a: raise HTTPException(404,'Asset nicht gefunden')
        a['services']=[dict(r) for r in c.execute('SELECT * FROM monitoring_services WHERE monitoring_host_id=? ORDER BY state DESC,description COLLATE NOCASE',(a.get('monitoring_host_id'),))] if a.get('monitoring_host_id') else []
        a['links']=[dict(r) for r in c.execute('SELECT * FROM asset_links WHERE primary_device_id=? OR linked_device_id=? ORDER BY id',(device_id,device_id))]; return a
@router.put('/api/v1/assets/{device_id}/metadata')
def update_asset_metadata(device_id:int,p:AssetMetadataUpdate):
    d=p.model_dump()
    with _db() as c:
        if not get_asset(c,device_id): raise HTTPException(404,'Asset nicht gefunden')
        c.execute('INSERT INTO asset_metadata(device_id,asset_tag,location,responsible_person,lifecycle_status,purchase_date,warranty_until,notes) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET asset_tag=excluded.asset_tag,location=excluded.location,responsible_person=excluded.responsible_person,lifecycle_status=excluded.lifecycle_status,purchase_date=excluded.purchase_date,warranty_until=excluded.warranty_until,notes=excluded.notes',(device_id,d['asset_tag'],d['location'],d['responsible_person'],d['lifecycle_status'],d['purchase_date'],d['warranty_until'],d['notes'])); c.commit(); return get_asset(c,device_id) or {}

@router.get('/assets',response_class=HTMLResponse)
def assets_page():
    with _db() as c:
        s=asset_summary(c); rows=[dict(r) for r in c.execute(asset_query()+' ORDER BY c.name COLLATE NOCASE,d.hostname COLLATE NOCASE')]; dup=detect_duplicates(c)
        links=[dict(r) for r in c.execute('SELECT l.*,a.hostname primary_hostname,b.hostname linked_hostname,a.source primary_source,b.source linked_source FROM asset_links l JOIN managed_devices a ON a.id=l.primary_device_id JOIN managed_devices b ON b.id=l.linked_device_id ORDER BY l.id DESC')]
    cards=''.join(f"<div class=card><b>{v}</b><span>{k}</span></div>" for k,v in [('Assets',s['total']),('Online',s['online']),('Offline',s['offline']),('GLPI',s['glpi_linked']),('Checkmk',s['checkmk_linked']),('Mögliche Dubletten',len(dup))])
    body=''.join(f"<tr><td><a href='/devices/{r['id']}'>{_e(r['hostname'])}</a></td><td>{_e(r.get('customer_name'))}</td><td>{_e(r.get('asset_tag'))}</td><td>{_e(r.get('online_status'))}</td><td>{_e(r.get('glpi_asset_id'))}</td><td>{_e(r.get('monitoring_state_label'))}</td><td>{r.get('services_warn') or 0}/{r.get('services_crit') or 0}</td></tr>" for r in rows) or '<tr><td colspan=7>Keine Assets.</td></tr>'
    dr=''.join(f"<tr><td>{_e(d['left']['hostname'])} <small>{_e(d['left']['source'])}</small></td><td>{_e(d['right']['hostname'])} <small>{_e(d['right']['source'])}</small></td><td>{_e(d['matched_by'])}</td><td>{d['score']}%</td><td><form method=post action='/assets/link' class=inline><input type=hidden name=primary_device_id value='{d['left']['id']}'><input type=hidden name=linked_device_id value='{d['right']['id']}'><button>Zusammenführen</button></form><form method=post action='/assets/reject' class=inline><input type=hidden name=left_device_id value='{d['left']['id']}'><input type=hidden name=right_device_id value='{d['right']['id']}'><button class=secondary>Nicht identisch</button></form></td></tr>" for d in dup) or '<tr><td colspan=5>Keine offenen Dubletten.</td></tr>'
    lr=''.join(f"<tr><td>{_e(l['primary_hostname'])} ({_e(l['primary_source'])})</td><td>{_e(l['linked_hostname'])} ({_e(l['linked_source'])})</td><td>{_e(l['match_method'])}</td><td>{l['confidence']}%</td><td><form method=post action='/assets/unlink'><input type=hidden name=linked_device_id value='{l['linked_device_id']}'><button class=secondary>Zuordnung lösen</button></form></td></tr>" for l in links) or '<tr><td colspan=5>Keine Verknüpfungen.</td></tr>'
    return HTMLResponse(f"""<!doctype html><html><head><meta charset=utf-8><title>ContactSync Asset-Zentrale</title><style>body{{font-family:Arial;margin:30px;background:#f6f7f9;color:#20242a}}.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}}.card{{background:white;padding:16px 22px;border-radius:8px;box-shadow:0 1px 4px #ccd;min-width:120px}}.card b{{display:block;font-size:25px}}.card span,small{{color:#667}}table{{width:100%;border-collapse:collapse;background:white;margin-bottom:28px}}th,td{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#eef1f5}}button{{padding:7px 10px;border:0;border-radius:5px;background:#1769aa;color:white;cursor:pointer}}button.secondary{{background:#697386}}form.inline{{display:inline;margin-right:6px}}a{{color:#1769aa;text-decoration:none}}</style></head><body><h1>Asset-Zentrale</h1><p>NetLock RMM, GLPI und Checkmk als gemeinsame Geräteansicht.</p><div class=cards>{cards}</div><h2>Assets</h2><table><tr><th>Gerät</th><th>Kunde</th><th>Asset-Tag</th><th>RMM</th><th>GLPI</th><th>Checkmk</th><th>WARN/CRIT</th></tr>{body}</table><h2>Dubletten prüfen</h2><table><tr><th>Gerät A</th><th>Gerät B</th><th>Treffer</th><th>Vertrauen</th><th>Aktion</th></tr>{dr}</table><h2>Bestehende Zuordnungen</h2><table><tr><th>Hauptgerät</th><th>Verknüpft</th><th>Methode</th><th>Vertrauen</th><th>Aktion</th></tr>{lr}</table></body></html>""")
