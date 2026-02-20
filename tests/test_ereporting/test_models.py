"""Tests pour les modèles de données e-reporting."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

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
    OperationCategory,
    VATRegime,
)


class TestTaxBreakdown:
    """Tests du modèle TaxBreakdown."""

    def test_creation(self) -> None:
        tb = TaxBreakdown(
            vat_rate=Decimal("20.0"),
            taxable_amount=Decimal("1000.00"),
            vat_amount=Decimal("200.00"),
        )
        assert tb.vat_rate == Decimal("20.0")
        assert tb.taxable_amount == Decimal("1000.00")
        assert tb.vat_amount == Decimal("200.00")
        assert tb.vat_exemption is False

    def test_with_exemption(self) -> None:
        tb = TaxBreakdown(
            vat_exemption=True,
            taxable_amount=Decimal("500.00"),
            vat_amount=Decimal("0"),
        )
        assert tb.vat_rate is None
        assert tb.vat_exemption is True


class TestTransactionData:
    """Tests du modèle TransactionData."""

    def test_creation(self, sample_transaction: TransactionData) -> None:
        assert sample_transaction.seller_siren == "123456789"
        assert sample_transaction.transaction_type == EReportingTransactionType.B2C_DOMESTIC
        assert sample_transaction.total_excl_tax == Decimal("100.00")
        assert sample_transaction.vat_amount == Decimal("20.00")

    def test_computed_total_incl_tax(self, sample_transaction: TransactionData) -> None:
        assert sample_transaction.total_incl_tax == Decimal("120.00")

    def test_siren_validation_too_short(self) -> None:
        with pytest.raises(ValidationError, match="seller_siren"):
            TransactionData(
                seller_siren="12345",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 15),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("100.00"),
            )

    def test_siren_validation_non_numeric(self) -> None:
        with pytest.raises(ValidationError, match="seller_siren"):
            TransactionData(
                seller_siren="12345678A",
                transaction_type=EReportingTransactionType.B2C_DOMESTIC,
                invoice_date=date(2026, 9, 15),
                operation_category=OperationCategory.DELIVERY,
                total_excl_tax=Decimal("100.00"),
            )

    def test_auto_transaction_id(self) -> None:
        t1 = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
            vat_rate=Decimal("20.0"),
        )
        t2 = TransactionData(
            seller_siren="123456789",
            transaction_type=EReportingTransactionType.B2C_DOMESTIC,
            invoice_date=date(2026, 9, 15),
            operation_category=OperationCategory.DELIVERY,
            total_excl_tax=Decimal("100.00"),
            vat_rate=Decimal("20.0"),
        )
        assert t1.transaction_id != t2.transaction_id

    def test_with_country_code(
        self, sample_international_transaction: TransactionData
    ) -> None:
        assert sample_international_transaction.country_code == "DE"
        assert sample_international_transaction.transaction_type == (
            EReportingTransactionType.B2B_INTRA_EU
        )

    def test_default_currency(self, sample_transaction: TransactionData) -> None:
        assert sample_transaction.currency == "EUR"

    def test_default_vat_on_debits(self, sample_transaction: TransactionData) -> None:
        assert sample_transaction.vat_on_debits is False


class TestPaymentData:
    """Tests du modèle PaymentData."""

    def test_creation(self, sample_payment: PaymentData) -> None:
        assert sample_payment.seller_siren == "123456789"
        assert sample_payment.cashing_date == date(2026, 10, 1)
        assert sample_payment.cashed_amount == Decimal("120.00")
        assert sample_payment.invoice_reference == "FA-2026-042"

    def test_cashed_amount_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="cashed_amount"):
            PaymentData(
                seller_siren="123456789",
                cashing_date=date(2026, 10, 1),
                cashed_amount=Decimal("0"),
                invoice_reference="FA-001",
            )

    def test_cashed_amount_negative(self) -> None:
        with pytest.raises(ValidationError, match="cashed_amount"):
            PaymentData(
                seller_siren="123456789",
                cashing_date=date(2026, 10, 1),
                cashed_amount=Decimal("-10.00"),
                invoice_reference="FA-001",
            )

    def test_invoice_reference_non_empty(self) -> None:
        with pytest.raises(ValidationError, match="invoice_reference"):
            PaymentData(
                seller_siren="123456789",
                cashing_date=date(2026, 10, 1),
                cashed_amount=Decimal("100.00"),
                invoice_reference="",
            )

    def test_auto_payment_id(self) -> None:
        p1 = PaymentData(
            seller_siren="123456789",
            cashing_date=date(2026, 10, 1),
            cashed_amount=Decimal("100.00"),
            invoice_reference="FA-001",
        )
        p2 = PaymentData(
            seller_siren="123456789",
            cashing_date=date(2026, 10, 1),
            cashed_amount=Decimal("100.00"),
            invoice_reference="FA-001",
        )
        assert p1.payment_id != p2.payment_id


class TestAggregatedTransactionData:
    """Tests du modèle AggregatedTransactionData."""

    def test_creation(self, sample_aggregated: AggregatedTransactionData) -> None:
        assert sample_aggregated.seller_siren == "123456789"
        assert len(sample_aggregated.tax_breakdowns) == 2

    def test_computed_total_excl_tax(
        self, sample_aggregated: AggregatedTransactionData
    ) -> None:
        assert sample_aggregated.total_excl_tax == Decimal("1500.00")

    def test_computed_total_vat(
        self, sample_aggregated: AggregatedTransactionData
    ) -> None:
        assert sample_aggregated.total_vat == Decimal("227.50")

    def test_computed_total_incl_tax(
        self, sample_aggregated: AggregatedTransactionData
    ) -> None:
        assert sample_aggregated.total_incl_tax == Decimal("1727.50")

    def test_min_one_breakdown(self) -> None:
        with pytest.raises(ValidationError, match="tax_breakdowns"):
            AggregatedTransactionData(
                seller_siren="123456789",
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                operation_category=OperationCategory.DELIVERY,
                tax_breakdowns=[],
            )


class TestEReportingSubmission:
    """Tests du modèle EReportingSubmission."""

    def test_individual_with_transaction(
        self, sample_transaction: TransactionData
    ) -> None:
        sub = EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.INDIVIDUAL,
            transaction_data=sample_transaction,
        )
        assert sub.transmission_mode == EReportingTransmissionMode.INDIVIDUAL
        assert sub.transaction_data is not None
        assert sub.aggregated_data is None
        assert sub.payment_data is None

    def test_aggregated_with_data(
        self, sample_aggregated: AggregatedTransactionData
    ) -> None:
        sub = EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.AGGREGATED,
            aggregated_data=sample_aggregated,
        )
        assert sub.transmission_mode == EReportingTransmissionMode.AGGREGATED
        assert sub.aggregated_data is not None

    def test_with_payment(self, sample_payment: PaymentData) -> None:
        sub = EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.INDIVIDUAL,
            payment_data=sample_payment,
        )
        assert sub.payment_data is not None

    def test_auto_submission_id(self) -> None:
        s1 = EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.INDIVIDUAL,
        )
        s2 = EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.INDIVIDUAL,
        )
        assert s1.submission_id != s2.submission_id

    def test_has_created_at(self) -> None:
        sub = EReportingSubmission(
            transmission_mode=EReportingTransmissionMode.INDIVIDUAL,
        )
        assert sub.created_at is not None


class TestTransmissionSchedule:
    """Tests du modèle TransmissionSchedule."""

    def test_real_normal(self) -> None:
        schedule = TransmissionSchedule(
            vat_regime=VATRegime.REAL_NORMAL_MONTHLY,
            transaction_frequency="tous les 10 jours",
            payment_frequency="mensuel",
        )
        assert schedule.vat_regime == VATRegime.REAL_NORMAL_MONTHLY
        assert schedule.payment_frequency == "mensuel"

    def test_franchise(self) -> None:
        schedule = TransmissionSchedule(
            vat_regime=VATRegime.FRANCHISE,
            transaction_frequency="mensuel",
            payment_frequency=None,
        )
        assert schedule.payment_frequency is None
