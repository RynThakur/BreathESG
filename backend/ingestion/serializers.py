from rest_framework import serializers
from .models import Tenant, IngestJob, EmissionRecord, AuditEvent, PlantCode


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'slug', 'created_at']


class PlantCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlantCode
        fields = ['id', 'code', 'name', 'country', 'region']


class IngestJobSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = IngestJob
        fields = [
            'id', 'source_type', 'filename', 'uploaded_by_name',
            'uploaded_at', 'status', 'rows_total', 'rows_ok',
            'rows_failed', 'rows_flagged', 'error_log'
        ]

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username if obj.uploaded_by else None


class EmissionRecordSerializer(serializers.ModelSerializer):
    ingest_job_filename = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'category', 'quantity', 'unit',
            'raw_quantity', 'raw_unit',
            'period_start', 'period_end',
            'facility_name', 'facility_country',
            'origin', 'destination', 'distance_km', 'traveler_count',
            'meter_id', 'tariff_code', 'is_estimated_read',
            'sap_document_number', 'sap_material_code', 'vendor_name',
            'review_status', 'reviewed_by_name', 'reviewed_at', 'review_notes',
            'anomaly_flags', 'is_edited', 'edit_reason',
            'ingest_job_filename', 'ingest_job',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'scope', 'category', 'quantity', 'unit',
            'raw_quantity', 'raw_unit', 'raw_row',
            'ingest_job_filename', 'created_at',
        ]

    def get_ingest_job_filename(self, obj):
        return obj.ingest_job.filename if obj.ingest_job else None

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None


class AuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = ['id', 'event_type', 'actor_name', 'timestamp', 'payload']

    def get_actor_name(self, obj):
        return obj.actor.username if obj.actor else 'system'


class ReviewActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'flag', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)
    edit_quantity = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, allow_null=True
    )
    edit_reason = serializers.CharField(required=False, allow_blank=True)


class DashboardStatsSerializer(serializers.Serializer):
    total_records = serializers.IntegerField()
    pending = serializers.IntegerField()
    approved = serializers.IntegerField()
    flagged = serializers.IntegerField()
    rejected = serializers.IntegerField()
    by_scope = serializers.DictField()
    by_category = serializers.DictField()
    recent_jobs = IngestJobSerializer(many=True)
