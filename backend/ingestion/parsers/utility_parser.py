"""
Utility Portal CSV Parser
==========================
We model the Green Button / EnergyCAP flat-file format — the de-facto standard
for US commercial utility portal exports. This is what a facilities manager
downloads from Con Edison, PG&E, National Grid, etc.

Real Green Button CSV columns (per EnergyCAP / ESPI spec):
  account_number, meter_id, commodity, unit, bill_start_date, bill_end_date,
  consumption, demand_kw, cost, rate_schedule, read_type (actual/estimated)

Key complexity handled:
  - Billing periods don't align with calendar months (a "November bill" might
    cover Oct 14 – Nov 12). We store period_start/period_end exactly.
  - Read type: actual vs estimated — flagged for analyst review
  - Demand charges (kW) vs energy consumption (kWh) are different things;
    we only care about kWh for Scope 2 emissions
  - Multiple meters per account, multiple accounts per tenant
  - Unit variations: kWh, MWh, Wh, therms (gas), ccf (gas), MMBTU
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Optional

UTILITY_UNIT_MAP = {
    'KWH':   ('kwh', Decimal('1')),
    'MWH':   ('kwh', Decimal('1000')),
    'WH':    ('kwh', Decimal('0.001')),
    'THERM': ('kwh', Decimal('29.3071')),   # therm → kWh
    'THERMS':('kwh', Decimal('29.3071')),
    'CCF':   ('kwh', Decimal('29.3')),      # 100 cubic feet of gas ≈ 29.3 kWh
    'MCF':   ('kwh', Decimal('293')),       # 1000 cubic feet → kWh
    'MMBTU': ('kwh', Decimal('293.071')),
    'GJ':    ('kwh', Decimal('277.778')),
}

# Commodity → scope mapping
COMMODITY_SCOPE = {
    'electric':   '2',  # Purchased electricity = Scope 2
    'electricity':'2',
    'gas':        '1',  # Natural gas combustion = Scope 1
    'naturalgas': '1',
    'steam':      '2',  # District heating = Scope 2
    'chilled_water': '2',
}


def parse_utility_date(value: str) -> Optional[date]:
    value = value.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%Y%m%d'):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_utility_csv(file_content: str, tenant, ingest_job):
    """
    Parse a utility portal CSV export.

    Expected columns (case-insensitive):
      account_number, meter_id, commodity, unit, bill_start_date, bill_end_date,
      consumption, demand_kw, cost, rate_schedule, read_type, facility_name,
      facility_country
    """
    records = []
    errors = []

    try:
        sample = file_content[:2048]
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t;')
    except csv.Error:
        dialect = 'excel'

    reader = csv.DictReader(io.StringIO(file_content), dialect=dialect)

    # Normalize headers to lowercase
    def norm(s): return s.strip().lower().replace(' ', '_').replace('-', '_')

    for row_num, raw_row in enumerate(reader, start=2):
        row = {norm(k): v.strip() for k, v in raw_row.items() if k}
        row_errors = []

        # --- Consumption ---
        raw_qty_str = row.get('consumption', row.get('usage', row.get('kwh', '')))
        try:
            raw_qty = Decimal(raw_qty_str.replace(',', ''))
        except (InvalidOperation, AttributeError):
            row_errors.append(f"Row {row_num}: Cannot parse consumption '{raw_qty_str}'")
            raw_qty = None

        # --- Unit ---
        raw_unit = row.get('unit', row.get('uom', 'KWH')).strip().upper()
        canonical_unit = converted_qty = None
        if raw_qty is not None:
            mapping = UTILITY_UNIT_MAP.get(raw_unit)
            if mapping:
                canonical_unit, factor = mapping
                converted_qty = raw_qty * factor
            else:
                row_errors.append(f"Row {row_num}: Unknown utility unit '{raw_unit}'")

        # --- Dates ---
        start_str = row.get('bill_start_date', row.get('start_date', ''))
        end_str = row.get('bill_end_date', row.get('end_date', row.get('service_end', '')))
        period_start = parse_utility_date(start_str)
        period_end = parse_utility_date(end_str)
        if period_start is None:
            row_errors.append(f"Row {row_num}: Cannot parse bill_start_date '{start_str}'")
        if period_end is None:
            row_errors.append(f"Row {row_num}: Cannot parse bill_end_date '{end_str}'")

        # --- Scope / commodity ---
        commodity = row.get('commodity', 'electric').strip().lower().replace(' ', '')
        scope = COMMODITY_SCOPE.get(commodity, '2')
        category = 'electricity' if scope == '2' else 'fuel_stationary'

        # --- Read type ---
        read_type = row.get('read_type', row.get('reading_type', 'actual')).strip().lower()
        is_estimated = read_type in ('estimated', 'estimate', 'e', 'est')

        # --- Anomaly flags ---
        anomaly_flags = []
        if is_estimated:
            anomaly_flags.append('estimated_read')
        if raw_qty and raw_qty < 0:
            anomaly_flags.append('negative_consumption')
        if raw_qty and raw_qty > 5_000_000:
            anomaly_flags.append('outlier_consumption')
        if period_start and period_end:
            days = (period_end - period_start).days
            if days > 45:
                anomaly_flags.append('long_billing_period')
            if days < 20:
                anomaly_flags.append('short_billing_period')

        if row_errors:
            errors.extend(row_errors)
            continue

        records.append({
            'scope': scope,
            'category': category,
            'quantity': converted_qty,
            'unit': canonical_unit,
            'raw_quantity': raw_qty_str,
            'raw_unit': raw_unit,
            'raw_row': dict(raw_row),
            'period_start': period_start,
            'period_end': period_end,
            'facility_name': row.get('facility_name', row.get('service_address', '')),
            'facility_country': row.get('country', row.get('facility_country', 'US')),
            'meter_id': row.get('meter_id', row.get('meter_number', '')),
            'tariff_code': row.get('rate_schedule', row.get('tariff', '')),
            'is_estimated_read': is_estimated,
            'anomaly_flags': anomaly_flags,
        })

    return records, errors
