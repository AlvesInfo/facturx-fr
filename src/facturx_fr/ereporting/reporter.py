"""Gestionnaire d'e-reporting.

FR: Classe principale pour la préparation, validation et agrégation des données
    e-reporting (transactions B2C, B2B internationales, paiements).
    Conforme aux spécifications DGFiP v3.1 et simplifications sept. 2025.
EN: Main class for preparation, validation and aggregation of e-reporting data
    (B2C transactions, international B2B, payments).
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal

from facturx_fr.ereporting.errors import (
    EReportingEmptyDeclarationError,
    EReportingValidationError,
)
from facturx_fr.ereporting.models import (
    AggregatedTransactionData,
    EReportingSubmission,
    PaymentData,
    TaxBreakdown,
    TransactionData,
    TransmissionSchedule,
)
from facturx_fr.models.enums import (
    EReportingTransactionType,
    EReportingTransmissionMode,
    VATRegime,
)
from facturx_fr.models.invoice import Invoice

_SIREN_RE = re.compile(r"^\d{9}$")

# Fréquences de transmission par régime de TVA
_TRANSACTION_FREQUENCIES: dict[VATRegime, str] = {
    VATRegime.REAL_NORMAL_MONTHLY: "tous les 10 jours",
    VATRegime.REAL_NORMAL_QUARTERLY: "tous les 10 jours",
    VATRegime.SIMPLIFIED_REAL: "mensuel",
    VATRegime.FRANCHISE: "mensuel",
}

_PAYMENT_FREQUENCIES: dict[VATRegime, str | None] = {
    VATRegime.REAL_NORMAL_MONTHLY: "mensuel",
    VATRegime.REAL_NORMAL_QUARTERLY: "mensuel",
    VATRegime.SIMPLIFIED_REAL: "mensuel",
    VATRegime.FRANCHISE: None,
}


class EReporter:
    """Gestionnaire d'e-reporting.

    FR: Prépare, valide et agrège les données e-reporting pour transmission
        à la PA. Calcule les échéances selon le régime de TVA.
    EN: Prepares, validates and aggregates e-reporting data for transmission
        to the PA. Computes deadlines based on VAT regime.
    """

    def __init__(self, seller_siren: str, vat_regime: VATRegime) -> None:
        if not _SIREN_RE.match(seller_siren):
            msg = f"SIREN invalide : {seller_siren!r} (9 chiffres attendus)"
            raise ValueError(msg)
        self.seller_siren = seller_siren
        self.vat_regime = vat_regime

    # --- Validation ---

    def validate_transaction(self, transaction: TransactionData) -> list[str]:
        """Valide une transaction e-reporting. Retourne la liste des erreurs."""
        errors: list[str] = []

        # SIREN doit correspondre
        if transaction.seller_siren != self.seller_siren:
            errors.append(
                f"SIREN de la transaction ({transaction.seller_siren}) "
                f"ne correspond pas au SIREN du reporter ({self.seller_siren})"
            )

        # Code pays obligatoire pour transactions internationales
        if transaction.transaction_type in (
            EReportingTransactionType.B2B_INTRA_EU,
            EReportingTransactionType.B2B_EXTRA_EU,
        ):
            if not transaction.country_code:
                errors.append(
                    "Code pays obligatoire pour les transactions internationales"
                )
            elif transaction.country_code == "FR":
                errors.append(
                    "Code pays ne peut pas être 'FR' pour une transaction internationale"
                )

        # Taux TVA ou exonération requis
        if transaction.vat_rate is None and not transaction.vat_exemption:
            errors.append(
                "Taux de TVA ou indicateur d'exonération requis"
            )

        # Date facture ou période requis
        if (
            transaction.invoice_date is None
            and transaction.period_start is None
        ):
            errors.append(
                "Date de facture ou période de début requise"
            )

        return errors

    def validate_payment(self, payment: PaymentData) -> list[str]:
        """Valide des données de paiement e-reporting. Retourne la liste des erreurs."""
        errors: list[str] = []

        # SIREN doit correspondre
        if payment.seller_siren != self.seller_siren:
            errors.append(
                f"SIREN du paiement ({payment.seller_siren}) "
                f"ne correspond pas au SIREN du reporter ({self.seller_siren})"
            )

        return errors

    def validate_aggregated(
        self, aggregated: AggregatedTransactionData
    ) -> list[str]:
        """Valide des données agrégées e-reporting. Retourne la liste des erreurs."""
        errors: list[str] = []

        # SIREN doit correspondre
        if aggregated.seller_siren != self.seller_siren:
            errors.append(
                f"SIREN de l'agrégat ({aggregated.seller_siren}) "
                f"ne correspond pas au SIREN du reporter ({self.seller_siren})"
            )

        # Vérifier que les montants ne sont pas tous à zéro
        if aggregated.total_excl_tax == 0 and aggregated.total_vat == 0:
            msg = (
                "Déclaration vide interdite depuis les simplifications "
                "DGFiP septembre 2025 : pas d'opérations = pas de transmission"
            )
            raise EReportingEmptyDeclarationError(msg)

        return errors

    # --- Préparation ---

    def prepare_transaction(
        self, transaction: TransactionData
    ) -> EReportingSubmission:
        """Valide et prépare une transaction individuelle pour soumission."""
        errors = self.validate_transaction(transaction)
        if errors:
            msg = f"Transaction invalide : {'; '.join(errors)}"
            raise EReportingValidationError(msg, errors=errors)

        return EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.INDIVIDUAL,
            transaction_data=transaction,
        )

    def prepare_aggregated(
        self, aggregated: AggregatedTransactionData
    ) -> EReportingSubmission:
        """Valide et prépare des données agrégées pour soumission."""
        errors = self.validate_aggregated(aggregated)
        if errors:
            msg = f"Agrégat invalide : {'; '.join(errors)}"
            raise EReportingValidationError(msg, errors=errors)

        return EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.AGGREGATED,
            aggregated_data=aggregated,
        )

    def prepare_payment(self, payment: PaymentData) -> EReportingSubmission:
        """Valide et prépare des données de paiement pour soumission."""
        errors = self.validate_payment(payment)
        if errors:
            msg = f"Paiement invalide : {'; '.join(errors)}"
            raise EReportingValidationError(msg, errors=errors)

        return EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.INDIVIDUAL,
            payment_data=payment,
        )

    # --- Conversion depuis Invoice ---

    def transaction_from_invoice(
        self,
        invoice: Invoice,
        transaction_type: EReportingTransactionType,
        country_code: str | None = None,
    ) -> TransactionData:
        """Crée une TransactionData depuis une Invoice.

        FR: Extrait les données pertinentes d'une facture pour constituer
            une transaction e-reporting.
        EN: Extracts relevant data from an invoice to create an e-reporting
            transaction.
        """
        # Déterminer le taux TVA dominant (le premier taux trouvé)
        vat_rate: Decimal | None = None
        vat_exemption = False
        if invoice.lines:
            first_line = invoice.lines[0]
            vat_rate = first_line.vat_rate
            if first_line.vat_category.value in ("E", "O", "G"):
                vat_exemption = True

        return TransactionData(
            seller_siren=invoice.seller.siren or self.seller_siren,
            transaction_type=transaction_type,
            invoice_date=invoice.issue_date,
            invoice_number=invoice.number,
            operation_category=invoice.operation_category,
            total_excl_tax=invoice.total_excl_tax,
            vat_amount=invoice.total_vat,
            vat_rate=vat_rate,
            vat_exemption=vat_exemption,
            tax_due_in_france=invoice.total_vat if not vat_exemption else Decimal("0"),
            vat_on_debits=invoice.vat_on_debits,
            country_code=country_code,
            currency=invoice.currency,
        )

    # --- Agrégation ---

    def aggregate_transactions(
        self,
        transactions: list[TransactionData],
        period_start: date,
        period_end: date,
    ) -> AggregatedTransactionData:
        """Agrège une liste de transactions par taux de TVA.

        FR: Regroupe les transactions individuelles en totaux par taux de TVA
            pour une période donnée. Toutes les transactions doivent avoir
            le même SIREN vendeur.
        EN: Groups individual transactions into totals per VAT rate
            for a given period.
        """
        if not transactions:
            msg = (
                "Déclaration vide interdite depuis les simplifications "
                "DGFiP septembre 2025 : pas d'opérations = pas de transmission"
            )
            raise EReportingEmptyDeclarationError(msg)

        # Vérifier que tous les SIREN sont identiques
        sirens = {t.seller_siren for t in transactions}
        if len(sirens) > 1:
            msg = (
                f"Toutes les transactions doivent avoir le même SIREN vendeur, "
                f"trouvés : {', '.join(sorted(sirens))}"
            )
            raise EReportingValidationError(msg)

        # Regrouper par (taux_tva, exonération)
        breakdowns: dict[tuple[Decimal | None, bool], tuple[Decimal, Decimal]] = {}
        operation_category = transactions[0].operation_category
        vat_on_debits = transactions[0].vat_on_debits

        for txn in transactions:
            key = (txn.vat_rate, txn.vat_exemption)
            existing = breakdowns.get(key)
            if existing:
                taxable, vat = existing
                breakdowns[key] = (
                    taxable + txn.total_excl_tax,
                    vat + txn.vat_amount,
                )
            else:
                breakdowns[key] = (txn.total_excl_tax, txn.vat_amount)

        tax_breakdowns = [
            TaxBreakdown(
                vat_rate=rate,
                vat_exemption=exemption,
                taxable_amount=taxable,
                vat_amount=vat,
            )
            for (rate, exemption), (taxable, vat) in sorted(
                breakdowns.items(), key=lambda x: (x[0][0] or Decimal("-1"), x[0][1])
            )
        ]

        return AggregatedTransactionData(
            seller_siren=transactions[0].seller_siren,
            period_start=period_start,
            period_end=period_end,
            operation_category=operation_category,
            tax_breakdowns=tax_breakdowns,
            vat_on_debits=vat_on_debits,
        )

    # --- Calendrier de transmission ---

    def get_transmission_schedule(self) -> TransmissionSchedule:
        """Retourne le calendrier de transmission selon le régime de TVA."""
        return TransmissionSchedule(
            vat_regime=self.vat_regime,
            transaction_frequency=_TRANSACTION_FREQUENCIES[self.vat_regime],
            payment_frequency=_PAYMENT_FREQUENCIES[self.vat_regime],
        )

    def next_transaction_deadline(self, reference_date: date) -> date:
        """Calcule la prochaine échéance de transmission des transactions.

        FR: Pour les régimes « tous les 10 jours » : prochaine date parmi
            {10, 20, dernier jour du mois} après reference_date.
            Pour les régimes « mensuel » : dernier jour du mois suivant.
        EN: For "every 10 days" regimes: next date among {10, 20, last day}
            after reference_date. For "monthly" regimes: last day of next month.
        """
        if self.vat_regime in (
            VATRegime.REAL_NORMAL_MONTHLY,
            VATRegime.REAL_NORMAL_QUARTERLY,
        ):
            return self._next_decadal_deadline(reference_date)
        else:
            return self._last_day_of_next_month(reference_date)

    def next_payment_deadline(self, reference_date: date) -> date | None:
        """Calcule la prochaine échéance de transmission des paiements.

        FR: Toujours mensuel sauf franchise (pas de données de paiement).
        EN: Always monthly except franchise (no payment data).
        """
        if self.vat_regime == VATRegime.FRANCHISE:
            return None
        return self._last_day_of_next_month(reference_date)

    @staticmethod
    def _next_decadal_deadline(reference_date: date) -> date:
        """Prochaine échéance décadaire : 10, 20 ou dernier jour du mois."""
        year = reference_date.year
        month = reference_date.month
        last_day = calendar.monthrange(year, month)[1]

        # Dates candidates dans le mois courant
        candidates = [
            date(year, month, 10),
            date(year, month, 20),
            date(year, month, last_day),
        ]

        # Trouver la prochaine date strictement après reference_date
        for candidate in candidates:
            if candidate > reference_date:
                return candidate

        # Si aucune date dans le mois courant, le 10 du mois suivant
        if month == 12:
            return date(year + 1, 1, 10)
        return date(year, month + 1, 10)

    @staticmethod
    def _last_day_of_next_month(reference_date: date) -> date:
        """Dernier jour du mois suivant reference_date."""
        year = reference_date.year
        month = reference_date.month

        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1

        last_day = calendar.monthrange(next_year, next_month)[1]
        return date(next_year, next_month, last_day)
