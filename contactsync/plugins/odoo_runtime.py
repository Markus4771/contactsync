from __future__ import annotations

import itertools
from typing import Any
import httpx

from contactsync.plugins.odoo import OdooPlugin
from contactsync.plugins.contracts import ConnectionTestResult, WriteResult


class OdooRuntimePlugin(OdooPlugin):
    _ids = itertools.count(1)
    metadata = OdooPlugin.metadata.__class__(
        key="odoo", title="Odoo", version="1.2.0",
        capabilities=("partners.read", "partners.write", "delta"),
        description="Odoo Connector für Kunden und Ansprechpartner",
        automation_events=("customer.created", "customer.updated", "person.updated"),
        required_config=("url", "database", "username", "api_key"),
    )

    async def _rpc(self, config: dict[str, Any], service: str, method: str, args: list[Any]) -> Any:
        endpoint = config["url"].rstrip("/") + "/jsonrpc"
        payload = {"jsonrpc":"2.0","method":"call","params":{"service":service,"method":method,"args":args},"id":next(self._ids)}
        async with httpx.AsyncClient(timeout=float(config.get("timeout", 20)), verify=bool(config.get("verify_ssl", True))) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
        body = response.json()
        if body.get("error"):
            error = body["error"]
            raise RuntimeError(error.get("data", {}).get("message") or error.get("message") or "Odoo JSON-RPC Fehler")
        return body.get("result")

    async def _uid(self, config: dict[str, Any]) -> int:
        uid = await self._rpc(config, "common", "authenticate", [config["database"], config["username"], config["api_key"], {}])
        if not uid:
            raise RuntimeError("Odoo Anmeldung fehlgeschlagen")
        return int(uid)

    async def _execute(self, config: dict[str, Any], model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        uid = await self._uid(config)
        return await self._rpc(config, "object", "execute_kw", [config["database"], uid, config["api_key"], model, method, args, kwargs or {}])

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(False, "Odoo Konfiguration unvollständig", {"errors": errors})
        try:
            uid = await self._uid(config)
            version = await self._rpc(config, "common", "version", [])
            return ConnectionTestResult(True, "Odoo Verbindung erfolgreich", {"uid": uid, "server_version": version.get("server_version") if isinstance(version, dict) else None})
        except Exception as exc:
            return ConnectionTestResult(False, f"Odoo Verbindung fehlgeschlagen: {exc}")

    async def fetch_customers(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        domain = [["is_company","=",True],["customer_rank",">",0]]
        if since:
            domain.append(["write_date",">=",since])
        fields = ["id","ref","name","email","phone","mobile","street","zip","city","website","vat","write_date","active"]
        rows = await self._execute(config, "res.partner", "search_read", [domain], {"fields":fields,"order":"id asc","limit":int(config.get("batch_limit",1000))})
        return [self.normalize_customer(r) | {"external_id":str(r["id"]),"external_updated_at":r.get("write_date")} for r in rows]

    async def fetch_persons(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        domain = [["parent_id","!=",False],["type","=","contact"]]
        if since:
            domain.append(["write_date",">=",since])
        fields = ["id","parent_id","name","email","phone","mobile","function","write_date","active"]
        rows = await self._execute(config, "res.partner", "search_read", [domain], {"fields":fields,"order":"id asc","limit":int(config.get("batch_limit",1000))})
        result=[]
        for r in rows:
            parent=r.get("parent_id")
            parent_id=parent[0] if isinstance(parent,(list,tuple)) and parent else parent
            result.append(self.normalize_person(r) | {"external_customer_id":str(parent_id) if parent_id else None,"external_updated_at":r.get("write_date")})
        return result

    @staticmethod
    def _customer_values(c: dict[str, Any]) -> dict[str, Any]:
        pairs={"customer_number":"ref","name":"name","email":"email","phone":"phone","mobile":"mobile","street":"street","postal_code":"zip","city":"city","website":"website","vat_id":"vat"}
        values={dst:c[src] for src,dst in pairs.items() if c.get(src) not in (None,"")}
        values.update({"is_company":True,"company_type":"company","customer_rank":1})
        if c.get("status")=="inactive": values["active"]=False
        return values

    @staticmethod
    def _person_values(p: dict[str, Any]) -> dict[str, Any]:
        values={"name":" ".join(x for x in (p.get("first_name"),p.get("last_name")) if x).strip() or "Kontakt","type":"contact"}
        for src,dst in {"email":"email","phone":"phone","mobile":"mobile","function":"function"}.items():
            if p.get(src) not in (None,""): values[dst]=p[src]
        parent=p.get("external_customer_id") or p.get("customer_external_id")
        if parent: values["parent_id"]=int(parent)
        if p.get("status")=="inactive": values["active"]=False
        return values

    async def create_customer(self, config: dict[str, Any], customer: dict[str, Any]) -> WriteResult:
        external_id=await self._execute(config,"res.partner","create",[self._customer_values(customer)])
        return WriteResult(str(external_id),True,{"model":"res.partner"})

    async def update_customer(self, config: dict[str, Any], external_id: str, customer: dict[str, Any]) -> WriteResult:
        await self._execute(config,"res.partner","write",[[int(external_id)],self._customer_values(customer)])
        return WriteResult(str(external_id),False,{"model":"res.partner"})

    async def create_person(self, config: dict[str, Any], person: dict[str, Any]) -> WriteResult:
        external_id=await self._execute(config,"res.partner","create",[self._person_values(person)])
        return WriteResult(str(external_id),True,{"model":"res.partner"})

    async def update_person(self, config: dict[str, Any], external_id: str, person: dict[str, Any]) -> WriteResult:
        await self._execute(config,"res.partner","write",[[int(external_id)],self._person_values(person)])
        return WriteResult(str(external_id),False,{"model":"res.partner"})
