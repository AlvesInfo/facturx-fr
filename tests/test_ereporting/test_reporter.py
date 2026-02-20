"""Tests pour le gestionnaire EReporter."""

from datetime import date
from decimal import Decimal

import pytest

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
)
from facturx_fr.ereporting.reporter import EReporter
from facturx_fr.models.enums import (
    EReportingTransactionType,
    EReportingTransmissionMode,
    OperationCategory,
    VATRegime,
)
from facturx_fr.models.invoice import Invoice


class TestEReporterInit:
    """Tests d'initialisation du EReporter."""

    def test_valid_init(self) -> None:
        reporter = EReporter(
            seller_siren="123456789",
            vat_regime=VATRegime.REAL_NORMAL_MONTHLY,
        )
        assert reporter.seller_siren == "123456789"
        assert reporter.vat_regime == VATRegime.REAL_NORMAL_MONTHLY

    def test_invalid_siren(self) -> None:
        with pytest.raises(ValueError, match="SIREN invalide"):
            EReporter(seller_siren="12345", vat_regime=VATRegime.FRANCHISE)

    def test_non_numeric_siren(self) -> None:
        with pytest.raises(ValueError, match="SIREN invalide"):
            EReporter(seller_siren="12345678A", vat_regime=VATRegime.FRANCHISE)


class TestValidateTransaction:
    """Tests de validation des transactions."""

    def test_valid_b2c(
        self, ereporter_monthly: EReporter, sample_transaction: TransactionData
    ) -> None:
        errors = ereporter_monthly.validate_transaction(sample_transaction)
        assert errors == []

    def test_valid_international(
        self,
        ereporter_monthly: EReporter,
        sample_international_transaction: TransactionData,
    ) -> None:
        errors = ereporter_monthly.validate_transaction(
            sample_international_transaction
        )
        assert errors == []

    def test_missing_country_for_international(
        self, ereporter_monthly: EReporter
    ) -> None:
        txn = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2B_INTRA_EU,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("500.00"),
            vat_rate=Decimal("0.0"),
        )
        errors = ereporter_monthly.validate_transaction(txn)
        assert any("pays obligatoire" in e for e in errors)

    def test_country_fr_for_international(
        self, ereporter_monthly: EReporter
    ) -> None:
        txn = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2B_EXTRA_EU,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("500.00"),
            vat_rate=Decimal("0.0"),
            country_code="FR",
        )
        errors = ereporter_monthly.validate_transaction(txn)
        assert any("FR" in e for e in errors)

    def test_siren_mismatch(self, ereporter_monthly: EReporter) -> None:
        txn = TransactionData(
            seller_siren="999999999",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
            vat_rate=Decimal("20.0"),
        )
        errors = ereporter_monthly.validate_transaction(txn)
        assert any("SIREN" in e for e in errors)

    def test_missing_date_and_period(self, ereporter_monthly: EReporter) -> None:
        txn = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
            vat_rate=Decimal("20.0"),
        )
        errors = ereporter_monthly.validate_transaction(txn)
        assert any("Date" in e or "date" in e for e in errors)

    def test_with_period_instead_of_date(
        self, ereporter_monthly: EReporter
    ) -> None:
        txn = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
            vat_rate=Decimal("20.0"),
        )
        errors = ereporter_monthly.validate_transaction(txn)
        assert errors == []

    def test_missing_vat_rate_and_exemption(
        self, ereporter_monthly: EReporter
    ) -> None:
        txn = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
        )
        errors = ereporter_monthly.validate_transaction(txn)
        assert any("TVA" in e or "exonération" in e for e in errors)

    def test_with_vat_exemption(self, ereporter_monthly: EReporter) -> None:
        txn = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
            vat_exemption=True,
        )
        errors = ereporter_monthly.validate_transaction(txn)
        assert errors == []


class TestValidatePayment:
    """Tests de validation des paiements."""

    def test_valid_payment(
        self, ereporter_monthly: EReporter, sample_payment: PaymentData
    ) -> None:
        errors = ereporter_monthly.validate_payment(sample_payment)
        assert errors == []

    def test_siren_mismatch(self, ereporter_monthly: EReporter) -> None:
        payment = PaymentData(
            seller_siren="999999999",
            cashing_date=date(2026, 10, 1),
            cashed_amount=Decimal("100.00"),
            invoice_reference="FA-001",
        )
        errors = ereporter_monthly.validate_payment(payment)
        assert any("SIREN" in e for e in errors)


