"""Modèles principaux pour les factures électroniques.

FR: Modèles Pydantic pour les factures, lignes de facture et récapitulatifs TVA,
    conformes à la norme EN16931 et aux exigences françaises sept. 2026.
EN: Pydantic models for invoices, invoice lines and VAT summaries,
    conforming to EN16931 and the French Sept. 2026 requirements.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field

from facturx_fr.models.enums import (
    Currency,
    InvoiceTypeCode,
    OperationCategory,
    UnitOfMeasure,
    VATCategory,
)
from facturx_fr.models.party import Party
from facturx_fr.models.payment import PaymentMeans, PaymentTerms


class InvoiceLine(BaseModel):
    """Ligne de facture.

    FR: Représente un poste de facturation avec quantité, prix unitaire et TVA.
        Conforme à EN16931 BG-25 (Invoice line).
        Supporte les sous-lignes (Factur-X 1.08 / profil Extended).
    EN: Represents an invoice item with quantity, unit price and VAT.
    """

    line_number: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Numéro de ligne (auto-numéroté si absent) / "
            "Line number (auto-numbered if not set)"
        ),
    )
    description: str = Field(..., description="Désignation / Item description")
    quantity: Decimal = Field(
        ...,
        description=(
            "Quantité facturée (peut être négative pour reprise d'acomptes) / "
            "Invoiced quantity (can be negative for advance reprise)"
        ),
    )
    unit: UnitOfMeasure = Field(
        default=UnitOfMeasure.UNIT,
        description="Unité de mesure UN/ECE Rec. 20 / Unit of measure",
    )
    unit_price: Decimal = Field(
        ...,
        description=(
            "Prix unitaire HT (peut être négatif pour lignes de déduction) / "
            "Unit price excl. tax (can be negative for deduction lines)"
        ),
    )
    vat_rate: Decimal = Field(
        default=Decimal("20.0"),
        ge=0,
        description="Taux de TVA en % / VAT rate in %",
    )
    vat_category: VATCategory = Field(
        default=VATCategory.STANDARD,
        description="Catégorie de TVA / VAT category",
    )
    item_reference: str | None = Field(
        default=None,
        description="Référence article vendeur / Seller item reference",
    )
    buyer_reference: str | None = Field(
        default=None,
        description="Référence article acheteur / Buyer item reference",
    )
    discount_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Montant de remise / Discount amount",
    )
    charge_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Montant de majoration / Charge amount",
    )
    vat_exemption_reason: str | None = Field(
        default=None,
        description=(
            "Motif d'exonération TVA BT-121 (ex: 'Autoliquidation — "
            "Article 283-2 nonies du CGI') / VAT exemption reason text"
        ),
    )
    vat_exemption_reason_code: str | None = Field(
        default=None,
        description=(
            "Code motif d'exonération TVA BT-120 (ex: 'vatex-eu-ae') / "
            "VAT exemption reason code (VATEX code list)"
        ),
    )
    billing_period_start: date | None = Field(
        default=None,
        description=(
            "Début de la période de facturation BG-26 "
            "(situations de travaux, services) / Billing period start date"
        ),
    )
    billing_period_end: date | None = Field(
        default=None,
        description=(
            "Fin de la période de facturation BG-26 / "
            "Billing period end date"
        ),
    )
    sub_lines: list["InvoiceLine"] | None = Field(
        default=None,
        description=(
            "Sous-lignes (Factur-X 1.08, profil Extended : sous-totaux, kits, bundles) / "
            "Sub-lines (Factur-X 1.08, Extended profile)"
        ),
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total_excl_tax(self) -> Decimal:
        """Montant total HT de la ligne / Line total excluding tax."""
        total = self.quantity * self.unit_price
        if self.discount_amount:
            total -= self.discount_amount
        if self.charge_amount:
            total += self.charge_amount
        return total

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_vat_amount(self) -> Decimal:
        """Montant de TVA de la ligne / Line VAT amount."""
        return (self.line_total_excl_tax * self.vat_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total_incl_tax(self) -> Decimal:
        """Montant total TTC de la ligne / Line total including tax."""
        return self.line_total_excl_tax + self.line_vat_amount


# Résolution de la référence circulaire pour sub_lines
InvoiceLine.model_rebuild()


class TaxSummary(BaseModel):
    """Récapitulatif TVA par taux.

    FR: Regroupe les montants HT et TVA pour un taux donné.
        Inclut le motif d'exonération si applicable (AE, E, Z, etc.).
    EN: Groups amounts excl. and incl. tax for a given rate.
    """

    vat_category: VATCategory = Field(..., description="Catégorie de TVA / VAT category")
    vat_rate: Decimal = Field(..., ge=0, description="Taux de TVA en % / VAT rate in %")
    taxable_amount: Decimal = Field(..., description="Base imposable HT / Taxable amount")
    tax_amount: Decimal = Field(..., description="Montant de TVA / Tax amount")
    vat_exemption_reason: str | None = Field(
        default=None,
        description="Motif d'exonération TVA BT-121 / VAT exemption reason text",
    )
    vat_exemption_reason_code: str | None = Field(
        default=None,
        description="Code motif d'exonération TVA BT-120 / VAT exemption reason code",
    )


class Invoice(BaseModel):
    """Facture électronique.

    FR: Modèle principal de facture conforme à EN16931 avec les mentions
        obligatoires de la réforme française sept. 2026 :
        - catégorie de l'opération
        - numéro SIREN du destinataire
        - adresse de livraison si différente
        - option TVA sur les débits
    EN: Main invoice model conforming to EN16931 with mandatory fields
        from the French Sept. 2026 reform.
    """

    # --- Identification ---
    number: str = Field(..., description="Numéro de facture / Invoice number")
    issue_date: date = Field(..., description="Date d'émission / Issue date")
    due_date: date | None = Field(
        default=None,
        description="Date d'échéance de paiement / Payment due date",
    )
    type_code: InvoiceTypeCode = Field(
        default=InvoiceTypeCode.INVOICE,
        description="Type de document / Document type code",
    )
    currency: str = Field(
        default=Currency.EUR,
        description="Code devise ISO 4217 / Currency code",
    )

    # --- Parties ---
    seller: Party = Field(..., description="Vendeur / Seller")
    buyer: Party = Field(..., description="Acheteur / Buyer")

    # --- Lignes ---
    lines: list[InvoiceLine] = Field(
        ...,
        min_length=1,
        description="Lignes de facture / Invoice lines",
    )

    # --- Mentions obligatoires sept. 2026 ---
    operation_category: OperationCategory = Field(
        ...,
        description=(
            "Catégorie de l'opération (mention obligatoire sept. 2026) / "
            "Operation category (mandatory Sept. 2026)"
        ),
    )
    vat_on_debits: bool = Field(
        default=False,
        description=(
            "Option TVA sur les débits (mention obligatoire si applicable) / "
            "VAT on debits option"
        ),
    )

    # --- Références ---
    purchase_order_reference: str | None = Field(
        default=None,
        description="Référence du bon de commande / Purchase order reference",
    )
    contract_reference: str | None = Field(
        default=None,
        description="Référence du contrat / Contract reference",
    )
    preceding_invoice_reference: str | None = Field(
        default=None,
        description="Référence de la facture précédente (pour avoirs) / Preceding invoice ref",
    )
    buyer_accounting_reference: str | None = Field(
        default=None,
        description="Référence comptable acheteur / Buyer accounting reference",
    )

    # --- Paiement ---
    payment_terms: PaymentTerms | None = Field(
        default=None,
        description="Conditions de paiement / Payment terms",
    )
    payment_means: PaymentMeans | None = Field(
        default=None,
        description="Moyen de paiement / Payment means",
    )

    # --- Montants prépayés / retenus ---
    prepaid_amount: Decimal | None = Field(
        default=None,
        description=(
            "Montant déjà payé / retenu (BT-113 : acomptes, retenue de garantie) / "
            "Prepaid amount (advances, retention guarantee)"
        ),
    )

    # --- Période de facturation (niveau facture) ---
    billing_period_start: date | None = Field(
        default=None,
        description=(
            "Début de la période de facturation BG-14 "
            "(situations de travaux) / Billing period start date"
        ),
    )
    billing_period_end: date | None = Field(
        default=None,
        description=(
            "Fin de la période de facturation BG-14 / "
            "Billing period end date"
        ),
    )

    # --- Tiers (bénéficiaire, payeur) ---
    payee: Party | None = Field(
        default=None,
        description=(
            "Bénéficiaire du paiement si différent du vendeur BG-10 "
            "(affacturage, centralisation trésorerie) / "
            "Payee if different from seller"
        ),
    )
    payer: Party | None = Field(
        default=None,
        description=(
            "Payeur tiers EXTENDED-CTC-FR EXT-FR-FE-BG-02 "
            "(paiement direct sous-traitance BTP) / "
            "Third-party payer (EXTENDED-CTC-FR only)"
        ),
    )

    # --- Notes ---
    note: str | None = Field(
        default=None,
        description="Note libre / Free text note",
    )

    # --- Totaux calculés ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_excl_tax(self) -> Decimal:
        """Total HT de la facture / Invoice total excluding tax."""
        return sum((line.line_total_excl_tax for line in self.lines), Decimal("0"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_vat(self) -> Decimal:
        """Total TVA de la facture / Invoice total VAT."""
        return sum((line.line_vat_amount for line in self.lines), Decimal("0"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_incl_tax(self) -> Decimal:
        """Total TTC de la facture / Invoice total including tax."""
        return self.total_excl_tax + self.total_vat

    @computed_field  # type: ignore[prop-decorator]
    @property
    def amount_due(self) -> Decimal:
        """Montant à payer (TTC - acomptes/retenues) / Amount due for payment.

        FR: Déduit le montant prépayé (acomptes, retenue de garantie) du TTC.
        EN: Deducts prepaid amount (advances, retention guarantee) from total incl. tax.
        """
        total = self.total_incl_tax
        if self.prepaid_amount:
            total -= self.prepaid_amount
        return total

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tax_summaries(self) -> list[TaxSummary]:
        """Récapitulatifs TVA par taux / Tax summaries by rate."""
        summaries: dict[
            tuple[VATCategory, Decimal],
            tuple[Decimal, Decimal, str | None, str | None],
        ] = {}
        for line in self.lines:
            key = (line.vat_category, line.vat_rate)
            existing = summaries.get(key)
            if existing:
                taxable, tax, reason, reason_code = existing
                summaries[key] = (
                    taxable + line.line_total_excl_tax,
                    tax + line.line_vat_amount,
                    reason or line.vat_exemption_reason,
                    reason_code or line.vat_exemption_reason_code,
                )
            else:
                summaries[key] = (
                    line.line_total_excl_tax,
                    line.line_vat_amount,
                    line.vat_exemption_reason,
                    line.vat_exemption_reason_code,
                )
        return [
            TaxSummary(
                vat_category=cat,
                vat_rate=rate,
                taxable_amount=taxable,
                tax_amount=tax,
                vat_exemption_reason=reason,
                vat_exemption_reason_code=reason_code,
            )
            for (cat, rate), (taxable, tax, reason, reason_code) in sorted(
                summaries.items()
            )
        ]
