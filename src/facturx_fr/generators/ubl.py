"""Générateur UBL 2.1 (XML pur, standard OASIS).

FR: Produit un XML conforme au standard OASIS UBL 2.1,
    compatible PEPPOL BIS Invoice 3.0. Supporte les factures
    (Invoice) et les avoirs (CreditNote).
EN: Produces an XML conforming to the OASIS UBL 2.1 standard,
    compatible with PEPPOL BIS Invoice 3.0.
"""

from decimal import Decimal

from lxml import etree

from facturx_fr.generators.base import BaseGenerator, GenerationResult
from facturx_fr.models.enums import InvoiceTypeCode, OperationCategory
from facturx_fr.models.invoice import Invoice, InvoiceLine, TaxSummary
from facturx_fr.models.party import Address, Party

# --- Namespaces UBL 2.1 ---
INV_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CN_NS = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

# --- URN des profils UBL ---
PROFILE_URNS = {
    "EN16931": {
        "customization_id": "urn:cen.eu:en16931:2017",
    },
    "PEPPOL": {
        "customization_id": (
            "urn:cen.eu:en16931:2017#compliant#"
            "urn:fdc:peppol.eu:2017:poacc:billing:3.0"
        ),
        "profile_id": "urn:fdc:peppol.eu:2017:poacc:billing:3.0",
    },
}

# --- Descriptions des catégories d'opération (mention obligatoire sept. 2026) ---
_OPERATION_LABELS = {
    OperationCategory.DELIVERY: "Livraison de biens",
    OperationCategory.SERVICE: "Prestation de services",
    OperationCategory.MIXED: "Livraison de biens et prestation de services",
}


def _cac(tag: str) -> str:
    """Construit un nom qualifié dans le namespace CAC."""
    return f"{{{CAC}}}{tag}"


def _cbc(tag: str) -> str:
    """Construit un nom qualifié dans le namespace CBC."""
    return f"{{{CBC}}}{tag}"


def _fmt_amount(amount: Decimal) -> str:
    """Formate un montant avec 2 décimales."""
    return f"{amount:.2f}"


def _fmt_date(d: object) -> str:
    """Formate une date au format ISO 8601 (YYYY-MM-DD)."""
    return d.strftime("%Y-%m-%d")  # type: ignore[union-attr]


