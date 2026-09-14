from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class OdooPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="odoo",
        title="Odoo",
        version="1.1.0",
        capabilities=("partners.read", "partners.write", "delta"),
        description="Odoo Connector für Kunden und Ansprechpartner",
        automation_events=("customer.created", "customer.updated", "person.updated"),
        required_config=("url", "database", "username", "api_key"),
    )

    def connection_hint(self) -> str:
        return "Odoo URL, Datenbank, Benutzername und API-Key"

    def normalize_customer(self, record: dict) -> dict:
        return {
            "customer_number": record.get("ref") or record.get("customer_number"),
            "name": record.get("name") or "",
            "email": record.get("email"),
            "phone": record.get("phone"),
            "mobile": record.get("mobile"),
            "street": record.get("street"),
            "postal_code": record.get("zip"),
            "city": record.get("city"),
            "website": record.get("website"),
            "vat_id": record.get("vat"),
            "source": "odoo",
        }

    def normalize_person(self, record: dict) -> dict:
        name = (record.get("name") or "").strip()
        parts = name.split(" ", 1)
        return {
            "first_name": parts[0] if len(parts) > 1 else None,
            "last_name": parts[-1] if parts else "",
            "email": record.get("email"),
            "phone": record.get("phone"),
            "mobile": record.get("mobile"),
            "function": record.get("function"),
            "source": "odoo",
            "external_id": str(record.get("id")) if record.get("id") is not None else None,
        }
