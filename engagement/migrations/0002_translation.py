# Generated by Django 5.1.9 on 2025-05-15 23:01

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("engagement", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Translation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "language_code",
                    models.CharField(
                        help_text='Language code for the translation (e.g., "en", "fr")',
                        max_length=10,
                        verbose_name="language code",
                    ),
                ),
                (
                    "translated_text",
                    models.TextField(
                        help_text="Translated content of the message",
                        verbose_name="translated text",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        help_text="Message being translated",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="translations",
                        to="engagement.message",
                        verbose_name="message",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "translation",
                "verbose_name_plural": "translations",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["message", "language_code"],
                        name="engagement__message_239a8c_idx",
                    ),
                    models.Index(
                        fields=["created_at"], name="engagement__created_8d0532_idx"
                    ),
                ],
            },
        ),
    ]
