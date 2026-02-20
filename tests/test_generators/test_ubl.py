"""Tests unitaires du générateur UBL 2.1.

FR: Vérifie la structure XML UBL générée, les namespaces, profils,
    parties, lignes, taxes, totaux et les champs optionnels.
EN: Verifies the generated UBL XML structure, namespaces, profiles,
    parties, lines, taxes, totals and optional fields.
"""

from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from facturx_fr.generators.ubl import (
    CAC,
    CBC,
    CN_NS,
    INV_NS,
    PROFILE_URNS,
    UBLGenerator,
)
from facturx_fr.models import (
    Address,
    BankAccount,
    Invoice,
    InvoiceLine,
    Party,
    PaymentMeans,
    PaymentTerms,
)
from facturx_fr.models.enums import (
    InvoiceTypeCode,
    OperationCategory,
    PaymentMeansCode,
    UnitOfMeasure,
    VATCategory,
)

# Namespaces pour les requêtes XPath
NS = {"cac": CAC, "cbc": CBC}


def _parse(xml_bytes: bytes) -> etree._Element:
    """Parse le XML et retourne l'élément racine."""
    return etree.fromstring(xml_bytes)


@pytest.fixture
def sample_invoice() -> Invoice:
    """Facture de test simple avec une ligne."""
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


class TestBasicInvoiceXML:
    """Tests de la structure XML de base."""

    def test_root_element_is_invoice(self, sample_invoice: Invoice) -> None:
        """Vérifie que l'élément racine est Invoice."""
        gen = UBLGenerator(profile="EN16931")
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.tag == f"{{{INV_NS}}}Invoice"

    def test_xml_namespaces(self, sample_invoice: Invoice) -> None:
        """Vérifie que les namespaces UBL sont correctement déclarés."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.nsmap[None] == INV_NS
        assert root.nsmap["cac"] == CAC
        assert root.nsmap["cbc"] == CBC

    def test_main_sections_present(self, sample_invoice: Invoice) -> None:
        """Vérifie que les sections principales sont présentes."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.find("cbc:ID", NS) is not None
        assert root.find("cac:AccountingSupplierParty", NS) is not None
        assert root.find("cac:AccountingCustomerParty", NS) is not None
        assert root.find("cac:TaxTotal", NS) is not None
        assert root.find("cac:LegalMonetaryTotal", NS) is not None
        assert root.find("cac:InvoiceLine", NS) is not None


class TestHeader:
    """Tests des éléments d'en-tête."""

    def test_customization_id(self, sample_invoice: Invoice) -> None:
        """Vérifie le CustomizationID pour le profil EN16931."""
        gen = UBLGenerator(profile="EN16931")
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        cust_id = root.find("cbc:CustomizationID", NS)
        assert cust_id is not None
        assert cust_id.text == "urn:cen.eu:en16931:2017"

    def test_invoice_id(self, sample_invoice: Invoice) -> None:
        """Vérifie le numéro de facture."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.find("cbc:ID", NS).text == "FA-2026-042"

    def test_issue_date(self, sample_invoice: Invoice) -> None:
        """Vérifie la date d'émission au format ISO 8601."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.find("cbc:IssueDate", NS).text == "2026-09-15"

    def test_invoice_type_code(self, sample_invoice: Invoice) -> None:
        """Vérifie le code type de document."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.find("cbc:InvoiceTypeCode", NS).text == "380"

    def test_document_currency_code(self, sample_invoice: Invoice) -> None:
        """Vérifie le code devise."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.find("cbc:DocumentCurrencyCode", NS).text == "EUR"


