from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class NextcloudPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="nextcloud",
        title="Nextcloud CardDAV",
        version="1.1.0",
        capabilities=("contacts.read", "contacts.write", "delta"),
        description="Nextcloud CardDAV Connector",
        automation_events=("customer.updated", "person.updated"),
        required_config=("url", "username", "app_password", "addressbook"),
    )

    def connection_hint(self) -> str:
        return "Nextcloud URL, Benutzername, App-Passwort und Adressbuch"

    def normalize_customer(self, record: dict) -> dict:
        return {
            "customer_number": record.get("customer_number") or record.get("x-contactsync-customer-number"),
            "name": record.get("organization") or record.get("fn") or record.get("name") or "",
            "email": record.get("email"),
            "phone": record.get("phone"),
            "mobile": record.get("mobile"),
            "street": record.get("street"),
            "postal_code": record.get("postal_code"),
            "city": record.get("city"),
            "country": record.get("country"),
            "source": "nextcloud",
        }

    def normalize_person(self, record: dict) -> dict:
        return {
            "first_name": record.get("first_name") or record.get("given_name"),
            "last_name": record.get("last_name") or record.get("family_name") or "",
            "email": record.get("email"),
            "phone": record.get("phone"),
            "mobile": record.get("mobile"),
            "source": "nextcloud",
            "external_id": str(record.get("uid")) if record.get("uid") is not None else None,
        }
