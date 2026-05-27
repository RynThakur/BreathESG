from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

router.register(
    'jobs',
    views.IngestJobViewSet,
    basename='ingestjob'
)

router.register(
    'records',
    views.EmissionRecordViewSet,
    basename='emissionrecord'
)

router.register(
    'plant-codes',
    views.PlantCodeViewSet,
    basename='plantcode'
)

urlpatterns = [

    path(
        'auth/login/',
        views.login_view
    ),

    path(
        'auth/logout/',
        views.logout_view
    ),

    path(
        'ingest/',
        views.IngestView.as_view(),
        name='ingest'
    ),

    path(
        'dashboard/',
        views.dashboard_stats,
        name='dashboard'
    ),

    path(
        'me/',
        views.me,
        name='me'
    ),

    path(
        '',
        include(router.urls)
    ),
]