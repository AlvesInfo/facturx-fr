# Intégration Django

> **Note** : l'intégration Django est en cours de développement. Les fichiers dans `facturx_fr.contrib.django` sont des stubs. Ce guide décrit l'architecture recommandée et les patterns à suivre pour intégrer `facturx-fr` dans un projet Django 5.2+ (LTS).

## Installation

```bash
pip install "facturx-fr[django,celery]"
```

## Architecture recommandée

Le principe est de séparer les modèles Django (persistance) et les modèles Pydantic (logique métier, génération, validation) :

```
Modèle Django (DB)
    ↕  conversion
Modèle Pydantic (facturx_fr.models.Invoice)
    ↓
Générateur XML/PDF
    ↓
Connecteur PDP (async, via Celery)
```

## Modèle Django pour les factures

```python
# invoices/models.py

from django.db import models
from django.db.models import Q
from decimal import Decimal

from facturx_fr.models import Invoice as PydanticInvoice, InvoiceLine, Party, Address
from facturx_fr.models.payment import PaymentTerms, PaymentMeans, BankAccount
from facturx_fr.models.enums import (
    InvoiceTypeCode,
    OperationCategory,
    VATCategory,
    PaymentMeansCode,
)


class Invoice(models.Model):
    """Facture électronique stockée en base."""

    class OperationCategoryChoices(models.TextChoices):
        DELIVERY = "delivery", "Livraison de biens"
        SERVICE = "service", "Prestation de services"
        MIXED = "mixed", "Mixte"

    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        DEPOSEE = "200", "Déposée"
        EMISE = "201", "Émise"
        APPROUVEE = "205", "Approuvée"
        REFUSEE = "210", "Refusée"
        ENCAISSEE = "213", "Encaissée"
        # ... ajouter les autres statuts selon le besoin

    # Identification
    number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    # db_default (Django 5.0+) : la valeur par défaut est gérée côté DB
    type_code = models.CharField(max_length=3, db_default="380")
    currency = models.CharField(max_length=3, db_default="EUR")
    operation_category = models.CharField(
        max_length=10,
        choices=OperationCategoryChoices.choices,
    )

    # Vendeur
    seller_name = models.CharField(max_length=200)
    seller_siren = models.CharField(max_length=9)
    seller_vat_number = models.CharField(max_length=20, blank=True)
    seller_street = models.CharField(max_length=200)
    seller_city = models.CharField(max_length=100)
    seller_postal_code = models.CharField(max_length=10)

    # Acheteur
    buyer_name = models.CharField(max_length=200)
    buyer_siren = models.CharField(max_length=9)
    buyer_vat_number = models.CharField(max_length=20, blank=True)
    buyer_street = models.CharField(max_length=200)
    buyer_city = models.CharField(max_length=100)
    buyer_postal_code = models.CharField(max_length=10)

    # Paiement
    payment_iban = models.CharField(max_length=34, blank=True)
    payment_bic = models.CharField(max_length=11, blank=True)

    # Statut PDP
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        db_default="draft",
    )
    pdp_invoice_id = models.CharField(max_length=100, blank=True)

    # Fichiers générés
    xml_file = models.FileField(upload_to="invoices/xml/", blank=True)
    pdf_file = models.FileField(upload_to="invoices/pdf/", blank=True)

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(seller_siren__regex=r"^\d{9}$"),
                name="invoice_seller_siren_format",
            ),
            models.CheckConstraint(
                condition=Q(buyer_siren__regex=r"^\d{9}$"),
                name="invoice_buyer_siren_format",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "issue_date"]),
            models.Index(fields=["seller_siren"]),
            models.Index(fields=["buyer_siren"]),
        ]

    def __str__(self):
        return f"{self.number} — {self.buyer_name}"

    def to_pydantic(self) -> PydanticInvoice:
        """Convertit le modèle Django en modèle Pydantic."""
        lines = [line.to_pydantic() for line in self.lines.all()]

        payment_means = None
        if self.payment_iban:
            payment_means = PaymentMeans(
                code=PaymentMeansCode.CREDIT_TRANSFER,
                bank_account=BankAccount(
                    iban=self.payment_iban,
                    bic=self.payment_bic or None,
                ),
            )

        return PydanticInvoice(
            number=self.number,
            issue_date=self.issue_date,
            due_date=self.due_date,
            type_code=InvoiceTypeCode(self.type_code),
            currency=self.currency,
            operation_category=OperationCategory(self.operation_category),
            seller=Party(
                name=self.seller_name,
                siren=self.seller_siren,
                vat_number=self.seller_vat_number or None,
                address=Address(
                    street=self.seller_street,
                    city=self.seller_city,
                    postal_code=self.seller_postal_code,
                ),
            ),
            buyer=Party(
                name=self.buyer_name,
                siren=self.buyer_siren,
                vat_number=self.buyer_vat_number or None,
                address=Address(
                    street=self.buyer_street,
                    city=self.buyer_city,
                    postal_code=self.buyer_postal_code,
                ),
            ),
            lines=lines,
            payment_means=payment_means,
        )


class InvoiceLine(models.Model):
    """Ligne de facture."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    line_number = models.PositiveIntegerField()
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, db_default=Decimal("20.0"))
    vat_category = models.CharField(max_length=2, db_default="S")

    class Meta:
        ordering = ["line_number"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__isnull=False),
                name="line_quantity_not_null",
            ),
        ]

    def to_pydantic(self) -> InvoiceLine:
        """Convertit en modèle Pydantic."""
        from facturx_fr.models import InvoiceLine as PydanticLine

        return PydanticLine(
            line_number=self.line_number,
            description=self.description,
            quantity=self.quantity,
            unit_price=self.unit_price,
            vat_rate=self.vat_rate,
            vat_category=VATCategory(self.vat_category),
        )
```

