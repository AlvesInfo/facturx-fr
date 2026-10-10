"""Tests des vues Django liées aux modèles (génération, soumission, téléchargement)."""

from unittest.mock import MagicMock, patch

import pytest
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse

URLCONF = "facturx_fr.contrib.django.urls"


@pytest.fixture
def client(settings) -> Client:
    """Client de test avec l'URLconf complète de l'app."""
    settings.ROOT_URLCONF = URLCONF
    return Client()


def _url(name: str, pk: int) -> str:
    return reverse(name, args=[pk])


class TestGenerateXMLView:
    """POST <id>/generate-xml/."""

    def test_success_saves_xml(self, client, sample_invoice, media_root):
        """Le XML est généré, validé et sauvegardé sur la facture."""
        response = client.post(_url("generate-xml", sample_invoice.pk))

        assert response.status_code == 200, response.content
        assert response.json()["status"] == "ok"
        sample_invoice.refresh_from_db()
        assert sample_invoice.xml_file
        assert b"CrossIndustryInvoice" in sample_invoice.xml_file.read()

    def test_generation_error(self, client, sample_invoice):
        """Une exception du générateur renvoie 500."""
        with patch(
            "facturx_fr.generators.cii.CIIGenerator.generate_xml",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(_url("generate-xml", sample_invoice.pk))
        assert response.status_code == 500
        assert "génération" in response.json()["error"]

    def test_validation_errors(self, client, sample_invoice):
        """Des erreurs de validation renvoient 400 avec le détail."""
        with patch("facturx_fr.validators.validate_xml", return_value=["BR-01 KO"]):
            response = client.post(_url("generate-xml", sample_invoice.pk))
        assert response.status_code == 400
        assert response.json()["details"] == ["BR-01 KO"]

    def test_unknown_invoice(self, client, db):
        """Un identifiant inconnu renvoie 404."""
        assert client.post(_url("generate-xml", 999_999)).status_code == 404


class TestSubmitToPDPView:
    """POST <id>/submit/."""

    def test_requires_xml(self, client, sample_invoice):
        """Sans XML généré : 400."""
        response = client.post(_url("submit", sample_invoice.pk))
        assert response.status_code == 400
        assert "XML non généré" in response.json()["error"]

    def test_celery_missing(self, client, invoice_with_xml):
        """Si le module des tâches est indisponible : 500."""
        with patch.dict("sys.modules", {"facturx_fr.contrib.django.tasks": None}):
            response = client.post(_url("submit", invoice_with_xml.pk))
        assert response.status_code == 500
        assert "Celery" in response.json()["error"]

    def test_launches_task(self, client, invoice_with_xml):
        """La tâche Celery est lancée avec l'identifiant de la facture."""
        task = MagicMock()
        with patch("facturx_fr.contrib.django.tasks.submit_to_pdp", task):
            response = client.post(_url("submit", invoice_with_xml.pk))
        assert response.status_code == 200
        task.delay.assert_called_once_with(invoice_with_xml.pk)


class TestDownloadViews:
    """GET <id>/download-xml/ et <id>/download-pdf/."""

    def test_download_xml(self, client, invoice_with_xml):
        """Le XML est servi en pièce jointe."""
        response = client.get(_url("download-xml", invoice_with_xml.pk))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/xml"
        assert "FA-2026-001.xml" in response["Content-Disposition"]
        assert b"CrossIndustryInvoice" in b"".join(response.streaming_content)

    def test_download_xml_missing(self, client, sample_invoice):
        """Sans fichier XML : 404."""
        assert client.get(_url("download-xml", sample_invoice.pk)).status_code == 404

    def test_download_pdf(self, client, sample_invoice, media_root):
        """Le PDF est servi en pièce jointe."""
        sample_invoice.pdf_file.save("facture.pdf", ContentFile(b"%PDF-1.7 test"), save=True)
        response = client.get(_url("download-pdf", sample_invoice.pk))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert "FA-2026-001.pdf" in response["Content-Disposition"]
        assert b"".join(response.streaming_content) == b"%PDF-1.7 test"

    def test_download_pdf_missing(self, client, sample_invoice):
        """Sans fichier PDF : 404."""
        assert client.get(_url("download-pdf", sample_invoice.pk)).status_code == 404


class TestCheckStatusView:
    """POST <id>/check-status/."""

    def test_requires_pdp_id(self, client, sample_invoice):
        """Facture jamais soumise : 400."""
        response = client.post(_url("check-status", sample_invoice.pk))
        assert response.status_code == 400
        assert "non soumise" in response.json()["error"]

    def test_celery_missing(self, client, sample_invoice):
        """Si le module des tâches est indisponible : 500."""
        sample_invoice.pdp_invoice_id = "PDP-1"
        sample_invoice.save()
        with patch.dict("sys.modules", {"facturx_fr.contrib.django.tasks": None}):
            response = client.post(_url("check-status", sample_invoice.pk))
        assert response.status_code == 500

    def test_launches_task(self, client, sample_invoice):
        """La tâche de vérification est lancée."""
        sample_invoice.pdp_invoice_id = "PDP-1"
        sample_invoice.save()
        task = MagicMock()
        with patch("facturx_fr.contrib.django.tasks.check_invoice_status", task):
            response = client.post(_url("check-status", sample_invoice.pk))
        assert response.status_code == 200
        task.delay.assert_called_once_with(sample_invoice.pk)
