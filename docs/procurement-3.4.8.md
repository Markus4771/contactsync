# ContactSync 3.4.8 – Automatisierte Beschaffung

Punkt 8 ergänzt eine Beschaffungs-Bridge zwischen ContactSync, dem vorhandenen Automatisierungs-Worker und externen Prozessen wie n8n/Odoo.

## Workflow

1. Eine Beschaffungsanforderung wird als `draft` angelegt.
2. ContactSync erzeugt `procurement.created`.
3. Nach Freigabe wird `procurement.approved` erzeugt.
4. Der vorhandene Webhook-Worker kann das Ereignis an n8n weitergeben.
5. n8n bzw. die vorhandene Bestellautomation kann daraus eine Bestellung in Odoo erzeugen.
6. Die externe Bestellnummer wird beim Status `ordered` als `external_order_id` zurückgeschrieben.
7. Nach Wareneingang kann der Status auf `received` gesetzt werden.

Statuswerte: `draft`, `approved`, `ordered`, `received`, `cancelled`.

CLI-Beispiele:

```bash
contactsync-procurement create "Notebook für Techniker" --supplier "Lieferant" --quantity 2 --unit-price 799
contactsync-procurement status 1 approved
contactsync-procurement status 1 ordered --external-order-id PO-2026-1001
contactsync-procurement list --status ordered
```

Die eigentliche Bestellung beim Händler bleibt bewusst außerhalb von ContactSync. ContactSync verwaltet Anforderung, Kundenbezug, Status und Automatisierungsereignisse; n8n/Odoo übernehmen die Beschaffungslogik.
