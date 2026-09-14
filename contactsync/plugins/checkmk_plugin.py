from contactsync.plugins.base import ConnectorPlugin
from contactsync.plugins.checkmk_runtime import CheckmkRuntimePlugin


class CheckmkPlugin(CheckmkRuntimePlugin):
    def __init__(self) -> None:
        from contactsync.main import app
        from contactsync.monitoring_api import router
        if not any(getattr(item, "path", "") == "/api/v1/monitoring/summary" for item in app.routes):
            app.include_router(router)

    def definition(self):
        definition = super().definition()
        definition["monitoring_operations"] = definition["operations"]
        definition["operations"] = list(ConnectorPlugin.SYNC_OPERATIONS)
        return definition
