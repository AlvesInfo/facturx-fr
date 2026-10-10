"""Tests complémentaires de l'EReporter : exonération et agrégats invalides."""

from datetime import date
from decimal import Decimal

import pytest

from facturx_fr.ereporting.errors import EReportingValidationError
from facturx_fr.ereporting.models import AggregatedTransactionData, TaxBreakdown
from facturx_fr.ereporting.reporter import EReporter
from facturx_fr.models import Address, Invoice, InvoiceLine, Party
from facturx_fr.models.enums import (
    EReportingTransactionType,
    OperationCategory,
    VATCategory,
)


def _invoice_with_category(category: VATCategory) -> Invoice:
    return Invoice(
        number="FA-EXO-001",
        issue_date=date(2026, 9, 15),
        seller=Party(
            name="Vendeur",
            siren="123456789",
            address=Address(street="1 rue", city="Paris", postal_code="75001"),
        ),
        buyer=Party(
            name="Acheteur",
            address=Address(street="2 rue", city="Lyon", postal_code="69001"),
        ),
        lines=[
            InvoiceLine(
                description="Prestation",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                vat_rate=Decimal("0"),
                vat_category=category,
            ),
        ],
        operation_category=OperationCategory.SERVICE,
    )


@pytest.mark.parametrize(
    "category",
    [VATCategory.EXEMPT, VATCategory.NOT_SUBJECT, VATCategory.EXPORT],
    ids=["exempt", "not_subject", "export"],
)
def test_transaction_from_invoice_detects_exemption(
    ereporter_monthly: EReporter, category: VATCategory
) -> None:
    """Les catégories E, O et G marquent la transaction comme exonérée."""
    txn = ereporter_monthly.transaction_from_invoice(
        _invoice_with_category(category),
        transaction_type=EReportingTransactionType.B2C_DOMESTIC,
    )
    assert txn.vat_exemption is True


def test_prepare_aggregated_raises_on_invalid(ereporter_monthly: EReporter) -> None:
    """Un agrégat d'un autre SIREN est rejeté avec la liste des erreurs."""
    aggregated = AggregatedTransactionData(
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
    with pytest.raises(EReportingValidationError, match="Agrégat invalide") as exc_info:
        ereporter_monthly.prepare_aggregated(aggregated)
    assert exc_info.value.errors
