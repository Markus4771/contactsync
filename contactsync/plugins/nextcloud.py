from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class NextcloudPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="nextcloud",
        title="Nextcloud CardDAV",
        version="1.0.0",
        capabilities=("contacts.read", "contacts.write", "delta"),
        description="Nextcloud Connector",
        automation_events=("customer.updated", "person.updated"),
    )

    def connection_hint(self) -> str:
        return "Nextcloud Verbindung"
