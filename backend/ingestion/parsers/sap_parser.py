"""
SAP Flat File Parser
====================
SAP IDoc-derived flat files are the most realistic export format for enterprise
integrations. While SAP's OData services exist, most enterprise ESG workflows
receive periodic batch exports — either from the MM (Materials Management) or
FI (Finance) modules — as tab-delimited flat files or CSVs.

We handle the MATMAS/MBGMCR (goods movement) and FI document exports that
contain fuel purchases and procurement spend.

Real-world pain points handled here:
  - German column headers (MENGE = quantity, MEINS = unit of measure, WERKS = plant)
  - Date format: YYYYMMDD (SAP internal format)
  - Units: SAP uses internal UoM codes (L=litres, GAL=gallons, KG=kg, TO=tonnes,
    MMBTU=million BTU, KWH=kWh, PC=piece/count)
  - Plant codes that require lookup table resolution
  - Mixed decimal separators (some SAP configs use comma as decimal)
  - Material descriptions in German
"""

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Optional

# SAP internal UoM → canonical unit mapping
SAP_UNIT_MAP = {
    'L':     ('litre',  Decimal('1')),
    'LTR':   ('litre',  Decimal('1')),
    'GAL':   ('litre',  Decimal('3.78541')),    # US gallon → litre
    'GL':    ('litre',  Decimal('3.78541')),
    'KG':    ('kg',     Decimal('1')),
    'TO':    ('kg',     Decimal('1000')),        # tonne → kg
    'G':     ('kg',     Decimal('0.001')),
    'LB':    ('kg',     Decimal('0.453592')),
    'KWH':   ('kwh',    Decimal('1')),
    'MWH':   ('kwh',    Decimal('1000')),
    'GWH':   ('kwh',    Decimal('1000000')),
    'MMBTU': ('kwh',    Decimal('293.071')),     # MMBTU → kWh
    'GJ':    ('kwh',    Decimal('277.778')),     # GJ → kWh
    'M3':    ('litre',  Decimal('1000')),        # cubic metre → litre (for liquid fuels)
    'PC':    ('unit',   Decimal('1')),
    'ST':    ('unit',   Decimal('1')),           # Stück (German for piece)
    'USD':   ('usd',    Decimal('1')),
    'EUR':   ('usd',    Decimal('1.08')),        # approx; real impl would use FX API
}

# SAP material group → ESG category mapping
# Real SAP material groups (MATKL field) use hierarchical codes
SAP_MATGROUP_TO_CATEGORY = {
    '001':   'fuel_stationary',  # Stationary fuels (heating oil, natural gas)
    '002':   'fuel_mobile',      # Mobile fuels (diesel, petrol for fleet)
    '003':   'fuel_stationary',  # LPG / propane
    '010':   'procurement',      # Raw materials
    '011':   'procurement',      # Packaging
    '020':   'procurement',      # Office supplies
    # Default: procurement
}

# German → English header aliases (common in European SAP configs)
SAP_HEADER_ALIASES = {
    'MENGE':    'quantity',
    'MEINS':    'unit',
    'WERKS':    'plant_code',
    'BUDAT':    'posting_date',
    'BLDAT':    'document_date',
    'BELNR':    'document_number',
    'MATNR':    'material_number',
    'MAKTX':    'material_description',
    'MATKL':    'material_group',
    'LIFNR':    'vendor_number',
    'NAME1':    'vendor_name',
    'WRBTR':    'amount',
    'WAERS':    'currency',
    'KOSTL':    'cost_center',
    # English passthrough
    'quantity': 'quantity',
    'unit':     'unit',
    'plant_code': 'plant_code',
    'posting_date': 'posting_date',
    'document_number': 'document_number',
    'material_number': 'material_number',
    'material_description': 'material_description',
    'material_group': 'material_group',
    'vendor_name': 'vendor_name',
    'amount': 'amount',
    'currency': 'currency',
}