class TestProfiles:
    """Tests des profils supportés."""

    def test_en16931_profile(self, sample_invoice: Invoice) -> None:
        """Vérifie le profil EN16931 (CustomizationID sans ProfileID)."""
        gen = UBLGenerator(profile="EN16931")
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        cust_id = root.find("cbc:CustomizationID", NS)
        assert cust_id is not None
        assert cust_id.text == "urn:cen.eu:en16931:2017"

        # Pas de ProfileID pour EN16931
        profile_id = root.find("cbc:ProfileID", NS)
        assert profile_id is None

    def test_peppol_profile(self, sample_invoice: Invoice) -> None:
        """Vérifie le profil PEPPOL (CustomizationID + ProfileID)."""
        gen = UBLGenerator(profile="PEPPOL")
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        cust_id = root.find("cbc:CustomizationID", NS)
        assert cust_id is not None
        assert cust_id.text == (
            "urn:cen.eu:en16931:2017#compliant#"
            "urn:fdc:peppol.eu:2017:poacc:billing:3.0"
        )

        profile_id = root.find("cbc:ProfileID", NS)
        assert profile_id is not None
        assert profile_id.text == "urn:fdc:peppol.eu:2017:poacc:billing:3.0"

    def test_invalid_profile(self, sample_invoice: Invoice) -> None:
        """Vérifie qu'un profil inconnu lève une erreur."""
        gen = UBLGenerator(profile="INVALID")
        with pytest.raises(ValueError, match="Profil inconnu"):
            gen.generate_xml(sample_invoice)


