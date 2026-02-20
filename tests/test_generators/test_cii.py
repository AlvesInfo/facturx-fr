"""Tests unitaires du générateur CII.

FR: Vérifie la structure XML CII générée, les namespaces, profils,
    parties, lignes, taxes, totaux et la validation XSD.
EN: Verifies the generated CII XML structure, namespaces, profiles,
    parties, lines, taxes, totals and XSD validation.
"""

from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from facturx_fr.generators.cii import CIIGenerator, PROFILE_URNS
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
    OperationCategory,
    PaymentMeansCode,
    UnitOfMeasure,
    VATCategory,
)

# Namespaces pour les requêtes XPath
RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
NS = {"rsm": RSM, "ram": RAM, "udt": UDT}


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

    def test_basic_invoice_xml(self, sample_invoice: Invoice) -> None:
        """Vérifie que le XML contient les 3 sections principales."""
        gen = CIIGenerator(profile="EN16931")
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.tag == f"{{{RSM}}}CrossIndustryInvoice"
        assert root.find("rsm:ExchangedDocumentContext", NS) is not None
        assert root.find("rsm:ExchangedDocument", NS) is not None
        assert root.find("rsm:SupplyChainTradeTransaction", NS) is not None

    def test_xml_namespaces(self, sample_invoice: Invoice) -> None:
        """Vérifie que les namespaces CII sont correctement déclarés."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        assert root.nsmap["rsm"] == RSM
        assert root.nsmap["ram"] == RAM
        assert root.nsmap["udt"] == UDT

    def test_profile_urn(self, sample_invoice: Invoice) -> None:
        """Vérifie l'URN du profil dans ExchangedDocumentContext."""
        for profile, expected_urn in PROFILE_URNS.items():
            gen = CIIGenerator(profile=profile)
            xml_bytes = gen.generate_xml(sample_invoice)
            root = _parse(xml_bytes)

            urn = root.find(
                "rsm:ExchangedDocumentContext/"
                "ram:GuidelineSpecifiedDocumentContextParameter/"
                "ram:ID",
                NS,
            )
            assert urn is not None
            assert urn.text == expected_urn

    def test_invalid_profile(self, sample_invoice: Invoice) -> None:
        """Vérifie qu'un profil inconnu lève une erreur."""
        gen = CIIGenerator(profile="INVALID")
        with pytest.raises(ValueError, match="Profil inconnu"):
            gen.generate_xml(sample_invoice)

    def test_document_info(self, sample_invoice: Invoice) -> None:
        """Vérifie les informations du document (ID, type, date)."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        doc = root.find("rsm:ExchangedDocument", NS)
        assert doc is not None

        assert doc.find("ram:ID", NS).text == "FA-2026-042"
        assert doc.find("ram:TypeCode", NS).text == "380"

        dt = doc.find("ram:IssueDateTime/udt:DateTimeString", NS)
        assert dt is not None
        assert dt.text == "20260915"
        assert dt.get("format") == "102"


class TestSellerBuyerParties:
    """Tests des parties vendeur/acheteur."""

    def test_seller_buyer_parties(self, sample_invoice: Invoice) -> None:
        """Vérifie SIREN, TVA, nom et adresse du vendeur et de l'acheteur."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        agreement = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeAgreement",
            NS,
        )
        assert agreement is not None

        # Vendeur
        seller = agreement.find("ram:SellerTradeParty", NS)
        assert seller is not None
        assert seller.find("ram:Name", NS).text == "OptiPaulo SARL"

        siren = seller.find("ram:SpecifiedLegalOrganization/ram:ID", NS)
        assert siren is not None
        assert siren.text == "123456789"
        assert siren.get("schemeID") == "0002"

        vat = seller.find("ram:SpecifiedTaxRegistration/ram:ID", NS)
        assert vat is not None
        assert vat.text == "FR12345678901"
        assert vat.get("schemeID") == "VA"

        addr = seller.find("ram:PostalTradeAddress", NS)
        assert addr is not None
        assert addr.find("ram:LineOne", NS).text == "12 rue des Opticiens"
        assert addr.find("ram:CityName", NS).text == "Créteil"
        assert addr.find("ram:PostcodeCode", NS).text == "94000"
        assert addr.find("ram:CountryID", NS).text == "FR"

        # Acheteur
        buyer = agreement.find("ram:BuyerTradeParty", NS)
        assert buyer is not None
        assert buyer.find("ram:Name", NS).text == "LunettesPlus SA"

        buyer_siren = buyer.find("ram:SpecifiedLegalOrganization/ram:ID", NS)
        assert buyer_siren is not None
        assert buyer_siren.text == "987654321"
        assert buyer_siren.get("schemeID") == "0002"


