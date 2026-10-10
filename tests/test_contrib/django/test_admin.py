"""Tests de l'admin Django (enregistrement et actions)."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib import admin, messages
from django.test import RequestFactory

from facturx_fr.contrib.django.admin import InvoiceAdmin
from facturx_fr.contrib.django.models import Invoice


@pytest.fixture
def model_admin():
    return InvoiceAdmin(Invoice, admin.site)


@pytest.fixture
def request_():
    return RequestFactory().post("/admin/")


@pytest.fixture
def message_user(model_admin):
    """Remplace message_user pour capturer les messages émis."""
    with patch.object(model_admin, "message_user") as mocked:
        yield mocked


def _levels(message_user) -> list[int]:
    return [call.args[2] for call in message_user.call_args_list]


def test_invoice_is_registered():
    """Le modèle Invoice est enregistré avec InvoiceAdmin."""
    assert isinstance(admin.site._registry[Invoice], InvoiceAdmin)


@pytest.mark.django_db
class TestGenerateXMLAction:
    """Action « Générer le XML CII »."""

    def test_success(self, model_admin, request_, message_user, sample_invoice, media_root):
        model_admin.generate_xml(request_, Invoice.objects.filter(pk=sample_invoice.pk))

        sample_invoice.refresh_from_db()
        assert sample_invoice.xml_file
        assert _levels(message_user) == [messages.SUCCESS]
        assert "1 facture(s)" in message_user.call_args.args[1]

    def test_validation_errors(self, model_admin, request_, message_user, sample_invoice):
        with patch("facturx_fr.validators.validate_xml", return_value=["BR-01 KO"]):
            model_admin.generate_xml(request_, Invoice.objects.all())

        assert _levels(message_user) == [messages.ERROR]
        assert "BR-01 KO" in message_user.call_args.args[1]

    def test_generation_exception(self, model_admin, request_, message_user, sample_invoice):
        with patch(
            "facturx_fr.generators.cii.CIIGenerator.generate_xml",
            side_effect=RuntimeError("boom"),
        ):
            model_admin.generate_xml(request_, Invoice.objects.all())

        assert _levels(message_user) == [messages.ERROR]
        assert "Erreur lors de la génération" in message_user.call_args.args[1]


@pytest.mark.django_db
class TestSubmitToPDPAction:
    """Action « Soumettre à la PDP »."""

    def test_celery_missing(self, model_admin, request_, message_user, sample_invoice):
        with patch.dict("sys.modules", {"facturx_fr.contrib.django.tasks": None}):
            model_admin.submit_to_pdp(request_, Invoice.objects.all())

        assert _levels(message_user) == [messages.ERROR]
        assert "Celery" in message_user.call_args.args[1]

    def test_without_xml(self, model_admin, request_, message_user, sample_invoice):
        task = MagicMock()
        with patch("facturx_fr.contrib.django.tasks.submit_to_pdp", task):
            model_admin.submit_to_pdp(request_, Invoice.objects.all())

        task.delay.assert_not_called()
        assert _levels(message_user) == [messages.WARNING]

    def test_success(self, model_admin, request_, message_user, invoice_with_xml):
        task = MagicMock()
        with patch("facturx_fr.contrib.django.tasks.submit_to_pdp", task):
            model_admin.submit_to_pdp(request_, Invoice.objects.all())

        task.delay.assert_called_once_with(invoice_with_xml.pk)
        assert _levels(message_user) == [messages.SUCCESS]
