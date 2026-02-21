"""Modèles de données pour le e-reporting.

FR: Modèles Pydantic pour les transactions B2C, B2B internationales,
    les données de paiement et les agrégats, conformes aux spécifications
    DGFiP v3.1 et aux simplifications de septembre 2025.
EN: Pydantic models for B2C, international B2B transactions,
    payment data and aggregates.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field

from facturx_fr.models.enums import (
    EReportingTransactionType,
    EReportingTransmissionMode,
    OperationCategory,
    VATRegime,
)


class TaxBreakdown(BaseModel):
    """Ventilation TVA pour données agrégées.

    FR: Représente une ligne de ventilation TVA dans un agrégat e-reporting,
        avec taux ou indicateur d'exonération.
    EN: Represents a VAT breakdown line in an e-reporting aggregate.
    """

    vat_rate: Decimal | None = Field(
        default=None,
        ge=0,
        description="Taux de TVA en % / VAT rate in %",
    )
    vat_exemption: bool = Field(
        default=False,
        description="Indicateur d'exonération TVA / VAT exemption indicator",
    )
    taxable_amount: Decimal = Field(
        ...,
        description="Base imposable HT / Taxable amount excl. tax",
    )
    vat_amount: Decimal = Field(
        ...,
        description="Montant de TVA / VAT amount",
    )


class TransactionData(BaseModel):
    """Données d'une transaction individuelle e-reporting.

    FR: Représente une transaction soumise au e-reporting (B2C domestique,
        B2B intracommunautaire ou hors UE). Conforme aux flux 8/9 DGFiP.
    EN: Represents a transaction subject to e-reporting.
    """

    # Identification
    transaction_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Identifiant unique de la transaction / Transaction ID",
    )
    seller_siren: str = Field(
        ...,
        min_length=9,
        max_length=9,
        pattern=r"^\d{9}$",
        description="SIREN du vendeur (9 chiffres) / Seller SIREN",
    )
    transaction_type: EReportingTransactionType = Field(
        ...,
        description="Type de transaction / Transaction type",
    )

    # Période ou date
    period_start: date | None = Field(
        default=None,
        description="Début de la période / Period start date",
    )
    period_end: date | None = Field(
        default=None,
        description="Fin de la période / Period end date",
    )
    invoice_date: date | None = Field(
        default=None,
        description="Date de la facture / Invoice date",
    )
    invoice_number: str | None = Field(
        default=None,
        description="Numéro de facture (requis en mode individuel) / Invoice number",
    )

    # Opération
    operation_category: OperationCategory = Field(
        ...,
        description="Catégorie de l'opération / Operation category",
    )

    # Montants
    total_excl_tax: Decimal = Field(
        ...,
        description="Montant total HT / Total amount excl. tax",
    )
    vat_amount: Decimal = Field(
        default=Decimal("0"),
        description="Montant de TVA / VAT amount",
    )
    vat_rate: Decimal | None = Field(
        default=None,
        ge=0,
        description="Taux de TVA appliqué en % / Applied VAT rate in %",
    )
    vat_exemption: bool = Field(
        default=False,
        description="Indicateur d'exonération TVA / VAT exemption indicator",
    )
    tax_due_in_france: Decimal | None = Field(
        default=None,
        description="Montant total de taxe due en France (en EUR) / Tax due in France",
    )

    # Options
    vat_on_debits: bool = Field(
        default=False,
        description="Option TVA sur les débits / VAT on debits option",
    )
    country_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Code pays (obligatoire si hors France) / Country code",
    )
    currency: str = Field(
        default="EUR",
        description="Code devise ISO 4217 / Currency code",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_incl_tax(self) -> Decimal:
        """Montant total TTC / Total amount incl. tax."""
        return self.total_excl_tax + self.vat_amount


class PaymentData(BaseModel):
    """Données d'encaissement e-reporting.

    FR: Représente un encaissement pour une prestation de services
        (TVA sur encaissements). Conforme au flux 10 DGFiP.
    EN: Represents a payment receipt for a service provision
        (VAT on receipts).
    """

    payment_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Identifiant unique du paiement / Payment ID",
    )
    seller_siren: str = Field(
        ...,
        min_length=9,
        max_length=9,
        pattern=r"^\d{9}$",
        description="SIREN du vendeur (9 chiffres) / Seller SIREN",
    )
    cashing_date: date = Field(
        ...,
        description="Date d'encaissement / Cashing date",
    )
    cashed_amount: Decimal = Field(
        ...,
        gt=0,
        description="Montant encaissé (> 0) / Cashed amount",
    )
    currency: str = Field(
        default="EUR",
        description="Code devise ISO 4217 / Currency code",
    )
    invoice_reference: str = Field(
        ...,
        min_length=1,
        description="Référence de la facture associée / Associated invoice reference",
    )


class AggregatedTransactionData(BaseModel):
    """Données de transactions agrégées e-reporting.

    FR: Regroupement des transactions sur une période (totaux quotidiens
        par SIREN pour B2C). Conforme au flux 9 DGFiP.
    EN: Aggregated transactions over a period (daily totals per SIREN for B2C).
    """

    seller_siren: str = Field(
        ...,
        min_length=9,
        max_length=9,
        pattern=r"^\d{9}$",
        description="SIREN du vendeur (9 chiffres) / Seller SIREN",
    )
    period_start: date = Field(
        ...,
        description="Début de la période d'agrégation / Aggregation period start",
    )
    period_end: date = Field(
        ...,
        description="Fin de la période d'agrégation / Aggregation period end",
    )
    operation_category: OperationCategory = Field(
        ...,
        description="Catégorie de l'opération / Operation category",
    )
    tax_breakdowns: list[TaxBreakdown] = Field(
        ...,
        min_length=1,
        description="Ventilations TVA / Tax breakdowns",
    )
    vat_on_debits: bool = Field(
        default=False,
        description="Option TVA sur les débits / VAT on debits option",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_excl_tax(self) -> Decimal:
        """Total HT de l'agrégat / Aggregate total excl. tax."""
        return sum(
            (tb.taxable_amount for tb in self.tax_breakdowns), Decimal("0")
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_vat(self) -> Decimal:
        """Total TVA de l'agrégat / Aggregate total VAT."""
        return sum(
            (tb.vat_amount for tb in self.tax_breakdowns), Decimal("0")
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_incl_tax(self) -> Decimal:
        """Total TTC de l'agrégat / Aggregate total incl. tax."""
        return self.total_excl_tax + self.total_vat


class EReportingSubmission(BaseModel):
    """Soumission e-reporting préparée.

    FR: Encapsule une soumission prête à être envoyée à la PA,
        avec le mode de transmission et les données associées.
    EN: Encapsulates a submission ready to be sent to the PA.
    """

    submission_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Identifiant unique de la soumission / Submission ID",
    )
    transmission_mode: EReportingTransmissionMode = Field(
        ...,
        description="Mode de transmission / Transmission mode",
    )
    transaction_data: TransactionData | None = Field(
        default=None,
        description="Données de transaction individuelle / Individual transaction data",
    )
    aggregated_data: AggregatedTransactionData | None = Field(
        default=None,
        description="Données agrégées / Aggregated data",
    )
    payment_data: PaymentData | None = Field(
        default=None,
        description="Données de paiement / Payment data",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Date de création / Creation timestamp",
    )


class TransmissionSchedule(BaseModel):
    """Calendrier de transmission e-reporting.

    FR: Indique les fréquences de transmission des données de transaction
        et de paiement selon le régime de TVA du vendeur.
    EN: Indicates transmission frequencies for transaction and payment data
        based on the seller's VAT regime.
    """

    vat_regime: VATRegime = Field(
        ...,
        description="Régime de TVA / VAT regime",
    )
    transaction_frequency: str = Field(
        ...,
        description="Fréquence transactions / Transaction frequency",
    )
    payment_frequency: str | None = Field(
        default=None,
        description="Fréquence paiements (None si franchise) / Payment frequency",
    )
