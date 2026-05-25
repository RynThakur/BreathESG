"""
Corporate Travel JSON Parser
==============================
We model the SAP Concur Expense Report export format.

Concur exposes travel data via its v4 Expense Reports API. The export structure
groups expenses under "reports", each with line items ("entries"). Each entry
has an ExpenseTypeCode that maps to a travel category.

Key Concur ExpenseTypeCodes for emissions:
  AIRFR  - Airfare
  HOTEL  - Hotel / lodging
  CARRT  - Car rental
  TAXI   - Taxi / rideshare
  TRAIN  - Rail
  FERRY  - Ferry
  MILES  - Personal car mileage

Real complexity handled:
  - Airport codes (IATA) for flights — we need to derive distance
  - Hotels only give nights + city, not a usable quantity for emissions;
    we store nights as the quantity (emission factor applied downstream)
  - Ground transport may give distance or just cost; we flag missing distance
  - Multi-currency amounts (converted to USD at ingest)
  - Multiple travelers per booking (group bookings)

Distance estimation for flights (IATA code pairs):
  In production, this calls a great-circle-distance service.
  In this prototype we use a lookup table of major routes.
"""

import json
from decimal import Decimal
from datetime import date, datetime
from typing import Optional

# Concur ExpenseTypeCode → ESG category
CONCUR_TYPE_MAP = {
    'AIRFR':  ('travel_flight',  '3'),
    'AIRPU':  ('travel_flight',  '3'),   # airfare purchase
    'HOTEL':  ('travel_hotel',   '3'),
    'LODNG':  ('travel_hotel',   '3'),
    'CARRT':  ('travel_ground',  '3'),   # car rental
    'TAXI':   ('travel_ground',  '3'),
    'UBER':   ('travel_ground',  '3'),
    'TRAIN':  ('travel_ground',  '3'),
    'RAIL':   ('travel_ground',  '3'),
    'FERRY':  ('travel_ground',  '3'),
    'MILES':  ('travel_ground',  '3'),   # personal car mileage
    'GRNDTR': ('travel_ground',  '3'),
}

# Approximate great-circle distances for common routes (km)
# In production: use aviation edge or OpenFlights dataset
FLIGHT_DISTANCES = {
    ('JFK', 'LHR'): 5570,  ('LHR', 'JFK'): 5570,
    ('JFK', 'CDG'): 5836,  ('CDG', 'JFK'): 5836,
    ('JFK', 'SFO'): 4130,  ('SFO', 'JFK'): 4130,
    ('ORD', 'LHR'): 6352,  ('LHR', 'ORD'): 6352,
    ('LAX', 'NRT'): 8754,  ('NRT', 'LAX'): 8754,
    ('BOM', 'LHR'): 7192,  ('LHR', 'BOM'): 7192,
    ('DEL', 'LHR'): 6742,  ('LHR', 'DEL'): 6742,
    ('DXB', 'LHR'): 5517,  ('LHR', 'DXB'): 5517,
    ('SIN', 'LHR'): 10841, ('LHR', 'SIN'): 10841,
    ('SYD', 'LAX'): 12054, ('LAX', 'SYD'): 12054,
    ('JFK', 'ORD'): 1191,  ('ORD', 'JFK'): 1191,
    ('LAX', 'SFO'): 559,   ('SFO', 'LAX'): 559,
}

FX_RATES_TO_USD = {
    'USD': Decimal('1'),
    'EUR': Decimal('1.08'),
    'GBP': Decimal('1.27'),
    'INR': Decimal('0.012'),
    'AUD': Decimal('0.65'),
    'CAD': Decimal('0.74'),
    'JPY': Decimal('0.0067'),
    'AED': Decimal('0.272'),
    'SGD': Decimal('0.74'),
}


def parse_concur_date(value: str) -> Optional[date]:
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%m/%d/%Y'):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def estimate_flight_distance(origin: str, dest: str) -> Optional[Decimal]:
    """Return great-circle distance in km, or None if unknown route."""
    key = (origin.upper(), dest.upper())
    dist = FLIGHT_DISTANCES.get(key)
    return Decimal(str(dist)) if dist else None


