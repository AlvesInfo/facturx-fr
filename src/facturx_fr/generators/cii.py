"""Générateur CII pur (XML, standard UN/CEFACT).

FR: Produit un XML conforme au standard UN/CEFACT CII D16B,
    utilisé par le format Factur-X. Construit l'arbre XML avec lxml
    en respectant l'ordre imposé par le XSD (xs:sequence).
EN: Produces an XML conforming to the UN/CEFACT CII D16B standard,
    used by the Factur-X format.
"""

from decimal import Decimal

from lxml import etree

from facturx_fr.generators.base import BaseGenerator, GenerationResult
from facturx_fr.models.enums import OperationCategory
from facturx_fr.models.invoice import Invoice, InvoiceLine, TaxSummary
from facturx_fr.models.party import Address
from facturx_fr.models.payment import PaymentMeans

# --- Namespaces CII D16B ---
RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
QDT = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

NSMAP = {
    "rsm": RSM,
    "ram": RAM,
    "qdt": QDT,
    "udt": UDT,
}

# --- URN des profils Factur-X ---
PROFILE_URNS = {
    "MINIMUM": "urn:factur-x.eu:1p0:minimum",
    "BASICWL": "urn:factur-x.eu:1p0:basicwl",
    "BASIC": "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic",
    "EN16931": "urn:cen.eu:en16931:2017",
    "EXTENDED": "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended",
}

# --- Descriptions des catégories d'opération (mention obligatoire sept. 2026) ---
_OPERATION_LABELS = {
    OperationCategory.DELIVERY: "Livraison de biens",
    OperationCategory.SERVICE: "Prestation de services",
    OperationCategory.MIXED: "Livraison de biens et prestation de services",
}


def _rsm(tag: str) -> str:
    """Construit un nom qualifié dans le namespace RSM."""
    return f"{{{RSM}}}{tag}"


def _ram(tag: str) -> str:
    """Construit un nom qualifié dans le namespace RAM."""
    return f"{{{RAM}}}{tag}"


def _udt(tag: str) -> str:
    """Construit un nom qualifié dans le namespace UDT."""
    return f"{{{UDT}}}{tag}"


def _fmt_amount(amount: Decimal) -> str:
    """Formate un montant avec 2 décimales."""
    return f"{amount:.2f}"


def _fmt_date(d: object) -> str:
    """Formate une date au format CII 102 (YYYYMMDD)."""
    return d.strftime("%Y%m%d")  # type: ignore[union-attr]


