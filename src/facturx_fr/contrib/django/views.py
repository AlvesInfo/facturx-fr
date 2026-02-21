"""Vues Django pour la facturation électronique.

FR: Vues CBV (Class-Based Views) pour la génération XML, la soumission
    PDP, le téléchargement de fichiers et la vérification de statut.
    Pas de dépendance à Django REST Framework.
EN: CBV views for XML generation, PDP submission, file downloads
    and status checking. No DRF dependency.
"""

import logging

from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from facturx_fr.contrib.django.models import Invoice

logger = logging.getLogger(__name__)


class InvoiceMixin:
    """Mixin fournissant un helper pour récupérer une facture."""

    def get_invoice(self, invoice_id: int) -> Invoice:
        """Récupère une facture par son ID ou lève Http404."""
        return get_object_or_404(Invoice, pk=invoice_id)


@method_decorator(csrf_exempt, name="dispatch")
class GenerateXMLView(InvoiceMixin, View):
    """Génère le XML CII pour une facture (POST)."""

    def post(self, request, invoice_id: int) -> JsonResponse:
        """Génère le XML CII, valide et sauvegarde."""
        from facturx_fr.generators.cii import CIIGenerator
        from facturx_fr.validators import validate_xml

        invoice = self.get_invoice(invoice_id)

        try:
            pydantic_invoice = invoice.to_pydantic()
            generator = CIIGenerator()
            xml_bytes = generator.generate_xml(pydantic_invoice)
        except Exception:
            logger.exception("Erreur de génération XML pour facture %s", invoice.number)
            return JsonResponse(
                {"error": "Erreur lors de la génération du XML."},
                status=500,
            )

        errors = validate_xml(xml_bytes)
        if errors:
            return JsonResponse(
                {"error": "Erreurs de validation XML.", "details": errors},
                status=400,
            )

        invoice.xml_file.save(
            f"{invoice.number}.xml",
            ContentFile(xml_bytes),
            save=True,
        )
        return JsonResponse({"status": "ok", "message": "XML généré avec succès."})


@method_decorator(csrf_exempt, name="dispatch")
class SubmitToPDPView(InvoiceMixin, View):
    """Soumet une facture à la PDP via Celery (POST)."""

    def post(self, request, invoice_id: int) -> JsonResponse:
        """Vérifie le XML et lance la tâche Celery."""
        invoice = self.get_invoice(invoice_id)

        if not invoice.xml_file:
            return JsonResponse(
                {"error": "XML non généré. Générez le XML d'abord."},
                status=400,
            )

        try:
            from facturx_fr.contrib.django.tasks import submit_to_pdp
        except ImportError:
            return JsonResponse(
                {"error": "Celery n'est pas installé."},
                status=500,
            )

        submit_to_pdp.delay(invoice.pk)
        return JsonResponse({"status": "ok", "message": "Soumission en cours."})


class DownloadXMLView(InvoiceMixin, View):
    """Télécharge le fichier XML d'une facture (GET)."""

    def get(self, request, invoice_id: int) -> FileResponse:
        """Sert le fichier XML."""
        invoice = self.get_invoice(invoice_id)

        if not invoice.xml_file:
            raise Http404("Fichier XML non disponible.")

        return FileResponse(
            invoice.xml_file.open("rb"),
            content_type="application/xml",
            as_attachment=True,
            filename=f"{invoice.number}.xml",
        )


class DownloadPDFView(InvoiceMixin, View):
    """Télécharge le fichier PDF d'une facture (GET)."""

    def get(self, request, invoice_id: int) -> FileResponse:
        """Sert le fichier PDF."""
        invoice = self.get_invoice(invoice_id)

        if not invoice.pdf_file:
            raise Http404("Fichier PDF non disponible.")

        return FileResponse(
            invoice.pdf_file.open("rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=f"{invoice.number}.pdf",
        )


@method_decorator(csrf_exempt, name="dispatch")
class CheckStatusView(InvoiceMixin, View):
    """Vérifie le statut d'une facture sur la PDP (POST)."""

    def post(self, request, invoice_id: int) -> JsonResponse:
        """Lance la tâche Celery de vérification de statut."""
        invoice = self.get_invoice(invoice_id)

        if not invoice.pdp_invoice_id:
            return JsonResponse(
                {"error": "Facture non soumise à la PDP."},
                status=400,
            )

        try:
            from facturx_fr.contrib.django.tasks import check_invoice_status
        except ImportError:
            return JsonResponse(
                {"error": "Celery n'est pas installé."},
                status=500,
            )

        check_invoice_status.delay(invoice.pk)
        return JsonResponse({"status": "ok", "message": "Vérification en cours."})
