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


class PluginManager:
    def __init__(self, specs: Iterable[str] | None = None) -> None:
        self._plugins: dict[str, ConnectorPlugin] = {}
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
            plugin_obj = item.load()()
            self.register(plugin_obj)

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
        _MANAGER = PluginManager()
    return _MANAGER


def connector_definitions() -> dict[str, dict]:
    return get_plugin_manager().definitions()
