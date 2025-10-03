from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

import inventory.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0003_businessinvitation_payload"),
        ("inventory", "0009_make_tax_fields_nullable"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Transfer",
        ),
        migrations.CreateModel(
            name="StoreFrontInventory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="storefront_inventory_entries",
                        to="inventory.product",
                    ),
                ),
                (
                    "storefront",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_entries",
                        to="inventory.storefront",
                    ),
                ),
            ],
            options={
                "db_table": "storefront_inventory",
                "indexes": [
                    models.Index(fields=["storefront", "product"], name="storefront__storefr_0dbd95_idx"),
                    models.Index(fields=["product"], name="storefront__product_84d9f2_idx"),
                ],
                "unique_together": {("storefront", "product")},
            },
        ),
        migrations.CreateModel(
            name="Transfer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reference", models.CharField(default=inventory.models._generate_transfer_reference, max_length=32, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("REQUESTED", "Requested"),
                            ("APPROVED", "Approved"),
                            ("IN_TRANSIT", "In transit"),
                            ("COMPLETED", "Completed"),
                            ("REJECTED", "Rejected"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="DRAFT",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_transfers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transfers",
                        to="accounts.business",
                    ),
                ),
                (
                    "destination_storefront",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inbound_transfer_orders",
                        to="inventory.storefront",
                    ),
                ),
                (
                    "fulfilled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fulfilled_transfers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="requested_transfers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_warehouse",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outbound_transfer_orders",
                        to="inventory.warehouse",
                    ),
                ),
            ],
            options={
                "db_table": "transfers",
                "indexes": [
                    models.Index(fields=["business", "status"], name="transfers_busines_e521cc_idx"),
                    models.Index(fields=["source_warehouse", "status"], name="transfers_source__1e9d40_idx"),
                    models.Index(fields=["destination_storefront", "status"], name="transfers_destina_35111c_idx"),
                    models.Index(fields=["reference"], name="transfers_referen_ad0d1d_idx"),
                ],
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TransferLineItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("requested_quantity", models.PositiveIntegerField()),
                ("approved_quantity", models.PositiveIntegerField(blank=True, null=True)),
                ("fulfilled_quantity", models.PositiveIntegerField(blank=True, null=True)),
                ("unit_of_measure", models.CharField(blank=True, max_length=50, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transfer_line_items",
                        to="inventory.product",
                    ),
                ),
                (
                    "transfer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="line_items",
                        to="inventory.transfer",
                    ),
                ),
            ],
            options={
                "db_table": "transfer_line_items",
                "indexes": [
                    models.Index(fields=["transfer"], name="transfer_li_transfe_3ea7fe_idx"),
                    models.Index(fields=["product"], name="transfer_li_product_53f8bb_idx"),
                ],
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="TransferAuditEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("SUBMITTED", "Submitted"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                            ("CANCELLED", "Cancelled"),
                            ("DISPATCHED", "Dispatched"),
                            ("COMPLETED", "Completed"),
                            ("UPDATED", "Updated"),
                        ],
                        max_length=20,
                    ),
                ),
                ("remarks", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="transfer_audit_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "transfer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audit_entries",
                        to="inventory.transfer",
                    ),
                ),
            ],
            options={
                "db_table": "transfer_audit_entries",
                "indexes": [
                    models.Index(fields=["transfer"], name="transfer_au_transfe_dc3e96_idx"),
                    models.Index(fields=["action"], name="transfer_au_action_25204c_idx"),
                ],
                "ordering": ["created_at"],
            },
        ),
    ]
