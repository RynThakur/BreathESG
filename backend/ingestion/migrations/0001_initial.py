from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='TenantMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('analyst', 'Analyst'), ('admin', 'Admin')], default='analyst', max_length=20)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='ingestion.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='auth.user')),
            ],
            options={'unique_together': {('user', 'tenant')}},
        ),
        migrations.CreateModel(
            name='PlantCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20)),
                ('name', models.CharField(max_length=255)),
                ('country', models.CharField(blank=True, max_length=2)),
                ('region', models.CharField(blank=True, max_length=100)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plant_codes', to='ingestion.tenant')),
            ],
            options={'unique_together': {('tenant', 'code')}},
        ),
        migrations.CreateModel(
            name='IngestJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source_type', models.CharField(choices=[('sap_flat', 'SAP Flat File (IDoc-derived CSV)'), ('utility_csv', 'Utility Portal CSV'), ('travel_json', 'Corporate Travel JSON (Concur-style)')], max_length=20)),
                ('filename', models.CharField(max_length=500)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('done', 'Done'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('rows_total', models.IntegerField(default=0)),
                ('rows_ok', models.IntegerField(default=0)),
                ('rows_failed', models.IntegerField(default=0)),
                ('rows_flagged', models.IntegerField(default=0)),
                ('error_log', models.JSONField(default=list)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ingest_jobs', to='ingestion.tenant')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.CreateModel(
            name='EmissionRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scope', models.CharField(choices=[('1', 'Scope 1'), ('2', 'Scope 2'), ('3', 'Scope 3')], max_length=1)),
                ('category', models.CharField(choices=[('fuel_stationary', 'Stationary Combustion (fuel)'), ('fuel_mobile', 'Mobile Combustion (fleet/vehicles)'), ('electricity', 'Purchased Electricity'), ('travel_flight', 'Business Travel — Flight'), ('travel_hotel', 'Business Travel — Hotel'), ('travel_ground', 'Business Travel — Ground Transport'), ('procurement', 'Purchased Goods & Services')], max_length=30)),
                ('quantity', models.DecimalField(decimal_places=4, max_digits=20)),
                ('unit', models.CharField(choices=[('kwh', 'kWh'), ('litre', 'Litre'), ('kg', 'Kilogram'), ('km', 'Kilometre'), ('usd', 'USD'), ('unit', 'Unit (count)')], max_length=10)),
                ('raw_quantity', models.CharField(max_length=100)),
                ('raw_unit', models.CharField(max_length=50)),
                ('raw_row', models.JSONField(default=dict)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('facility_name', models.CharField(blank=True, max_length=255)),
                ('facility_country', models.CharField(blank=True, max_length=2)),
                ('origin', models.CharField(blank=True, max_length=10)),
                ('destination', models.CharField(blank=True, max_length=10)),
                ('distance_km', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('traveler_count', models.IntegerField(default=1)),
                ('meter_id', models.CharField(blank=True, max_length=100)),
                ('tariff_code', models.CharField(blank=True, max_length=100)),
                ('is_estimated_read', models.BooleanField(default=False)),
                ('sap_document_number', models.CharField(blank=True, max_length=50)),
                ('sap_material_code', models.CharField(blank=True, max_length=50)),
                ('vendor_name', models.CharField(blank=True, max_length=255)),
                ('review_status', models.CharField(choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('flagged', 'Flagged'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_notes', models.TextField(blank=True)),
                ('anomaly_flags', models.JSONField(default=list)),
                ('is_edited', models.BooleanField(default=False)),
                ('edit_reason', models.TextField(blank=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ingest_job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='ingestion.ingestjob')),
                ('plant_code', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingestion.plantcode')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_records', to='auth.user')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='emission_records', to='ingestion.tenant')),
            ],
            options={'ordering': ['-period_start']},
        ),
        migrations.AddIndex(
            model_name='emissionrecord',
            index=models.Index(fields=['tenant', 'scope', 'review_status'], name='ingestion_e_tenant_i_scope_rs_idx'),
        ),
        migrations.AddIndex(
            model_name='emissionrecord',
            index=models.Index(fields=['tenant', 'category', 'period_start'], name='ingestion_e_tenant_i_cat_ps_idx'),
        ),
        migrations.AddIndex(
            model_name='emissionrecord',
            index=models.Index(fields=['ingest_job'], name='ingestion_e_ingest_job_idx'),
        ),
        migrations.CreateModel(
            name='AuditEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('ingested', 'Record Ingested'), ('approved', 'Record Approved'), ('flagged', 'Record Flagged'), ('rejected', 'Record Rejected'), ('edited', 'Record Edited'), ('deleted', 'Record Soft-Deleted')], max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('payload', models.JSONField(default=dict)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_events', to='ingestion.emissionrecord')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ingestion.tenant')),
            ],
            options={'ordering': ['timestamp']},
        ),
    ]