class CIIGenerator(BaseGenerator):
    """Générateur de factures au format CII pur.

    FR: Produit un XML conforme au standard UN/CEFACT CII D16B,
        utilisé par le format Factur-X. L'ordre des éléments respecte
        strictement le XSD (xs:sequence).
    EN: Produces an XML conforming to the UN/CEFACT CII D16B standard,
        used by the Factur-X format.
    """

    def generate(self, invoice: Invoice, **kwargs: object) -> GenerationResult:
        """Génère une facture CII (XML uniquement)."""
        xml_bytes = self.generate_xml(invoice)
        return GenerationResult(xml_bytes=xml_bytes, profile=self.profile)

    def generate_xml(self, invoice: Invoice) -> bytes:
        """Génère le XML CII de la facture."""
        root = self._build_root()
        self._build_context(root)
        self._build_document(root, invoice)
        self._build_transaction(root, invoice)
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    # --- Construction de l'arbre XML ---

    def _build_root(self) -> etree._Element:
        """Construit l'élément racine CrossIndustryInvoice."""
        return etree.Element(_rsm("CrossIndustryInvoice"), nsmap=NSMAP)

    def _build_context(self, root: etree._Element) -> None:
        """Construit ExchangedDocumentContext avec le profil Factur-X."""
        profile_urn = PROFILE_URNS.get(self.profile.upper())
        if not profile_urn:
            msg = (
                f"Profil inconnu : {self.profile}. "
                f"Profils disponibles : {', '.join(PROFILE_URNS)}"
            )
            raise ValueError(msg)

        ctx = etree.SubElement(root, _rsm("ExchangedDocumentContext"))
        guideline = etree.SubElement(
            ctx, _ram("GuidelineSpecifiedDocumentContextParameter")
        )
        etree.SubElement(guideline, _ram("ID")).text = profile_urn

    def _build_document(self, root: etree._Element, invoice: Invoice) -> None:
        """Construit ExchangedDocument (ID, TypeCode, date, notes)."""
        doc = etree.SubElement(root, _rsm("ExchangedDocument"))

        # ID (numéro de facture)
        etree.SubElement(doc, _ram("ID")).text = invoice.number

        # TypeCode (380 = facture, 381 = avoir, etc.)
        etree.SubElement(doc, _ram("TypeCode")).text = str(invoice.type_code)

        # IssueDateTime au format 102 (YYYYMMDD)
        issue_dt = etree.SubElement(doc, _ram("IssueDateTime"))
        dt_str = etree.SubElement(issue_dt, _udt("DateTimeString"))
        dt_str.set("format", "102")
        dt_str.text = _fmt_date(invoice.issue_date)

        # Note libre
        if invoice.note:
            note_el = etree.SubElement(doc, _ram("IncludedNote"))
            etree.SubElement(note_el, _ram("Content")).text = invoice.note

        # Catégorie d'opération (mention obligatoire sept. 2026)
        # Pas de champ CII natif → IncludedNote avec SubjectCode AAI
        op_note = etree.SubElement(doc, _ram("IncludedNote"))
        etree.SubElement(op_note, _ram("Content")).text = _OPERATION_LABELS[
            invoice.operation_category
        ]
        etree.SubElement(op_note, _ram("SubjectCode")).text = "AAI"

    def _build_transaction(self, root: etree._Element, invoice: Invoice) -> None:
        """Construit SupplyChainTradeTransaction.

        Ordre XSD : lignes d'abord, puis agreement, delivery, settlement.
        """
        transaction = etree.SubElement(root, _rsm("SupplyChainTradeTransaction"))

        # 1. IncludedSupplyChainTradeLineItem (1..n)
        for idx, line in enumerate(invoice.lines, start=1):
            self._build_line_item(transaction, line, idx)

        # 2. ApplicableHeaderTradeAgreement
        self._build_trade_agreement(transaction, invoice)

        # 3. ApplicableHeaderTradeDelivery
        self._build_trade_delivery(transaction, invoice)

        # 4. ApplicableHeaderTradeSettlement
        self._build_trade_settlement(transaction, invoice)

    # --- Lignes de facture ---

    def _build_line_item(
        self, parent: etree._Element, line: InvoiceLine, idx: int
    ) -> None:
        """Construit IncludedSupplyChainTradeLineItem."""
        item = etree.SubElement(parent, _ram("IncludedSupplyChainTradeLineItem"))

        # AssociatedDocumentLineDocument
        line_doc = etree.SubElement(item, _ram("AssociatedDocumentLineDocument"))
        line_id = str(line.line_number) if line.line_number is not None else str(idx)
        etree.SubElement(line_doc, _ram("LineID")).text = line_id

        # SpecifiedTradeProduct
        product = etree.SubElement(item, _ram("SpecifiedTradeProduct"))
        if line.item_reference:
            etree.SubElement(product, _ram("SellerAssignedID")).text = line.item_reference
        if line.buyer_reference:
            etree.SubElement(product, _ram("BuyerAssignedID")).text = line.buyer_reference
        etree.SubElement(product, _ram("Name")).text = line.description

        # SpecifiedLineTradeAgreement
        agreement = etree.SubElement(item, _ram("SpecifiedLineTradeAgreement"))
        net_price = etree.SubElement(agreement, _ram("NetPriceProductTradePrice"))
        etree.SubElement(net_price, _ram("ChargeAmount")).text = _fmt_amount(
            line.unit_price
        )

        # SpecifiedLineTradeDelivery
        delivery = etree.SubElement(item, _ram("SpecifiedLineTradeDelivery"))
        billed_qty = etree.SubElement(delivery, _ram("BilledQuantity"))
        billed_qty.set("unitCode", str(line.unit))
        billed_qty.text = str(line.quantity)

        # SpecifiedLineTradeSettlement
        settlement = etree.SubElement(item, _ram("SpecifiedLineTradeSettlement"))

        tax = etree.SubElement(settlement, _ram("ApplicableTradeTax"))
        etree.SubElement(tax, _ram("TypeCode")).text = "VAT"
        etree.SubElement(tax, _ram("CategoryCode")).text = str(line.vat_category)
        etree.SubElement(tax, _ram("RateApplicablePercent")).text = _fmt_amount(
            line.vat_rate
        )

        summation = etree.SubElement(
            settlement, _ram("SpecifiedTradeSettlementLineMonetarySummation")
        )
        etree.SubElement(summation, _ram("LineTotalAmount")).text = _fmt_amount(
            line.line_total_excl_tax
        )

    # --- Header : Agreement (vendeur, acheteur, références) ---

    def _build_trade_agreement(
        self, parent: etree._Element, invoice: Invoice
    ) -> None:
        """Construit ApplicableHeaderTradeAgreement."""
        agreement = etree.SubElement(parent, _ram("ApplicableHeaderTradeAgreement"))

        # SellerTradeParty
        self._build_trade_party(agreement, "SellerTradeParty", invoice.seller)

        # BuyerTradeParty
        self._build_trade_party(agreement, "BuyerTradeParty", invoice.buyer)

        # BuyerOrderReferencedDocument
        if invoice.purchase_order_reference:
            order_ref = etree.SubElement(
                agreement, _ram("BuyerOrderReferencedDocument")
            )
            etree.SubElement(
                order_ref, _ram("IssuerAssignedID")
            ).text = invoice.purchase_order_reference

        # ContractReferencedDocument
        if invoice.contract_reference:
            contract_ref = etree.SubElement(
                agreement, _ram("ContractReferencedDocument")
            )
            etree.SubElement(
                contract_ref, _ram("IssuerAssignedID")
            ).text = invoice.contract_reference

    def _build_trade_party(
        self, parent: etree._Element, tag: str, party: Party
    ) -> None:
        """Construit un élément SellerTradeParty ou BuyerTradeParty."""
        party_el = etree.SubElement(parent, _ram(tag))

        # Name
        etree.SubElement(party_el, _ram("Name")).text = party.name

        # SpecifiedLegalOrganization (SIREN, schemeID 0002)
        if party.siren:
            legal_org = etree.SubElement(
                party_el, _ram("SpecifiedLegalOrganization")
            )
            siren_id = etree.SubElement(legal_org, _ram("ID"))
            siren_id.set("schemeID", "0002")
            siren_id.text = party.siren

        # PostalTradeAddress
        self._build_address(party_el, party.address)

        # SpecifiedTaxRegistration (TVA, schemeID VA)
        if party.vat_number:
            tax_reg = etree.SubElement(party_el, _ram("SpecifiedTaxRegistration"))
            vat_id = etree.SubElement(tax_reg, _ram("ID"))
            vat_id.set("schemeID", "VA")
            vat_id.text = party.vat_number

    def _build_address(self, parent: etree._Element, address: Address) -> None:
        """Construit PostalTradeAddress (ordre XSD respecté)."""
        addr = etree.SubElement(parent, _ram("PostalTradeAddress"))
        etree.SubElement(addr, _ram("PostcodeCode")).text = address.postal_code
        etree.SubElement(addr, _ram("LineOne")).text = address.street
        if address.additional_street:
            etree.SubElement(addr, _ram("LineTwo")).text = address.additional_street
        etree.SubElement(addr, _ram("CityName")).text = address.city
        etree.SubElement(addr, _ram("CountryID")).text = address.country_code
        if address.country_subdivision:
            etree.SubElement(
                addr, _ram("CountrySubDivisionName")
            ).text = address.country_subdivision

    # --- Header : Delivery ---

    def _build_trade_delivery(
        self, parent: etree._Element, invoice: Invoice
    ) -> None:
        """Construit ApplicableHeaderTradeDelivery."""
        delivery = etree.SubElement(parent, _ram("ApplicableHeaderTradeDelivery"))

        # ShipToTradeParty (adresse de livraison si différente)
        if invoice.buyer.delivery_address:
            ship_to = etree.SubElement(delivery, _ram("ShipToTradeParty"))
            self._build_address(ship_to, invoice.buyer.delivery_address)

    # --- Header : Settlement (paiement, taxes, totaux) ---

    def _build_trade_settlement(
        self, parent: etree._Element, invoice: Invoice
    ) -> None:
        """Construit ApplicableHeaderTradeSettlement (ordre XSD respecté)."""
        settlement = etree.SubElement(parent, _ram("ApplicableHeaderTradeSettlement"))

        # PaymentReference (BT-83)
        if invoice.payment_means and invoice.payment_means.payment_reference:
            etree.SubElement(
                settlement, _ram("PaymentReference")
            ).text = invoice.payment_means.payment_reference

        # InvoiceCurrencyCode
        etree.SubElement(
            settlement, _ram("InvoiceCurrencyCode")
        ).text = invoice.currency

        # SpecifiedTradeSettlementPaymentMeans
        if invoice.payment_means:
            self._build_payment_means(settlement, invoice.payment_means)

        # ApplicableTradeTax (un bloc par taux de TVA)
        for summary in invoice.tax_summaries:
            self._build_tax_summary(settlement, summary, invoice.vat_on_debits)

        # SpecifiedTradePaymentTerms
        if invoice.payment_terms or invoice.due_date:
            self._build_payment_terms(settlement, invoice)

        # SpecifiedTradeSettlementHeaderMonetarySummation
        self._build_monetary_summation(settlement, invoice)

        # InvoiceReferencedDocument (facture précédente, pour avoirs)
        if invoice.preceding_invoice_reference:
            inv_ref = etree.SubElement(settlement, _ram("InvoiceReferencedDocument"))
            etree.SubElement(
                inv_ref, _ram("IssuerAssignedID")
            ).text = invoice.preceding_invoice_reference

        # ReceivableSpecifiedTradeAccountingAccount
        if invoice.buyer_accounting_reference:
            acct = etree.SubElement(
                settlement, _ram("ReceivableSpecifiedTradeAccountingAccount")
            )
            etree.SubElement(
                acct, _ram("ID")
            ).text = invoice.buyer_accounting_reference

    def _build_payment_means(
        self, parent: etree._Element, pm: PaymentMeans
    ) -> None:
        """Construit SpecifiedTradeSettlementPaymentMeans."""
        means = etree.SubElement(
            parent, _ram("SpecifiedTradeSettlementPaymentMeans")
        )
        etree.SubElement(means, _ram("TypeCode")).text = str(pm.code)

        if pm.bank_account and pm.bank_account.iban:
            account = etree.SubElement(
                means, _ram("PayeePartyCreditorFinancialAccount")
            )
            etree.SubElement(account, _ram("IBANID")).text = pm.bank_account.iban

        if pm.bank_account and pm.bank_account.bic:
            institution = etree.SubElement(
                means, _ram("PayeeSpecifiedCreditorFinancialInstitution")
            )
            etree.SubElement(institution, _ram("BICID")).text = pm.bank_account.bic

    def _build_tax_summary(
        self,
        parent: etree._Element,
        summary: TaxSummary,
        vat_on_debits: bool,
    ) -> None:
        """Construit un bloc ApplicableTradeTax du settlement."""
        tax = etree.SubElement(parent, _ram("ApplicableTradeTax"))
        etree.SubElement(tax, _ram("CalculatedAmount")).text = _fmt_amount(
            summary.tax_amount
        )
        etree.SubElement(tax, _ram("TypeCode")).text = "VAT"
        etree.SubElement(tax, _ram("BasisAmount")).text = _fmt_amount(
            summary.taxable_amount
        )
        etree.SubElement(tax, _ram("CategoryCode")).text = str(summary.vat_category)
        if vat_on_debits:
            etree.SubElement(tax, _ram("DueDateTypeCode")).text = "5"
        etree.SubElement(tax, _ram("RateApplicablePercent")).text = _fmt_amount(
            summary.vat_rate
        )

    def _build_payment_terms(
        self, parent: etree._Element, invoice: Invoice
    ) -> None:
        """Construit SpecifiedTradePaymentTerms."""
        terms = etree.SubElement(parent, _ram("SpecifiedTradePaymentTerms"))
        if invoice.payment_terms and invoice.payment_terms.description:
            etree.SubElement(
                terms, _ram("Description")
            ).text = invoice.payment_terms.description
        if invoice.due_date:
            due_dt = etree.SubElement(terms, _ram("DueDateDateTime"))
            dt_str = etree.SubElement(due_dt, _udt("DateTimeString"))
            dt_str.set("format", "102")
            dt_str.text = _fmt_date(invoice.due_date)

    def _build_monetary_summation(
        self, parent: etree._Element, invoice: Invoice
    ) -> None:
        """Construit SpecifiedTradeSettlementHeaderMonetarySummation."""
        summation = etree.SubElement(
            parent, _ram("SpecifiedTradeSettlementHeaderMonetarySummation")
        )
        etree.SubElement(summation, _ram("LineTotalAmount")).text = _fmt_amount(
            invoice.total_excl_tax
        )
        etree.SubElement(summation, _ram("TaxBasisTotalAmount")).text = _fmt_amount(
            invoice.total_excl_tax
        )
        tax_total = etree.SubElement(summation, _ram("TaxTotalAmount"))
        tax_total.set("currencyID", invoice.currency)
        tax_total.text = _fmt_amount(invoice.total_vat)
        etree.SubElement(summation, _ram("GrandTotalAmount")).text = _fmt_amount(
            invoice.total_incl_tax
        )
        etree.SubElement(summation, _ram("DuePayableAmount")).text = _fmt_amount(
            invoice.total_incl_tax
        )