class TestSellerBuyerParties:
    """Tests des parties vendeur/acheteur."""

    def test_seller_party_name(self, sample_invoice: Invoice) -> None:
        """Vérifie le nom du vendeur."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        name = root.find(
            "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        )
        assert name is not None
        assert name.text == "OptiPaulo SARL"

    def test_seller_postal_address(self, sample_invoice: Invoice) -> None:
        """Vérifie l'adresse postale du vendeur."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        addr = root.find(
            "cac:AccountingSupplierParty/cac:Party/cac:PostalAddress",
            NS,
        )
        assert addr is not None
        assert addr.find("cbc:StreetName", NS).text == "12 rue des Opticiens"
        assert addr.find("cbc:CityName", NS).text == "Créteil"
        assert addr.find("cbc:PostalZone", NS).text == "94000"
        assert (
            addr.find("cac:Country/cbc:IdentificationCode", NS).text == "FR"
        )

    def test_seller_vat_number(self, sample_invoice: Invoice) -> None:
        """Vérifie le numéro de TVA du vendeur."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        vat = root.find(
            "cac:AccountingSupplierParty/cac:Party/"
            "cac:PartyTaxScheme/cbc:CompanyID",
            NS,
        )
        assert vat is not None
        assert vat.text == "FR12345678901"

        tax_scheme = root.find(
            "cac:AccountingSupplierParty/cac:Party/"
            "cac:PartyTaxScheme/cac:TaxScheme/cbc:ID",
            NS,
        )
        assert tax_scheme is not None
        assert tax_scheme.text == "VAT"

    def test_seller_siren(self, sample_invoice: Invoice) -> None:
        """Vérifie le SIREN du vendeur (PartyLegalEntity)."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        legal = root.find(
            "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity",
            NS,
        )
        assert legal is not None
        assert legal.find("cbc:RegistrationName", NS).text == "OptiPaulo SARL"

        company_id = legal.find("cbc:CompanyID", NS)
        assert company_id is not None
        assert company_id.text == "123456789"
        assert company_id.get("schemeID") == "0002"

    def test_buyer_party(self, sample_invoice: Invoice) -> None:
        """Vérifie les informations de l'acheteur."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        name = root.find(
            "cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        )
        assert name is not None
        assert name.text == "LunettesPlus SA"

        siren = root.find(
            "cac:AccountingCustomerParty/cac:Party/"
            "cac:PartyLegalEntity/cbc:CompanyID",
            NS,
        )
        assert siren is not None
        assert siren.text == "987654321"
        assert siren.get("schemeID") == "0002"

    def test_additional_street(self) -> None:
        """Vérifie le complément d'adresse."""
        invoice = Invoice(
            number="FA-ADDR-001",
            issue_date=date(2026, 9, 15),
            seller=Party(
                name="Vendeur",
                address=Address(
                    street="10 rue Complète",
                    additional_street="Bâtiment B",
                    city="Paris",
                    postal_code="75001",
                ),
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

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        addr = root.find(
            "cac:AccountingSupplierParty/cac:Party/cac:PostalAddress",
            NS,
        )
        assert addr.find("cbc:AdditionalStreetName", NS).text == "Bâtiment B"


class TestLineItems:
    """Tests des lignes de facture."""

    def test_line_id(self, sample_invoice: Invoice) -> None:
        """Vérifie l'ID de la ligne."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        line = root.find("cac:InvoiceLine", NS)
        assert line is not None
        assert line.find("cbc:ID", NS).text == "1"

    def test_invoiced_quantity(self, sample_invoice: Invoice) -> None:
        """Vérifie la quantité facturée et l'unité."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        qty = root.find("cac:InvoiceLine/cbc:InvoicedQuantity", NS)
        assert qty is not None
        assert qty.text == "10"
        assert qty.get("unitCode") == "C62"

    def test_line_extension_amount(self, sample_invoice: Invoice) -> None:
        """Vérifie le montant HT de la ligne avec currencyID."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        line_ext = root.find(
            "cac:InvoiceLine/cbc:LineExtensionAmount", NS
        )
        assert line_ext is not None
        assert line_ext.text == "850.00"
        assert line_ext.get("currencyID") == "EUR"

    def test_item_name(self, sample_invoice: Invoice) -> None:
        """Vérifie le nom de l'article."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        name = root.find("cac:InvoiceLine/cac:Item/cbc:Name", NS)
        assert name is not None
        assert name.text == "Monture Ray-Ban Aviator"

    def test_classified_tax_category(self, sample_invoice: Invoice) -> None:
        """Vérifie la catégorie de TVA de la ligne."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        tax_cat = root.find(
            "cac:InvoiceLine/cac:Item/cac:ClassifiedTaxCategory", NS
        )
        assert tax_cat is not None
        assert tax_cat.find("cbc:ID", NS).text == "S"
        assert tax_cat.find("cbc:Percent", NS).text == "20.00"
        assert (
            tax_cat.find("cac:TaxScheme/cbc:ID", NS).text == "VAT"
        )

    def test_price_amount(self, sample_invoice: Invoice) -> None:
        """Vérifie le prix unitaire avec currencyID."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        price = root.find(
            "cac:InvoiceLine/cac:Price/cbc:PriceAmount", NS
        )
        assert price is not None
        assert price.text == "85.00"
        assert price.get("currencyID") == "EUR"

    def test_explicit_line_number(self) -> None:
        """Vérifie que line_number explicite est utilisé comme ID."""
        invoice = Invoice(
            number="FA-LN-001",
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
                    line_number=10,
                    description="Ligne avec numéro explicite",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                ),
            ],
            operation_category=OperationCategory.DELIVERY,
        )

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        line_id = root.find("cac:InvoiceLine/cbc:ID", NS)
        assert line_id is not None
        assert line_id.text == "10"

    def test_unit_of_measure(self) -> None:
        """Vérifie que l'unité de mesure est correctement émise."""
        invoice = Invoice(
            number="FA-UNIT-001",
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
                    description="Consultation 2h",
                    quantity=Decimal("2"),
                    unit=UnitOfMeasure.HOUR,
                    unit_price=Decimal("75.00"),
                ),
            ],
            operation_category=OperationCategory.SERVICE,
        )

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        qty = root.find("cac:InvoiceLine/cbc:InvoicedQuantity", NS)
        assert qty is not None
        assert qty.get("unitCode") == "HUR"

    def test_multiple_lines(self) -> None:
        """Vérifie une facture avec plusieurs lignes et taux de TVA différents."""
        invoice = Invoice(
            number="FA-2026-100",
            issue_date=date(2026, 10, 1),
            seller=Party(
                name="Vendeur Test",
                siren="111222333",
                vat_number="FR11122233301",
                address=Address(
                    street="1 rue Test",
                    city="Lyon",
                    postal_code="69001",
                ),
            ),
            buyer=Party(
                name="Acheteur Test",
                siren="444555666",
                address=Address(
                    street="2 rue Test",
                    city="Marseille",
                    postal_code="13001",
                ),
            ),
            lines=[
                InvoiceLine(
                    description="Article A",
                    quantity=Decimal("5"),
                    unit_price=Decimal("100.00"),
                    vat_rate=Decimal("20.0"),
                ),
                InvoiceLine(
                    description="Article B",
                    quantity=Decimal("2"),
                    unit_price=Decimal("50.00"),
                    vat_rate=Decimal("5.5"),
                    vat_category=VATCategory.STANDARD,
                ),
            ],
            operation_category=OperationCategory.MIXED,
        )

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        lines = root.findall("cac:InvoiceLine", NS)
        assert len(lines) == 2
        assert lines[0].find("cbc:ID", NS).text == "1"
        assert lines[1].find("cbc:ID", NS).text == "2"

    def test_line_item_references(self) -> None:
        """Vérifie les références article vendeur/acheteur sur une ligne."""
        invoice = Invoice(
            number="FA-REF-001",
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
                    item_reference="REF-VEND-001",
                    buyer_reference="REF-ACH-001",
                ),
            ],
            operation_category=OperationCategory.DELIVERY,
        )

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        item = root.find("cac:InvoiceLine/cac:Item", NS)
        assert item is not None
        assert (
            item.find("cac:SellersItemIdentification/cbc:ID", NS).text
            == "REF-VEND-001"
        )
        assert (
            item.find("cac:BuyersItemIdentification/cbc:ID", NS).text
            == "REF-ACH-001"
        )


