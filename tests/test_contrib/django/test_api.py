"""Tests de l'API HTTP stateless (facturx_fr.contrib.django.api_views)."""

import base64
import io
import json
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from pypdf import PdfReader, PdfWriter

API_KEY = "cle-de-test-123"
API_SETTINGS = {"API_KEYS": [API_KEY], "API_VALIDATE_DEFAULT": True}
URLCONF = "facturx_fr.contrib.django.api_urls"


def _blank_pdf() -> bytes:
    """Construit un PDF minimal d'une page blanche."""
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def client():
    """Client de test Django, avec l'URLconf de l'API et une clé configurée."""
    with override_settings(ROOT_URLCONF=URLCONF, FACTURX_FR=API_SETTINGS):
        yield Client()


@pytest.fixture
def auth() -> dict[str, str]:
    """En-tête d'authentification valide."""
    return {"HTTP_AUTHORIZATION": f"Bearer {API_KEY}"}


@pytest.fixture
def invoice_json(sample_pydantic_invoice) -> str:
    """Facture de test sérialisée en JSON (format attendu par l'API)."""
    return sample_pydantic_invoice.model_dump_json()


@pytest.fixture
def pdf_bytes() -> bytes:
    """PDF source minimal."""
    return _blank_pdf()


class TestAuthentication:
    """Authentification par clé d'API."""

    def test_missing_key(self, client):
        """Sans clé : 401."""
        response = client.get("/health/")
        assert response.status_code == 401
        assert "manquante" in response.json()["error"]

    def test_invalid_key(self, client):
        """Clé inconnue : 401."""
        response = client.get("/health/", HTTP_X_API_KEY="mauvaise-cle")
        assert response.status_code == 401
        assert "invalide" in response.json()["error"]

    def test_bearer_key(self, client, auth):
        """Clé valide via Authorization: Bearer."""
        response = client.get("/health/", **auth)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_x_api_key_header(self, client):
        """Clé valide via X-API-Key."""
        response = client.get("/health/", HTTP_X_API_KEY=API_KEY)
        assert response.status_code == 200

    def test_no_key_configured(self, client):
        """Aucune clé configurée et anonyme interdit : 503."""
        with override_settings(FACTURX_FR={}):
            response = client.get("/health/")
        assert response.status_code == 503

    def test_anonymous_allowed(self, client):
        """Accès anonyme explicitement autorisé."""
        with override_settings(FACTURX_FR={"API_ALLOW_ANONYMOUS": True}):
            response = client.get("/health/")
        assert response.status_code == 200


class TestHealth:
    """Endpoint /health/."""

    def test_payload(self, client, auth):
        """Renvoie version, profils et formats."""
        data = client.get("/health/", **auth).json()
        assert data["service"] == "facturx-fr"
        assert "EN16931" in data["profiles"]
        assert data["xml_formats"] == ["cii", "ubl"]
        assert data["default_profile"] == "EN16931"


