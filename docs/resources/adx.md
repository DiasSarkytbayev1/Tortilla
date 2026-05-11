# ADX — connecting from the backend

Quick reference for connecting to Azure Data Explorer from the FastAPI backend
to run analytical queries. ADX is the OLAP store for `bill_items_fact`
(see `docs/scaling-plan.md` §5).

---

## Connection details

| Setting          | Value                                                  |
|------------------|--------------------------------------------------------|
| Cluster URI      | `https://tortilla-adx.spaincentral.kusto.windows.net`  |
| Ingestion URI    | `https://ingest-tortilla-adx.spaincentral.kusto.windows.net` |
| Database         | `analytics`                                            |
| Region           | `spaincentral`                                         |
| Auth (dev)       | Azure CLI (your `az login` token)                      |
| Auth (server)    | Service principal (client ID + secret)                 |

The **Cluster URI** is for *queries*. The **Ingestion URI** is for *writes*
(only the Event Hub → ADX data connection uses this; you don't need it for
analytics endpoints).

---

## Env variables

Add to `.env` and `.env.example`:

```bash
# ADX — analytical queries
ADX_CLUSTER_URI=https://tortilla-adx.spaincentral.kusto.windows.net
ADX_DATABASE=analytics

# Auth (server-side only; local dev uses `az login`)
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<service-principal-app-id>
AZURE_CLIENT_SECRET=<service-principal-secret>
```

Get the tenant ID once: `az account show --query tenantId -o tsv`.

To create a service principal scoped to read the ADX database:

```bash
az ad sp create-for-rbac \
  --name "tortilla-backend-adx" \
  --scopes $(az kusto cluster show -n tortilla-adx -g tortilla-rg --query id -o tsv)
```

Output gives you `appId` (= `AZURE_CLIENT_ID`), `password` (= `AZURE_CLIENT_SECRET`),
and `tenant` (= `AZURE_TENANT_ID`). Then in the ADX web UI run:

```kql
.add database analytics viewers ('aadapp=<AZURE_CLIENT_ID>;<AZURE_TENANT_ID>')
```

---

## Python — package

```bash
# In backend/pyproject.toml dependencies:
azure-kusto-data>=4.0
```

