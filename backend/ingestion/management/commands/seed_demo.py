"""
Seed command: creates a demo tenant, analyst user, and sample data for all three sources.
Run: python manage.py seed_demo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ingestion.models import Tenant, TenantMembership, PlantCode, IngestJob, EmissionRecord, AuditEvent
from decimal import Decimal
from datetime import date
import uuid


class Command(BaseCommand):
    help = 'Seed demo tenant and sample emission records'

    def handle(self, *args, **options):
        # Tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug='acme-corp',
            defaults={'name': 'Acme Manufacturing Corp'}
        )

        # Demo user
        user, created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acmecorp.com',
                'first_name': 'Sarah',
                'last_name': 'Chen',
                'is_staff': True,
            }
        )
        if created:
            user.set_password('demo1234')
            user.save()

        TenantMembership.objects.get_or_create(user=user, tenant=tenant, defaults={'role': 'analyst'})

        # Admin user
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@acmecorp.com', 'is_staff': True, 'is_superuser': True}
        )
        if created:
            admin.set_password('admin1234')
            admin.save()
        TenantMembership.objects.get_or_create(user=admin, tenant=tenant, defaults={'role': 'admin'})

        # Plant codes (SAP)
        plants = [
            ('1000', 'Hamburg Manufacturing Plant', 'DE', 'Northern Europe'),
            ('1100', 'Munich Logistics Hub', 'DE', 'Southern Europe'),
            ('2000', 'Chicago Distribution Center', 'US', 'North America'),
            ('3000', 'Singapore Regional HQ', 'SG', 'APAC'),
        ]
        plant_objs = {}
        for code, name, country, region in plants:
            pc, _ = PlantCode.objects.get_or_create(
                tenant=tenant, code=code,
                defaults={'name': name, 'country': country, 'region': region}
            )
            plant_objs[code] = pc

        if EmissionRecord.objects.filter(tenant=tenant).count() > 10:
            self.stdout.write('Demo data already seeded, skipping records.')
            self.stdout.write(self.style.SUCCESS(f'Login: analyst / demo1234'))
            return

        # --- SAP job ---
        sap_job = IngestJob.objects.create(
            tenant=tenant, source_type='sap_flat',
            filename='SAP_MM_FuelProcurement_Q1_2024.csv',
            uploaded_by=user, status='done',
            rows_total=8, rows_ok=7, rows_failed=1, rows_flagged=2,
            error_log=['Row 6: Cannot parse quantity "N/A"']
        )

        sap_records = [
            # Diesel fuel - Hamburg plant (Scope 1 stationary)
            dict(scope='1', category='fuel_stationary', quantity=Decimal('45200.00'), unit='litre',
                 raw_quantity='45200', raw_unit='L', raw_row={'MENGE':'45200','MEINS':'L','WERKS':'1000','BUDAT':'20240115','MATNR':'000000000000100001','MAKTX':'Diesel Kraftstoff','MATKL':'001','NAME1':'Shell Deutschland GmbH','BELNR':'5100012345'},
                 period_start=date(2024,1,15), period_end=date(2024,1,15),
                 facility_name='Hamburg Manufacturing Plant', facility_country='DE',
                 plant_code=plant_objs['1000'], sap_document_number='5100012345',
                 sap_material_code='000000000000100001', vendor_name='Shell Deutschland GmbH',
                 review_status='approved', reviewed_by=user, reviewed_at='2024-01-20T10:00:00Z',
                 review_notes='Verified against delivery note DN-2024-0115', anomaly_flags=[]),
            # Fleet diesel - Munich (Scope 1 mobile)
            dict(scope='1', category='fuel_mobile', quantity=Decimal('12800.00'), unit='litre',
                 raw_quantity='12800', raw_unit='L', raw_row={'MENGE':'12800','MEINS':'L','WERKS':'1100','BUDAT':'20240122','MATNR':'000000000000100002','MAKTX':'Diesel Fleet','MATKL':'002','NAME1':'BP Europa SE','BELNR':'5100012346'},
                 period_start=date(2024,1,22), period_end=date(2024,1,22),
                 facility_name='Munich Logistics Hub', facility_country='DE',
                 plant_code=plant_objs['1100'], sap_document_number='5100012346',
                 vendor_name='BP Europa SE', review_status='pending', anomaly_flags=[]),
            # Natural gas - Hamburg (converted from MMBTU → kWh)
            dict(scope='1', category='fuel_stationary', quantity=Decimal('586142.00'), unit='kwh',
                 raw_quantity='2000', raw_unit='MMBTU', raw_row={'MENGE':'2000','MEINS':'MMBTU','WERKS':'1000','BUDAT':'20240131','MATNR':'000000000000200001','MAKTX':'Natural Gas','MATKL':'001','NAME1':'E.ON SE','BELNR':'5100012350'},
                 period_start=date(2024,1,31), period_end=date(2024,1,31),
                 facility_name='Hamburg Manufacturing Plant', facility_country='DE',
                 plant_code=plant_objs['1000'], sap_document_number='5100012350',
                 vendor_name='E.ON SE', review_status='pending', anomaly_flags=[]),
            # Outlier: unusually large diesel purchase - flagged
            dict(scope='1', category='fuel_stationary', quantity=Decimal('1500000.00'), unit='litre',
                 raw_quantity='1500000', raw_unit='L', raw_row={'MENGE':'1500000','MEINS':'L','WERKS':'2000','BUDAT':'20240210','MATNR':'000000000000100001','MAKTX':'Diesel Fuel','MATKL':'001','NAME1':'BP America Inc','BELNR':'5100012399'},
                 period_start=date(2024,2,10), period_end=date(2024,2,10),
                 facility_name='Chicago Distribution Center', facility_country='US',
                 plant_code=plant_objs['2000'], sap_document_number='5100012399',
                 vendor_name='BP America Inc', review_status='flagged',
                 review_notes='Quantity exceeds monthly capacity for this facility. Awaiting confirmation from procurement.',
                 anomaly_flags=['outlier_quantity']),
            # Procurement spend (Scope 3)
            dict(scope='3', category='procurement', quantity=Decimal('45000.00'), unit='usd',
                 raw_quantity='41666.67', raw_unit='EUR', raw_row={'MENGE':'41666.67','MEINS':'EUR','WERKS':'1000','BUDAT':'20240215','MATNR':'000000000000300001','MAKTX':'Packaging Materials','MATKL':'011','NAME1':'Smurfit Kappa GmbH','BELNR':'5100012360'},
                 period_start=date(2024,2,15), period_end=date(2024,2,15),
                 facility_name='Hamburg Manufacturing Plant', facility_country='DE',
                 plant_code=plant_objs['1000'], vendor_name='Smurfit Kappa GmbH',
                 review_status='pending', anomaly_flags=[]),
            # Unknown plant code - flagged
            dict(scope='1', category='fuel_stationary', quantity=Decimal('8500.00'), unit='litre',
                 raw_quantity='8500', raw_unit='L', raw_row={'MENGE':'8500','MEINS':'L','WERKS':'9999','BUDAT':'20240220','MATNR':'000000000000100001','MAKTX':'Heizöl','MATKL':'001','NAME1':'Total Energies','BELNR':'5100012370'},
                 period_start=date(2024,2,20), period_end=date(2024,2,20),
                 facility_name='Plant 9999', vendor_name='Total Energies',
                 review_status='pending', anomaly_flags=['unknown_plant_code']),
        ]

        for rd in sap_records:
            r = EmissionRecord.objects.create(tenant=tenant, ingest_job=sap_job, **rd)
            AuditEvent.objects.create(tenant=tenant, record=r, event_type='ingested',
                                       actor=user, payload={'source': 'sap_flat'})
            if r.review_status == 'approved':
                AuditEvent.objects.create(tenant=tenant, record=r, event_type='approved',
                                           actor=user, payload={'notes': r.review_notes})
            elif r.review_status == 'flagged':
                AuditEvent.objects.create(tenant=tenant, record=r, event_type='flagged',
                                           actor=user, payload={'notes': r.review_notes})

        # --- Utility job ---
        util_job = IngestJob.objects.create(
            tenant=tenant, source_type='utility_csv',
            filename='ConEdison_HQ_Jan_Mar_2024.csv',
            uploaded_by=user, status='done',
            rows_total=6, rows_ok=6, rows_failed=0, rows_flagged=2, error_log=[]
        )

        util_records = [
            dict(scope='2', category='electricity', quantity=Decimal('347000.00'), unit='kwh',
                 raw_quantity='347000', raw_unit='KWH', raw_row={'account_number':'43406','meter_id':'1424','commodity':'electric','unit':'kwh','bill_start_date':'2024-01-03','bill_end_date':'2024-02-02','consumption':'347000','demand_kw':'890','cost':'41640','rate_schedule':'SC-9','read_type':'actual','facility_name':'Chicago HQ - North Tower'},
                 period_start=date(2024,1,3), period_end=date(2024,2,2),
                 facility_name='Chicago HQ - North Tower', facility_country='US',
                 meter_id='1424', tariff_code='SC-9', is_estimated_read=False,
                 review_status='approved', reviewed_by=user, reviewed_at='2024-02-10T09:00:00Z',
                 review_notes='', anomaly_flags=[]),
            dict(scope='2', category='electricity', quantity=Decimal('298000.00'), unit='kwh',
                 raw_quantity='298000', raw_unit='KWH', raw_row={'account_number':'43407','meter_id':'1425','commodity':'electric','unit':'kwh','bill_start_date':'2024-02-03','bill_end_date':'2024-03-05','consumption':'298000','demand_kw':'780','cost':'35760','rate_schedule':'SC-9','read_type':'estimated','facility_name':'Chicago HQ - North Tower'},
                 period_start=date(2024,2,3), period_end=date(2024,3,5),
                 facility_name='Chicago HQ - North Tower', facility_country='US',
                 meter_id='1425', tariff_code='SC-9', is_estimated_read=True,
                 review_status='flagged', review_notes='Estimated read — awaiting actual meter confirmation.',
                 anomaly_flags=['estimated_read']),
            dict(scope='2', category='electricity', quantity=Decimal('512000.00'), unit='kwh',
                 raw_quantity='512000', raw_unit='KWH', raw_row={'account_number':'43410','meter_id':'2001','commodity':'electric','unit':'kwh','bill_start_date':'2024-01-08','bill_end_date':'2024-02-07','consumption':'512000','demand_kw':'1200','cost':'61440','rate_schedule':'SC-9-Large','read_type':'actual','facility_name':'Hamburg Plant - Grid Connection'},
                 period_start=date(2024,1,8), period_end=date(2024,2,7),
                 facility_name='Hamburg Plant - Grid Connection', facility_country='DE',
                 meter_id='2001', tariff_code='SC-9-Large', is_estimated_read=False,
                 review_status='pending', anomaly_flags=[]),
        ]

        for rd in util_records:
            r = EmissionRecord.objects.create(tenant=tenant, ingest_job=util_job, **rd)
            AuditEvent.objects.create(tenant=tenant, record=r, event_type='ingested',
                                       actor=user, payload={'source': 'utility_csv'})

        # --- Travel job ---
        travel_job = IngestJob.objects.create(
            tenant=tenant, source_type='travel_json',
            filename='Concur_Q1_2024_ExpenseExport.json',
            uploaded_by=user, status='done',
            rows_total=9, rows_ok=8, rows_failed=0, rows_flagged=2, error_log=[]
        )

        travel_records = [
            dict(scope='3', category='travel_flight', quantity=Decimal('5570.00'), unit='km',
                 raw_quantity='890.00', raw_unit='USD', raw_row={'entryId':'E001','expenseTypeCode':'AIRFR','transactionDate':'2024-01-15','transactionAmount':890.00,'transactionCurrencyCode':'USD','vendorDescription':'United Airlines','locationCity':'New York','custom1':'JFK','custom2':'LHR','custom3':'1'},
                 period_start=date(2024,1,15), period_end=date(2024,1,15),
                 origin='JFK', destination='LHR', distance_km=Decimal('5570'),
                 traveler_count=1, vendor_name='United Airlines',
                 facility_name='New York', review_status='approved',
                 reviewed_by=user, reviewed_at='2024-01-25T11:00:00Z',
                 review_notes='', anomaly_flags=[]),
            dict(scope='3', category='travel_flight', quantity=Decimal('5570.00'), unit='km',
                 raw_quantity='1240.00', raw_unit='USD', raw_row={'entryId':'E002','expenseTypeCode':'AIRFR','transactionDate':'2024-01-18','transactionAmount':1240.00,'transactionCurrencyCode':'USD','vendorDescription':'British Airways','locationCity':'London','custom1':'LHR','custom2':'JFK','custom3':'2'},
                 period_start=date(2024,1,18), period_end=date(2024,1,18),
                 origin='LHR', destination='JFK', distance_km=Decimal('5570'),
                 traveler_count=2, vendor_name='British Airways',
                 facility_name='London', review_status='pending', anomaly_flags=[]),
            dict(scope='3', category='travel_hotel', quantity=Decimal('3.00'), unit='unit',
                 raw_quantity='3', raw_unit='USD', raw_row={'entryId':'E003','expenseTypeCode':'HOTEL','transactionDate':'2024-01-15','transactionAmount':680.00,'transactionCurrencyCode':'USD','vendorDescription':'Marriott London','locationCity':'London','quantity':3},
                 period_start=date(2024,1,15), period_end=date(2024,1,18),
                 vendor_name='Marriott London', facility_name='London', facility_country='GB',
                 review_status='approved', reviewed_by=user, reviewed_at='2024-01-25T11:00:00Z',
                 review_notes='', anomaly_flags=[]),
            dict(scope='3', category='travel_ground', quantity=Decimal('45.00'), unit='usd',
                 raw_quantity='45.00', raw_unit='USD', raw_row={'entryId':'E004','expenseTypeCode':'TAXI','transactionDate':'2024-01-15','transactionAmount':45.00,'transactionCurrencyCode':'USD','vendorDescription':'Uber','locationCity':'New York'},
                 period_start=date(2024,1,15), period_end=date(2024,1,15),
                 vendor_name='Uber', facility_name='New York', facility_country='US',
                 review_status='pending', anomaly_flags=['no_distance_using_spend']),
            # Long haul flight - Singapore
            dict(scope='3', category='travel_flight', quantity=Decimal('10841.00'), unit='km',
                 raw_quantity='2100.00', raw_unit='USD', raw_row={'entryId':'E005','expenseTypeCode':'AIRFR','transactionDate':'2024-02-05','transactionAmount':2100.00,'transactionCurrencyCode':'USD','vendorDescription':'Singapore Airlines','locationCity':'Los Angeles','custom1':'LAX','custom2':'SYD','custom3':'1'},
                 period_start=date(2024,2,5), period_end=date(2024,2,5),
                 origin='LAX', destination='SYD', distance_km=Decimal('12054'),
                 traveler_count=1, vendor_name='Singapore Airlines',
                 facility_name='Los Angeles', review_status='pending', anomaly_flags=[]),
            # Unknown route - flagged
            dict(scope='3', category='travel_flight', quantity=Decimal('0.00'), unit='km',
                 raw_quantity='350.00', raw_unit='USD', raw_row={'entryId':'E006','expenseTypeCode':'AIRFR','transactionDate':'2024-02-12','transactionAmount':350.00,'transactionCurrencyCode':'USD','vendorDescription':'IndiGo','locationCity':'Delhi','custom1':'DEL','custom2':'BLR','custom3':'1'},
                 period_start=date(2024,2,12), period_end=date(2024,2,12),
                 origin='DEL', destination='BLR', distance_km=None,
                 traveler_count=1, vendor_name='IndiGo',
                 facility_name='Delhi', facility_country='IN',
                 review_status='flagged', review_notes='Route DEL→BLR not in distance table; distance needed for emission calc.',
                 anomaly_flags=['unknown_route_distance']),
        ]

        for rd in travel_records:
            r = EmissionRecord.objects.create(tenant=tenant, ingest_job=travel_job, **rd)
            AuditEvent.objects.create(tenant=tenant, record=r, event_type='ingested',
                                       actor=user, payload={'source': 'travel_json'})

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Demo data seeded successfully!'
            f'\n  Tenant: {tenant.name}'
            f'\n  Login:  analyst / demo1234'
            f'\n  Admin:  admin / admin1234'
            f'\n  Records: {EmissionRecord.objects.filter(tenant=tenant).count()} emission records'
        ))
