# ContactSync Plugin-Schnittstelle 3.4.3

Die Connector-Plugins verwenden ab 3.4.3 eine einheitliche asynchrone Schnittstelle.

Pflichtoperationen:

- `test_connection(config)`
- `fetch_customers(config, *, since=None)`
- `fetch_persons(config, *, since=None)`
- `create_customer(config, customer)`
- `update_customer(config, external_id, customer)`
- `create_person(config, person)`
- `update_person(config, external_id, person)`

Alle Plugins müssen diese Methoden bereitstellen. Noch nicht an einen produktiven Endpunkt angebundene Operationen melden `PluginOperationNotImplemented`. Dadurch kann der Core zwischen fehlender Implementierung und einem echten Verbindungs-/API-Fehler unterscheiden.

Die eigentliche Provider-Kommunikation wird pro Connector schrittweise implementiert; die Schnittstelle bleibt dabei stabil.