"""Tests des montants calculés d'une ligne de facture."""

from decimal import Decimal

import pytest

from facturx_fr.models import InvoiceLine


@pytest.mark.parametrize(
    ("discount", "charge", "expected"),
    [
        (None, None, Decimal("200.00")),
        (Decimal("15.00"), None, Decimal("185.00")),
        (None, Decimal("5.00"), Decimal("205.00")),
        (Decimal("15.00"), Decimal("5.00"), Decimal("190.00")),
    ],
    ids=["none", "discount", "charge", "both"],
)
def test_line_total_excl_tax(
    discount: Decimal | None, charge: Decimal | None, expected: Decimal
) -> None:
    """Le total HT applique la remise et la majoration de ligne."""
    line = InvoiceLine(
        description="Produit",
        quantity=Decimal("2"),
        unit_price=Decimal("100.00"),
        discount_amount=discount,
        charge_amount=charge,
    )
    assert line.line_total_excl_tax == expected
