from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class ZammadPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="zammad",
        title="Zammad",
        version="1.0.0",
        capabilities=("organizations.read", "users.read", "contacts.write"),
        description="Zammad Connector",
        automation_events=("customer.created", "customer.updated", "person.updated"),
    )

    def connection_hint(self) -> str:
        return "Zammad Verbindung"