class TestTaxSummaries:
    """Tests des récapitulatifs TVA."""

    def test_tax_total(self, sample_invoice: Invoice) -> None:
        """Vérifie TaxTotal et TaxSubtotal."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        tax_total = root.find("cac:TaxTotal", NS)
        assert tax_total is not None

        # TaxAmount au niveau TaxTotal
        tax_amount = tax_total.find("cbc:TaxAmount", NS)
        assert tax_amount is not None
        assert tax_amount.text == "170.00"
        assert tax_amount.get("currencyID") == "EUR"

        # TaxSubtotal
        subtotals = tax_total.findall("cac:TaxSubtotal", NS)
        assert len(subtotals) == 1

        subtotal = subtotals[0]
        taxable = subtotal.find("cbc:TaxableAmount", NS)
        assert taxable is not None
        assert taxable.text == "850.00"
        assert taxable.get("currencyID") == "EUR"

        sub_tax_amount = subtotal.find("cbc:TaxAmount", NS)
        assert sub_tax_amount is not None
        assert sub_tax_amount.text == "170.00"
        assert sub_tax_amount.get("currencyID") == "EUR"

        tax_cat = subtotal.find("cac:TaxCategory", NS)
        assert tax_cat is not None
        assert tax_cat.find("cbc:ID", NS).text == "S"
        assert tax_cat.find("cbc:Percent", NS).text == "20.00"
        assert tax_cat.find("cac:TaxScheme/cbc:ID", NS).text == "VAT"

    def test_multiple_tax_rates(self) -> None:
        """Vérifie les TaxSubtotal avec plusieurs taux de TVA."""
        invoice = Invoice(
            number="FA-MULTI-TVA",
            issue_date=date(2026, 9, 15),
            seller=Party(
                name="Vendeur",
                siren="111222333",
                address=Address(
                    street="1 rue", city="Paris", postal_code="75001"
                ),
            ),
            buyer=Party(
                name="Acheteur",
                siren="444555666",
                address=Address(
                    street="2 rue", city="Lyon", postal_code="69001"
                ),
            ),
            lines=[
                InvoiceLine(
                    description="Article 20%",
                    quantity=Decimal("5"),
                    unit_price=Decimal("100.00"),
                    vat_rate=Decimal("20.0"),
                ),
                InvoiceLine(
                    description="Article 5.5%",
                    quantity=Decimal("2"),
                    unit_price=Decimal("50.00"),
                    vat_rate=Decimal("5.5"),
                ),
            ],
            operation_category=OperationCategory.MIXED,
        )

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        subtotals = root.findall("cac:TaxTotal/cac:TaxSubtotal", NS)
        assert len(subtotals) == 2

        percents = [
            s.find("cac:TaxCategory/cbc:Percent", NS).text for s in subtotals
        ]
        assert percents == ["5.50", "20.00"]


class TestMonetarySummation:
    """Tests des totaux monétaires."""

    def test_legal_monetary_total(self, sample_invoice: Invoice) -> None:
        """Vérifie LegalMonetaryTotal avec currencyID sur tous les montants."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        monetary = root.find("cac:LegalMonetaryTotal", NS)
        assert monetary is not None

        line_ext = monetary.find("cbc:LineExtensionAmount", NS)
        assert line_ext is not None
        assert line_ext.text == "850.00"
        assert line_ext.get("currencyID") == "EUR"

        tax_excl = monetary.find("cbc:TaxExclusiveAmount", NS)
        assert tax_excl is not None
        assert tax_excl.text == "850.00"
        assert tax_excl.get("currencyID") == "EUR"

        tax_incl = monetary.find("cbc:TaxInclusiveAmount", NS)
        assert tax_incl is not None
        assert tax_incl.text == "1020.00"
        assert tax_incl.get("currencyID") == "EUR"

        payable = monetary.find("cbc:PayableAmount", NS)
        assert payable is not None
        assert payable.text == "1020.00"
        assert payable.get("currencyID") == "EUR"