class TestLineItems:
    """Tests des lignes de facture."""

    def test_line_items(self, sample_invoice: Invoice) -> None:
        """Vérifie quantité, prix, TVA et total d'une ligne."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        lines = root.findall(
            "rsm:SupplyChainTradeTransaction/"
            "ram:IncludedSupplyChainTradeLineItem",
            NS,
        )
        assert len(lines) == 1

        line = lines[0]
        assert (
            line.find(
                "ram:AssociatedDocumentLineDocument/ram:LineID", NS
            ).text
            == "1"
        )
        assert (
            line.find("ram:SpecifiedTradeProduct/ram:Name", NS).text
            == "Monture Ray-Ban Aviator"
        )

        # Prix unitaire
        price = line.find(
            "ram:SpecifiedLineTradeAgreement/"
            "ram:NetPriceProductTradePrice/"
            "ram:ChargeAmount",
            NS,
        )
        assert price is not None
        assert price.text == "85.00"

        # Quantité
        qty = line.find(
            "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", NS
        )
        assert qty is not None
        assert qty.text == "10"
        assert qty.get("unitCode") == "C62"

        # TVA de la ligne
        tax = line.find(
            "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax", NS
        )
        assert tax is not None
        assert tax.find("ram:TypeCode", NS).text == "VAT"
        assert tax.find("ram:CategoryCode", NS).text == "S"
        assert tax.find("ram:RateApplicablePercent", NS).text == "20.00"

        # Total HT de la ligne
        total = line.find(
            "ram:SpecifiedLineTradeSettlement/"
            "ram:SpecifiedTradeSettlementLineMonetarySummation/"
            "ram:LineTotalAmount",
            NS,
        )
        assert total is not None
        assert total.text == "850.00"

    def test_explicit_line_number(self) -> None:
        """Vérifie que line_number explicite est utilisé comme LineID."""
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

        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        line_id = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:IncludedSupplyChainTradeLineItem/"
            "ram:AssociatedDocumentLineDocument/"
            "ram:LineID",
            NS,
        )
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

        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        qty = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:IncludedSupplyChainTradeLineItem/"
            "ram:SpecifiedLineTradeDelivery/"
            "ram:BilledQuantity",
            NS,
        )
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

        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        lines = root.findall(
            "rsm:SupplyChainTradeTransaction/"
            "ram:IncludedSupplyChainTradeLineItem",
            NS,
        )
        assert len(lines) == 2
        assert (
            lines[0].find(
                "ram:AssociatedDocumentLineDocument/ram:LineID", NS
            ).text
            == "1"
        )
        assert (
            lines[1].find(
                "ram:AssociatedDocumentLineDocument/ram:LineID", NS
            ).text
            == "2"
        )

        # 2 blocs ApplicableTradeTax (5.5% et 20%) triés par taux
        taxes = root.findall(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:ApplicableTradeTax",
            NS,
        )
        assert len(taxes) == 2
        rates = [
            t.find("ram:RateApplicablePercent", NS).text for t in taxes
        ]
        assert rates == ["5.50", "20.00"]

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

        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        product = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:IncludedSupplyChainTradeLineItem/"
            "ram:SpecifiedTradeProduct",
            NS,
        )
        assert product is not None
        assert (
            product.find("ram:SellerAssignedID", NS).text == "REF-VEND-001"
        )
        assert (
            product.find("ram:BuyerAssignedID", NS).text == "REF-ACH-001"
        )


class TestTaxSummaries:
    """Tests des récapitulatifs TVA."""

    def test_tax_summaries(self, sample_invoice: Invoice) -> None:
        """Vérifie les blocs ApplicableTradeTax du settlement."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        taxes = root.findall(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:ApplicableTradeTax",
            NS,
        )
        assert len(taxes) == 1

        tax = taxes[0]
        assert tax.find("ram:CalculatedAmount", NS).text == "170.00"
        assert tax.find("ram:TypeCode", NS).text == "VAT"
        assert tax.find("ram:BasisAmount", NS).text == "850.00"
        assert tax.find("ram:CategoryCode", NS).text == "S"
        assert tax.find("ram:RateApplicablePercent", NS).text == "20.00"
        # Pas de DueDateTypeCode par défaut (vat_on_debits=False)
        assert tax.find("ram:DueDateTypeCode", NS) is None

    def test_vat_on_debits(self, sample_invoice: Invoice) -> None:
        """Vérifie DueDateTypeCode=5 quand vat_on_debits est activé."""
        sample_invoice.vat_on_debits = True
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        tax = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:ApplicableTradeTax",
            NS,
        )
        assert tax is not None
        assert tax.find("ram:DueDateTypeCode", NS).text == "5"


