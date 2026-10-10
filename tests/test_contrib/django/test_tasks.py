"""Tests des tâches Celery (exécutées de manière synchrone, sans worker)."""

from unittest.mock import patch

import pytest

from facturx_fr.contrib.django import tasks
from facturx_fr.models.enums import InvoiceStatus
from facturx_fr.pdp.connectors.memory import MemoryPDP
from facturx_fr.pdp.errors import PDPNotFoundError

MEMORY_PDP = {"PDP_CLASS": "facturx_fr.pdp.connectors.memory.MemoryPDP"}


class _FakeRequest:
    retries = 2


class _FakeTask:
    """Imite le `self` d'une tâche Celery liée (bind=True)."""

    request = _FakeRequest()

    def __init__(self) -> None:
        self.retry_kwargs: dict | None = None

    def retry(self, **kwargs):
        self.retry_kwargs = kwargs
        return RuntimeError("retry")


def _run(task, *args):
    """Exécute une tâche, qu'elle soit décorée par Celery ou par le décorateur factice."""
    run = getattr(task, "run", None)
    if run is not None:  # Celery installé : `run` est la fonction d'origine
        return run(*args)
    return task(*args)


class TestSharedTaskFallback:
    """Le décorateur (réel ou factice) accepte les deux formes d'appel."""

    def test_decorator_without_arguments(self):
        def func():
            return "ok"

        assert callable(tasks.shared_task(func))

    def test_decorator_with_arguments(self):
        def func():
            return "ok"

        assert callable(tasks.shared_task(bind=True, max_retries=3)(func))


@pytest.mark.django_db
class TestSubmitToPDP:
    """Tests de submit_to_pdp."""

    def test_submit_with_xml(self, invoice_with_xml, settings):
        """La facture (avec XML) est soumise et mise à jour."""
        settings.FACTURX_FR = MEMORY_PDP
        pdp_id = _run(tasks.submit_to_pdp, _FakeTask(), invoice_with_xml.pk)

        invoice_with_xml.refresh_from_db()
        assert pdp_id
        assert invoice_with_xml.pdp_invoice_id == pdp_id
        assert invoice_with_xml.status == str(InvoiceStatus.DEPOSEE)

    def test_submit_without_xml(self, sample_invoice, settings):
        """Sans fichier XML, la soumission transmet xml_bytes=None."""
        settings.FACTURX_FR = MEMORY_PDP
        pdp_id = _run(tasks.submit_to_pdp, _FakeTask(), sample_invoice.pk)
        sample_invoice.refresh_from_db()
        assert sample_invoice.pdp_invoice_id == pdp_id

    def test_submit_failure_retries(self, sample_invoice):
        """Sans PDP configurée, la tâche demande un retry avec backoff."""
        fake = _FakeTask()
        with pytest.raises(RuntimeError, match="retry"):
            _run(tasks.submit_to_pdp, fake, sample_invoice.pk)
        assert fake.retry_kwargs is not None
        assert fake.retry_kwargs["countdown"] == 180
        assert isinstance(fake.retry_kwargs["exc"], ValueError)


@pytest.mark.django_db
class TestCheckInvoiceStatus:
    """Tests de check_invoice_status."""

    def test_no_pdp_id(self, sample_invoice):
        """Facture jamais soumise : retourne une chaîne vide."""
        assert _run(tasks.check_invoice_status, sample_invoice.pk) == ""

    def test_status_updated(self, sample_invoice):
        """Le statut Django est mis à jour quand il diffère de la PDP."""
        pdp = MemoryPDP()
        with patch("facturx_fr.contrib.django.conf.get_pdp_instance", return_value=pdp):
            _run(tasks.submit_to_pdp, _FakeTask(), sample_invoice.pk)
            sample_invoice.refresh_from_db()
            sample_invoice.status = "draft"
            sample_invoice.save()

            new_status = _run(tasks.check_invoice_status, sample_invoice.pk)

        sample_invoice.refresh_from_db()
        assert new_status == str(InvoiceStatus.DEPOSEE)
        assert sample_invoice.status == new_status

    def test_status_unchanged(self, sample_invoice):
        """Statut identique : aucune écriture, valeur retournée."""
        pdp = MemoryPDP()
        with patch("facturx_fr.contrib.django.conf.get_pdp_instance", return_value=pdp):
            _run(tasks.submit_to_pdp, _FakeTask(), sample_invoice.pk)
            before = sample_invoice.__class__.objects.get(pk=sample_invoice.pk).updated_at
            new_status = _run(tasks.check_invoice_status, sample_invoice.pk)

        sample_invoice.refresh_from_db()
        assert sample_invoice.status == new_status
        assert sample_invoice.updated_at == before

    def test_pdp_error_propagates(self, sample_invoice, settings):
        """Une erreur PDP est journalisée puis relancée."""
        settings.FACTURX_FR = MEMORY_PDP
        sample_invoice.pdp_invoice_id = "INCONNU"
        sample_invoice.save()
        with pytest.raises(PDPNotFoundError):
            _run(tasks.check_invoice_status, sample_invoice.pk)
