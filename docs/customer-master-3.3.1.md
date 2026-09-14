# Kundenstamm – ContactSync Professional 3.3.1

## Datenmodell

ContactSync trennt Kunden/Firmen von Ansprechpartnern. Ein Kunde kann mehrere Ansprechpartner besitzen.

### Kunde / Firma

- `customer_number` – Kundennummer, eindeutig
- `name` – Firmenname bzw. Name des Privatkunden
- `customer_type` – Firma oder Privatkunde
- `email` – zentrale E-Mail-Adresse
- `phone` – zentrale Telefonnummer
- `mobile` – Mobilnummer
- `street`
- `postal_code`
- `city`
- `country`
- `website`
- `vat_id` – USt-IdNr.
- `tax_number` – Steuernummer
- `debtor_number` – Debitorennummer
- `industry` – Branche
- `status` – aktiv/inaktiv
- `source` – führende bzw. ursprüngliche Datenquelle
- `tags`
- `notes`
- `assigned_technician`
- `contract_type`
- `contract_start`
- `contract_end`
- `created_at`
- `updated_at`

### Ansprechpartner

- `customer_id` – Zuordnung zum Kunden
- `first_name`
- `last_name`
- `email`
- `phone`
- `mobile`
- `function`
- `department`
- `is_primary`
- `status`
- `source`
- `external_id`
- `created_at`
- `updated_at`

## Synchronisation

Die Kundennummer wird als wichtiger Abgleichschlüssel verwendet. Externe IDs der Connectoren bleiben zusätzlich erhalten. Feldmapping wird zentral gepflegt und nicht auf den einzelnen Connector-Seiten.

Kern-Connectoren für 3.3.x:

- Odoo
- Zammad
- 3CX
- Nextcloud CardDAV

Bestehende Kontakte aus 3.3.0 dürfen bei der Datenbankmigration nicht gelöscht werden.