class TestMonetarySummation:
    """Tests des totaux monétaires."""

    def test_monetary_summation(self, sample_invoice: Invoice) -> None:
        """Vérifie LineTotalAmount, TaxBasisTotalAmount, TaxTotalAmount,
        GrandTotalAmount et DuePayableAmount."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        summation = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation",
            NS,
        )
        assert summation is not None

        assert summation.find("ram:LineTotalAmount", NS).text == "850.00"
        assert summation.find("ram:TaxBasisTotalAmount", NS).text == "850.00"

        tax_total = summation.find("ram:TaxTotalAmount", NS)
        assert tax_total is not None
        assert tax_total.text == "170.00"
        assert tax_total.get("currencyID") == "EUR"

        assert summation.find("ram:GrandTotalAmount", NS).text == "1020.00"
        assert summation.find("ram:DuePayableAmount", NS).text == "1020.00"


class TestDueDate:
    """Tests de la date d'échéance au niveau facture."""

    def test_due_date_emitted(self, sample_invoice: Invoice) -> None:
        """Vérifie que due_date est émise dans SpecifiedTradePaymentTerms."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        due_dt = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradePaymentTerms/"
            "ram:DueDateDateTime/"
            "udt:DateTimeString",
            NS,
        )
        assert due_dt is not None
        assert due_dt.text == "20261015"
        assert due_dt.get("format") == "102"

    def test_no_due_date_no_terms(self) -> None:
        """Vérifie qu'aucun SpecifiedTradePaymentTerms n'est émis sans due_date ni terms."""
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

        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        terms = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradePaymentTerms",
            NS,
        )
        assert terms is None

    def test_due_date_with_payment_terms(self, sample_invoice: Invoice) -> None:
        """Vérifie la combinaison due_date + payment_terms.description."""
        sample_invoice.payment_terms = PaymentTerms(
            description="30 jours fin de mois",
        )
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        terms = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradePaymentTerms",
            NS,
        )
        assert terms is not None
        assert terms.find("ram:Description", NS).text == "30 jours fin de mois"

        due_dt = terms.find("ram:DueDateDateTime/udt:DateTimeString", NS)
        assert due_dt is not None
        assert due_dt.text == "20261015"


class TestOptionalFields:
    """Tests des champs optionnels (paiement, notes, références)."""

    def test_payment_means(self, sample_invoice: Invoice) -> None:
        """Vérifie les moyens de paiement (type, IBAN, BIC via BankAccount)."""
        sample_invoice.payment_means = PaymentMeans(
            code=PaymentMeansCode.CREDIT_TRANSFER,
            bank_account=BankAccount(
                iban="FR7630006000011234567890189",
                bic="BNPAFRPP",
            ),
        )
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        means = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementPaymentMeans",
            NS,
        )
        assert means is not None
        assert means.find("ram:TypeCode", NS).text == "30"
        assert (
            means.find(
                "ram:PayeePartyCreditorFinancialAccount/ram:IBANID", NS
            ).text
            == "FR7630006000011234567890189"
        )
        assert (
            means.find(
                "ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID",
                NS,
            ).text
            == "BNPAFRPP"
        )

    def test_payment_reference(self, sample_invoice: Invoice) -> None:
        """Vérifie la référence de paiement au niveau settlement."""
        sample_invoice.payment_means = PaymentMeans(
            code=PaymentMeansCode.CREDIT_TRANSFER,
            payment_reference="PAY-2026-042",
        )
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        pay_ref = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:PaymentReference",
            NS,
        )
        assert pay_ref is not None
        assert pay_ref.text == "PAY-2026-042"

    def test_note(self, sample_invoice: Invoice) -> None:
        """Vérifie la note libre sur le document."""
        sample_invoice.note = "Facture de test"
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        notes = root.findall("rsm:ExchangedDocument/ram:IncludedNote", NS)
        contents = [n.find("ram:Content", NS).text for n in notes]
        assert "Facture de test" in contents

    def test_operation_category_note(self, sample_invoice: Invoice) -> None:
        """Vérifie la note catégorie d'opération avec SubjectCode AAI."""
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        notes = root.findall("rsm:ExchangedDocument/ram:IncludedNote", NS)
        op_notes = [
            n
            for n in notes
            if n.find("ram:SubjectCode", NS) is not None
            and n.find("ram:SubjectCode", NS).text == "AAI"
        ]
        assert len(op_notes) == 1
        assert (
            op_notes[0].find("ram:Content", NS).text == "Livraison de biens"
        )

    def test_references(self, sample_invoice: Invoice) -> None:
        """Vérifie les références (commande, contrat, compte comptable)."""
        sample_invoice.purchase_order_reference = "PO-2026-001"
        sample_invoice.contract_reference = "CTR-2025-042"
        sample_invoice.buyer_accounting_reference = "411000"

        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        agreement = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeAgreement",
            NS,
        )
        assert agreement is not None

        po_ref = agreement.find(
            "ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID", NS
        )
        assert po_ref is not None
        assert po_ref.text == "PO-2026-001"

        ctr_ref = agreement.find(
            "ram:ContractReferencedDocument/ram:IssuerAssignedID", NS
        )
        assert ctr_ref is not None
        assert ctr_ref.text == "CTR-2025-042"

        settlement = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement",
            NS,
        )
        acct = settlement.find(
            "ram:ReceivableSpecifiedTradeAccountingAccount/ram:ID", NS
        )
        assert acct is not None
        assert acct.text == "411000"

    def test_preceding_invoice_reference(
        self, sample_invoice: Invoice
    ) -> None:
        """Vérifie la référence de facture précédente (pour avoirs)."""
        sample_invoice.preceding_invoice_reference = "FA-2026-040"
        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(sample_invoice)
        root = _parse(xml_bytes)

        inv_ref = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:InvoiceReferencedDocument/"
            "ram:IssuerAssignedID",
            NS,
        )
        assert inv_ref is not None
        assert inv_ref.text == "FA-2026-040"

    def test_delivery_address(self) -> None:
        """Vérifie l'adresse de livraison dans ShipToTradeParty."""
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

        gen = CIIGenerator()
        xml_bytes = gen.generate_xml(invoice)
        root = _parse(xml_bytes)

        ship_to_addr = root.find(
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeDelivery/"
            "ram:ShipToTradeParty/"
            "ram:PostalTradeAddress",
            NS,
        )
        assert ship_to_addr is not None
        assert (
            ship_to_addr.find("ram:LineOne", NS).text == "3 rue Entrepôt"
        )
        assert (
            ship_to_addr.find("ram:CityName", NS).text == "Marseille"
        )
        assert ship_to_addr.find("ram:PostcodeCode", NS).text == "13001"


