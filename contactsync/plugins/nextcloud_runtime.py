from __future__ import annotations

from typing import Any
from urllib.parse import quote
from uuid import uuid4
from xml.etree import ElementTree as ET

import httpx

from contactsync.plugins.contracts import ConnectionTestResult, WriteResult
from contactsync.plugins.nextcloud import NextcloudPlugin

DAV = "DAV:"
CARD = "urn:ietf:params:xml:ns:carddav"


class NextcloudRuntimePlugin(NextcloudPlugin):
    metadata = NextcloudPlugin.metadata.__class__(
        key="nextcloud",
        title="Nextcloud CardDAV",
        version="1.2.0",
        capabilities=("contacts.read", "contacts.write", "delta"),
        description="Nextcloud CardDAV Connector",
        automation_events=("customer.updated", "person.updated"),
        required_config=("url", "username", "app_password", "addressbook"),
    )

    @staticmethod
    def _base_url(config: dict[str, Any]) -> str:
        return str(config["url"]).rstrip("/")

    def _addressbook_url(self, config: dict[str, Any]) -> str:
        addressbook = str(config["addressbook"]).strip()
        if addressbook.startswith("https://") or addressbook.startswith("http://"):
            return addressbook.rstrip("/") + "/"
        username = quote(str(config["username"]), safe="")
        book = "/".join(quote(part, safe="") for part in addressbook.strip("/").split("/") if part)
        return f"{self._base_url(config)}/remote.php/dav/addressbooks/users/{username}/{book}/"

    @staticmethod
    def _auth(config: dict[str, Any]) -> tuple[str, str]:
        return str(config["username"]), str(config["app_password"])

    async def _request(
        self,
        config: dict[str, Any],
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: str | bytes | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=float(config.get("timeout", 20)),
            verify=bool(config.get("verify_ssl", True)),
            follow_redirects=True,
        ) as client:
            response = await client.request(
                method,
                url,
                auth=self._auth(config),
                headers=headers,
                content=content,
            )
            response.raise_for_status()
            return response

    async def test_connection(self, config: dict[str, Any]) -> ConnectionTestResult:
        errors = self.validate_config(config)
        if errors:
            return ConnectionTestResult(False, "Nextcloud Konfiguration unvollstaendig", {"errors": errors})
        try:
            body = "<?xml version='1.0'?><d:propfind xmlns:d='DAV:'><d:prop><d:resourcetype/></d:prop></d:propfind>"
            response = await self._request(
                config,
                "PROPFIND",
                self._addressbook_url(config),
                headers={"Depth": "0", "Content-Type": "application/xml"},
                content=body,
            )
            return ConnectionTestResult(
                response.status_code in (200, 207),
                "Nextcloud CardDAV Verbindung erfolgreich",
                {"status_code": response.status_code, "addressbook": self._addressbook_url(config)},
            )
        except Exception as exc:
            return ConnectionTestResult(False, f"Nextcloud Verbindung fehlgeschlagen: {exc}")

    @staticmethod
    def _unfold_vcard(text: str) -> list[str]:
        raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines: list[str] = []
        for line in raw:
            if line.startswith((" ", "\t")) and lines:
                lines[-1] += line[1:]
            else:
                lines.append(line)
        return lines

    @classmethod
    def _parse_vcard(cls, text: str) -> dict[str, Any]:
        values: dict[str, list[str]] = {}
        for line in cls._unfold_vcard(text):
            if ":" not in line:
                continue
            left, value = line.split(":", 1)
            key = left.split(";", 1)[0].upper()
            values.setdefault(key, []).append(value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";"))
        n = (values.get("N") or [""])[0].split(";")
        adr = (values.get("ADR") or [""])[0].split(";")
        return {
            "uid": (values.get("UID") or [None])[0],
            "fn": (values.get("FN") or [""])[0],
            "first_name": n[1] if len(n) > 1 else None,
            "last_name": n[0] if n else None,
            "organization": (values.get("ORG") or [None])[0],
            "email": (values.get("EMAIL") or [None])[0],
            "phone": (values.get("TEL") or [None])[0],
            "mobile": (values.get("X-CONTACTSYNC-MOBILE") or [None])[0],
            "street": adr[2] if len(adr) > 2 else None,
            "city": adr[3] if len(adr) > 3 else None,
            "postal_code": adr[5] if len(adr) > 5 else None,
            "country": adr[6] if len(adr) > 6 else None,
            "customer_number": (values.get("X-CONTACTSYNC-CUSTOMER-NUMBER") or [None])[0],
            "entity": (values.get("X-CONTACTSYNC-ENTITY") or [None])[0],
            "external_customer_id": (values.get("X-CONTACTSYNC-CUSTOMER-ID") or [None])[0],
            "rev": (values.get("REV") or [None])[0],
            "note": (values.get("NOTE") or [None])[0],
        }

    async def _cards(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        body = """<?xml version='1.0' encoding='utf-8'?>
<c:addressbook-query xmlns:d='DAV:' xmlns:c='urn:ietf:params:xml:ns:carddav'>
  <d:prop><d:getetag/><c:address-data/></d:prop>
</c:addressbook-query>"""
        response = await self._request(
            config,
            "REPORT",
            self._addressbook_url(config),
            headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
            content=body,
        )
        root = ET.fromstring(response.content)
        cards: list[dict[str, Any]] = []
        for item in root.findall(f".//{{{DAV}}}response"):
            href = item.findtext(f"{{{DAV}}}href")
            address_data = item.find(f".//{{{CARD}}}address-data")
            if address_data is None or not address_data.text:
                continue
            parsed = self._parse_vcard(address_data.text)
            parsed["href"] = href
            etag = item.findtext(f".//{{{DAV}}}getetag")
            parsed["etag"] = etag
            cards.append(parsed)
        return cards

    async def fetch_customers(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for card in await self._cards(config):
            if str(card.get("entity") or "").lower() != "customer":
                continue
            if since and card.get("rev") and str(card["rev"]) < since:
                continue
            customer = self.normalize_customer(card)
            customer["external_id"] = card.get("uid")
            customer["external_updated_at"] = card.get("rev")
            customer["notes"] = card.get("note")
            result.append(customer)
        return result

    async def fetch_persons(self, config: dict[str, Any], *, since: str | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for card in await self._cards(config):
            if str(card.get("entity") or "").lower() == "customer":
                continue
            if since and card.get("rev") and str(card["rev"]) < since:
                continue
            person = self.normalize_person(card)
            person["external_id"] = card.get("uid")
            person["external_customer_id"] = card.get("external_customer_id")
            person["external_updated_at"] = card.get("rev")
            result.append(person)
        return result

    @staticmethod
    def _esc(value: Any) -> str:
        return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    @classmethod
    def _customer_vcard(cls, uid: str, customer: dict[str, Any]) -> str:
        name = cls._esc(customer.get("name") or "Kunde")
        lines = [
            "BEGIN:VCARD", "VERSION:3.0", f"UID:{cls._esc(uid)}", f"FN:{name}", f"ORG:{name}",
            "X-CONTACTSYNC-ENTITY:CUSTOMER",
        ]
        if customer.get("customer_number"):
            lines.append(f"X-CONTACTSYNC-CUSTOMER-NUMBER:{cls._esc(customer['customer_number'])}")
        if customer.get("email"):
            lines.append(f"EMAIL:{cls._esc(customer['email'])}")
        if customer.get("phone"):
            lines.append(f"TEL;TYPE=WORK:{cls._esc(customer['phone'])}")
        if customer.get("mobile"):
            lines.append(f"X-CONTACTSYNC-MOBILE:{cls._esc(customer['mobile'])}")
        if any(customer.get(k) for k in ("street", "city", "postal_code", "country")):
            lines.append(f"ADR;TYPE=WORK:;;{cls._esc(customer.get('street'))};{cls._esc(customer.get('city'))};;{cls._esc(customer.get('postal_code'))};{cls._esc(customer.get('country'))}")
        if customer.get("notes"):
            lines.append(f"NOTE:{cls._esc(customer['notes'])}")
        lines.append("END:VCARD")
        return "\r\n".join(lines) + "\r\n"

    @classmethod
    def _person_vcard(cls, uid: str, person: dict[str, Any]) -> str:
        first = cls._esc(person.get("first_name"))
        last = cls._esc(person.get("last_name"))
        full = cls._esc(" ".join(x for x in (person.get("first_name"), person.get("last_name")) if x).strip() or "Kontakt")
        lines = [
            "BEGIN:VCARD", "VERSION:3.0", f"UID:{cls._esc(uid)}", f"FN:{full}", f"N:{last};{first};;;",
            "X-CONTACTSYNC-ENTITY:PERSON",
        ]
        if person.get("email"):
            lines.append(f"EMAIL:{cls._esc(person['email'])}")
        if person.get("phone"):
            lines.append(f"TEL;TYPE=WORK:{cls._esc(person['phone'])}")
        if person.get("mobile"):
            lines.append(f"X-CONTACTSYNC-MOBILE:{cls._esc(person['mobile'])}")
        customer_id = person.get("external_customer_id") or person.get("customer_external_id")
        if customer_id:
            lines.append(f"X-CONTACTSYNC-CUSTOMER-ID:{cls._esc(customer_id)}")
        lines.append("END:VCARD")
        return "\r\n".join(lines) + "\r\n"

    async def _put_card(self, config: dict[str, Any], uid: str, card: str) -> None:
        url = self._addressbook_url(config) + quote(uid, safe="") + ".vcf"
        await self._request(
            config,
            "PUT",
            url,
            headers={"Content-Type": "text/vcard; charset=utf-8"},
            content=card,
        )

    async def create_customer(self, config: dict[str, Any], customer: dict[str, Any]) -> WriteResult:
        uid = str(uuid4())
        await self._put_card(config, uid, self._customer_vcard(uid, customer))
        return WriteResult(uid, True, {"href": uid + ".vcf"})

    async def update_customer(self, config: dict[str, Any], external_id: str, customer: dict[str, Any]) -> WriteResult:
        await self._put_card(config, external_id, self._customer_vcard(external_id, customer))
        return WriteResult(external_id, False, {"href": external_id + ".vcf"})

    async def create_person(self, config: dict[str, Any], person: dict[str, Any]) -> WriteResult:
        uid = str(uuid4())
        await self._put_card(config, uid, self._person_vcard(uid, person))
        return WriteResult(uid, True, {"href": uid + ".vcf"})

    async def update_person(self, config: dict[str, Any], external_id: str, person: dict[str, Any]) -> WriteResult:
        await self._put_card(config, external_id, self._person_vcard(external_id, person))
        return WriteResult(external_id, False, {"href": external_id + ".vcf"})
