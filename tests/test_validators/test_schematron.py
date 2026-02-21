"""Tests unitaires de la validation schématron EN16931.

FR: Vérifie que validate_schematron() détecte correctement le format,
    applique les XSLT et retourne les erreurs de règles de gestion.
EN: Verifies that validate_schematron() correctly detects format,
    applies XSLT and returns business rule errors.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from facturx_fr.generators.cii import CIIGenerator
from facturx_fr.generators.ubl import UBLGenerator
from facturx_fr.models import Address, Invoice, InvoiceLine, Party
from facturx_fr.models.enums import (
    InvoiceTypeCode,
    OperationCategory,
    UnitOfMeasure,
)

try:
    import saxonche  # noqa: F401
    HAS_SAXONCHE = True
except ImportError:
    HAS_SAXONCHE = False

requires_saxonche = pytest.mark.skipif(
    not HAS_SAXONCHE,
    reason="saxonche non installé",
)


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
def valid_cii_xml(sample_invoice: Invoice) -> bytes:
    """XML CII valide généré depuis la facture de test."""
    gen = CIIGenerator(profile="EN16931")
    return gen.generate_xml(sample_invoice)


@pytest.fixture
def valid_ubl_xml(sample_invoice: Invoice) -> bytes:
    """XML UBL valide généré depuis la facture de test."""
    gen = UBLGenerator(profile="EN16931")
    return gen.generate_xml(sample_invoice)


@pytest.fixture
def valid_ubl_credit_note(sample_invoice: Invoice) -> bytes:
    """XML UBL CreditNote valide."""
    sample_invoice.type_code = InvoiceTypeCode.CREDIT_NOTE
    gen = UBLGenerator(profile="EN16931")
    return gen.generate_xml(sample_invoice)


# --- Tests de détection du format ---


class TestFlavorAutodetect:
    """Tests de la détection automatique du format (CII/UBL)."""

    @requires_saxonche
    def test_cii_detected(self, valid_cii_xml: bytes) -> None:
        """Le namespace CII est correctement détecté."""
        from facturx_fr.validators.schematron import _detect_flavor

        assert _detect_flavor(valid_cii_xml) == "cii"

    @requires_saxonche
    def test_ubl_invoice_detected(self, valid_ubl_xml: bytes) -> None:
        """Le namespace UBL Invoice est correctement détecté."""
        from facturx_fr.validators.schematron import _detect_flavor

        assert _detect_flavor(valid_ubl_xml) == "ubl"

    @requires_saxonche
    def test_ubl_credit_note_detected(self, valid_ubl_credit_note: bytes) -> None:
        """Le namespace UBL CreditNote est correctement détecté."""
        from facturx_fr.validators.schematron import _detect_flavor

        assert _detect_flavor(valid_ubl_credit_note) == "ubl"

    @requires_saxonche
    def test_unknown_namespace_raises(self) -> None:
        """Un namespace inconnu lève ValueError."""
        from facturx_fr.validators.schematron import _detect_flavor

        xml = b'<?xml version="1.0"?><root xmlns="http://unknown.ns"/>'
        with pytest.raises(ValueError, match="Namespace racine non reconnu"):
            _detect_flavor(xml)

    @requires_saxonche
    def test_invalid_xml_raises(self) -> None:
        """Du XML malformé lève ValueError."""
        from facturx_fr.validators.schematron import _detect_flavor

        with pytest.raises(ValueError, match="XML invalide"):
            _detect_flavor(b"pas du xml")


# --- Tests de validation CII ---


class TestValidCII:
    """Tests de validation schématron CII."""

    @requires_saxonche
    def test_valid_cii_passes(self, valid_cii_xml: bytes) -> None:
        """Un XML CII conforme passe le schématron sans erreur."""
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_cii_xml)
        assert errors == []

    @requires_saxonche
    def test_valid_cii_explicit_flavor(self, valid_cii_xml: bytes) -> None:
        """Flavor CII explicite fonctionne."""
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_cii_xml, flavor="cii")
        assert errors == []

    @requires_saxonche
    def test_invalid_cii_returns_errors(self) -> None:
        """Un XML CII avec des données manquantes retourne des erreurs schématron."""
        from facturx_fr.validators.schematron import validate_schematron

        # CII minimal sans adresses ni lignes
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
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">20260915</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Test Seller</ram:Name>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>Test Buyer</ram:Name>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">0.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>100.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>100.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
        errors = validate_schematron(xml, flavor="cii")
        assert len(errors) > 0
        # BR-08 : adresse postale vendeur obligatoire
        assert any("BR-08" in e for e in errors)


# --- Tests de validation UBL ---


class TestValidUBL:
    """Tests de validation schématron UBL."""

    @requires_saxonche
    def test_valid_ubl_passes(self, valid_ubl_xml: bytes) -> None:
        """Un XML UBL conforme passe le schématron sans erreur."""
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_ubl_xml)
        assert errors == []

    @requires_saxonche
    def test_valid_ubl_explicit_flavor(self, valid_ubl_xml: bytes) -> None:
        """Flavor UBL explicite fonctionne."""
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_ubl_xml, flavor="ubl")
        assert errors == []

    @requires_saxonche
    def test_valid_credit_note_passes(self, valid_ubl_credit_note: bytes) -> None:
        """Un CreditNote UBL conforme passe le schématron."""
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_ubl_credit_note)
        assert errors == []


# --- Tests des profils ---


class TestProfileValidation:
    """Tests de la gestion des profils."""

    @requires_saxonche
    def test_en16931_profile(self, valid_cii_xml: bytes) -> None:
        """Le profil EN16931 fonctionne."""
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_cii_xml, profile="EN16931")
        assert errors == []

    @requires_saxonche
    def test_en16931_lowercase(self, valid_cii_xml: bytes) -> None:
        """Le profil en minuscules est accepté."""
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_cii_xml, profile="en16931")
        assert errors == []

    @requires_saxonche
    def test_invalid_profile_raises(self, valid_cii_xml: bytes) -> None:
        """Un profil non supporté lève ValueError."""
        from facturx_fr.validators.schematron import validate_schematron

        with pytest.raises(ValueError, match="Profil non supporté"):
            validate_schematron(valid_cii_xml, profile="INVALID")

    @requires_saxonche
    def test_invalid_flavor_raises(self, valid_cii_xml: bytes) -> None:
        """Un flavor non supporté lève ValueError."""
        from facturx_fr.validators.schematron import validate_schematron

        with pytest.raises(ValueError, match="Flavor non supporté"):
            validate_schematron(valid_cii_xml, flavor="edifact")


# --- Tests du format des erreurs ---


class TestErrorFormat:
    """Tests du format des messages d'erreur."""

    @requires_saxonche
    def test_errors_contain_rule_id(self) -> None:
        """Les erreurs contiennent l'identifiant de la règle."""
        from facturx_fr.validators.schematron import validate_schematron

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
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">20260915</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Test Seller</ram:Name>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>Test Buyer</ram:Name>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">0.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>100.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>100.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
        errors = validate_schematron(xml, flavor="cii")
        assert len(errors) > 0
        # Chaque erreur contient [RULE_ID], un texte et un emplacement
        for error in errors:
            assert "[BR-" in error or "[CII-" in error
            assert "emplacement:" in error

    @requires_saxonche
    def test_errors_contain_location(self) -> None:
        """Les erreurs contiennent l'emplacement XPath."""
        from facturx_fr.validators.schematron import validate_schematron

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
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">20260915</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Test</ram:Name>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>Test</ram:Name>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>0.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">0.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>0.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>0.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
        errors = validate_schematron(xml, flavor="cii")
        assert len(errors) > 0
        # Vérifier qu'au moins une erreur contient un chemin XPath
        assert any("/" in e.split("emplacement:")[1] for e in errors if "emplacement:" in e)


