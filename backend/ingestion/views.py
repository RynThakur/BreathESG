import json
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q

from django.contrib.auth import (
    authenticate,
    login,
    logout
)

from rest_framework import viewsets, status
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes
)

from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny
)

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Tenant,
    IngestJob,
    EmissionRecord,
    AuditEvent,
    PlantCode,
    TenantMembership
)

from .serializers import (
    IngestJobSerializer,
    EmissionRecordSerializer,
    AuditEventSerializer,
    ReviewActionSerializer,
    TenantSerializer,
    PlantCodeSerializer
)

from .parsers import (
    parse_sap_csv,
    parse_utility_csv,
    parse_travel_json
)


def get_tenant(request):
    membership = (
        TenantMembership.objects
        .filter(user=request.user)
        .select_related('tenant')
        .first()
    )

    return membership.tenant if membership else None


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok'})


# ===========================
# AUTH
# ===========================

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):

    username = request.data.get(
        'username'
    )

    password = request.data.get(
        'password'
    )

    user = authenticate(
        request,
        username=username,
        password=password
    )

    if user is None:

        return Response(
            {
                'error':
                'Invalid credentials'
            },
            status=401
        )

    login(
        request,
        user
    )

    return Response({
        'success': True,
        'username': user.username
    })


@api_view(['POST'])
def logout_view(request):

    logout(request)

    return Response({
        'success': True
    })


# ===========================
# USER
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):

    tenant = get_tenant(
        request
    )

    return Response({

        'id':
        request.user.id,

        'username':
        request.user.username,

        'email':
        request.user.email,

        'name':
        request.user.get_full_name(),

        'tenant':
        TenantSerializer(
            tenant
        ).data if tenant else None,

    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):

    tenant = get_tenant(
        request
    )

    if not tenant:

        return Response(
            {
                'error':
                'No tenant'
            },
            status=400
        )

    qs = EmissionRecord.objects.filter(
        tenant=tenant,
        is_deleted=False
    )

    by_scope = {}

    for s, label in EmissionRecord.SCOPE:

        by_scope[s] = {

            'label':
            label,

            'count':
            qs.filter(
                scope=s
            ).count()

        }

    by_category = {}

    for cat, label in EmissionRecord.CATEGORY:

        count = qs.filter(
            category=cat
        ).count()

        if count:

            by_category[cat] = {

                'label':
                label,

                'count':
                count

            }

    recent_jobs = (
        IngestJob.objects
        .filter(tenant=tenant)
        .order_by('-uploaded_at')[:5]
    )

    return Response({

        'total_records':
        qs.count(),

        'pending':
        qs.filter(
            review_status='pending'
        ).count(),

        'approved':
        qs.filter(
            review_status='approved'
        ).count(),

        'flagged':
        qs.filter(
            review_status='flagged'
        ).count(),

        'rejected':
        qs.filter(
            review_status='rejected'
        ).count(),

        'by_scope':
        by_scope,

        'by_category':
        by_category,

        'recent_jobs':
        IngestJobSerializer(
            recent_jobs,
            many=True
        ).data,

    })


class IngestJobViewSet(
    viewsets.ReadOnlyModelViewSet
):

    serializer_class = (
        IngestJobSerializer
    )

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        tenant = get_tenant(
            self.request
        )

        if not tenant:

            return (
                IngestJob.objects.none()
            )

        return (
            IngestJob.objects
            .filter(
                tenant=tenant
            )
            .order_by(
                '-uploaded_at'
            )
        )


class EmissionRecordViewSet(
    viewsets.ModelViewSet
):

    serializer_class = (
        EmissionRecordSerializer
    )

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        tenant = get_tenant(
            self.request
        )

        if not tenant:

            return (
                EmissionRecord.objects.none()
            )

        return (
            EmissionRecord.objects
            .filter(
                tenant=tenant,
                is_deleted=False
            )
            .select_related(
                'ingest_job',
                'reviewed_by',
                'plant_code'
            )
        )


class IngestView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def post(
        self,
        request
    ):

        return Response({
            "message":
            "existing ingest code stays same"
        })


class PlantCodeViewSet(
    viewsets.ModelViewSet
):

    serializer_class = (
        PlantCodeSerializer
    )

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        tenant = get_tenant(
            self.request
        )

        return (

            PlantCode.objects.filter(
                tenant=tenant
            )

            if tenant

            else

            PlantCode.objects.none()

        )

    def perform_create(
        self,
        serializer
    ):

        tenant = get_tenant(
            self.request
        )

        serializer.save(
            tenant=tenant
        )