`azure-kusto-data` is for queries. Add `azure-kusto-ingest` only if the backend
also writes to ADX (it shouldn't — ingestion is via Event Hubs).

---

## Python — connect and query

```python
# backend/app/analytics/kql_client.py
import os
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder

ADX_CLUSTER_URI = os.environ["ADX_CLUSTER_URI"]
ADX_DATABASE    = os.environ["ADX_DATABASE"]


def _kcsb():
    """Pick auth strategy from env."""
    if os.getenv("AZURE_CLIENT_ID") and os.getenv("AZURE_CLIENT_SECRET"):
        # Server-side: service principal
        return KustoConnectionStringBuilder.with_aad_application_key_authentication(
            ADX_CLUSTER_URI,
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
            authority_id=os.environ["AZURE_TENANT_ID"],
        )
    # Local dev: reuse `az login`
    return KustoConnectionStringBuilder.with_az_cli_authentication(ADX_CLUSTER_URI)


_client = KustoClient(_kcsb())


def query(kql: str, params: dict | None = None) -> list[dict]:
    """Run a KQL query and return a list of dicts."""
    crp = None
    if params:
        from azure.kusto.data import ClientRequestProperties
        crp = ClientRequestProperties()
        for k, v in params.items():
            crp.set_parameter(k, v)
    result = _client.execute(ADX_DATABASE, kql, crp)
    rows = result.primary_results[0]
    cols = [c.column_name for c in rows.columns]
    return [dict(zip(cols, r.to_list())) for r in rows]
```

Parameterized queries — declare params at the top of the KQL with `declare query_parameters`:

```python
kql = """
declare query_parameters(from_ts: datetime, to_ts: datetime, restaurant_ids: dynamic);
bill_items_fact
| where EventType == "bill.created" and isnull(VoidedAtUtc)
| where SoldAtUtc between (from_ts .. to_ts)
| where array_length(restaurant_ids) == 0 or RestaurantId in (restaurant_ids)
| summarize Revenue = sum(LineTotal), Bills = dcount(BillNo)
"""
rows = query(kql, {
    "from_ts": "2026-05-01T00:00:00Z",
    "to_ts":   "2026-05-31T23:59:59Z",
    "restaurant_ids": [1, 2, 3],
})
```

---

## Example queries — mapping to the analytics endpoints

All examples assume `EventType == "bill.created"` and `isnull(VoidedAtUtc)`
(live bills only — voided ones excluded). See `docs/scaling-plan.md` §7 for
why.

### 1. Overview KPIs (`/api/overview/kpis`)

```kql
bill_items_fact
| where EventType == "bill.created" and isnull(VoidedAtUtc)
| where SoldAtUtc between (datetime(2026-05-01) .. datetime(2026-05-31))
| summarize
    Revenue   = sum(LineTotal),
    Bills     = dcount(BillNo),
    AvgTicket = sum(LineTotal) / todouble(dcount(BillNo))
```

### 2. Best sellers (`/api/best-sellers`)

```kql
bill_items_fact
| where EventType == "bill.created" and isnull(VoidedAtUtc)
| where SoldAtUtc between (datetime(2026-05-01) .. datetime(2026-05-31))
| summarize
    Quantity = sum(Quantity),
    Revenue  = sum(LineTotal)
  by MenuItemId, MenuItemName, MenuItemCategory
| top 20 by Quantity desc
```

### 3. Time series, daily revenue (`/api/time-series`)

```kql
bill_items_fact
| where EventType == "bill.created" and isnull(VoidedAtUtc)
| where SoldAtUtc between (datetime(2026-05-01) .. datetime(2026-05-31))
| summarize
    Revenue = sum(LineTotal),
    Bills   = dcount(BillNo)
  by bin(SoldAtLocal, 1d)
| order by SoldAtLocal asc
```

Hourly grain: `bin(SoldAtLocal, 1h)`. Weekly: `bin(SoldAtLocal, 7d)`.

### 4. Peak hours, DOW × hour heatmap (`/api/peak-hours`)

```kql
bill_items_fact
| where EventType == "bill.created" and isnull(VoidedAtUtc)
| where SoldAtUtc between (datetime(2026-05-01) .. datetime(2026-05-31))
| extend
    Hour = datetime_part("Hour", SoldAtLocal),
    DOW  = dayofweek(SoldAtLocal) / 1d
| summarize Bills = dcount(BillNo) by DOW, Hour
| order by DOW asc, Hour asc
```

### 5. Restaurant comparison (`/api/comparison`)

```kql
bill_items_fact
| where EventType == "bill.created" and isnull(VoidedAtUtc)
| where SoldAtUtc between (datetime(2026-05-01) .. datetime(2026-05-31))
| summarize
    Revenue   = sum(LineTotal),
    Bills     = dcount(BillNo),
    AvgTicket = sum(LineTotal) / todouble(dcount(BillNo)),
    TopItem   = arg_max(Quantity, MenuItemName)
  by RestaurantId, RestaurantName, RestaurantCity
| order by Revenue desc
```

---

## Smoke test — does it work?

After ingesting a few events, run this in the ADX web UI to confirm:

```kql
bill_items_fact | count                              // total events
bill_items_fact | take 5                             // sample rows
bill_items_fact | summarize by EventType             // event type distribution
bill_items_fact | summarize max(SoldAtUtc)           // most recent event
```

Or from Python:

```python
from app.analytics.kql_client import query
print(query("bill_items_fact | count"))
```

If you get `0` rows: check the Event Hub → ADX data connection in the Azure
portal (Data ingestion → tab "Data connections").

---

## Troubleshooting

| Symptom                                            | Likely cause                                            | Fix                                              |
|----------------------------------------------------|---------------------------------------------------------|--------------------------------------------------|
| `Unauthorized` from Python                         | Service principal lacks DB access                       | Run the `.add database analytics viewers` KQL    |
| Local dev: "AzCliCredential failed"                | Not logged in                                           | `az login`                                       |
| Query slow (>2s) on small data                     | Cluster auto-stopped, just resumed                      | First query after wake costs ~30s; subsequent are fast |
| `Table 'bill_items_fact' not found`                | Schema not yet created in the right database            | Check you ran the `.create table` in db `analytics`, not the default |
| Cost climbing                                      | Cluster running 24/7                                    | `az kusto cluster stop -n tortilla-adx -g tortilla-rg` when idle |

---

## Event Hub → ADX (already wired)

Event Hubs are configured to stream into ADX automatically. Producers
write to the Event Hub via the Kafka API; ADX reads via the native
Event Hubs API — same underlying log.

### What exists

| Resource         | Name                                       | Notes                                |
|------------------|--------------------------------------------|--------------------------------------|
| EH namespace     | `kafka-dev-01`                             | Kafka-enabled, region `spaincentral` |
| Event Hub topic  | `bills-raw`                                | Source of all bill events            |
| ADX cluster      | `tortilla-adx`                             | Region `spaincentral`                |
| ADX database     | `analytics`                                | Hot cache 31d, retention 365d        |
| Target table     | `bill_items_fact`                          | Denormalized wide rows               |
| JSON mapping     | `bill_items_mapping`                       | Maps event fields → table columns    |
| Data connection  | `tortilla-adx/analytics/bills-from-eventhub` | EH → ADX, JSON, `$Default` consumer group, Succeeded |

### Kafka bootstrap (for producers)

```
servers:    kafka-dev-01.servicebus.windows.net:9093
topic:      bills-raw
security:   SASL_SSL, mechanism PLAIN
username:   $ConnectionString
password:   <EH connection string from `.env`>
```

### Quick verify

```bash
az kusto data-connection list \
  --cluster-name tortilla-adx \
  --database-name analytics \
  --resource-group tortilla-rg \
  -o table
```

Expect `ProvisioningState: Succeeded` on the `bills-from-eventhub` row.
