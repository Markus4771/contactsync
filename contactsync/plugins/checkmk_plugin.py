from contactsync.plugins.checkmk_runtime import CheckmkRuntimePlugin


class CheckmkPlugin(CheckmkRuntimePlugin):
    def __init__(self) -> None:
        from contactsync.main import app
        from contactsync.monitoring_api import router
        if not any(getattr(item, "path", "") == "/api/v1/monitoring/summary" for item in app.routes):
            app.include_router(router)
