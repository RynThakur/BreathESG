# DATA MODEL

## Overview

The data model is built around five concerns the assignment explicitly requires: multi-tenancy, Scope 1/2/3 classification, source-of-truth tracking, unit normalization, and audit trail. Every design decision below traces back to one of those.

---

## Entity Relationship

```
Tenant
  ├── TenantMembership (user ↔ tenant, with role)
  ├── PlantCode (SAP plant lookup table)
  ├── IngestJob (one per upload event)
  │     └── EmissionRecord (N records per job)
  │           └── AuditEvent (append-only log)
```

---

## Multi-Tenancy

Every table has a `tenant_id` foreign key. There is no shared data. Queries always filter by tenant first — the `get_tenant()` helper in views enforces this before any queryset is built.

I chose row-level tenancy (single database, tenant_id column) over a separate-database-per-tenant approach. The tradeoff: shared-database is simpler to operate at prototype scale, but a production deployment handling clients with strict data-residency requirements (GDPR, etc.) would need to reconsider this. I'd flag this to the PM.

`TenantMembership` gives each user a role (`analyst` or `admin`) within a tenant. A user could belong to multiple tenants — this matters for consultants who manage multiple client accounts.

---

## IngestJob

One row per upload event. Tracks:
- **source_type**: which of the three parsers handled this file
- **filename**: the original filename, preserved for audit
- **uploaded_by / uploaded_at**: who triggered the ingest and when
- **status**: `pending → processing → done | failed`
- **rows_total, rows_ok, rows_failed, rows_flagged**: ingest statistics
- **error_log**: JSON array of `{row, reason}` for failed rows

The job is the "provenance envelope" for a batch of records. If an analyst asks "where did this number come from?", they can trace it to a specific file uploaded by a specific person at a specific time.

---

## EmissionRecord (the fact table)

This is where most of the design work lives.

### Scope classification

```
scope: '1' | '2' | '3'
category: fuel_stationary | fuel_mobile | electricity |
          travel_flight | travel_hotel | travel_ground | procurement
```

Scope is set at ingest time by the parser, based on:
- SAP material group codes → Scope 1 (fuel) or Scope 3 (procurement)
- Utility commodity field → Scope 2 (electricity) or Scope 1 (natural gas)
- Concur expense type code → Scope 3 (all travel)

An analyst can override scope/category through the review workflow (the `is_edited` flag tracks this). We don't recalculate scope automatically after an edit — the analyst's judgment is the source of truth once they've reviewed it.

### Unit normalization

All quantities are stored normalized to a canonical unit:

| Source unit | Canonical | Factor |
|---|---|---|
| L, GAL, GL | litre | 1, 3.785, 3.785 |
| KG, TO, LB | kg | 1, 1000, 0.454 |
| KWH, MWH, GWH | kwh | 1, 1000, 1e6 |
| MMBTU | kwh | 293.071 |
| GJ | kwh | 277.778 |
| km | km | 1 |
| USD, EUR, GBP, etc. | usd | FX rate at ingest time |

**Why normalize at ingest rather than at query time?** Because the source data may be corrected or the file may be deleted. Once ingested, the canonical quantity should be stable and auditable. If we stored raw values only and normalized on the fly, a change to the conversion factors would silently change historical figures — which is catastrophic for auditors.

**Raw values are always preserved**: `raw_quantity` and `raw_unit` store exactly what appeared in the source file. `raw_row` stores the full source row as JSON. This means an auditor can always reconstruct the original data.

### Source-of-truth tracking

Every record has:
- `ingest_job` → which upload produced this record
- `raw_row` → full snapshot of the source row at ingest time
- `is_edited` + `edit_reason` → whether a human corrected the value post-ingest
- `reviewed_by` + `reviewed_at` → which analyst signed off and when
- `AuditEvent` entries → the full timeline of state changes

The combination of these means you can always answer: "What did the original file say, what did the system parse it as, did anyone change it, who approved it, and when?"

### Review state machine

```
pending → approved
pending → flagged → approved
pending → rejected
flagged → approved
```

Records cannot go from `approved` back to `pending` without an edit action (which creates a new audit event). This is intentional — once something is approved, reopening it should be a deliberate action with a paper trail, not an accidental click.

### Anomaly flags

Flags are set at parse time by the parser and stored as a JSON array on the record. Examples:
- `outlier_quantity` — value exceeds a threshold for that category
- `estimated_read` — utility meter reading flagged as estimated
- `unknown_plant_code` — SAP plant code not in the lookup table
- `unknown_route_distance` — flight route not in distance table
- `no_distance_using_spend` — ground transport had no distance; fell back to USD

Flags do not block ingest — the record is created in `pending` status and surfaced to the analyst for judgment. This is correct because the parser cannot know whether an "outlier" is a genuine data error or a legitimate large purchase.

### Soft delete

Records are never hard-deleted. `is_deleted` moves them out of normal queries but they remain in the database and in the audit log. This is essential for audit integrity.

---

## PlantCode

SAP plant codes (`WERKS` field) are meaningless without a lookup table — `1000` could be any facility. The `PlantCode` table maps codes to human-readable names plus country and region.

In a real deployment, this table would be populated from the client's SAP organizational structure (transaction code OX10). For this prototype, it's seeded with demo data and can be managed through the API.

Records where the plant code isn't found get an `unknown_plant_code` anomaly flag rather than failing outright — a missing lookup shouldn't block data from being reviewed.

---

## AuditEvent

Append-only. Never updated, never deleted. Every state change to an `EmissionRecord` creates an `AuditEvent` with:
- `event_type`: ingested | approved | flagged | rejected | edited | deleted
- `actor`: the user who triggered it (or `null` for system events)
- `timestamp`: auto-set
- `payload`: JSON snapshot — for edits, includes before/after values; for reviews, includes notes

This is the paper trail that goes to auditors. The audit log is separate from the record itself so that even if someone with database access modifies a record directly, the audit log still reflects what happened through the application.

---

## What I would add with more time

1. **Emission factors table**: A separate `EmissionFactor` model keyed by (category, unit, country, year) that converts normalized quantities to tCO₂e. Currently the app ingests and reviews activity data but doesn't compute the final carbon figure — that step was deliberately excluded (see TRADEOFFS.md).

2. **Reporting period model**: A `ReportingPeriod` that groups approved records for a specific date range and locks them for submission. Right now "locking for audit" is implicit (approved records shouldn't be edited), but a proper period model would make this explicit.

3. **FX rate history table**: Currently FX rates are hardcoded constants in the travel parser. A real system would fetch rates from an external service at ingest time and store the rate used per record.
