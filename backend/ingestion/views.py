import json
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tenant, IngestJob, EmissionRecord, AuditEvent, PlantCode, TenantMembership
from .serializers import (
    IngestJobSerializer, EmissionRecordSerializer, AuditEventSerializer,
    ReviewActionSerializer, TenantSerializer, PlantCodeSerializer
)
from .parsers import parse_sap_csv, parse_utility_csv, parse_travel_json


def get_tenant(request):
    """Get the tenant for the current user (first membership)."""
    membership = TenantMembership.objects.filter(user=request.user).select_related('tenant').first()
    return membership.tenant if membership else None


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    tenant = get_tenant(request)
    return Response({
        'id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'name': request.user.get_full_name(),
        'tenant': TenantSerializer(tenant).data if tenant else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    tenant = get_tenant(request)
    if not tenant:
        return Response({'error': 'No tenant'}, status=400)

    qs = EmissionRecord.objects.filter(tenant=tenant, is_deleted=False)

    by_scope = {}
    for s, label in EmissionRecord.SCOPE:
        by_scope[s] = {
            'label': label,
            'count': qs.filter(scope=s).count(),
        }

    by_category = {}
    for cat, label in EmissionRecord.CATEGORY:
        count = qs.filter(category=cat).count()
        if count:
            by_category[cat] = {'label': label, 'count': count}

    recent_jobs = IngestJob.objects.filter(tenant=tenant).order_by('-uploaded_at')[:5]

    return Response({
        'total_records': qs.count(),
        'pending': qs.filter(review_status='pending').count(),
        'approved': qs.filter(review_status='approved').count(),
        'flagged': qs.filter(review_status='flagged').count(),
        'rejected': qs.filter(review_status='rejected').count(),
        'by_scope': by_scope,
        'by_category': by_category,
        'recent_jobs': IngestJobSerializer(recent_jobs, many=True).data,
    })


class IngestJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = get_tenant(self.request)
        if not tenant:
            return IngestJob.objects.none()
        return IngestJob.objects.filter(tenant=tenant).order_by('-uploaded_at')


class EmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = get_tenant(self.request)
        if not tenant:
            return EmissionRecord.objects.none()
        qs = EmissionRecord.objects.filter(tenant=tenant, is_deleted=False)

        # Filters
        scope = self.request.query_params.get('scope')
        category = self.request.query_params.get('category')
        review_status = self.request.query_params.get('review_status')
        job_id = self.request.query_params.get('job')
        has_flags = self.request.query_params.get('has_flags')

        if scope:
            qs = qs.filter(scope=scope)
        if category:
            qs = qs.filter(category=category)
        if review_status:
            qs = qs.filter(review_status=review_status)
        if job_id:
            qs = qs.filter(ingest_job_id=job_id)
        if has_flags == 'true':
            qs = qs.exclude(anomaly_flags=[])

        return qs.select_related('ingest_job', 'reviewed_by', 'plant_code')

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        record = self.get_object()
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_type = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')
        edit_quantity = serializer.validated_data.get('edit_quantity')
        edit_reason = serializer.validated_data.get('edit_reason', '')

        old_status = record.review_status
        old_quantity = record.quantity

        with transaction.atomic():
            # Apply edit if provided
            if edit_quantity is not None:
                record.quantity = edit_quantity
                record.is_edited = True
                record.edit_reason = edit_reason

            # Update review status
            status_map = {
                'approve': 'approved',
                'flag': 'flagged',
                'reject': 'rejected',
            }
            record.review_status = status_map[action_type]
            record.reviewed_by = request.user
            record.reviewed_at = timezone.now()
            record.review_notes = notes
            record.save()

            # Append to audit trail
            AuditEvent.objects.create(
                tenant=record.tenant,
                record=record,
                event_type=action_type + 'd' if action_type != 'flag' else 'flagged',
                actor=request.user,
                payload={
                    'previous_status': old_status,
                    'new_status': record.review_status,
                    'notes': notes,
                    'quantity_before': str(old_quantity) if edit_quantity else None,
                    'quantity_after': str(record.quantity) if edit_quantity else None,
                }
            )

        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        record = self.get_object()
        events = AuditEvent.objects.filter(record=record).order_by('timestamp')
        return Response(AuditEventSerializer(events, many=True).data)


class IngestView(APIView):
    """Handles file uploads for all three source types."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = get_tenant(request)
        if not tenant:
            return Response({'error': 'No tenant associated with this user'}, status=400)

        source_type = request.data.get('source_type')
        if source_type not in ('sap_flat', 'utility_csv', 'travel_json'):
            return Response({'error': 'Invalid source_type'}, status=400)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'No file provided'}, status=400)

        if uploaded_file.size > 10 * 1024 * 1024:
            return Response({'error': 'File exceeds 10MB limit'}, status=400)

        filename = uploaded_file.name

        with transaction.atomic():
            job = IngestJob.objects.create(
                tenant=tenant,
                source_type=source_type,
                filename=filename,
                uploaded_by=request.user,
                status='processing',
            )

            try:
                content = uploaded_file.read().decode('utf-8-sig')  # handle BOM

                if source_type == 'sap_flat':
                    plant_codes = {pc.code: pc for pc in PlantCode.objects.filter(tenant=tenant)}
                    records_data, errors = parse_sap_csv(content, tenant, job, plant_codes)
                elif source_type == 'utility_csv':
                    records_data, errors = parse_utility_csv(content, tenant, job)
                else:  # travel_json
                    records_data, errors = parse_travel_json(content, tenant, job)

                # Bulk create records
                created = []
                for rd in records_data:
                    plant_code_obj = rd.pop('plant_code', None)
                    record = EmissionRecord(
                        tenant=tenant,
                        ingest_job=job,
                        plant_code=plant_code_obj,
                        **rd,
                    )
                    created.append(record)

                EmissionRecord.objects.bulk_create(created)

                # Create ingest audit events
                AuditEvent.objects.bulk_create([
                    AuditEvent(
                        tenant=tenant,
                        record=r,
                        event_type='ingested',
                        actor=request.user,
                        payload={'source_type': source_type, 'filename': filename}
                    )
                    for r in EmissionRecord.objects.filter(ingest_job=job)
                ])

                flagged_count = sum(1 for r in records_data if r.get('anomaly_flags'))

                job.status = 'done'
                job.rows_total = len(records_data) + len(errors)
                job.rows_ok = len(records_data)
                job.rows_failed = len(errors)
                job.rows_flagged = flagged_count
                job.error_log = errors
                job.save()

            except Exception as e:
                job.status = 'failed'
                job.error_log = [str(e)]
                job.save()
                return Response(
                    {'error': f'Ingest failed: {str(e)}', 'job_id': str(job.id)},
                    status=500
                )

        return Response(IngestJobSerializer(job).data, status=201)


class PlantCodeViewSet(viewsets.ModelViewSet):
    serializer_class = PlantCodeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = get_tenant(self.request)
        return PlantCode.objects.filter(tenant=tenant) if tenant else PlantCode.objects.none()

    def perform_create(self, serializer):
        tenant = get_tenant(self.request)
        serializer.save(tenant=tenant)