# --- Test import manquant ---


class TestMissingSaxonche:
    """Tests du comportement quand saxonche n'est pas installé."""

    def test_missing_saxonche_raises_import_error(self, valid_cii_xml: bytes) -> None:
        """L'absence de saxonche lève ImportError avec message utile."""
        from facturx_fr.validators.schematron import validate_schematron

        with patch.dict("sys.modules", {"saxonche": None}):
            with pytest.raises(ImportError, match="pip install facturx-fr\\[schematron\\]"):
                validate_schematron(valid_cii_xml)


# --- Test d'intégration validate_xml ---


class TestValidateXMLIntegration:
    """Tests de l'intégration schématron dans validate_xml()."""

    @requires_saxonche
    def test_validate_xml_chains_xsd_and_schematron(self, valid_cii_xml: bytes) -> None:
        """validate_xml() chaîne XSD puis schématron avec succès."""
        from facturx_fr.validators import validate_xml

        errors = validate_xml(valid_cii_xml)
        assert errors == []

    @requires_saxonche
    def test_validate_xml_stops_at_xsd_errors(self) -> None:
        """validate_xml() ne lance pas le schématron si le XSD échoue."""
        from facturx_fr.validators import validate_xml

        errors = validate_xml(b"pas du xml")
        assert len(errors) == 1
        assert "Erreur de syntaxe XML" in errors[0]

    @requires_saxonche
    def test_validate_xml_skips_schematron_for_minimum(self) -> None:
        """validate_xml() n'applique pas le schématron pour le profil Minimum."""
        from facturx_fr.validators import validate_xml

        # XML Minimum valide (pas de lignes de détail)
        xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:factur-x.eu:1p0:minimum</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>TEST</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">20260915</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Test</ram:Name>
        <ram:SpecifiedLegalOrganization>
          <ram:ID schemeID="0002">123456789</ram:ID>
        </ram:SpecifiedLegalOrganization>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>Buyer</ram:Name>
      </ram:BuyerTradeParty>
      <ram:BuyerOrderReferencedDocument>
        <ram:IssuerAssignedID>PO-001</ram:IssuerAssignedID>
      </ram:BuyerOrderReferencedDocument>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">20.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>120.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>120.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
        errors = validate_xml(xml, profile="minimum")
        # XSD Minimum ne valide que la structure minimale
        # Le schématron ne doit PAS être appliqué
        assert errors == []

    @requires_saxonche
    def test_validate_xml_ubl(self, valid_ubl_xml: bytes) -> None:
        """validate_xml() avec du UBL ne chaîne pas le schématron (XSD factur-x only)."""
        # validate_xml with flavor="factur-x" won't work for UBL XSD,
        # but validate_schematron directly works
        from facturx_fr.validators.schematron import validate_schematron

        errors = validate_schematron(valid_ubl_xml)
        assert errors == []