class TestDueDate:
    """Tests de la date d'échéance."""

    def test_due_date_present(self, sample_invoice: Invoice) -> None:
        """Vérifie que DueDate est émise au niveau racine."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        due_date = root.find("cbc:DueDate", NS)
        assert due_date is not None
        assert due_date.text == "2026-10-15"

    def test_no_due_date(self) -> None:
        """Vérifie qu'aucun DueDate n'est émis sans due_date."""
        invoice = Invoice(
            number="FA-NODUE-001",
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

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        assert root.find("cbc:DueDate", NS) is None


class TestOptionalFields:
    """Tests des champs optionnels (paiement, notes, références)."""

    def test_payment_means(self, sample_invoice: Invoice) -> None:
        """Vérifie les moyens de paiement (code, IBAN, BIC)."""
        sample_invoice.payment_means = PaymentMeans(
            code=PaymentMeansCode.CREDIT_TRANSFER,
            bank_account=BankAccount(
                iban="FR7630006000011234567890189",
                bic="BNPAFRPP",
            ),
        )
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        means = root.find("cac:PaymentMeans", NS)
        assert means is not None
        assert means.find("cbc:PaymentMeansCode", NS).text == "30"
        assert (
            means.find("cac:PayeeFinancialAccount/cbc:ID", NS).text
            == "FR7630006000011234567890189"
        )
        assert (
            means.find(
                "cac:PayeeFinancialAccount/"
                "cac:FinancialInstitutionBranch/cbc:ID",
                NS,
            ).text
            == "BNPAFRPP"
        )

    def test_payment_reference(self, sample_invoice: Invoice) -> None:
        """Vérifie la référence de paiement (PaymentID)."""
        sample_invoice.payment_means = PaymentMeans(
            code=PaymentMeansCode.CREDIT_TRANSFER,
            payment_reference="PAY-2026-042",
        )
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        pay_id = root.find("cac:PaymentMeans/cbc:PaymentID", NS)
        assert pay_id is not None
        assert pay_id.text == "PAY-2026-042"

    def test_payment_terms(self, sample_invoice: Invoice) -> None:
        """Vérifie les conditions de paiement."""
        sample_invoice.payment_terms = PaymentTerms(
            description="30 jours fin de mois",
        )
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        terms = root.find("cac:PaymentTerms", NS)
        assert terms is not None
        assert terms.find("cbc:Note", NS).text == "30 jours fin de mois"

    def test_no_payment_means(self, sample_invoice: Invoice) -> None:
        """Vérifie qu'aucun PaymentMeans n'est émis sans payment_means."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.find("cac:PaymentMeans", NS) is None

    def test_no_payment_terms(self) -> None:
        """Vérifie qu'aucun PaymentTerms n'est émis sans payment_terms."""
        invoice = Invoice(
            number="FA-NOTERMS-001",
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

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        assert root.find("cac:PaymentTerms", NS) is None

    def test_note(self, sample_invoice: Invoice) -> None:
        """Vérifie la note libre sur le document."""
        sample_invoice.note = "Facture de test"
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        notes = root.findall("cbc:Note", NS)
        note_texts = [n.text for n in notes]
        assert "Facture de test" in note_texts

    def test_operation_category_note(self, sample_invoice: Invoice) -> None:
        """Vérifie la note catégorie d'opération avec préfixe #AAI#."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        notes = root.findall("cbc:Note", NS)
        aai_notes = [n.text for n in notes if n.text and n.text.startswith("#AAI#")]
        assert len(aai_notes) == 1
        assert aai_notes[0] == "#AAI#Livraison de biens"

    def test_order_reference(self, sample_invoice: Invoice) -> None:
        """Vérifie la référence de commande."""
        sample_invoice.purchase_order_reference = "PO-2026-001"
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        order_ref = root.find("cac:OrderReference/cbc:ID", NS)
        assert order_ref is not None
        assert order_ref.text == "PO-2026-001"

        # BuyerReference aussi présent
        buyer_ref = root.find("cbc:BuyerReference", NS)
        assert buyer_ref is not None
        assert buyer_ref.text == "PO-2026-001"

    def test_billing_reference(self, sample_invoice: Invoice) -> None:
        """Vérifie la référence de facture précédente."""
        sample_invoice.preceding_invoice_reference = "FA-2026-040"
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        billing_ref = root.find(
            "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID",
            NS,
        )
        assert billing_ref is not None
        assert billing_ref.text == "FA-2026-040"

    def test_contract_reference(self, sample_invoice: Invoice) -> None:
        """Vérifie la référence de contrat."""
        sample_invoice.contract_reference = "CTR-2025-042"
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        contract_ref = root.find(
            "cac:ContractDocumentReference/cbc:ID", NS
        )
        assert contract_ref is not None
        assert contract_ref.text == "CTR-2025-042"

    def test_accounting_cost(self, sample_invoice: Invoice) -> None:
        """Vérifie la référence comptable acheteur."""
        sample_invoice.buyer_accounting_reference = "411000"
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        acct = root.find("cbc:AccountingCost", NS)
        assert acct is not None
        assert acct.text == "411000"

    def test_delivery_address(self) -> None:
        """Vérifie l'adresse de livraison dans Delivery."""
        invoice = Invoice(
            number="FA-LIVR-001",
            issue_date=date(2026, 9, 15),
            seller=Party(
                name="Vendeur",
                address=Address(
                    street="1 rue", city="Paris", postal_code="75001"
                ),
            ),
            buyer=Party(
                name="Acheteur",
                address=Address(
                    street="2 rue", city="Lyon", postal_code="69001"
                ),
                delivery_address=Address(
                    street="3 rue Entrepôt",
                    city="Marseille",
                    postal_code="13001",
                ),
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

        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        addr = root.find(
            "cac:Delivery/cac:DeliveryLocation/cac:PostalAddress", NS
        )
        assert addr is not None
        assert addr.find("cbc:StreetName", NS).text == "3 rue Entrepôt"
        assert addr.find("cbc:CityName", NS).text == "Marseille"
        assert addr.find("cbc:PostalZone", NS).text == "13001"

    def test_no_delivery_without_address(self, sample_invoice: Invoice) -> None:
        """Vérifie qu'aucun Delivery n'est émis sans adresse de livraison."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.find("cac:Delivery", NS) is None


class TestCreditNote:
    """Tests de la gestion des avoirs (CreditNote)."""

    @pytest.fixture
    def credit_note_invoice(self) -> Invoice:
        """Avoir de test."""
        return Invoice(
            number="AV-2026-001",
            issue_date=date(2026, 9, 20),
            type_code=InvoiceTypeCode.CREDIT_NOTE,
            seller=Party(
                name="OptiPaulo SARL",
                siren="123456789",
                address=Address(
                    street="12 rue des Opticiens",
                    city="Créteil",
                    postal_code="94000",
                ),
            ),
            buyer=Party(
                name="LunettesPlus SA",
                siren="987654321",
                address=Address(
                    street="5 avenue de la Vision",
                    city="Paris",
                    postal_code="75011",
                ),
            ),
            lines=[
                InvoiceLine(
                    description="Retour monture",
                    quantity=Decimal("1"),
                    unit_price=Decimal("85.00"),
                ),
            ],
            operation_category=OperationCategory.DELIVERY,
            preceding_invoice_reference="FA-2026-042",
        )

    def test_credit_note_root(self, credit_note_invoice: Invoice) -> None:
        """Vérifie que l'élément racine est CreditNote."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(credit_note_invoice)
        root = _parse(xml_bytes)

        assert root.tag == f"{{{CN_NS}}}CreditNote"

    def test_credit_note_namespace(self, credit_note_invoice: Invoice) -> None:
        """Vérifie le namespace CreditNote."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(credit_note_invoice)
        root = _parse(xml_bytes)

        assert root.nsmap[None] == CN_NS

    def test_credit_note_type_code(self, credit_note_invoice: Invoice) -> None:
        """Vérifie CreditNoteTypeCode au lieu de InvoiceTypeCode."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(credit_note_invoice)
        root = _parse(xml_bytes)

        assert root.find("cbc:CreditNoteTypeCode", NS).text == "381"
        assert root.find("cbc:InvoiceTypeCode", NS) is None

    def test_credit_note_line(self, credit_note_invoice: Invoice) -> None:
        """Vérifie CreditNoteLine au lieu de InvoiceLine."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(credit_note_invoice)
        root = _parse(xml_bytes)

        assert root.find("cac:InvoiceLine", NS) is None
        cn_line = root.find("cac:CreditNoteLine", NS)
        assert cn_line is not None
        assert cn_line.find("cbc:ID", NS).text == "1"

    def test_credited_quantity(self, credit_note_invoice: Invoice) -> None:
        """Vérifie CreditedQuantity au lieu de InvoicedQuantity."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(credit_note_invoice)
        root = _parse(xml_bytes)

        cn_line = root.find("cac:CreditNoteLine", NS)
        assert cn_line.find("cbc:InvoicedQuantity", NS) is None
        qty = cn_line.find("cbc:CreditedQuantity", NS)
        assert qty is not None
        assert qty.text == "1"
        assert qty.get("unitCode") == "C62"


class TestGenerationResult:
    """Tests du GenerationResult retourné par generate()."""

    def test_generate_returns_result(self, sample_invoice: Invoice) -> None:
        """Vérifie que generate() retourne un GenerationResult correct."""
        gen = UBLGenerator(profile="EN16931")
        result = gen.generate(sample_invoice)

        assert result.xml_bytes is not None
        assert len(result.xml_bytes) > 0
        assert result.profile == "EN16931"
        assert result.pdf_bytes is None


class TestVATOnDebits:
    """Tests de la mention TVA sur les débits."""

    def test_vat_on_debits_note(self, sample_invoice: Invoice) -> None:
        """Vérifie la note TVA sur les débits."""
        sample_invoice.vat_on_debits = True
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        notes = root.findall("cbc:Note", NS)
        note_texts = [n.text for n in notes]
        assert "TVA sur les débits" in note_texts

    def test_no_vat_on_debits_note(self, sample_invoice: Invoice) -> None:
        """Vérifie l'absence de note TVA sur les débits par défaut."""
        gen = UBLGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        notes = root.findall("cbc:Note", NS)
        note_texts = [n.text for n in notes]
        assert "TVA sur les débits" not in note_texts