> **Note Django 5.x** : `db_default` (introduit dans Django 5.0) permet de définir les valeurs par défaut côté base de données plutôt que côté Python. Cela garantit la cohérence même pour les insertions directes en SQL. `CheckConstraint(condition=...)` utilise la syntaxe Django 5.1+ (le paramètre `check` est déprécié au profit de `condition`).

## Vue/API pour la génération et le dépôt

```python
# invoices/views.py

from django.http import HttpResponse, JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404

from facturx_fr.generators import CIIGenerator
from facturx_fr.validators import validate_xml

from .models import Invoice
from .tasks import submit_to_pdp


class GenerateXMLView(View):
    """Génère le XML CII d'une facture."""

    def post(self, request, invoice_id):
        invoice_db = get_object_or_404(Invoice, pk=invoice_id)
        pydantic_invoice = invoice_db.to_pydantic()

        generator = CIIGenerator(profile="EN16931")
        xml_bytes = generator.generate_xml(pydantic_invoice)

        # Valider avant de sauvegarder
        errors = validate_xml(xml_bytes)
        if errors:
            return JsonResponse({"errors": errors}, status=422)

        # Sauvegarder le XML
        from django.core.files.base import ContentFile
        invoice_db.xml_file.save(
            f"{invoice_db.number}.xml",
            ContentFile(xml_bytes),
        )

        return JsonResponse({
            "status": "ok",
            "number": invoice_db.number,
        })


class SubmitToPDPView(View):
    """Lance le dépôt asynchrone à la PDP via Celery."""

    def post(self, request, invoice_id):
        invoice_db = get_object_or_404(Invoice, pk=invoice_id)

        if not invoice_db.xml_file:
            return JsonResponse(
                {"error": "XML non généré — générez d'abord le XML"},
                status=400,
            )

        # Lancer la tâche Celery
        submit_to_pdp.delay(invoice_db.pk)

        return JsonResponse({
            "status": "submitted",
            "number": invoice_db.number,
        })


class DownloadXMLView(View):
    """Télécharge le XML d'une facture."""

    def get(self, request, invoice_id):
        invoice_db = get_object_or_404(Invoice, pk=invoice_id)

        if not invoice_db.xml_file:
            return JsonResponse({"error": "XML non disponible"}, status=404)

        response = HttpResponse(
            invoice_db.xml_file.read(),
            content_type="application/xml",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{invoice_db.number}.xml"'
        )
        return response
```

## Tâches Celery pour les opérations PDP

Les opérations PDP sont async (httpx). Celery permet de les exécuter en arrière-plan :

