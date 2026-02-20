"""Fixtures partagées pour les tests e-reporting."""

from datetime import date
from decimal import Decimal

import pytest

from facturx_fr.ereporting.models import (
    AggregatedTransactionData,
    PaymentData,
    TaxBreakdown,
    TransactionData,
)
from facturx_fr.ereporting.reporter import EReporter
from facturx_fr.models.enums import (
    EReportingTransactionType,
    InvoiceTypeCode,
    OperationCategory,
    UnitOfMeasure,
    VATCategory,
    VATRegime,
)
from facturx_fr.models.invoice import Invoice, InvoiceLine
from facturx_fr.models.party import Address, Party


@pytest.fixture
def sample_transaction() -> TransactionData:
    """Transaction B2C domestique de test."""
    return TransactionData(
        seller_siren="123456789",
        transaction_type=EReportingTransactionType.B2C_DOMESTIC,
        invoice_date=date(2026, 9, 15),
        invoice_number="FA-B2C-001",
        operation_category=OperationCategory.DELIVERY,
        total_excl_tax=Decimal("100.00"),
        vat_amount=Decimal("20.00"),
        vat_rate=Decimal("20.0"),
    )


@pytest.fixture
def sample_international_transaction() -> TransactionData:
    """Transaction B2B intracommunautaire de test."""
    return TransactionData(
        seller_siren="123456789",
        transaction_type=EReportingTransactionType.B2B_INTRA_EU,
        invoice_date=date(2026, 9, 20),
        invoice_number="FA-EU-001",
        operation_category=OperationCategory.DELIVERY,
        total_excl_tax=Decimal("500.00"),
        vat_amount=Decimal("0.00"),
        vat_rate=Decimal("0.0"),
        country_code="DE",
    )


@pytest.fixture
def sample_payment() -> PaymentData:
    """Données de paiement de test."""
    return PaymentData(
        seller_siren="123456789",
        cashing_date=date(2026, 10, 1),
        cashed_amount=Decimal("120.00"),
        invoice_reference="FA-2026-042",
    )


@pytest.fixture
def sample_aggregated() -> AggregatedTransactionData:
    """Données agrégées de test."""
    return AggregatedTransactionData(
        seller_siren="123456789",
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        operation_category=OperationCategory.DELIVERY,
        tax_breakdowns=[
            TaxBreakdown(
                vat_rate=Decimal("20.0"),
                taxable_amount=Decimal("1000.00"),
                vat_amount=Decimal("200.00"),
            ),
            TaxBreakdown(
                vat_rate=Decimal("5.5"),
                taxable_amount=Decimal("500.00"),
                vat_amount=Decimal("27.50"),
            ),
        ],
    )


@pytest.fixture
def ereporter_monthly() -> EReporter:
    """EReporter avec régime réel normal mensuel."""
    return EReporter(
        seller_siren="123456789",
        vat_regime=VATRegime.REAL_NORMAL_MONTHLY,
    )


@pytest.fixture
def ereporter_franchise() -> EReporter:
    """EReporter avec régime franchise en base."""
    return EReporter(
        seller_siren="123456789",
        vat_regime=VATRegime.FRANCHISE,
    )


@pytest.fixture
def sample_invoice() -> Invoice:
    """Facture de test pour conversion e-reporting."""
    return Invoice(
        number="FA-2026-042",
        issue_date=date(2026, 9, 15),
        due_date=date(2026, 10, 15),
        type_code=InvoiceTypeCode.INVOICE,
        currency="EUR",
        operation_category=OperationCategory.DELIVERY,
        vat_on_debits=False,
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
                vat_category=VATCategory.STANDARD,
            ),
            InvoiceLine(
                description="Verres progressifs Essilor",
                quantity=Decimal("10"),
                unit=UnitOfMeasure.UNIT,
                unit_price=Decimal("35.00"),
                vat_rate=Decimal("20.0"),
                vat_category=VATCategory.STANDARD,
            ),
        ],
    )
