from contactsync.plugins.base import ConnectorPlugin, PluginMetadata


class OdooPlugin(ConnectorPlugin):
    metadata = PluginMetadata(
        key="odoo",
        title="Odoo",
        version="1.0.0",
        capabilities=("partners.read", "partners.write", "delta"),
        description="Odoo Connector",
        automation_events=("customer.created", "customer.updated", "person.updated"),
    )

    def connection_hint(self) -> str:
        return "Odoo Verbindung"
