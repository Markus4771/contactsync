from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class ZammadPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="zammad",
        title="Zammad",
        version="1.1.0",
        capabilities=("organizations.read", "users.read", "contacts.write"),
        description="Zammad Connector für Organisationen und Benutzer",
        automation_events=("customer.created", "customer.updated", "person.updated"),
        required_config=("url", "token"),
    )

    def connection_hint(self) -> str:
        return "Zammad URL und API-Token"

    def normalize_customer(self, record: dict) -> dict:
        return {
            "customer_number": record.get("customer_number") or record.get("customer_id"),
            "name": record.get("name") or "",
            "email": record.get("email"),
            "phone": record.get("phone"),
            "notes": record.get("note"),
            "source": "zammad",
        }

    def normalize_person(self, record: dict) -> dict:
        return {
            "first_name": record.get("firstname") or record.get("first_name"),
            "last_name": record.get("lastname") or record.get("last_name") or "",
            "email": record.get("email"),
            "phone": record.get("phone"),
            "mobile": record.get("mobile"),
            "source": "zammad",
            "external_id": str(record.get("id")) if record.get("id") is not None else None,
        }
