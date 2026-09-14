from __future__ import annotations

from typing import Any

import httpx

from contactsync.plugins.base import ConnectorPlugin, PluginMetadata
from contactsync.plugins.contracts import ConnectionTestResult, WriteResult


class GLPIRuntimePlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="glpi",
        title="GLPI",
        version="1.0.0",
        capabilities=("entities.read", "entities.write", "users.read", "users.write", "delta"),
        description="GLPI REST Connector fuer Kunden/Entities und Ansprechpartner/Users",
        automation_events=("customer.created", "customer.updated", "person.created", "person.updated"),
        required_config=("url", "user_token"),
    )

    def connection_hint(self) -> str:
        return "GLPI REST API URL (apirest.php) und Benutzer-Token; optional App-Token."

    @staticmethod
    def _base_url(config: dict[str, Any]) -> str:
        url = str(config["url"]).rstrip("/")
        return url if url.endswith("apirest.php") else url + "/apirest.php"

    @staticmethod
    def _auth_headers(config: dict[str, Any]) -> dict[str, str]:
        headers = {"Authorization": f"user_token {config['user_token']}", "Accept": "application/json"}
        if config.get("app_token"):
            headers["App-Token"] = str(config["app_token"])
        return headers

    @staticmethod
    def _session_headers(config: dict[str, Any], session_token: str) -> dict[str, str]:
        headers = {"Session-Token": session_token, "Accept": "application/json", "Content-Type": "application/json"}
        if config.get("app_token"):
            headers["App-Token"] = str(config["app_token"])
        return headers

    async def _init_session(self, config: dict[str, Any]) -> str:
        async with httpx.AsyncClient(timeout=float(config.get("timeout", 20)), verify=bool(config.get("verify_ssl", True)), follow_redirects=True) as client:
            response = await client.get(self._base_url(config) + "/initSession", headers=self._auth_headers(config))
            response.raise_for_status()
            token = response.json().get("session_token")
            if not token:
                raise RuntimeError("GLPI lieferte kein session_token")
            return str(token)

    async def _kill_session(self, config: dict[str, Any], session_token: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10, verify=bool(config.get("verify_ssl", True)), follow_redirects=True) as client:
                await client.get(self._base_url(config) + "/killSession", headers=self._session_headers(config, session_token))
        except Exception:
            pass

    async def _request(self, config: dict[str, Any], method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> Any:
        token = await self._init_session(config)
        try:
            async with httpx.AsyncClient(timeout=float(config.get("timeout", 20)), verify=bool(config.get("verify_ssl", True)), follow_redirects=True) as client:
                response = await client.request(method, self._base_url(config) + path, headers=self._session_headers(config, token), params=params, json=json_body)
                response.raise_for_status()
                return {} if not response.content else response.json()
        finally:
            await self._kill_session(config, token)

    async def _paged(self, config: dict[str, Any], itemtype: str) -> list[dict[str, Any]]:
        page_size = max(1, min(int(config.get("page_size", 100)), 1000))
        start = 0
        rows: list[dict[str, Any]] = []
        while True:
            batch = await self._request(config, "GET", f"/{itemtype}", params={"range": f"{start}-{start + page_size - 1}"})
            if not isinstance(batch, list):
                raise RuntimeError(f"Unerwartete GLPI Antwort fuer {itemtype}")
            rows.extend(row for row in batch if isinstance(row, dict))
            if len(batch) < page_size:
                break
            start += page_size
        return rows

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(False, "GLPI Konfiguration unvollstaendig", {"errors": errors})
        try:
            token = await self._init_session(config)
            await self._kill_session(config, token)
            return ConnectionTestResult(True, "GLPI Verbindung erfolgreich")
        except Exception as exc:
            return ConnectionTestResult(False, f"GLPI Verbindung fehlgeschlagen: {exc}")

    @staticmethod
    def _customer_number(record: dict[str, Any]) -> Any:
        if record.get("customer_number"):
            return record.get("customer_number")
        comment = str(record.get("comment") or "")
        first_line = comment.splitlines()[0] if comment else ""
        if first_line.lower().startswith("kundennummer:"):
            return first_line.split(":", 1)[1].strip() or None
        return None

    def normalize_customer(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": str(record["id"]) if record.get("id") is not None else None,
            "customer_number": self._customer_number(record),
            "name": record.get("name") or record.get("completename") or "GLPI Entity",
            "notes": record.get("comment"),
            "status": "active",
            "source": "glpi",
            "external_updated_at": record.get("date_mod"),
        }

    def normalize_person(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": str(record["id"]) if record.get("id") is not None else None,
            "external_customer_id": str(record["default_entities_id"]) if record.get("default_entities_id") not in (None, 0, "0") else None,
            "first_name": record.get("firstname") or "",
            "last_name": record.get("realname") or record.get("name") or "",
            "email": record.get("email"),
            "phone": record.get("phone"),
            "mobile": record.get("mobile"),
            "status": "active" if not record.get("is_deleted", 0) else "inactive",
            "source": "glpi",
            "external_updated_at": record.get("date_mod"),
        }

    async def fetch_customers(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        rows = await self._paged(config, "Entity")
        if config.get("exclude_root_entity", True):
            rows = [row for row in rows if int(row.get("id", 0) or 0) != 0]
        if since:
            rows = [row for row in rows if not row.get("date_mod") or str(row["date_mod"]) >= since]
        return [self.normalize_customer(row) for row in rows]

    async def fetch_persons(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        rows = await self._paged(config, "User")
        if since:
            rows = [row for row in rows if not row.get("date_mod") or str(row["date_mod"]) >= since]
        return [self.normalize_person(row) for row in rows]

    @staticmethod
    def _customer_values(config: dict[str, Any], customer: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {"name": customer.get("name") or "Kunde", "entities_id": int(config.get("parent_entity_id", 0))}
        note = customer.get("notes") or ""
        if customer.get("customer_number"):
            prefix = f"Kundennummer: {customer['customer_number']}"
            note = prefix if not note else prefix + "\n" + note
        if note:
            values["comment"] = note
        return values

    @staticmethod
    def _person_values(person: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {
            "name": person.get("email") or person.get("external_id") or "contactsync-user",
            "firstname": person.get("first_name") or "",
            "realname": person.get("last_name") or "",
        }
        for key in ("email", "phone", "mobile"):
            if person.get(key) is not None:
                values[key] = person.get(key) or ""
        entity_id = person.get("customer_external_id") or person.get("external_customer_id")
        if entity_id:
            values["default_entities_id"] = int(entity_id)
        return values

    async def create_customer(self, config: dict[str, Any], customer: dict[str, Any]) -> WriteResult:
        result = await self._request(config, "POST", "/Entity", json_body={"input": self._customer_values(config, customer)})
        external_id = result.get("id") if isinstance(result, dict) else None
        if external_id is None:
            raise RuntimeError("GLPI lieferte beim Anlegen der Entity keine ID")
        return WriteResult(str(external_id), True, result)

    async def update_customer(self, config: dict[str, Any], external_id: str, customer: dict[str, Any]) -> WriteResult:
        result = await self._request(config, "PUT", f"/Entity/{int(external_id)}", json_body={"input": self._customer_values(config, customer)})
        return WriteResult(str(external_id), False, result if isinstance(result, dict) else {})

    async def create_person(self, config: dict[str, Any], person: dict[str, Any]) -> WriteResult:
        result = await self._request(config, "POST", "/User", json_body={"input": self._person_values(person)})
        external_id = result.get("id") if isinstance(result, dict) else None
        if external_id is None:
            raise RuntimeError("GLPI lieferte beim Anlegen des Users keine ID")
        return WriteResult(str(external_id), True, result)

    async def update_person(self, config: dict[str, Any], external_id: str, person: dict[str, Any]) -> WriteResult:
        result = await self._request(config, "PUT", f"/User/{int(external_id)}", json_body={"input": self._person_values(person)})
        return WriteResult(str(external_id), False, result if isinstance(result, dict) else {})
