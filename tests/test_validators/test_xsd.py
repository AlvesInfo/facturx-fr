"""Tests unitaires de la validation XSD.

FR: Vérifie que validate_xsd() et validate_xml() retournent les erreurs
    attendues pour des XML valides, invalides et malformés.
EN: Verifies that validate_xsd() and validate_xml() return expected errors
    for valid, invalid and malformed XML documents.
"""

from datetime import date
from decimal import Decimal

import pytest

from facturx_fr.generators.cii import CIIGenerator
from facturx_fr.models import Address, Invoice, InvoiceLine, Party
from facturx_fr.models.enums import OperationCategory, UnitOfMeasure
from facturx_fr.validators import validate_xml
from facturx_fr.validators.xsd import validate_xsd


@pytest.fixture
def sample_invoice() -> Invoice:
    """Facture de test conforme EN16931."""
    return Invoice(
        number="FA-2026-042",
        issue_date=date(2026, 9, 15),
        due_date=date(2026, 10, 15),
        seller=Party(
            name="OptiPaulo SARL",
            siren="123456789",
            vat_number="FR12345678901",
            address=Address(
                street="12 rue des Opticiens",
                city="Créteil",
                postal_code="94000",
                country_code="FR",
            ),
        ),
        buyer=Party(
            name="LunettesPlus SA",
            siren="987654321",
            vat_number="FR98765432101",
            address=Address(
                street="5 avenue de la Vision",
                city="Paris",
                postal_code="75011",
                country_code="FR",
            ),
        ),
        lines=[
            InvoiceLine(
                description="Monture Ray-Ban Aviator",
                quantity=Decimal("10"),
                unit=UnitOfMeasure.UNIT,
                unit_price=Decimal("85.00"),
                vat_rate=Decimal("20.0"),
            ),
        ],
        operation_category=OperationCategory.DELIVERY,
        currency="EUR",
    )


@pytest.fixture
def valid_xml(sample_invoice: Invoice) -> bytes:
    """XML CII valide généré depuis la facture de test."""
    gen = CIIGenerator(profile="EN16931")
    return gen.generate_xml(sample_invoice)


class TestValidXML:
    """Tests avec du XML valide."""

    def test_valid_xml(self, valid_xml: bytes) -> None:
        """Un XML valide retourne une liste vide."""
        errors = validate_xsd(valid_xml)
        assert errors == []

    def test_autodetect_profile(self, valid_xml: bytes) -> None:
        """L'auto-détection du profil fonctionne avec du XML valide."""
        errors = validate_xsd(valid_xml, profile="autodetect")
        assert errors == []

    def test_explicit_profile_en16931(self, valid_xml: bytes) -> None:
        """Le profil EN16931 explicite valide le XML correctement."""
        errors = validate_xsd(valid_xml, profile="EN16931")
        assert errors == []

    def test_explicit_profile_lowercase(self, valid_xml: bytes) -> None:
        """Le profil en minuscules est accepté."""
        errors = validate_xsd(valid_xml, profile="en16931")
        assert errors == []


class TestInvalidXML:
    """Tests avec du XML invalide."""

    def test_invalid_xml_syntax(self) -> None:
        """Des bytes non-XML retournent une erreur de syntaxe."""
        errors = validate_xsd(b"ceci n'est pas du XML")
        assert len(errors) == 1
        assert "Erreur de syntaxe XML" in errors[0]

    def test_invalid_xml_structure(self) -> None:
        """Un XML bien formé mais avec une mauvaise structure CII retourne des erreurs."""
        xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>TEST</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
  </rsm:ExchangedDocument>
</rsm:CrossIndustryInvoice>"""
        errors = validate_xsd(xml, profile="en16931")
        assert len(errors) > 0
        assert any("Ligne" in e for e in errors)

    def test_multiple_errors(self) -> None:
        """Un XML avec plusieurs problèmes retourne plusieurs erreurs."""
        # XML minimal : manque ExchangedDocument et SupplyChainTradeTransaction
        xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>TEST</ram:ID>
  </rsm:ExchangedDocument>
</rsm:CrossIndustryInvoice>"""
        errors = validate_xsd(xml, profile="en16931")
        assert len(errors) > 1


class TestFlavorAndProfile:
    """Tests des paramètres flavor et profile."""

    def test_unsupported_flavor(self, valid_xml: bytes) -> None:
        """Un flavor non supporté lève ValueError."""
        with pytest.raises(ValueError, match="Flavor non supporté"):
            validate_xsd(valid_xml, flavor="ubl")

    def test_unknown_profile(self, valid_xml: bytes) -> None:
        """Un profil inconnu lève ValueError."""
        with pytest.raises(ValueError, match="Profil inconnu"):
            validate_xsd(valid_xml, profile="INVALID")


class TestValidateXMLAlias:
    """Tests du point d'entrée validate_xml()."""

    def test_validate_xml_alias(self, valid_xml: bytes) -> None:
        """validate_xml() retourne le même résultat que validate_xsd()."""
        xsd_result = validate_xsd(valid_xml)
        xml_result = validate_xml(valid_xml)
        assert xsd_result == xml_result

    def test_validate_xml_with_errors(self) -> None:
        """validate_xml() retourne bien les erreurs de syntaxe."""
        errors = validate_xml(b"pas du xml")
        assert len(errors) == 1
        assert "Erreur de syntaxe XML" in errors[0]