def parse_sap_date(value: str) -> Optional[date]:
    """SAP dates are YYYYMMDD internally; some exports add separators."""
    value = value.strip()
    for fmt in ('%Y%m%d', '%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_sap_quantity(value: str) -> Optional[Decimal]:
    """Handle SAP's comma-as-decimal and thousands separators."""
    value = value.strip()
    # Detect European format: 1.234,56 → 1234.56
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d+)?$', value):
        value = value.replace('.', '').replace(',', '.')
    else:
        value = value.replace(',', '')
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def normalize_unit(raw_unit: str, raw_quantity: Decimal):
    """Convert raw SAP UoM to canonical unit + converted quantity."""
    key = raw_unit.strip().upper()
    if key not in SAP_UNIT_MAP:
        return None, None, f"Unknown SAP unit: {raw_unit}"
    canonical_unit, factor = SAP_UNIT_MAP[key]
    return canonical_unit, raw_quantity * factor, None


def parse_sap_csv(file_content: str, tenant, ingest_job, plant_code_lookup: dict):
    """
    Parse a SAP flat file export.

    Expected columns (after header normalization):
      document_number, posting_date, document_date, plant_code,
      material_number, material_description, material_group,
      quantity, unit, vendor_name, amount, currency

    Returns: (records_data: list[dict], errors: list[dict])
    """
    records = []
    errors = []

    try:
        # Detect delimiter: SAP exports are sometimes tab-delimited
        sample = file_content[:2048]
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t|;')
        reader = csv.DictReader(io.StringIO(file_content), dialect=dialect)
    except csv.Error:
        reader = csv.DictReader(io.StringIO(file_content))

    for row_num, raw_row in enumerate(reader, start=2):
        # Normalize headers
        row = {SAP_HEADER_ALIASES.get(k.strip(), k.strip()): v.strip() for k, v in raw_row.items()}

        row_errors = []

        # --- Quantity ---
        raw_qty_str = row.get('quantity', '')
        raw_qty = parse_sap_quantity(raw_qty_str)
        if raw_qty is None:
            row_errors.append(f"Row {row_num}: Cannot parse quantity '{raw_qty_str}'")

        # --- Unit ---
        raw_unit = row.get('unit', '').upper()
        canonical_unit = converted_qty = unit_error = None
        if raw_qty is not None:
            canonical_unit, converted_qty, unit_error = normalize_unit(raw_unit, raw_qty)
            if unit_error:
                row_errors.append(f"Row {row_num}: {unit_error}")

        # --- Date ---
        date_str = row.get('posting_date') or row.get('document_date', '')
        period_date = parse_sap_date(date_str)
        if period_date is None:
            row_errors.append(f"Row {row_num}: Cannot parse date '{date_str}'")

        # --- Plant code ---
        plant_raw = row.get('plant_code', '')
        plant_obj = plant_code_lookup.get(plant_raw)
        facility_name = plant_obj.name if plant_obj else f'Plant {plant_raw}'
        facility_country = plant_obj.country if plant_obj else ''

        # --- Category ---
        mat_group = row.get('material_group', '').strip()
        category = SAP_MATGROUP_TO_CATEGORY.get(mat_group, 'procurement')
        scope = '1' if category.startswith('fuel') else '3'

        # --- Anomaly flags ---
        anomaly_flags = []
        if canonical_unit is None and not row_errors:
            anomaly_flags.append('unknown_unit')
        if raw_qty and raw_qty < 0:
            anomaly_flags.append('negative_quantity')
        if raw_qty and raw_qty > 1_000_000:
            anomaly_flags.append('outlier_quantity')
        if not plant_obj and plant_raw:
            anomaly_flags.append('unknown_plant_code')

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
            'period_start': period_date,
            'period_end': period_date,
            'facility_name': facility_name,
            'facility_country': facility_country,
            'plant_code': plant_obj,
            'sap_document_number': row.get('document_number', ''),
            'sap_material_code': row.get('material_number', ''),
            'vendor_name': row.get('vendor_name', ''),
            'anomaly_flags': anomaly_flags,
        })

    return records, errors