class TestGenerationResult:
    """Tests du GenerationResult retourné par generate()."""

    def test_generate_returns_result(self, sample_invoice: Invoice) -> None:
        """Vérifie que generate() retourne un GenerationResult correct."""
        gen = CIIGenerator(profile="EN16931")
        result = gen.generate(sample_invoice)

        assert result.xml_bytes is not None
        assert len(result.xml_bytes) > 0
        assert result.profile == "EN16931"
        assert result.pdf_bytes is None


class TestXSDValidation:
    """Validation XSD du XML généré via la lib factur-x."""

    def test_xsd_validation(self, sample_invoice: Invoice) -> None:
        """Valide le XML généré contre le XSD Factur-X."""
        from facturx import xml_check_xsd

        gen = CIIGenerator(profile="EN16931")
        xml_bytes = gen.generate_xml(sample_invoice)

        # xml_check_xsd lève une exception si le XML est invalide
        xml_check_xsd(xml_bytes)

    def test_xsd_validation_with_all_optional_fields(self) -> None:
        """Valide un XML complet avec tous les champs optionnels."""
        from facturx import xml_check_xsd

        invoice = Invoice(
            number="FA-FULL-001",
            issue_date=date(2026, 9, 15),
            due_date=date(2026, 10, 15),
            seller=Party(
                name="Vendeur Complet SARL",
                siren="123456789",
                vat_number="FR12345678901",
                address=Address(
                    street="10 rue Complète",
                    additional_street="Bâtiment B",
                    city="Paris",
                    postal_code="75001",
                    country_code="FR",
                ),
            ),
            buyer=Party(
                name="Acheteur Complet SA",
                siren="987654321",
                vat_number="FR98765432101",
                address=Address(
                    street="20 avenue Test",
                    city="Lyon",
                    postal_code="69001",
                    country_code="FR",
                ),
            ),
            lines=[
                InvoiceLine(
                    line_number=1,
                    description="Produit A",
                    quantity=Decimal("3"),
                    unit=UnitOfMeasure.UNIT,
                    unit_price=Decimal("150.00"),
                    vat_rate=Decimal("20.0"),
                    item_reference="REF-A",
                ),
                InvoiceLine(
                    line_number=2,
                    description="Service B",
                    quantity=Decimal("1"),
                    unit=UnitOfMeasure.HOUR,
                    unit_price=Decimal("200.00"),
                    vat_rate=Decimal("10.0"),
                    vat_category=VATCategory.STANDARD,
                ),
            ],
            operation_category=OperationCategory.MIXED,
            payment_terms=PaymentTerms(
                description="30 jours fin de mois",
                late_penalty_rate=Decimal("3.0"),
                early_discount="Néant",
                recovery_fee=Decimal("40.00"),
            ),
            payment_means=PaymentMeans(
                code=PaymentMeansCode.CREDIT_TRANSFER,
                bank_account=BankAccount(
                    iban="FR7630006000011234567890189",
                    bic="BNPAFRPP",
                ),
            ),
            note="Facture complète de test",
            purchase_order_reference="PO-001",
            contract_reference="CTR-001",
            buyer_accounting_reference="411000",
        )

        gen = CIIGenerator(profile="EN16931")
        xml_bytes = gen.generate_xml(invoice)

        # Doit passer la validation XSD sans erreur
        xml_check_xsd(xml_bytes)
