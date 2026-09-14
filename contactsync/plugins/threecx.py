from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class ThreeCXPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="3cx",
        title="3CX",
        version="1.0.0",
        capabilities=("users.read", "phonebook.write"),
        description="3CX Connector",
        automation_events=("person.updated",),
    )

    def connection_hint(self) -> str:
        return "3CX Server und API-Konfiguration"

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
