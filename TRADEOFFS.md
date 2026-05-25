# TRADEOFFS

Three things I deliberately did not build, and why.

---

## 1. Emission factor calculation (tCO₂e output)

**What I didn't build**: The final step of converting normalized activity data (litres of diesel, kWh of electricity, km of flight) into tonnes of CO₂ equivalent.

**Why not**: Emission factors are jurisdiction-specific, year-specific, and methodology-specific. The DEFRA factors for UK grid electricity are different from the EPA eGRID factors for US electricity, which are different again from the IEA factors used by most non-US companies. Getting this wrong — using the wrong factor for the wrong jurisdiction — produces numbers that will fail audit and damage the client relationship.

This is not a hard engineering problem. It's a data problem: you need a maintained table of `(category, unit, country, year) → tCO₂e/unit` with documented sources. Building a half-baked version in 4 days risks giving analysts false confidence in numbers that haven't been properly sourced.

**What I built instead**: The data model has a clear hook for this (`quantity` in canonical units + `scope` + `category` + `facility_country` on every record). When the emission factor table is added, the calculation is a simple join and multiply. Deferring the calculation doesn't compromise the data model — it just means the dashboard shows activity quantities rather than tCO₂e.

**What I'd ask the PM**: Which methodology is the client required to follow (GHG Protocol, ISO 14064, TCFD)? Which emission factor database (DEFRA, EPA, IPCC, custom)? This determines the factor table schema and sourcing process.

---

## 2. Live API connections (SAP OData, Concur API pull, utility APIs)

**What I didn't build**: Direct programmatic connections to SAP Gateway, the Concur v4 API, or utility Green Button Connect APIs.

**Why not**: Live API connections require credentials, network access, and schema agreements with the client's IT team — none of which can be prototyped without the actual client. Building mock API connectors would be testing the wrong thing: the interesting complexity is in parsing and normalization, not in HTTP client code.

More importantly, file upload is the right first integration for an onboarding client. A new enterprise client is not going to provision SAP API credentials for a vendor they haven't vetted yet. File upload gets data flowing immediately, proves the data model, and builds trust before asking for API access.

**What I'd build next**: Once the model is proven with file uploads, I'd add scheduled API pulls as a background job per source type. The parsers are already separated from the ingest view — plugging in an API pull that calls `parse_sap_csv()` with data fetched from OData rather than from an uploaded file is a minimal change.

---

## 3. Role-based access control beyond analyst/admin

**What I didn't build**: Fine-grained permissions — e.g., a user who can upload but not approve, or a user who can only see Scope 2 records, or a facility manager who can only see their own plant.

**Why not**: RBAC at this granularity requires a clear requirements conversation with the client. Enterprise ESG reporting involves multiple stakeholders: the sustainability manager who owns the process, facility managers who know their own data, the CFO who needs to sign off, the external auditor who needs read-only access. Getting the permission model wrong means either too much access (audit risk) or too little (the tool becomes unusable).

The current model (`analyst` vs `admin` within a tenant) is enough to demonstrate the workflow and gather requirements. Adding Django Guardian or a custom permission table once the roles are defined is straightforward.

**What I'd ask the PM**: Who are the user types? Does the external auditor get a login, or do they receive a locked PDF export? Should the same person who uploads data be allowed to approve it (conflict of interest)?
