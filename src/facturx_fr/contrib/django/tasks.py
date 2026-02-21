"""Tâches Celery pour la facturation électronique.

FR: Tâches asynchrones pour la soumission PDP et la vérification de statut.
    Import conditionnel de Celery (ne bloque pas si non installé).
EN: Async tasks for PDP submission and status checking.
    Conditional Celery import (does not block if not installed).
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:
    # Celery non installé — les tâches ne seront pas disponibles
    # mais le module peut quand même être importé sans erreur
    def shared_task(*args, **kwargs):  # type: ignore[misc]
        """Décorateur factice quand Celery n'est pas installé."""
        def decorator(func):
            return func
        if args and callable(args[0]):
            return args[0]
        return decorator


@shared_task(bind=True, max_retries=3)
def submit_to_pdp(self, invoice_id: int) -> str:
    """Soumet une facture à la PDP.

    FR: Récupère la facture Django, instancie le connecteur PDP configuré,
        et soumet la facture via asyncio.run(). Met à jour pdp_invoice_id
        et le statut en cas de succès.
    EN: Fetches the Django invoice, instantiates the configured PDP connector,
        and submits via asyncio.run(). Updates pdp_invoice_id and status.
    """
    from facturx_fr.contrib.django.conf import get_pdp_instance
    from facturx_fr.contrib.django.models import Invoice

    invoice = Invoice.objects.select_related().get(pk=invoice_id)

    try:
        pdp = get_pdp_instance()
        pydantic_invoice = invoice.to_pydantic()

        xml_bytes = None
        if invoice.xml_file:
            xml_bytes = invoice.xml_file.read()

        response = asyncio.run(pdp.submit(pydantic_invoice, xml_bytes=xml_bytes))

        invoice.pdp_invoice_id = response.invoice_id
        invoice.status = str(response.status)
        invoice.save(update_fields=["pdp_invoice_id", "status", "updated_at"])

        logger.info(
            "Facture %s soumise à la PDP : %s",
            invoice.number,
            response.invoice_id,
        )
        return response.invoice_id

    except Exception as exc:
        logger.exception("Erreur de soumission PDP pour facture %s", invoice.number)
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task
def check_invoice_status(invoice_id: int) -> str:
    """Vérifie le statut d'une facture sur la PDP.

    FR: Récupère le statut courant via le connecteur PDP et met à jour
        le modèle Django si le statut a changé.
    EN: Fetches current status from PDP connector and updates the
        Django model if status changed.
    """
    from facturx_fr.contrib.django.conf import get_pdp_instance
    from facturx_fr.contrib.django.models import Invoice

    invoice = Invoice.objects.get(pk=invoice_id)

    if not invoice.pdp_invoice_id:
        logger.warning("Facture %s : pas d'identifiant PDP.", invoice.number)
        return ""

    try:
        pdp = get_pdp_instance()
        status = asyncio.run(pdp.get_status(invoice.pdp_invoice_id))
        new_status = str(status)

        if invoice.status != new_status:
            old_status = invoice.status
            invoice.status = new_status
            invoice.save(update_fields=["status", "updated_at"])
            logger.info(
                "Facture %s : statut mis à jour %s → %s",
                invoice.number,
                old_status,
                new_status,
            )

        return new_status

    except Exception:
        logger.exception(
            "Erreur de vérification de statut pour facture %s", invoice.number
        )
        raise
