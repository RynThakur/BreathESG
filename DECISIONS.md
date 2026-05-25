# DECISIONS

Every non-obvious choice made during this build, with reasoning and what I'd ask the PM.

---

## SAP: Why flat file CSV, not IDoc or OData?

**The choice**: SAP IDoc-derived flat file CSV, exported via SAP transaction SE16 or a custom ABAP report.

**Why not raw IDoc?** IDoc files are structured EDI documents with control records, data records, and status records — parsing them requires either a dedicated IDoc library or substantial ABAP-side preprocessing. For a prototype integration, this is the wrong layer to engage at. Enterprise IT teams routinely provide flat-file extracts precisely because they don't want to expose live IDoc interfaces to external tools.

**Why not OData (SAP Gateway)?** OData would be the "correct" modern SAP integration. But OData access requires the client to have SAP Gateway configured, specific Fiori services exposed, and network access provisioned — none of which a new client is likely to have ready on day one. OData also requires OAuth/SAML configuration that's out of scope for an onboarding prototype.

**Why flat file CSV?** It's the most realistic format for a first ingestion from an enterprise client. In practice: the sustainability lead emails a CSV, or drops it on an SFTP. The integration doesn't need to be live on day one. Once the data model is proven, the SAP connection can be made direct.

**What I handled**: MM module goods-movement exports (MBGMCR-style) with fuel and procurement line items. Fields: `BELNR` (document number), `BUDAT` (posting date), `WERKS` (plant), `MATNR` (material), `MATKL` (material group), `MENGE/MEINS` (quantity/unit), `NAME1` (vendor), `WRBTR/WAERS` (amount/currency).

**What I ignored**: FI-CO allocations, cost center breakdowns, partial goods receipts, returns/reversals (negative postings). A reversal in SAP creates a new document with negative MENGE — the prototype will flag this as `negative_quantity` rather than automatically netting it out. This is intentional: auto-netting reversals is a common source of audit errors.

**What I'd ask the PM**: Does the client use a European SAP config (comma as decimal separator, German column headers)? Do they export from MM or FI? What material group taxonomy do they use — the default SAP hierarchy or a custom one? This determines whether the MATKL → Scope 1/3 mapping in the parser is accurate.

---

## Utility: Why Green Button CSV, not PDF bills?

**The choice**: Green Button / EnergyCAP CSV format from utility portal download.

**Why not PDF?** PDF parsing is fragile — every utility has a different bill layout, and OCR accuracy drops on scanned bills. A PDF-first approach would require a dedicated parsing service (Azure Form Recognizer, AWS Textract) and template maintenance per utility. This is a real production requirement but wrong scope for a prototype.

**Why Green Button CSV?** The Green Button standard (ESPI/NAESB) is adopted by most major US utilities for commercial customers. It's the standard export format from Con Edison, PG&E, National Grid, ComEd, etc. The CSV variant is what you actually get when you click "Export" on the portal — it's the intersection of "realistic format" and "parseable without external dependencies."

**Key fields**: `account_number`, `meter_id`, `commodity`, `unit`, `bill_start_date`, `bill_end_date`, `consumption`, `demand_kw`, `cost`, `rate_schedule`, `read_type`.

**What I handled**: Multi-meter accounts, billing periods that don't align with calendar months (e.g., Oct 14 – Nov 12 is stored exactly as those dates, not rounded to November), estimated vs actual reads (flagged for analyst review), and commodity types (electric → Scope 2, natural gas → Scope 1).

**What I ignored**: Demand charges (kW) vs energy charges (kWh) — only kWh matters for Scope 2 emissions; demand charges are a billing artifact. Time-of-use rate tiers (on-peak vs off-peak kWh) — for emission calculation you need total kWh, not the tariff breakdown. Reactive power (kVAR).

**What I'd ask the PM**: Which utilities does this client use, and in which countries? For EU clients, the Green Button standard doesn't apply — Eurostat/EED has different data formats. Does the client have a single utility account or hundreds of meters across facilities?

---

## Travel: Why JSON upload, not Concur API pull?

**The choice**: JSON file upload modeled on the Concur v4 Expense Reports API export format.

**Why not live Concur API?** Concur's API requires admin-level credentials, a company UUID, OAuth token provisioning, and in some cases special enablement from Concur support for the Expense Transaction API. None of this is available without the actual client's Concur admin. Building a live API pull without those credentials would be untestable.

**Why JSON?** Concur's v4 API returns JSON. Clients can export their expense data as JSON through Concur's standard export feature, or an admin can pull it via the API and drop the file. The JSON structure I modeled (`reports → entries → expenseTypeCode, transactionDate, transactionAmount, custom1/2 for airport codes`) matches the actual Concur v4 response schema.

**Key decisions within travel parsing:**
- **Flights**: Distance is derived from IATA code pairs (custom1/custom2 fields), not from the fare amount. Using spend as a proxy for emissions is common but less accurate — actual distance is the right driver for flight emissions (using ICAO or DEFRA factors).
- **Hotels**: Quantity = nights (not spend). The emission factor for hotels is per person-night, not per dollar.
- **Ground transport**: Distance preferred; fall back to spend with `no_distance_using_spend` flag if distance isn't in the record.
- **Multi-currency**: FX rates are hardcoded at approximate current rates. I'd flag this — for annual reporting, rates should be the annual average per the GHG Protocol.

**What I ignored**: Rail travel (would be Scope 3 with distance-based factor), ferry, personal car mileage (needs vehicle type). These Concur expense codes exist (`TRAIN`, `MILES`) but are not in the sample data.

**What I'd ask the PM**: Does the client use Concur or Navan? (Navan's API is significantly harder to access — requires special enablement from their support team.) Do they want us to pull live from the API, or is a periodic file export acceptable? How should we handle group bookings where one person books for multiple travelers?

---

## Review workflow: Why a state machine vs free-form status?

The review status is a constrained state machine (`pending → approved | flagged → approved | rejected`) rather than a free-form field. This is intentional. Free-form status fields accumulate entropy — someone types "Approved", someone else types "approved", a third person types "OK to submit". Querying and auditing becomes unreliable.

The state machine also enforces that approval is deliberate: you can't accidentally approve something by changing a dropdown.

---

## Unit normalization: Why at ingest time, not query time?

See MODEL.md. Short answer: query-time normalization means a change to your conversion constants silently rewrites historical data. Auditors need stable, reproducible numbers.

---

## Anomaly flags: Why not block ingest on anomalies?

Because the parser cannot distinguish between a data error and a legitimate unusual value. A 1.5M litre diesel purchase might be wrong, or it might be a legitimate bulk purchase for a large industrial facility. The analyst who knows the client's business is the right person to make that call — not the parser.

Blocking ingest on anomalies would cause real data to be silently dropped, which is worse than surfacing it for review.

---

## Authentication: Why Django session auth, not JWT?

For a server-rendered or same-origin React app calling the Django backend, session auth is simpler and more secure than JWT. No token storage in localStorage (XSS risk), no token refresh logic, built-in CSRF protection via Django's middleware. JWT becomes necessary when the frontend and backend are on different domains with no cookie sharing, or when you have mobile clients — neither applies here.

The tradeoff is that sessions require a shared session store for horizontal scaling. For a Railway deployment with a single backend instance, this is irrelevant.
