from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class ThreeCXPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="3cx",
        title="3CX",
        version="1.1.0",
        capabilities=("users.read", "phonebook.write"),
        description="3CX Connector für Benutzer und Telefonbuch",
        automation_events=("person.updated",),
        required_config=("url", "client_id", "client_secret"),
    )

    def connection_hint(self) -> str:
        return "3CX Server-URL, Client-ID und Client-Secret"

    def normalize_customer(self, record: dict) -> dict:
        return {
            "customer_number": record.get("customer_number") or record.get("CustomerNumber"),
            "name": record.get("company") or record.get("Company") or "",
            "email": record.get("email") or record.get("EmailAddress"),
            "phone": record.get("phone") or record.get("Number"),
            "source": "3cx",
        }

    def normalize_person(self, record: dict) -> dict:
        return {
            "first_name": record.get("first_name") or record.get("FirstName"),
            "last_name": record.get("last_name") or record.get("LastName") or "",
            "email": record.get("email") or record.get("EmailAddress"),
            "phone": record.get("phone") or record.get("Number"),
            "mobile": record.get("mobile") or record.get("Mobile"),
            "source": "3cx",
            "external_id": str(record.get("id")) if record.get("id") is not None else None,
        }