class TestValidateAggregated:
    """Tests de validation des données agrégées."""

    def test_valid_aggregated(
        self,
        ereporter_monthly: EReporter,
        sample_aggregated: AggregatedTransactionData,
    ) -> None:
        errors = ereporter_monthly.validate_aggregated(sample_aggregated)
        assert errors == []

    def test_siren_mismatch(self, ereporter_monthly: EReporter) -> None:
        agg = AggregatedTransactionData(
            seller_siren="999999999",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            operation_category=OperationCategory.DELIVERY,
            tax_breakdowns=[
                TaxBreakdown(
                    vat_rate=Decimal("20.0"),
                    taxable_amount=Decimal("100.00"),
                    vat_amount=Decimal("20.00"),
                ),
            ],
        )
        errors = ereporter_monthly.validate_aggregated(agg)
        assert any("SIREN" in e for e in errors)

    def test_empty_declaration_all_zeros(
        self, ereporter_monthly: EReporter
    ) -> None:
        agg = AggregatedTransactionData(
            seller_siren="123456789",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            operation_category=OperationCategory.DELIVERY,
            tax_breakdowns=[
                TaxBreakdown(
                    vat_rate=Decimal("20.0"),
                    taxable_amount=Decimal("0"),
                    vat_amount=Decimal("0"),
                ),
            ],
        )
        with pytest.raises(EReportingEmptyDeclarationError):
            ereporter_monthly.validate_aggregated(agg)


class TestPrepareTransaction:
    """Tests de préparation de transactions."""

    def test_returns_submission(
        self, ereporter_monthly: EReporter, sample_transaction: TransactionData
    ) -> None:
        sub = ereporter_monthly.prepare_transaction(sample_transaction)
        assert isinstance(sub, EReportingSubmission)
        assert sub.transmission_mode == EReportingTransmissionMode.INDIVIDUAL
        assert sub.transaction_data is not None

    def test_raises_on_invalid(self, ereporter_monthly: EReporter) -> None:
        txn = TransactionData(
            seller_siren="999999999",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
            vat_rate=Decimal("20.0"),
        )
        with pytest.raises(EReportingValidationError) as exc_info:
            ereporter_monthly.prepare_transaction(txn)
        assert len(exc_info.value.errors) > 0


class TestPrepareAggregated:
    """Tests de préparation de données agrégées."""

    def test_returns_submission(
        self,
        ereporter_monthly: EReporter,
        sample_aggregated: AggregatedTransactionData,
    ) -> None:
        sub = ereporter_monthly.prepare_aggregated(sample_aggregated)
        assert isinstance(sub, EReportingSubmission)
        assert sub.transmission_mode == EReportingTransmissionMode.AGGREGATED
        assert sub.aggregated_data is not None


class TestPreparePayment:
    """Tests de préparation de paiements."""

    def test_returns_submission(
        self, ereporter_monthly: EReporter, sample_payment: PaymentData
    ) -> None:
        sub = ereporter_monthly.prepare_payment(sample_payment)
        assert isinstance(sub, EReportingSubmission)
        assert sub.transmission_mode == EReportingTransmissionMode.INDIVIDUAL
        assert sub.payment_data is not None

    def test_raises_on_invalid(self, ereporter_monthly: EReporter) -> None:
        payment = PaymentData(
            seller_siren="999999999",
            cashing_date=date(2026, 10, 1),
            cashed_amount=Decimal("100.00"),
            invoice_reference="FA-001",
        )
        with pytest.raises(EReportingValidationError):
            ereporter_monthly.prepare_payment(payment)


class TestTransactionFromInvoice:
    """Tests de conversion Invoice → TransactionData."""

    def test_extraction(
        self, ereporter_monthly: EReporter, sample_invoice: Invoice
    ) -> None:
        txn = ereporter_monthly.transaction_from_invoice(
            sample_invoice,
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
        )
        assert txn.seller_siren == "123456789"
        assert txn.invoice_number == "FA-2026-042"
        assert txn.invoice_date == date(2026, 9, 15)
        assert txn.total_excl_tax == Decimal("1200.00")
        assert txn.vat_rate == Decimal("20.0")
        assert txn.operation_category == OperationCategory.DELIVERY

    def test_with_country_code(
        self, ereporter_monthly: EReporter, sample_invoice: Invoice
    ) -> None:
        txn = ereporter_monthly.transaction_from_invoice(
            sample_invoice,
            transaction_type=EReportingTransactionType.B2B_INTRA_EU,
            country_code="DE",
        )
        assert txn.country_code == "DE"
        assert txn.transaction_type == EReportingTransactionType.B2B_INTRA_EU


