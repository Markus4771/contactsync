from __future__ import annotations

from typing import Any

import httpx

from contactsync.plugins.contracts import ConnectionTestResult, WriteResult
from contactsync.plugins.zammad import ZammadPlugin


class ZammadRuntimePlugin(ZammadPlugin):
    metadata = ZammadPlugin.metadata.__class__(
        key="zammad",
        title="Zammad",
        version="1.2.0",
        capabilities=("organizations.read", "users.read", "contacts.write", "tickets.write", "delta"),
        description="Zammad Connector fuer Organisationen, Benutzer und Monitoring-Tickets",
        automation_events=("customer.created", "customer.updated", "person.updated"),
        required_config=("url", "token"),
    )

    @staticmethod
    def _base_url(config: dict[str, Any]) -> str:
        return str(config["url"]).rstrip("/")

    @staticmethod
    def _headers(config: dict[str, Any]) -> dict[str, str]:
        return {
            "Authorization": f"Token token={config['token']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        config: dict[str, Any],
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(
            timeout=float(config.get("timeout", 20)),
            verify=bool(config.get("verify_ssl", True)),
            follow_redirects=True,
        ) as client:
            response = await client.request(
                method,
                self._base_url(config) + path,
                headers=self._headers(config),
                params=params,
                json=json_body,
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

    async def _paged(self, config: dict[str, Any], path: str) -> list[dict[str, Any]]:
        page = 1
        per_page = max(1, min(int(config.get("page_size", 100)), 100))
        result: list[dict[str, Any]] = []
        while True:
            rows = await self._request(config, "GET", path, params={"page": page, "per_page": per_page})
            if not isinstance(rows, list):
                raise RuntimeError("Unerwartete Zammad API-Antwort")
            result.extend(row for row in rows if isinstance(row, dict))
            if len(rows) < per_page:
                break
            page += 1
        return result

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(False, "Zammad Konfiguration unvollstaendig", {"errors": errors})
        try:
            me = await self._request(config, "GET", "/api/v1/users/me")
            return ConnectionTestResult(
                True,
                "Zammad Verbindung erfolgreich",
                {"id": me.get("id"), "login": me.get("login"), "email": me.get("email")},
            )
        except Exception as exc:
            return ConnectionTestResult(False, f"Zammad Verbindung fehlgeschlagen: {exc}")

    def _normalize_customer(self, config: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        result = self.normalize_customer(record)
        customer_number_field = config.get("customer_number_field")
        if customer_number_field:
            result["customer_number"] = record.get(str(customer_number_field))
        result["external_id"] = str(record["id"]) if record.get("id") is not None else None
        result["external_updated_at"] = record.get("updated_at")
        result["status"] = "active" if record.get("active", True) else "inactive"
        return result

    async def fetch_customers(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        rows = await self._paged(config, "/api/v1/organizations")
        if since:
            rows = [r for r in rows if not r.get("updated_at") or str(r["updated_at"]) >= since]
        return [self._normalize_customer(config, row) for row in rows]

    async def fetch_persons(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        rows = await self._paged(config, "/api/v1/users")
        if since:
            rows = [r for r in rows if not r.get("updated_at") or str(r["updated_at"]) >= since]
        result: list[dict[str, Any]] = []
        for row in rows:
            person = self.normalize_person(row)
            person["external_customer_id"] = str(row["organization_id"]) if row.get("organization_id") else None
            person["external_updated_at"] = row.get("updated_at")
            person["department"] = row.get("department")
            person["status"] = "active" if row.get("active", True) else "inactive"
            result.append(person)
        return result

    @staticmethod
    def _customer_values(config: dict[str, Any], customer: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {
            "name": customer.get("name") or "Kunde",
            "active": customer.get("status") != "inactive",
        }
        if customer.get("notes") is not None:
            values["note"] = customer.get("notes") or ""
        customer_number_field = config.get("customer_number_field")
        if customer_number_field and customer.get("customer_number") is not None:
            values[str(customer_number_field)] = customer.get("customer_number")
        return values

    @staticmethod
    def _person_values(person: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {
            "firstname": person.get("first_name") or "",
            "lastname": person.get("last_name") or "",
            "email": person.get("email") or "",
            "login": person.get("email") or person.get("external_id") or "contactsync-user",
            "active": person.get("status") != "inactive",
        }
        for src, dst in {
            "phone": "phone",
            "mobile": "mobile",
            "department": "department",
        }.items():
            if person.get(src) is not None:
                values[dst] = person.get(src) or ""
        external_customer_id = person.get("external_customer_id") or person.get("customer_external_id")
        if external_customer_id:
            values["organization_id"] = int(external_customer_id)
        return values

    async def create_customer(self, config: dict[str, Any], customer: dict[str, Any]) -> WriteResult:
        row = await self._request(config, "POST", "/api/v1/organizations", json_body=self._customer_values(config, customer))
        return WriteResult(str(row["id"]), True, row)

    async def update_customer(self, config: dict[str, Any], external_id: str, customer: dict[str, Any]) -> WriteResult:
        row = await self._request(config, "PUT", f"/api/v1/organizations/{int(external_id)}", json_body=self._customer_values(config, customer))
        return WriteResult(str(external_id), False, row)

    async def create_person(self, config: dict[str, Any], person: dict[str, Any]) -> WriteResult:
        row = await self._request(config, "POST", "/api/v1/users", json_body=self._person_values(person))
        return WriteResult(str(row["id"]), True, row)

    async def update_person(self, config: dict[str, Any], external_id: str, person: dict[str, Any]) -> WriteResult:
        row = await self._request(config, "PUT", f"/api/v1/users/{int(external_id)}", json_body=self._person_values(person))
        return WriteResult(str(external_id), False, row)

    async def create_monitoring_ticket(
        self,
        config: dict[str, Any],
        *,
        title: str,
        body: str,
        customer: str,
    ) -> dict[str, Any]:
        payload = {
            "title": title,
            "group": str(config.get("monitoring_group") or "Users"),
            "customer": customer,
            "priority": str(config.get("monitoring_priority") or "2 normal"),
            "article": {
                "subject": title,
                "body": body,
                "type": "note",
                "internal": bool(config.get("monitoring_internal", True)),
            },
        }
        row = await self._request(config, "POST", "/api/v1/tickets", json_body=payload)
        if not isinstance(row, dict) or row.get("id") is None:
            raise RuntimeError("Zammad lieferte keine Ticket-ID")
        return row

    async def add_monitoring_article(self, config: dict[str, Any], ticket_id: str, body: str) -> dict[str, Any]:
        payload = {
            "ticket_id": int(ticket_id),
            "subject": "ContactSync Monitoring",
            "body": body,
            "type": "note",
            "internal": bool(config.get("monitoring_internal", True)),
        }
        row = await self._request(config, "POST", "/api/v1/ticket_articles", json_body=payload)
        return row if isinstance(row, dict) else {}

    async def close_monitoring_ticket(self, config: dict[str, Any], ticket_id: str) -> dict[str, Any]:
        row = await self._request(
            config,
            "PUT",
            f"/api/v1/tickets/{int(ticket_id)}",
            json_body={"state": str(config.get("monitoring_recovery_state") or "closed")},
        )
        return row if isinstance(row, dict) else {}
