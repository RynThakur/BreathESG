"""
Breathe ESG — Ingestion Data Model
===================================
Design principles:
  1. Multi-tenancy via Tenant → every query filters by tenant_id
  2. Source-of-truth: every EmissionRecord knows which IngestJob produced it,
     what file/row it came from, and whether a human edited it post-ingestion
  3. Scope 1/2/3 is set at ingest time and can be overridden by an analyst
  4. All quantities are normalized to a canonical unit at ingest time;
     the original raw value + unit are preserved for auditing
  5. Analyst approval is a state machine: pending → approved | flagged → approved
  6. Audit trail is append-only via AuditEvent; records are never hard-deleted
"""

from django.db import models
from django.contrib.auth.models import User
import uuid


# ---------------------------------------------------------------------------
# Tenant (multi-tenancy root)
# ---------------------------------------------------------------------------

class Tenant(models.Model):
    """One row per client company.  Every other model FK's back to this."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantMembership(models.Model):
    """Which users belong to which tenant, with what role."""
    ROLES = [('analyst', 'Analyst'), ('admin', 'Admin')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLES, default='analyst')

    class Meta:
        unique_together = ('user', 'tenant')


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

class PlantCode(models.Model):
    """SAP plant codes → human-readable facility names + location metadata.
    Without this table, SAP rows are meaningless (plant '1000' could be anything)."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='plant_codes')
    code = models.CharField(max_length=20)           # e.g. '1000', 'DE01'
    name = models.CharField(max_length=255)           # e.g. 'Hamburg Refinery'
    country = models.CharField(max_length=2, blank=True)   # ISO 3166-1 alpha-2
    region = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f'{self.code} — {self.name}'


# ---------------------------------------------------------------------------
# Ingest jobs (one per uploaded file / API pull)
# ---------------------------------------------------------------------------

class IngestJob(models.Model):
    """Tracks a single ingestion event: what came in, from where, and what happened."""
    SOURCE_TYPES = [
        ('sap_flat',   'SAP Flat File (IDoc-derived CSV)'),
        ('utility_csv', 'Utility Portal CSV'),
        ('travel_json', 'Corporate Travel JSON (Concur-style)'),
    ]
    STATUS = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('done',       'Done'),
        ('failed',     'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ingest_jobs')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    filename = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    rows_total = models.IntegerField(default=0)
    rows_ok = models.IntegerField(default=0)
    rows_failed = models.IntegerField(default=0)
    rows_flagged = models.IntegerField(default=0)
    error_log = models.JSONField(default=list)   # list of {row, reason}

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.source_type} / {self.filename} [{self.status}]'


# ---------------------------------------------------------------------------
# Emission records (the canonical normalized fact table)
# ---------------------------------------------------------------------------

class EmissionRecord(models.Model):
    """
    One row = one emission-relevant activity event, fully normalized.

    Unit normalization strategy
    ---------------------------
    All energy quantities → kWh
    All fuel quantities → litres (liquid fuels) or kg (solid/gas fuels)
    All distance → km
    Monetary values → USD (at ingest-time FX if multi-currency)

    Scope classification
    --------------------
    Scope 1: Direct combustion at company facilities (fuel, fleet)
    Scope 2: Purchased electricity / heat / cooling
    Scope 3: Business travel, supply chain, employee commute (we handle travel here)
    """

    SCOPE = [('1', 'Scope 1'), ('2', 'Scope 2'), ('3', 'Scope 3')]
    CATEGORY = [
        # Scope 1
        ('fuel_stationary',   'Stationary Combustion (fuel)'),
        ('fuel_mobile',       'Mobile Combustion (fleet/vehicles)'),
        # Scope 2
        ('electricity',       'Purchased Electricity'),
        # Scope 3
        ('travel_flight',     'Business Travel — Flight'),
        ('travel_hotel',      'Business Travel — Hotel'),
        ('travel_ground',     'Business Travel — Ground Transport'),
        ('procurement',       'Purchased Goods & Services'),
    ]
    REVIEW_STATUS = [
        ('pending',  'Pending Review'),
        ('approved', 'Approved'),
        ('flagged',  'Flagged'),
        ('rejected', 'Rejected'),
    ]
    UNIT_CHOICES = [
        ('kwh',    'kWh'),
        ('litre',  'Litre'),
        ('kg',     'Kilogram'),
        ('km',     'Kilometre'),
        ('usd',    'USD'),
        ('unit',   'Unit (count)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')
    ingest_job = models.ForeignKey(IngestJob, on_delete=models.CASCADE, related_name='records')

    # Classification
    scope = models.CharField(max_length=1, choices=SCOPE)
    category = models.CharField(max_length=30, choices=CATEGORY)

    # Activity data — normalized
    quantity = models.DecimalField(max_digits=20, decimal_places=4)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)

    # Raw values preserved for audit
    raw_quantity = models.CharField(max_length=100)   # exactly as it appeared in source
    raw_unit = models.CharField(max_length=50)        # e.g. 'GAL', 'MMBTU', 'L'
    raw_row = models.JSONField(default=dict)          # full source row snapshot

    # Temporal
    period_start = models.DateField()
    period_end = models.DateField()

    # Facility / location
    facility_name = models.CharField(max_length=255, blank=True)
    facility_country = models.CharField(max_length=2, blank=True)
    plant_code = models.ForeignKey(PlantCode, null=True, blank=True, on_delete=models.SET_NULL)

    # Travel-specific
    origin = models.CharField(max_length=10, blank=True)   # IATA code or city
    destination = models.CharField(max_length=10, blank=True)
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    traveler_count = models.IntegerField(default=1)

    # Utility-specific
    meter_id = models.CharField(max_length=100, blank=True)
    tariff_code = models.CharField(max_length=100, blank=True)
    is_estimated_read = models.BooleanField(default=False)

    # SAP-specific
    sap_document_number = models.CharField(max_length=50, blank=True)
    sap_material_code = models.CharField(max_length=50, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True)

    # Review workflow
    review_status = models.CharField(max_length=10, choices=REVIEW_STATUS, default='pending')
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Anomaly flags set during ingest
    anomaly_flags = models.JSONField(default=list)  # e.g. ['unit_mismatch', 'outlier_quantity']

    # Edit tracking — was this record manually corrected after ingest?
    is_edited = models.BooleanField(default=False)
    edit_reason = models.TextField(blank=True)

    # Soft delete
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['tenant', 'scope', 'review_status']),
            models.Index(fields=['tenant', 'category', 'period_start']),
            models.Index(fields=['ingest_job']),
        ]

    def __str__(self):
        return f'{self.scope}/{self.category} | {self.quantity}{self.unit} | {self.period_start}'


# ---------------------------------------------------------------------------
# Audit trail (append-only)
# ---------------------------------------------------------------------------

class AuditEvent(models.Model):
    """Every state change to an EmissionRecord is logged here.  Never updated, never deleted."""
    EVENT_TYPES = [
        ('ingested',  'Record Ingested'),
        ('approved',  'Record Approved'),
        ('flagged',   'Record Flagged'),
        ('rejected',  'Record Rejected'),
        ('edited',    'Record Edited'),
        ('deleted',   'Record Soft-Deleted'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)   # before/after snapshot for edits

    class Meta:
        ordering = ['timestamp']