class TestAggregateTransactions:
    """Tests d'agrégation de transactions."""

    def test_single_rate(self, ereporter_monthly: EReporter) -> None:
        transactions = [
            TransactionData(
                seller_siren="123456789",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 15),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("100.00"),
                vat_amount=Decimal("20.00"),
                vat_rate=Decimal("20.0"),
            ),
            TransactionData(
                seller_siren="123456789",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 16),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("200.00"),
                vat_amount=Decimal("40.00"),
                vat_rate=Decimal("20.0"),
            ),
        ]

        agg = ereporter_monthly.aggregate_transactions(
            transactions,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
        )
        assert len(agg.tax_breakdowns) == 1
        assert agg.total_excl_tax == Decimal("300.00")
        assert agg.total_vat == Decimal("60.00")

    def test_multi_rate(self, ereporter_monthly: EReporter) -> None:
        transactions = [
            TransactionData(
                seller_siren="123456789",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 15),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("100.00"),
                vat_amount=Decimal("20.00"),
                vat_rate=Decimal("20.0"),
            ),
            TransactionData(
                seller_siren="123456789",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 16),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("200.00"),
                vat_amount=Decimal("11.00"),
                vat_rate=Decimal("5.5"),
            ),
        ]

        agg = ereporter_monthly.aggregate_transactions(
            transactions,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
        )
        assert len(agg.tax_breakdowns) == 2
        assert agg.total_excl_tax == Decimal("300.00")
        assert agg.total_vat == Decimal("31.00")

    def test_empty_list(self, ereporter_monthly: EReporter) -> None:
        with pytest.raises(EReportingEmptyDeclarationError):
            ereporter_monthly.aggregate_transactions(
                [],
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
            )

    def test_mixed_sirens(self, ereporter_monthly: EReporter) -> None:
        transactions = [
            TransactionData(
                seller_siren="123456789",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 15),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("100.00"),
                vat_rate=Decimal("20.0"),
            ),
            TransactionData(
                seller_siren="999888777",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 16),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("200.00"),
                vat_rate=Decimal("20.0"),
            ),
        ]
        with pytest.raises(EReportingValidationError, match="même SIREN"):
            ereporter_monthly.aggregate_transactions(
                transactions,
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
            )


class TestTransmissionSchedule:
    """Tests du calendrier de transmission."""

    def test_real_normal_monthly(self, ereporter_monthly: EReporter) -> None:
        schedule = ereporter_monthly.get_transmission_schedule()
        assert schedule.transaction_frequency == "tous les 10 jours"
        assert schedule.payment_frequency == "mensuel"

    def test_real_normal_quarterly(self) -> None:
        reporter = EReporter(
            seller_siren="123456789",
            vat_regime=VATRegime.REAL_NORMAL_QUARTERLY,
        )
        schedule = reporter.get_transmission_schedule()
        assert schedule.transaction_frequency == "tous les 10 jours"
        assert schedule.payment_frequency == "mensuel"

    def test_simplified_real(self) -> None:
        reporter = EReporter(
            seller_siren="123456789",
            vat_regime=VATRegime.SIMPLIFIED_REAL,
        )
        schedule = reporter.get_transmission_schedule()
        assert schedule.transaction_frequency == "mensuel"
        assert schedule.payment_frequency == "mensuel"

    def test_franchise(self, ereporter_franchise: EReporter) -> None:
        schedule = ereporter_franchise.get_transmission_schedule()
        assert schedule.transaction_frequency == "mensuel"
        assert schedule.payment_frequency is None


class TestNextDeadlines:
    """Tests des calculs d'échéances."""

    # --- Transactions : "tous les 10 jours" ---

    def test_decadal_from_day_1(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 9, 1))
        assert deadline == date(2026, 9, 10)

    def test_decadal_from_day_10(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 9, 10))
        assert deadline == date(2026, 9, 20)

    def test_decadal_from_day_15(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 9, 15))
        assert deadline == date(2026, 9, 20)

    def test_decadal_from_day_20(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 9, 20))
        assert deadline == date(2026, 9, 30)

    def test_decadal_from_day_25(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 9, 25))
        assert deadline == date(2026, 9, 30)

    def test_decadal_from_last_day(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 9, 30))
        assert deadline == date(2026, 10, 10)

    def test_decadal_february(self, ereporter_monthly: EReporter) -> None:
        # Février 2026 a 28 jours
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 2, 20))
        assert deadline == date(2026, 2, 28)

    def test_decadal_december_rollover(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_transaction_deadline(date(2026, 12, 31))
        assert deadline == date(2027, 1, 10)

    # --- Transactions : "mensuel" ---

    def test_monthly_from_mid_month(self, ereporter_franchise: EReporter) -> None:
        deadline = ereporter_franchise.next_transaction_deadline(date(2026, 9, 15))
        assert deadline == date(2026, 10, 31)

    def test_monthly_from_last_day(self, ereporter_franchise: EReporter) -> None:
        deadline = ereporter_franchise.next_transaction_deadline(date(2026, 9, 30))
        assert deadline == date(2026, 10, 31)

    def test_monthly_december_rollover(self, ereporter_franchise: EReporter) -> None:
        deadline = ereporter_franchise.next_transaction_deadline(date(2026, 12, 15))
        assert deadline == date(2027, 1, 31)

    # --- Paiements ---

    def test_payment_deadline_monthly(self, ereporter_monthly: EReporter) -> None:
        deadline = ereporter_monthly.next_payment_deadline(date(2026, 9, 15))
        assert deadline == date(2026, 10, 31)

    def test_payment_deadline_franchise_none(
        self, ereporter_franchise: EReporter
    ) -> None:
        deadline = ereporter_franchise.next_payment_deadline(date(2026, 9, 15))
        assert deadline is None
