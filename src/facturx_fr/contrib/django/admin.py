"""Configuration de l'admin Django pour la facturation électronique."""

import logging

from django.contrib import admin, messages

from facturx_fr.contrib.django.models import Invoice, InvoiceLine

logger = logging.getLogger(__name__)


class InvoiceLineInline(admin.TabularInline):
    """Inline pour les lignes de facture."""

    model = InvoiceLine
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Administration des factures électroniques."""

    list_display = [
        "number",
        "issue_date",
        "buyer_name",
        "status",
        "pdp_invoice_id",
    ]
    list_filter = ["status", "operation_category", "issue_date"]
    search_fields = ["number", "buyer_name", "seller_name"]
    readonly_fields = ["pdp_invoice_id", "created_at", "updated_at"]
    inlines = [InvoiceLineInline]

    fieldsets = [
        (
            "Identification",
            {
                "fields": [
                    "number",
                    "issue_date",
                    "due_date",
                    "type_code",
                    "currency",
                    "operation_category",
                ],
            },
        ),
        (
            "Vendeur",
            {
                "fields": [
                    "seller_name",
                    "seller_siren",
                    "seller_vat_number",
                    "seller_street",
                    "seller_city",
                    "seller_postal_code",
                    "seller_country_code",
                ],
            },
        ),
        (
            "Acheteur",
            {
                "fields": [
                    "buyer_name",
                    "buyer_siren",
                    "buyer_vat_number",
                    "buyer_street",
                    "buyer_city",
                    "buyer_postal_code",
                    "buyer_country_code",
                ],
            },
        ),
        (
            "Paiement",
            {
                "fields": ["payment_iban", "payment_bic"],
            },
        ),
        (
            "Statut PDP",
            {
                "fields": ["status", "pdp_invoice_id"],
            },
        ),
        (
            "Fichiers",
            {
                "fields": ["xml_file", "pdf_file", "created_at", "updated_at"],
            },
        ),
    ]
    actions = ["generate_xml", "submit_to_pdp"]

    @admin.action(description="Générer le XML CII")
    def generate_xml(self, request, queryset):
        """Génère le XML CII pour les factures sélectionnées."""
        from django.core.files.base import ContentFile

        from facturx_fr.generators.cii import CIIGenerator
        from facturx_fr.validators import validate_xml

        generator = CIIGenerator()
        count = 0

        for invoice in queryset:
            try:
                pydantic_invoice = invoice.to_pydantic()
                xml_bytes = generator.generate_xml(pydantic_invoice)

                errors = validate_xml(xml_bytes)
                if errors:
                    self.message_user(
                        request,
                        f"Facture {invoice.number} : erreurs de validation — "
                        + " ; ".join(errors),
                        messages.ERROR,
                    )
                    continue

                invoice.xml_file.save(
                    f"{invoice.number}.xml",
                    ContentFile(xml_bytes),
                    save=True,
                )
                count += 1
            except Exception:
                logger.exception("Erreur lors de la génération XML de %s", invoice.number)
                self.message_user(
                    request,
                    f"Erreur lors de la génération de {invoice.number}.",
                    messages.ERROR,
                )

        if count:
            self.message_user(
                request,
                f"{count} facture(s) générée(s) avec succès.",
                messages.SUCCESS,
            )

    @admin.action(description="Soumettre à la PDP")
    def submit_to_pdp(self, request, queryset):
        """Lance la tâche Celery de soumission à la PDP."""
        try:
            from facturx_fr.contrib.django.tasks import submit_to_pdp as submit_task
        except ImportError:
            self.message_user(
                request,
                "Celery n'est pas installé. Installez avec : pip install facturx-fr[celery]",
                messages.ERROR,
            )
            return

        count = 0
        for invoice in queryset:
            if not invoice.xml_file:
                self.message_user(
                    request,
                    f"Facture {invoice.number} : XML non généré.",
                    messages.WARNING,
                )
                continue
            submit_task.delay(invoice.pk)
            count += 1

        if count:
            self.message_user(
                request,
                f"{count} facture(s) soumise(s) à la PDP.",
                messages.SUCCESS,
            )
