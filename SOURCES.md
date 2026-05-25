# SOURCES

For each of the three data sources: what I researched, what I learned, what my sample data looks like and why, and what would break in a real deployment.

---

## Source 1: SAP Fuel & Procurement (IDoc-derived flat file CSV)

### What I researched

SAP's data exchange formats break down into:
- **IDoc (Intermediate Document)**: SAP's native EDI format, structured as control records + data records + status records. Used for system-to-system integration. Each IDoc type has a specific segment structure (e.g., `E1EDK01` for header, `E1EDP01` for line items in an ORDERS IDoc).
- **OData/REST**: SAP Gateway exposes business objects as OData services. Modern approach for S/4HANA.
- **BAPI**: Remote Function Calls for programmatic data access. Requires ABAP connectivity.
- **Flat file / SE16 export**: Direct table dump from transaction SE16 (Data Browser) or via a custom ABAP report. This is what most companies actually give you when you ask for their data.

For goods movement (fuel and procurement), the relevant SAP tables are:
- `MKPF`/`MSEG`: Material document header and line items (goods movements)
- `BKPF`/`BSEG`: FI accounting document header and line items
- `MARA`/`MAKT`: Material master / material descriptions (often in German for European configs)
- `LFA1`: Vendor master (for vendor name)

Key SAP field names I encountered in research: `BELNR` (document number), `BUDAT` (posting date), `BLDAT` (document date), `WERKS` (plant code), `MATNR` (material number), `MAKTX` (material description, in German if European config), `MATKL` (material group — the taxonomy field for scope classification), `MENGE` (quantity), `MEINS` (unit of measure in SAP internal codes), `NAME1` (vendor name from LFA1), `WRBTR` (amount in document currency), `WAERS` (currency code).

SAP unit of measure codes are internal codes, not standard ISO codes: `L` = litre, `TO` = metric tonne (not `t`), `MMBTU` = million BTU, `KWH` = kilowatt-hour, `PC` = piece, `ST` = Stück (German for piece).

Dates in SAP internal format are `YYYYMMDD` with no separators. Some export configs add separators; some don't.

Decimal format: European SAP configs use comma as decimal separator and period as thousands separator — `1.234,56` means 1234.56, not 1.23456.

### What my sample data looks like and why

```
BELNR,BUDAT,BLDAT,WERKS,MATNR,MAKTX,MATKL,MENGE,MEINS,LIFNR,NAME1,WRBTR,WAERS
5100012345,20240115,20240114,1000,000000000000100001,Diesel Kraftstoff,001,45200,L,...
5100012350,20240131,20240130,1000,000000000000200001,Natural Gas,001,2000,MMBTU,...
```

- `BELNR` uses the real SAP document numbering format (10-digit starting with 5 for MM documents)
- `MATNR` uses the real 18-character zero-padded SAP material number format
- `MAKTX` is in German (`Diesel Kraftstoff` = diesel fuel) — realistic for a European config
- `MATKL` uses two-digit codes that map to fuel categories — I invented these for the prototype; real clients have custom hierarchies
- `MENGE/MEINS` uses real SAP UoM codes (`L`, `MMBTU`)
- `BUDAT`/`BLDAT` are YYYYMMDD as they appear in real exports
- Plant `1000` is the conventional SAP "primary plant" code (Hamburg in this case)

### What would break in a real deployment

1. **Material group mapping**: The `MATKL → Scope 1/3` mapping in the parser is invented. Real clients use their own MATKL taxonomy, which requires a discovery call to understand.
2. **German decimal format**: If the client has a European SAP config, quantities come as `1.500,00` (1500.00). The parser handles this, but it's easy to get wrong.
3. **Material descriptions in German**: `MAKTX` might need translation for analysts who don't read German.
4. **Reversal documents**: SAP creates negative-quantity goods movement documents for returns/reversals. These need to be netted against the original, not treated as a new data point. The parser flags them (`negative_quantity`) but doesn't auto-net.
5. **Multi-plant consolidation**: A client with 50 plants means 50 rows in the PlantCode lookup table, all needing correct country codes for the right emission factors.

---

## Source 2: Utility Electricity (Green Button CSV)

### What I researched

US commercial utility data is available in two formats:
- **Green Button Download My Data**: A standard (NAESB/ESPI) XML or CSV export available through the utility portal's "Download" button. This is what facilities managers actually use. Adopted by Con Edison, PG&E, National Grid, ComEd, and most major US utilities.
- **Green Button Connect My Data**: An OAuth-based API that utilities expose for third-party access. Requires the customer to authorize the connection through the utility portal.
- **EDI 810**: Invoice format used by some large commercial accounts.
- **PDF bills**: The fallback for utilities that don't offer digital export.

