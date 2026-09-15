from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points
from typing import Iterable

from contactsync.plugins.base import ConnectorPlugin

BUILTIN_PLUGINS = (
    "contactsync.plugins.odoo_runtime:OdooRuntimePlugin",
    "contactsync.plugins.zammad_runtime:ZammadRuntimePlugin",
    "contactsync.plugins.threecx_runtime:ThreeCXRuntimePlugin",
    "contactsync.plugins.nextcloud_runtime:NextcloudRuntimePlugin",
    "contactsync.plugins.glpi_runtime:GLPIRuntimePlugin",
    "contactsync.plugins.netlock:NetLockRMMPlugin",
    "contactsync.plugins.checkmk_plugin:CheckmkPlugin",
)

PLATFORM_ROUTES = (
    ("contactsync.rmm_api", "/api/v1/devices"),
    ("contactsync.netlock_api", "/api/v1/netlock/import-devices"),
    ("contactsync.security_api", "/api/v1/auth/login"),
    ("contactsync.field_mapping_api", "/api/v1/field-mappings"),
    ("contactsync.device_page", "/devices"),
    ("contactsync.customer_overview", "/api/v1/customers/{customer_id}/overview"),
    ("contactsync.incidents_page", "/api/v1/incidents"),
    ("contactsync.automation_page", "/api/v1/automation/monitoring"),
    ("contactsync.connector_status", "/api/v1/connectors/status"),
)


class PluginManager:
    def __init__(self, specs: Iterable[str] | None = None) -> None:
        self._plugins: dict[str, ConnectorPlugin] = {}
        self._routes_attached = False
        for spec in specs or BUILTIN_PLUGINS:
            self.register(self._load_spec(spec))
        self._load_external_plugins()

    @staticmethod
    def _load_spec(spec: str) -> ConnectorPlugin:
        module_name, class_name = spec.split(":", 1)
        plugin_cls = getattr(import_module(module_name), class_name)
        return plugin_cls()

    def _load_external_plugins(self) -> None:
        try:
            discovered = entry_points(group="contactsync.plugins")
        except TypeError:
            discovered = entry_points().get("contactsync.plugins", [])
        for item in discovered:
            self.register(item.load()())

    def attach_plugin_routes(self) -> None:
        """Attach platform and plugin routes once the global manager exists."""
        if self._routes_attached:
            return
        try:
            from contactsync.main import app
        except (ImportError, AttributeError):
            return

        # Platform routes are owned by ContactSync, not by the NetLock plugin.
        # This also makes their registration deterministic when a plugin hook
        # cannot be imported during application startup.
        for module_name, marker_path in PLATFORM_ROUTES:
            if any(getattr(route, "path", "") == marker_path for route in app.routes):
                continue
            router = getattr(import_module(module_name), "router")
            app.include_router(router)

        if not getattr(app.state, "security_guard_installed", False):
            guard = getattr(import_module("contactsync.security_guard"), "SecurityGuardMiddleware")
            app.add_middleware(guard)
            app.state.security_guard_installed = True

        detail_path = "/devices/{device_id}"
        if not any(getattr(route, "path", "") == detail_path for route in app.routes):
            detail_module = import_module("contactsync.device_detail")
            app.add_api_route(
                detail_path,
                getattr(detail_module, "device_detail_page"),
                methods=["GET"],
                response_class=getattr(detail_module, "HTMLResponse"),
                tags=["devices-ui"],
            )

        for plugin in self.all():
            attach_routes = getattr(plugin, "attach_routes", None)
            if callable(attach_routes):
                attach_routes()
        self._routes_attached = True

    def register(self, plugin: ConnectorPlugin) -> None:
        key = plugin.metadata.key
        if key in self._plugins:
            raise ValueError(f"Plugin-Schlüssel bereits registriert: {key}")
        self._plugins[key] = plugin

    def get(self, key: str) -> ConnectorPlugin:
        return self._plugins[key]

    def all(self) -> list[ConnectorPlugin]:
        return list(self._plugins.values())

    def definitions(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for plugin in self.all():
            definition = plugin.definition()
            if not plugin.supports_contact_sync():
                specialized = list(definition.get("operations", []))
                if specialized != list(ConnectorPlugin.SYNC_OPERATIONS):
                    definition["specialized_operations"] = specialized
                definition["operations"] = list(ConnectorPlugin.SYNC_OPERATIONS)
            result[plugin.metadata.key] = definition
        return result

    def contact_sync_plugins(self) -> list[ConnectorPlugin]:
        return [plugin for plugin in self.all() if plugin.supports_contact_sync()]

    def contact_sync_keys(self) -> tuple[str, ...]:
        return tuple(plugin.metadata.key for plugin in self.contact_sync_plugins())

    def supports_contact_sync(self, key: str) -> bool:
        plugin = self._plugins.get(key)
        return bool(plugin and plugin.supports_contact_sync())


_MANAGER: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    global _MANAGER
    if _MANAGER is None:
        manager = PluginManager()
        _MANAGER = manager
    # Route attachment is retried until main.app is fully available. This is
    # safe because attach_plugin_routes is idempotent.
    if not _MANAGER._routes_attached:
        _MANAGER.attach_plugin_routes()
    return _MANAGER


def connector_definitions() -> dict[str, dict]:
    return get_plugin_manager().definitions()