```python
# invoices/tasks.py

import asyncio
from celery import shared_task

from facturx_fr.pdp.connectors.memory import MemoryPDP  # remplacer par votre PDP


def _get_pdp():
    """Retourne le connecteur PDP configuré."""
    # En production, utilisez votre connecteur réel :
    # from myapp.pdp import MaPDP
    # return MaPDP(api_key=settings.PDP_API_KEY, environment="production")
    return MemoryPDP()


@shared_task(bind=True, max_retries=3)
def submit_to_pdp(self, invoice_id):
    """Soumet une facture à la PDP."""
    from .models import Invoice

    invoice_db = Invoice.objects.get(pk=invoice_id)
    pydantic_invoice = invoice_db.to_pydantic()
    xml_bytes = invoice_db.xml_file.read()

    pdp = _get_pdp()

    try:
        response = asyncio.run(
            pdp.submit(pydantic_invoice, xml_bytes=xml_bytes)
        )
    except Exception as exc:
        # Retry avec backoff exponentiel
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    # Mettre à jour le statut en base
    invoice_db.pdp_invoice_id = response.invoice_id
    invoice_db.status = str(response.status)
    invoice_db.save(update_fields=["pdp_invoice_id", "status"])

    return {
        "invoice_id": response.invoice_id,
        "status": str(response.status),
    }


@shared_task
def check_invoice_status(invoice_id):
    """Vérifie le statut d'une facture sur la PDP."""
    from .models import Invoice

    invoice_db = Invoice.objects.get(pk=invoice_id)
    if not invoice_db.pdp_invoice_id:
        return {"error": "Facture non déposée"}

    pdp = _get_pdp()
    status = asyncio.run(pdp.get_status(invoice_db.pdp_invoice_id))

    invoice_db.status = str(status)
    invoice_db.save(update_fields=["status"])

    return {"status": str(status)}
```

## Admin Django

```python
# invoices/admin.py

from django.contrib import admin
from .models import Invoice, InvoiceLine


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "number", "issue_date", "buyer_name",
        "status", "pdp_invoice_id",
    ]
    list_filter = ["status", "operation_category", "issue_date"]
    search_fields = ["number", "buyer_name", "seller_name"]
    readonly_fields = ["pdp_invoice_id", "created_at", "updated_at"]
    inlines = [InvoiceLineInline]

    actions = ["generate_xml", "submit_to_pdp"]

    @admin.action(description="Générer le XML CII")
    def generate_xml(self, request, queryset):
        from facturx_fr.generators import CIIGenerator
        from django.core.files.base import ContentFile

        generator = CIIGenerator(profile="EN16931")
        count = 0
        for invoice_db in queryset:
            pydantic_invoice = invoice_db.to_pydantic()
            xml_bytes = generator.generate_xml(pydantic_invoice)
            invoice_db.xml_file.save(
                f"{invoice_db.number}.xml",
                ContentFile(xml_bytes),
            )
            count += 1
        self.message_user(request, f"{count} fichier(s) XML généré(s).")

    @admin.action(description="Déposer à la PDP")
    def submit_to_pdp(self, request, queryset):
        from .tasks import submit_to_pdp as submit_task

        count = 0
        for invoice_db in queryset.filter(xml_file__isnull=False):
            submit_task.delay(invoice_db.pk)
            count += 1
        self.message_user(request, f"{count} facture(s) soumise(s) à la PDP.")
```

## URLs

```python
# invoices/urls.py

from django.urls import path
from . import views

app_name = "invoices"

urlpatterns = [
    path(
        "<int:invoice_id>/generate-xml/",
        views.GenerateXMLView.as_view(),
        name="generate-xml",
    ),
    path(
        "<int:invoice_id>/submit/",
        views.SubmitToPDPView.as_view(),
        name="submit-to-pdp",
    ),
    path(
        "<int:invoice_id>/download-xml/",
        views.DownloadXMLView.as_view(),
        name="download-xml",
    ),
]
```

## Configuration Django

Requiert **Django 5.2+** (LTS).

```python
# settings.py

INSTALLED_APPS = [
    # ...
    "invoices",
]

# Celery
CELERY_BROKER_URL = "redis://localhost:6379/0"

# PDP (à adapter selon votre connecteur)
PDP_API_KEY = "votre-cle-api"
PDP_ENVIRONMENT = "sandbox"  # ou "production"
```

## Pattern FastAPI

Pour les projets FastAPI, le pattern est similaire mais utilise directement `async/await` :

```python
from fastapi import APIRouter, HTTPException

from facturx_fr.generators import CIIGenerator
from facturx_fr.validators import validate_xml
from facturx_fr.pdp.connectors.memory import MemoryPDP

router = APIRouter(prefix="/invoices", tags=["invoices"])
pdp = MemoryPDP()


@router.post("/{invoice_id}/submit")
async def submit_invoice(invoice_id: int):
    # Récupérer la facture depuis votre source de données
    invoice = get_invoice_from_db(invoice_id)  # à implémenter

    generator = CIIGenerator(profile="EN16931")
    xml_bytes = generator.generate_xml(invoice)

    errors = validate_xml(xml_bytes)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    response = await pdp.submit(invoice, xml_bytes=xml_bytes)
    return {
        "invoice_id": response.invoice_id,
        "status": str(response.status),
    }
```

## Voir aussi

- [Guide de démarrage](getting_started.md) — Installation et premier exemple
- [Formats de factures](formats.md) — Factur-X, UBL, CII
- [Intégration PDP](pdp_integration.md) — Interface PDP, cycle de vie