The Green Button CSV format (per the ESPI standard and EnergyCAP's implementation) includes:
`account_number, meter_id, commodity, unit, bill_start_date, bill_end_date, consumption, demand_kw, cost, rate_schedule, read_type`

Key nuance: **billing periods don't align with calendar months**. A "January" bill might cover December 28 – January 27. For emissions reporting, you need the actual `bill_start_date` and `bill_end_date`, not the month label. Most naive implementations get this wrong and introduce systematic date errors.

**Estimated vs actual reads**: Utilities flag whether a meter reading is estimated (the meter reader didn't visit, so the utility estimated based on historical usage) or actual. Estimated reads should be flagged for analyst attention because they may be corrected in a future bill.

**Demand charges (kW)**: Commercial electricity bills typically include both a consumption charge (kWh × rate) and a demand charge (peak kW × demand rate). Only kWh matters for emissions. The demand figure is a billing artifact.

### What my sample data looks like and why

```
account_number,meter_id,commodity,unit,bill_start_date,bill_end_date,consumption,...,read_type,facility_name
43406,1424,electric,KWH,2024-01-03,2024-02-02,347000,...,actual,Chicago HQ - North Tower
43407,1425,electric,KWH,2024-02-03,2024-03-05,298000,...,estimated,Chicago HQ - North Tower
```

- Account numbers follow the EnergyCAP example format (5-digit)
- Billing periods deliberately don't align with calendar months — Jan 3 to Feb 2, not Jan 1 to Jan 31
- One record is flagged as `estimated` — this is a realistic scenario and tests the anomaly flagging
- A German facility uses `DE` country code — tests multi-country handling
- Consumption figures (347,000 kWh for a commercial tower over ~30 days) are plausible for a mid-size office building

### What would break in a real deployment

1. **Non-US utilities**: Green Button is US-specific. UK utilities use different portal formats; EU utilities use the EED directive's data formats. A client with EU facilities needs different parsing logic.
2. **Multiple utilities per facility**: A large campus might have electricity from Utility A and gas from Utility B, each with different export formats.
3. **Billing period corrections**: A utility may issue a corrected bill that retroactively changes a prior period's consumption. The current model has no concept of bill amendments — a re-upload would create duplicate records for the same period.
4. **Sub-metering**: A facility may have dozens of sub-meters that roll up to one account. The model handles multiple meter_ids, but visualizing the rollup requires additional logic.
5. **International tariff complexity**: Time-of-use rates, demand response programs, and net metering (solar credits) all appear on bills and need to be either handled or explicitly ignored.

---

## Source 3: Corporate Travel (Concur-style JSON)

### What I researched

Major corporate travel platforms: SAP Concur (market leader), Navan (formerly TripActions), Egencia (Expedia Group), TravelPerk.

**SAP Concur v4 API**: The Expense Reports API (`GET /expensereports/v4/users/{userID}/context/TRAVELER/expensereports`) returns a paginated list of reports, each with entries. Each entry has an `expenseTypeCode` (AIRFR, HOTEL, CARRT, TAXI, etc.), transaction amount, currency, date, and custom fields (up to custom20) that clients configure.

**Key problem with travel data for emissions**: Distance is often not provided. For flights, you typically get the fare and the destination city, but not the distance flown. Airport codes are sometimes in custom fields (custom1/custom2 is a common configuration), sometimes in the `locationCity` field as a string, sometimes absent entirely. For emission calculation, you need distance, so you either use a great-circle distance lookup or fall back to spend-based estimation.

**Navan**: Significantly harder to access programmatically than Concur. Requires admin credentials and special API enablement from Navan support. The data schema is similar in structure.

**Expense type codes relevant to emissions** (from Concur documentation):
- `AIRFR`/`AIRPU`: Airfare
- `HOTEL`/`LODNG`: Hotel/lodging
- `CARRT`: Car rental
- `TAXI`/`UBER`: Ground transport
- `TRAIN`/`RAIL`: Rail
- `MILES`: Personal car mileage (reimbursed)
- `GRNDTR`: General ground transport

**Why hotels use nights, not spend**: The GHG Protocol and DEFRA guidance for Scope 3 Category 6 (business travel) specifies hotel nights as the activity metric, not spend. Hotel spend varies by city (a London hotel costs more than a Delhi hotel) but the physical activity — one person sleeping for one night — is the same. Using spend would overstate emissions for high-cost cities and understate for low-cost ones.

### What my sample data looks like and why

```json
{
  "reports": [{
    "reportId": "RPT-2024-001",
    "entries": [
      {"expenseTypeCode": "AIRFR", "transactionDate": "2024-01-15",
       "transactionAmount": 890.00, "transactionCurrencyCode": "USD",
       "vendorDescription": "United Airlines",
       "custom1": "JFK", "custom2": "LHR", "custom3": "1"},
      {"expenseTypeCode": "HOTEL", "transactionDate": "2024-01-15",
       "transactionAmount": 680.00, "vendorDescription": "Marriott London",
       "quantity": 3}
    ]
  }]
}
```

- `custom1`/`custom2` for airport codes is a real Concur configuration pattern (many companies configure these fields for Scope 3 reporting)
- `custom3` for traveler count handles group bookings
- One flight deliberately uses a route not in the distance lookup table (DEL→BLR) to demonstrate the `unknown_route_distance` flag
- `quantity: 3` for the hotel record = 3 nights, following GHG Protocol guidance
- USD amounts are realistic for 2024 transatlantic business travel fares

### What would break in a real deployment

1. **Airport code gaps**: The distance lookup table covers ~15 major routes. A real deployment needs the full OpenFlights or ICAO dataset (~9,000 airports, 50,000+ route pairs) or an API call to a great-circle distance service.
2. **Non-standard custom field configuration**: Every Concur deployment is configured differently. `custom1`/`custom2` for airport codes is a common pattern, but not universal. Some clients put cost center codes in custom1. This requires a configuration conversation per client.
3. **Connecting flights**: A journey with a connection is typically booked as two separate fare segments. Summing them by route gives the right distance, but matching segments to journeys requires grouping logic the prototype doesn't implement.
4. **Rail vs flight misclassification**: `TRAIN` expense codes are sometimes used for high-speed rail (Eurostar, TGV) that covers distances comparable to short-haul flights. The emission factors are very different — rail is ~80% lower per km than flying. The parser handles `TRAIN` as ground transport, but a real implementation needs to distinguish rail modes.
5. **Concur pagination**: The v4 API paginates at 100 entries per page. A full year of travel for a 5,000-person company could be 50,000+ entries across hundreds of reports. The JSON upload approach handles this implicitly (you upload the full export), but a live API pull needs pagination handling.