class TestGenerateFacturX:
    """Endpoint /generate/ : PDF Factur-X."""

    def test_generate_pdf(self, client, auth, invoice_json, pdf_bytes):
        """Multipart JSON + PDF → PDF Factur-X avec XML embarqué."""
        response = client.post(
            "/generate/",
            {
                "invoice": invoice_json,
                "pdf": io.BytesIO(pdf_bytes),
                "profile": "en16931",
            },
            **auth,
        )
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "application/pdf"
        assert response["X-FacturX-Profile"] == "EN16931"
        assert response["X-Invoice-Number"] == "FA-2026-001"
        assert 'filename="FA-2026-001.pdf"' in response["Content-Disposition"]

        content = response.content
        assert content.startswith(b"%PDF")
        reader = PdfReader(io.BytesIO(content))
        attachments = reader.attachments
        assert "factur-x.xml" in attachments
        xml = attachments["factur-x.xml"][0]
        assert b"CrossIndustryInvoice" in xml
        assert b"FA-2026-001" in xml

    def test_generate_json_output(self, client, auth, invoice_json, pdf_bytes):
        """output=json renvoie le PDF et le XML encodés en base64."""
        response = client.post(
            "/generate/",
            {
                "invoice": invoice_json,
                "pdf": io.BytesIO(pdf_bytes),
                "output": "json",
            },
            **auth,
        )
        assert response.status_code == 200, response.content
        data = response.json()
        assert data["number"] == "FA-2026-001"
        assert data["profile"] == "EN16931"
        assert data["validated"] is True
        assert data["total_excl_tax"] == "1760.00"
        assert base64.b64decode(data["pdf_base64"]).startswith(b"%PDF")
        assert b"CrossIndustryInvoice" in base64.b64decode(data["xml_base64"])

    def test_invoice_as_file_and_pdf_base64(self, client, auth, invoice_json, pdf_bytes):
        """La facture peut être un fichier et le PDF un champ base64."""
        response = client.post(
            "/generate/",
            {
                "invoice": io.BytesIO(invoice_json.encode()),
                "pdf_base64": base64.b64encode(pdf_bytes).decode(),
                "validate": "false",
            },
            **auth,
        )
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "application/pdf"

    def test_missing_pdf(self, client, auth, invoice_json):
        """Sans PDF source : 400."""
        response = client.post("/generate/", {"invoice": invoice_json}, **auth)
        assert response.status_code == 400
        assert "PDF source manquant" in response.json()["error"]

    def test_not_a_pdf(self, client, auth, invoice_json):
        """Fichier qui n'est pas un PDF : 400."""
        response = client.post(
            "/generate/",
            {"invoice": invoice_json, "pdf": io.BytesIO(b"pas un pdf")},
            **auth,
        )
        assert response.status_code == 400
        assert "n'est pas un PDF" in response.json()["error"]

    def test_missing_invoice(self, client, auth, pdf_bytes):
        """Sans facture : 400."""
        response = client.post("/generate/", {"pdf": io.BytesIO(pdf_bytes)}, **auth)
        assert response.status_code == 400
        assert "Facture manquante" in response.json()["error"]

    def test_invalid_invoice(self, client, auth, pdf_bytes):
        """Facture ne respectant pas le schéma Pydantic : 400 avec détails."""
        response = client.post(
            "/generate/",
            {"invoice": json.dumps({"number": "X"}), "pdf": io.BytesIO(pdf_bytes)},
            **auth,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Facture invalide."
        missing = {err["loc"][0] for err in data["details"]}
        assert {"issue_date", "seller", "buyer", "lines"} <= missing

    def test_malformed_json(self, client, auth, pdf_bytes):
        """JSON illisible : 400."""
        response = client.post(
            "/generate/",
            {"invoice": "{pas du json", "pdf": io.BytesIO(pdf_bytes)},
            **auth,
        )
        assert response.status_code == 400
        assert response.json()["error"] == "Facture invalide."

    def test_unknown_profile(self, client, auth, invoice_json, pdf_bytes):
        """Profil inconnu : 400."""
        response = client.post(
            "/generate/",
            {"invoice": invoice_json, "pdf": io.BytesIO(pdf_bytes), "profile": "ZUGFERD"},
            **auth,
        )
        assert response.status_code == 400
        assert "Profil inconnu" in response.json()["error"]

    def test_unknown_output(self, client, auth, invoice_json, pdf_bytes):
        """Sortie inconnue : 400."""
        response = client.post(
            "/generate/",
            {"invoice": invoice_json, "pdf": io.BytesIO(pdf_bytes), "output": "zip"},
            **auth,
        )
        assert response.status_code == 400

    def test_upload_too_large(self, client, auth, invoice_json, pdf_bytes):
        """Dépassement de la taille maximale : 413."""
        with override_settings(FACTURX_FR={**API_SETTINGS, "API_MAX_UPLOAD_SIZE": 100}):
            response = client.post(
                "/generate/",
                {"invoice": invoice_json, "pdf": io.BytesIO(pdf_bytes)},
                **auth,
            )
        assert response.status_code == 413

    def test_get_not_allowed(self, client, auth):
        """GET sur /generate/ : 405."""
        response = client.get("/generate/", **auth)
        assert response.status_code == 405


class TestGenerateXML:
    """Endpoint /generate-xml/."""

    def test_cii_from_json_body(self, client, auth, invoice_json):
        """Corps application/json → XML CII."""
        response = client.post(
            "/generate-xml/", invoice_json, content_type="application/json", **auth
        )
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "application/xml"
        assert b"CrossIndustryInvoice" in response.content
        assert 'filename="FA-2026-001.xml"' in response["Content-Disposition"]

    def test_ubl_from_query_param(self, client, auth, invoice_json):
        """format=ubl → XML UBL."""
        response = client.post(
            "/generate-xml/?format=ubl",
            invoice_json,
            content_type="application/json",
            **auth,
        )
        assert response.status_code == 200, response.content
        assert b"Invoice" in response.content
        assert b"CrossIndustryInvoice" not in response.content

    def test_multipart_form(self, client, auth, invoice_json):
        """Champ multipart 'invoice' + format dans le formulaire."""
        response = client.post(
            "/generate-xml/", {"invoice": invoice_json, "format": "cii"}, **auth
        )
        assert response.status_code == 200, response.content
        assert b"CrossIndustryInvoice" in response.content

    def test_unknown_format(self, client, auth, invoice_json):
        """Format inconnu : 400."""
        response = client.post(
            "/generate-xml/?format=edifact",
            invoice_json,
            content_type="application/json",
            **auth,
        )
        assert response.status_code == 400


class TestValidateXML:
    """Endpoint /validate/."""

    def test_valid_xml_raw_body(self, client, auth, invoice_json):
        """Un XML généré par l'API est valide."""
        xml = client.post(
            "/generate-xml/", invoice_json, content_type="application/json", **auth
        ).content
        response = client.post("/validate/", xml, content_type="application/xml", **auth)
        assert response.status_code == 200
        assert response.json() == {"valid": True, "errors": []}

    def test_invalid_xml_file(self, client, auth):
        """Un XML CII incomplet est rejeté avec la liste des erreurs."""
        bad_xml = (
            b'<?xml version="1.0"?>'
            b'<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:'
            b'CrossIndustryInvoice:100"></rsm:CrossIndustryInvoice>'
        )
        response = client.post("/validate/", {"xml": io.BytesIO(bad_xml)}, **auth)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["errors"]

    def test_missing_xml(self, client, auth):
        """Sans XML : 400."""
        response = client.post("/validate/", {}, **auth)
        assert response.status_code == 400


class TestAPIEdgeCases:
    """Chemins d'erreur moins courants de l'API."""

    def test_explicit_true_boolean(self, client, auth, invoice_json, pdf_bytes):
        """Une valeur vraie explicite active la validation."""
        response = client.post(
            "/generate/",
            {
                "invoice": invoice_json,
                "pdf": io.BytesIO(pdf_bytes),
                "validate": "oui",
                "output": "json",
            },
            **auth,
        )
        assert response.status_code == 200, response.content
        assert response.json()["validated"] is True

    def test_invalid_boolean(self, client, auth, invoice_json, pdf_bytes):
        """Un booléen non reconnu renvoie 400."""
        response = client.post(
            "/generate/",
            {"invoice": invoice_json, "pdf": io.BytesIO(pdf_bytes), "validate": "peut-être"},
            **auth,
        )
        assert response.status_code == 400
        assert "booléenne" in response.json()["error"]

    def test_unreadable_json(self, client, auth, pdf_bytes):
        """Une ValueError hors Pydantic est renvoyée en 'JSON illisible'."""
        with patch(
            "facturx_fr.contrib.django.api_views.Invoice.model_validate_json",
            side_effect=ValueError("boom"),
        ):
            response = client.post(
                "/generate/", {"invoice": "{}", "pdf": io.BytesIO(pdf_bytes)}, **auth
            )
        assert response.status_code == 400
        assert "JSON illisible" in response.json()["error"]

    def test_invalid_pdf_base64(self, client, auth, invoice_json):
        """Un champ pdf_base64 mal encodé renvoie 400."""
        response = client.post(
            "/generate/", {"invoice": invoice_json, "pdf_base64": "%%pas-du-base64%%"}, **auth
        )
        assert response.status_code == 400
        assert "pdf_base64" in response.json()["error"]

    def test_generated_xml_fails_validation(self, client, auth, invoice_json, pdf_bytes):
        """Des erreurs de validation du XML généré renvoient 422."""
        with patch("facturx_fr.contrib.django.api_views.validate_xml", return_value=["BR-01 KO"]):
            response = client.post(
                "/generate/", {"invoice": invoice_json, "pdf": io.BytesIO(pdf_bytes)}, **auth
            )
        assert response.status_code == 422
        assert response.json()["details"] == ["BR-01 KO"]

    def test_facturx_generation_failure(self, client, auth, invoice_json, pdf_bytes):
        """Une exception de la lib factur-x renvoie 500."""
        with patch(
            "facturx_fr.contrib.django.api_views.FacturXGenerator.generate",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(
                "/generate/",
                {"invoice": invoice_json, "pdf": io.BytesIO(pdf_bytes), "validate": "0"},
                **auth,
            )
        assert response.status_code == 500
        assert "Échec de la génération" in response.json()["error"]

    def test_unexpected_error_is_500(self, client, auth):
        """Une erreur imprévue est convertie en 500 générique."""
        with patch(
            "facturx_fr.contrib.django.api_views.check_api_key",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/health/", **auth)
        assert response.status_code == 500
        assert response.json()["error"] == "Erreur interne du serveur."

    def test_validate_xml_as_form_field(self, client, auth, invoice_json):
        """Le XML peut être transmis dans un champ texte de formulaire."""
        xml = client.post(
            "/generate-xml/", invoice_json, content_type="application/json", **auth
        ).content
        response = client.post("/validate/", {"xml": xml.decode("utf-8")}, **auth)
        assert response.status_code == 200
        assert response.json()["valid"] is True
