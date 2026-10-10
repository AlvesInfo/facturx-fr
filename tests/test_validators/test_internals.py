"""Tests des chemins internes des validateurs (fallbacks, parsing SVRL)."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from facturx_fr.generators.cii import CIIGenerator
from facturx_fr.models import Address, Invoice, InvoiceLine, Party
from facturx_fr.models.enums import OperationCategory
from facturx_fr.validators import _resolve_profile, validate_xml
from facturx_fr.validators.schematron import _get_xslt_path, _parse_svrl

_SVRL = """<?xml version="1.0"?>
<svrl:schematron-output xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
  <svrl:failed-assert id="BR-01" location="/root/a">
    <svrl:text>Règle avec identifiant</svrl:text>
  </svrl:failed-assert>
  <svrl:failed-assert location="/root/b">
    <svrl:text>Règle sans identifiant</svrl:text>
  </svrl:failed-assert>
  <svrl:failed-assert id="BR-03" location="/root/c"/>
</svrl:schematron-output>
"""


class TestSchematronInternals:
    """Tests des helpers privés de schematron.py."""

    def test_get_xslt_path_unsupported_combination(self) -> None:
        """Une combinaison profil/flavor inconnue lève ValueError."""
        with pytest.raises(ValueError, match="Pas de schématron disponible"):
            _get_xslt_path("extended", "cii")

    def test_parse_svrl_formats_with_and_without_rule_id(self) -> None:
        """Les assertions sont formatées selon la présence d'un identifiant."""
        errors = _parse_svrl(_SVRL)
        assert errors == [
            "[BR-01] Règle avec identifiant (emplacement: /root/a)",
            "Règle sans identifiant (emplacement: /root/b)",
        ]

    def test_empty_svrl_output_returns_no_error(self) -> None:
        """Une transformation XSLT sans résultat est traitée comme valide."""
        pytest.importorskip("saxonche")
        from facturx_fr.validators.schematron import validate_schematron

        proc = MagicMock()
        proc.new_xslt30_processor().compile_stylesheet().transform_to_string.return_value = ""
        processor_cls = MagicMock()
        processor_cls.return_value.__enter__.return_value = proc

        xml = (
            b"<rsm:CrossIndustryInvoice"
            b' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"/>'
        )
        with patch("saxonche.PySaxonProcessor", processor_cls):
            assert validate_schematron(xml, flavor="cii") == []


class TestValidateXMLFallbacks:
    """Tests des replis de validate_xml et _resolve_profile."""

    def test_schematron_skipped_when_saxonche_missing(self) -> None:
        """Sans saxonche, validate_xml retourne une liste vide après le XSD."""
        invoice = Invoice(
            number="FA-FALLBACK-001",
            issue_date=date(2026, 9, 15),
            seller=Party(
                name="Vendeur",
                address=Address(street="1 rue", city="Paris", postal_code="75001"),
            ),
            buyer=Party(
                name="Acheteur",
                address=Address(street="2 rue", city="Lyon", postal_code="69001"),
            ),
            lines=[
                InvoiceLine(
                    description="Produit",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                ),
            ],
            operation_category=OperationCategory.DELIVERY,
        )
        xml_bytes = CIIGenerator(profile="EN16931").generate_xml(invoice)
        with patch(
            "facturx_fr.validators.validate_schematron",
            side_effect=ImportError("saxonche"),
        ):
            assert validate_xml(xml_bytes, profile="en16931") == []

    def test_resolve_profile_on_invalid_xml(self) -> None:
        """Un XML illisible donne un profil vide (pas d'exception)."""
        assert _resolve_profile(b"pas du xml") == ""