def parse_travel_json(file_content: str, tenant, ingest_job):
    """
    Parse a Concur-style expense report JSON export.

    Expected structure:
    {
      "reports": [
        {
          "reportId": "...",
          "reportName": "...",
          "submittedDate": "2024-03-15",
          "entries": [
            {
              "entryId": "...",
              "expenseTypeCode": "AIRFR",
              "transactionDate": "2024-03-10",
              "transactionAmount": 450.00,
              "transactionCurrencyCode": "USD",
              "vendorDescription": "United Airlines",
              "locationCity": "New York",
              "custom1": "JFK",      // origin airport (custom field)
              "custom2": "LHR",      // destination airport
              "custom3": "1",        // traveler count
              "quantity": 1,         // nights for hotel, distance for car
              "comment": "..."
            }
          ]
        }
      ]
    }
    """
    records = []
    errors = []

    try:
        data = json.loads(file_content)
    except json.JSONDecodeError as e:
        return [], [f"Invalid JSON: {e}"]

    reports = data if isinstance(data, list) else data.get('reports', [data])

    for report in reports:
        entries = report.get('entries', report.get('expenseEntries', []))
        report_id = report.get('reportId', report.get('id', ''))

        for entry_num, entry in enumerate(entries):
            expense_code = entry.get('expenseTypeCode', entry.get('type', '')).upper()
            if expense_code not in CONCUR_TYPE_MAP:
                # Not a travel-relevant expense (meals, misc) — skip
                continue

            category, scope = CONCUR_TYPE_MAP[expense_code]
            row_errors = []

            # --- Date ---
            date_str = entry.get('transactionDate', entry.get('date', ''))
            txn_date = parse_concur_date(date_str)
            if txn_date is None:
                row_errors.append(f"Report {report_id}, entry {entry_num}: Cannot parse date '{date_str}'")

            # --- Amount (converted to USD) ---
            raw_amount = entry.get('transactionAmount', entry.get('amount', 0))
            currency = entry.get('transactionCurrencyCode', entry.get('currency', 'USD')).upper()
            fx = FX_RATES_TO_USD.get(currency, Decimal('1'))
            amount_usd = Decimal(str(raw_amount)) * fx

            # --- Route / distance (flights) ---
            origin = (entry.get('custom1') or entry.get('originAirport') or '').upper().strip()
            destination = (entry.get('custom2') or entry.get('destAirport') or '').upper().strip()
            distance_km = None
            anomaly_flags = []

            if category == 'travel_flight':
                if origin and destination:
                    distance_km = estimate_flight_distance(origin, destination)
                    if distance_km is None:
                        anomaly_flags.append('unknown_route_distance')
                    quantity = distance_km or Decimal('0')
                    unit = 'km'
                else:
                    anomaly_flags.append('missing_airport_codes')
                    quantity = amount_usd
                    unit = 'usd'

            elif category == 'travel_hotel':
                # Nights is the meaningful quantity for hotel emissions
                nights = entry.get('quantity', entry.get('nights', 1))
                quantity = Decimal(str(nights))
                unit = 'unit'  # nights

            elif category == 'travel_ground':
                dist = entry.get('quantity', entry.get('distance', None))
                if dist:
                    quantity = Decimal(str(dist))
                    unit = 'km'
                else:
                    quantity = amount_usd
                    unit = 'usd'
                    anomaly_flags.append('no_distance_using_spend')

            else:
                quantity = amount_usd
                unit = 'usd'

            # --- Traveler count ---
            traveler_count = int(entry.get('custom3', entry.get('travelerCount', 1)) or 1)

            if row_errors:
                errors.extend(row_errors)
                continue

            records.append({
                'scope': scope,
                'category': category,
                'quantity': quantity,
                'unit': unit,
                'raw_quantity': str(raw_amount),
                'raw_unit': currency,
                'raw_row': entry,
                'period_start': txn_date,
                'period_end': txn_date,
                'facility_name': entry.get('locationCity', entry.get('location', '')),
                'facility_country': entry.get('locationCountry', ''),
                'origin': origin,
                'destination': destination,
                'distance_km': distance_km,
                'traveler_count': traveler_count,
                'vendor_name': entry.get('vendorDescription', entry.get('vendor', '')),
                'anomaly_flags': anomaly_flags,
            })

    return records, errors
