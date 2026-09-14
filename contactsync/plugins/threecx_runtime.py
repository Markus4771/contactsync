from __future__ import annotations

from typing import Any

import httpx

from contactsync.plugins.contracts import ConnectionTestResult
from contactsync.plugins.threecx import ThreeCXPlugin


class ThreeCXRuntimePlugin(ThreeCXPlugin):
    metadata = ThreeCXPlugin.metadata.__class__(
        key="3cx",
        title="3CX",
        version="1.2.0",
        capabilities=("users.read", "phonebook.write"),
        description="3CX V20 XAPI Connector fuer Benutzer und Telefonbuch",
        automation_events=("person.updated",),
        required_config=("url", "client_id", "client_secret"),
    )

    @staticmethod
    def _base_url(config: dict[str, Any]) -> str:
        return str(config["url"]).rstrip("/")

    async def _token(self, config: dict[str, Any]) -> str:
        async with httpx.AsyncClient(
            timeout=float(config.get("timeout", 20)),
            verify=bool(config.get("verify_ssl", True)),
            follow_redirects=True,
        ) as client:
            response = await client.post(
                self._base_url(config) + "/connect/token",
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "grant_type": "client_credentials",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token = response.json().get("access_token")
            if not token:
                raise RuntimeError("3CX Access-Token fehlt")
            return str(token)

    async def _get(
        self,
        config: dict[str, Any],
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, str]]:
        token = await self._token(config)
        async with httpx.AsyncClient(
            timeout=float(config.get("timeout", 20)),
            verify=bool(config.get("verify_ssl", True)),
            follow_redirects=True,
        ) as client:
            response = await client.get(
                self._base_url(config) + path,
                params=params,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json(), dict(response.headers)

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(False, "3CX Konfiguration unvollstaendig", {"errors": errors})
        try:
            body, headers = await self._get(config, "/xapi/v1/Defs", params={"$select": "Id"})
            return ConnectionTestResult(
                True,
                "3CX Verbindung erfolgreich",
                {"version": headers.get("x-3cx-version"), "defs": body.get("Id") if isinstance(body, dict) else None},
            )
        except Exception as exc:
            return ConnectionTestResult(False, f"3CX Verbindung fehlgeschlagen: {exc}")

    async def fetch_customers(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        # Die offizielle XAPI beschreibt Benutzer, aber keinen stabil dokumentierten
        # Kunden-/Firmen-Endpunkt. Kundenzuordnung bleibt deshalb im ContactSync-Core.
        return []

    async def fetch_persons(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        top = max(1, min(int(config.get("page_size", 100)), 100))
        skip = 0
        result: list[dict[str, Any]] = []
        while True:
            body, _headers = await self._get(
                config,
                "/xapi/v1/Users",
                params={
                    "$top": top,
                    "$skip": skip,
                    "$orderby": "Number",
                    "$select": "Id,FirstName,LastName,Number,EmailAddress,Mobile",
                },
            )
            rows = body.get("value", []) if isinstance(body, dict) else []
            if not isinstance(rows, list):
                raise RuntimeError("Unerwartete 3CX XAPI-Antwort")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                person = self.normalize_person(row)
                person["external_updated_at"] = None
                result.append(person)
            if len(rows) < top:
                break
            skip += top
        return result