class UBLGenerator(BaseGenerator):
    """Générateur de factures au format UBL 2.1.

    FR: Produit un XML conforme au standard OASIS UBL 2.1,
        compatible PEPPOL BIS Invoice 3.0. Gère automatiquement
        la distinction Invoice vs CreditNote selon le type_code.
    EN: Produces an XML conforming to the OASIS UBL 2.1 standard,
        compatible with PEPPOL BIS Invoice 3.0.
    """

    def generate(self, invoice: Invoice, **kwargs: object) -> GenerationResult:
        """Génère une facture UBL (XML uniquement)."""
        xml_bytes = self.generate_xml(invoice)
        return GenerationResult(xml_bytes=xml_bytes, profile=self.profile)

    def generate_xml(self, invoice: Invoice) -> bytes:
        """Génère le XML UBL de la facture."""
        self._credit_note = invoice.type_code == InvoiceTypeCode.CREDIT_NOTE
        root = self._build_root()
        self._build_header(root, invoice)
        self._build_invoice_period(root, invoice)
        self._build_order_reference(root, invoice)
        self._build_billing_reference(root, invoice)
        self._build_contract_reference(root, invoice)
        self._build_supplier_party(root, invoice)
        self._build_customer_party(root, invoice)
        self._build_payee_party(root, invoice)
        self._build_delivery(root, invoice)
        self._build_payment_means(root, invoice)
        self._build_payment_terms(root, invoice)
        self._build_tax_total(root, invoice)
        self._build_legal_monetary_total(root, invoice)
        for idx, line in enumerate(invoice.lines, start=1):
            self._build_invoice_line(root, line, idx, invoice.currency)
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=True,
        )

    # --- Construction de l'arbre XML ---

    def _build_root(self) -> etree._Element:
        """Construit l'élément racine Invoice ou CreditNote."""
        if self._credit_note:
            nsmap = {None: CN_NS, "cac": CAC, "cbc": CBC}
            return etree.Element(f"{{{CN_NS}}}CreditNote", nsmap=nsmap)
        nsmap = {None: INV_NS, "cac": CAC, "cbc": CBC}
        return etree.Element(f"{{{INV_NS}}}Invoice", nsmap=nsmap)

    def _build_header(self, root: etree._Element, invoice: Invoice) -> None:
        """Construit les éléments d'en-tête (ID, dates, type, devise, notes)."""
        profile_key = self.profile.upper()
        profile_data = PROFILE_URNS.get(profile_key)
        if not profile_data:
            msg = (
                f"Profil inconnu : {self.profile}. "
                f"Profils disponibles : {', '.join(PROFILE_URNS)}"
            )
            raise ValueError(msg)

        # CustomizationID
        etree.SubElement(
            root, _cbc("CustomizationID")
        ).text = profile_data["customization_id"]

        # ProfileID (PEPPOL seulement)
        if "profile_id" in profile_data:
            etree.SubElement(
                root, _cbc("ProfileID")
            ).text = profile_data["profile_id"]

        # ID (numéro de facture)
        etree.SubElement(root, _cbc("ID")).text = invoice.number

        # IssueDate (ISO 8601)
        etree.SubElement(root, _cbc("IssueDate")).text = _fmt_date(
            invoice.issue_date
        )

        # DueDate (optionnel, niveau racine en UBL)
        if invoice.due_date:
            etree.SubElement(root, _cbc("DueDate")).text = _fmt_date(
                invoice.due_date
            )

        # InvoiceTypeCode ou CreditNoteTypeCode
        type_tag = "CreditNoteTypeCode" if self._credit_note else "InvoiceTypeCode"
        etree.SubElement(root, _cbc(type_tag)).text = str(invoice.type_code)

        # Note libre
        if invoice.note:
            etree.SubElement(root, _cbc("Note")).text = invoice.note

        # Catégorie d'opération (convention PEPPOL : #AAI#label)
        op_label = _OPERATION_LABELS[invoice.operation_category]
        etree.SubElement(root, _cbc("Note")).text = f"#AAI#{op_label}"

        # TVA sur les débits
        if invoice.vat_on_debits:
            etree.SubElement(root, _cbc("Note")).text = "TVA sur les débits"

        # DocumentCurrencyCode
        etree.SubElement(root, _cbc("DocumentCurrencyCode")).text = invoice.currency

        # AccountingCost (référence comptable acheteur, optionnel)
        if invoice.buyer_accounting_reference:
            etree.SubElement(
                root, _cbc("AccountingCost")
            ).text = invoice.buyer_accounting_reference

        # BuyerReference (référence commande acheteur, optionnel)
        if invoice.purchase_order_reference:
            etree.SubElement(
                root, _cbc("BuyerReference")
            ).text = invoice.purchase_order_reference

    def _build_invoice_period(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit InvoicePeriod au niveau facture (BG-14)."""
        if not invoice.billing_period_start and not invoice.billing_period_end:
            return
        period = etree.SubElement(root, _cac("InvoicePeriod"))
        if invoice.billing_period_start:
            etree.SubElement(
                period, _cbc("StartDate")
            ).text = _fmt_date(invoice.billing_period_start)
        if invoice.billing_period_end:
            etree.SubElement(
                period, _cbc("EndDate")
            ).text = _fmt_date(invoice.billing_period_end)

    def _build_order_reference(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit OrderReference (si purchase_order_reference)."""
        if not invoice.purchase_order_reference:
            return
        order_ref = etree.SubElement(root, _cac("OrderReference"))
        etree.SubElement(
            order_ref, _cbc("ID")
        ).text = invoice.purchase_order_reference

    def _build_billing_reference(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit BillingReference (si preceding_invoice_reference)."""
        if not invoice.preceding_invoice_reference:
            return
        billing_ref = etree.SubElement(root, _cac("BillingReference"))
        inv_doc_ref = etree.SubElement(billing_ref, _cac("InvoiceDocumentReference"))
        etree.SubElement(
            inv_doc_ref, _cbc("ID")
        ).text = invoice.preceding_invoice_reference

    def _build_contract_reference(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit ContractDocumentReference (si contract_reference)."""
        if not invoice.contract_reference:
            return
        contract_ref = etree.SubElement(root, _cac("ContractDocumentReference"))
        etree.SubElement(
            contract_ref, _cbc("ID")
        ).text = invoice.contract_reference

    # --- Parties ---

    def _build_supplier_party(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit AccountingSupplierParty (vendeur)."""
        supplier = etree.SubElement(root, _cac("AccountingSupplierParty"))
        self._build_party(supplier, invoice.seller)

    def _build_customer_party(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit AccountingCustomerParty (acheteur)."""
        customer = etree.SubElement(root, _cac("AccountingCustomerParty"))
        self._build_party(customer, invoice.buyer)

    def _build_payee_party(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit PayeeParty (bénéficiaire si différent du vendeur)."""
        if not invoice.payee:
            return
        payee_el = etree.SubElement(root, _cac("PayeeParty"))
        self._build_party_contents(payee_el, invoice.payee)

    def _build_party(self, parent: etree._Element, party: Party) -> None:
        """Construit un élément Party avec nom, adresse, TVA et SIREN."""
        party_el = etree.SubElement(parent, _cac("Party"))
        self._build_party_contents(party_el, party)

    def _build_party_contents(
        self, party_el: etree._Element, party: Party
    ) -> None:
        """Remplit le contenu d'un élément Party."""

        # PartyName
        party_name = etree.SubElement(party_el, _cac("PartyName"))
        etree.SubElement(party_name, _cbc("Name")).text = party.name

        # PostalAddress
        self._build_postal_address(party_el, party.address)

        # PartyTaxScheme (TVA)
        if party.vat_number:
            tax_scheme_wrapper = etree.SubElement(party_el, _cac("PartyTaxScheme"))
            etree.SubElement(
                tax_scheme_wrapper, _cbc("CompanyID")
            ).text = party.vat_number
            tax_scheme = etree.SubElement(tax_scheme_wrapper, _cac("TaxScheme"))
            etree.SubElement(tax_scheme, _cbc("ID")).text = "VAT"

        # PartyLegalEntity (SIREN)
        legal_entity = etree.SubElement(party_el, _cac("PartyLegalEntity"))
        etree.SubElement(
            legal_entity, _cbc("RegistrationName")
        ).text = party.name
        if party.siren:
            company_id = etree.SubElement(legal_entity, _cbc("CompanyID"))
            company_id.set("schemeID", "0002")
            company_id.text = party.siren

    def _build_postal_address(
        self, parent: etree._Element, address: Address
    ) -> None:
        """Construit PostalAddress."""
        addr = etree.SubElement(parent, _cac("PostalAddress"))
        etree.SubElement(addr, _cbc("StreetName")).text = address.street
        if address.additional_street:
            etree.SubElement(
                addr, _cbc("AdditionalStreetName")
            ).text = address.additional_street
        etree.SubElement(addr, _cbc("CityName")).text = address.city
        etree.SubElement(addr, _cbc("PostalZone")).text = address.postal_code
        if address.country_subdivision:
            etree.SubElement(
                addr, _cbc("CountrySubentity")
            ).text = address.country_subdivision
        country = etree.SubElement(addr, _cac("Country"))
        etree.SubElement(
            country, _cbc("IdentificationCode")
        ).text = address.country_code

    # --- Livraison ---

    def _build_delivery(self, root: etree._Element, invoice: Invoice) -> None:
        """Construit Delivery avec adresse de livraison (si différente)."""
        if not invoice.buyer.delivery_address:
            return
        delivery = etree.SubElement(root, _cac("Delivery"))
        location = etree.SubElement(delivery, _cac("DeliveryLocation"))
        self._build_postal_address(location, invoice.buyer.delivery_address)

    # --- Paiement ---

    def _build_payment_means(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit PaymentMeans (moyen de paiement)."""
        if not invoice.payment_means:
            return
        pm = invoice.payment_means
        means = etree.SubElement(root, _cac("PaymentMeans"))
        etree.SubElement(means, _cbc("PaymentMeansCode")).text = str(pm.code)

        if pm.payment_reference:
            etree.SubElement(means, _cbc("PaymentID")).text = pm.payment_reference

        if pm.bank_account and pm.bank_account.iban:
            account = etree.SubElement(means, _cac("PayeeFinancialAccount"))
            etree.SubElement(account, _cbc("ID")).text = pm.bank_account.iban
            if pm.bank_account.bic:
                branch = etree.SubElement(
                    account, _cac("FinancialInstitutionBranch")
                )
                etree.SubElement(branch, _cbc("ID")).text = pm.bank_account.bic

    def _build_payment_terms(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit PaymentTerms (conditions de paiement)."""
        if not invoice.payment_terms:
            return
        terms = etree.SubElement(root, _cac("PaymentTerms"))
        if invoice.payment_terms.description:
            etree.SubElement(
                terms, _cbc("Note")
            ).text = invoice.payment_terms.description

    # --- TVA ---

    def _build_tax_total(self, root: etree._Element, invoice: Invoice) -> None:
        """Construit TaxTotal avec TaxSubtotal par taux de TVA."""
        tax_total = etree.SubElement(root, _cac("TaxTotal"))
        tax_amount = etree.SubElement(tax_total, _cbc("TaxAmount"))
        tax_amount.set("currencyID", invoice.currency)
        tax_amount.text = _fmt_amount(invoice.total_vat)

        for summary in invoice.tax_summaries:
            self._build_tax_subtotal(tax_total, summary, invoice.currency)

    def _build_tax_subtotal(
        self,
        parent: etree._Element,
        summary: TaxSummary,
        currency: str,
    ) -> None:
        """Construit un bloc TaxSubtotal."""
        subtotal = etree.SubElement(parent, _cac("TaxSubtotal"))

        taxable = etree.SubElement(subtotal, _cbc("TaxableAmount"))
        taxable.set("currencyID", currency)
        taxable.text = _fmt_amount(summary.taxable_amount)

        tax_amount = etree.SubElement(subtotal, _cbc("TaxAmount"))
        tax_amount.set("currencyID", currency)
        tax_amount.text = _fmt_amount(summary.tax_amount)

        tax_cat = etree.SubElement(subtotal, _cac("TaxCategory"))
        etree.SubElement(tax_cat, _cbc("ID")).text = str(summary.vat_category)
        etree.SubElement(tax_cat, _cbc("Percent")).text = _fmt_amount(
            summary.vat_rate
        )
        if summary.vat_exemption_reason_code:
            etree.SubElement(
                tax_cat, _cbc("TaxExemptionReasonCode")
            ).text = summary.vat_exemption_reason_code
        if summary.vat_exemption_reason:
            etree.SubElement(
                tax_cat, _cbc("TaxExemptionReason")
            ).text = summary.vat_exemption_reason
        tax_scheme = etree.SubElement(tax_cat, _cac("TaxScheme"))
        etree.SubElement(tax_scheme, _cbc("ID")).text = "VAT"

    # --- Totaux monétaires ---

    def _build_legal_monetary_total(
        self, root: etree._Element, invoice: Invoice
    ) -> None:
        """Construit LegalMonetaryTotal."""
        monetary = etree.SubElement(root, _cac("LegalMonetaryTotal"))
        currency = invoice.currency

        line_ext = etree.SubElement(monetary, _cbc("LineExtensionAmount"))
        line_ext.set("currencyID", currency)
        line_ext.text = _fmt_amount(invoice.total_excl_tax)

        tax_excl = etree.SubElement(monetary, _cbc("TaxExclusiveAmount"))
        tax_excl.set("currencyID", currency)
        tax_excl.text = _fmt_amount(invoice.total_excl_tax)

        tax_incl = etree.SubElement(monetary, _cbc("TaxInclusiveAmount"))
        tax_incl.set("currencyID", currency)
        tax_incl.text = _fmt_amount(invoice.total_incl_tax)

        if invoice.prepaid_amount:
            prepaid = etree.SubElement(monetary, _cbc("PrepaidAmount"))
            prepaid.set("currencyID", currency)
            prepaid.text = _fmt_amount(invoice.prepaid_amount)

        payable = etree.SubElement(monetary, _cbc("PayableAmount"))
        payable.set("currencyID", currency)
        payable.text = _fmt_amount(invoice.amount_due)

    # --- Lignes de facture ---

    def _build_invoice_line(
        self,
        root: etree._Element,
        line: InvoiceLine,
        idx: int,
        currency: str,
    ) -> None:
        """Construit InvoiceLine ou CreditNoteLine."""
        line_tag = "CreditNoteLine" if self._credit_note else "InvoiceLine"
        line_el = etree.SubElement(root, _cac(line_tag))

        # ID
        line_id = str(line.line_number) if line.line_number is not None else str(idx)
        etree.SubElement(line_el, _cbc("ID")).text = line_id

        # InvoicedQuantity ou CreditedQuantity
        qty_tag = "CreditedQuantity" if self._credit_note else "InvoicedQuantity"
        qty = etree.SubElement(line_el, _cbc(qty_tag))
        qty.set("unitCode", str(line.unit))
        qty.text = str(line.quantity)

        # LineExtensionAmount
        line_ext = etree.SubElement(line_el, _cbc("LineExtensionAmount"))
        line_ext.set("currencyID", currency)
        line_ext.text = _fmt_amount(line.line_total_excl_tax)

        # InvoicePeriod (période de facturation de la ligne BG-26)
        if line.billing_period_start or line.billing_period_end:
            period = etree.SubElement(line_el, _cac("InvoicePeriod"))
            if line.billing_period_start:
                etree.SubElement(
                    period, _cbc("StartDate")
                ).text = _fmt_date(line.billing_period_start)
            if line.billing_period_end:
                etree.SubElement(
                    period, _cbc("EndDate")
                ).text = _fmt_date(line.billing_period_end)

        # Item
        item = etree.SubElement(line_el, _cac("Item"))
        etree.SubElement(item, _cbc("Name")).text = line.description

        if line.item_reference:
            seller_id = etree.SubElement(item, _cac("SellersItemIdentification"))
            etree.SubElement(seller_id, _cbc("ID")).text = line.item_reference

        if line.buyer_reference:
            buyer_id = etree.SubElement(item, _cac("BuyersItemIdentification"))
            etree.SubElement(buyer_id, _cbc("ID")).text = line.buyer_reference

        # ClassifiedTaxCategory
        tax_cat = etree.SubElement(item, _cac("ClassifiedTaxCategory"))
        etree.SubElement(tax_cat, _cbc("ID")).text = str(line.vat_category)
        etree.SubElement(tax_cat, _cbc("Percent")).text = _fmt_amount(
            line.vat_rate
        )
        tax_scheme = etree.SubElement(tax_cat, _cac("TaxScheme"))
        etree.SubElement(tax_scheme, _cbc("ID")).text = "VAT"

        # Price
        price = etree.SubElement(line_el, _cac("Price"))
        price_amount = etree.SubElement(price, _cbc("PriceAmount"))
        price_amount.set("currencyID", currency)
        price_amount.text = _fmt_amount(line.unit_price)
