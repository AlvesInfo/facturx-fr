"""Tests des sérialiseurs Django → dict."""

from decimal import Decimal

import pytest

from facturx_fr.contrib.django.serializers import invoice_line_to_dict, invoice_to_dict


@pytest.mark.django_db
class TestInvoiceToDict:
    """Sérialisation d'une facture complète."""

    def test_full_invoice(self, sample_invoice):
        data = invoice_to_dict(sample_invoice)

        assert data["id"] == sample_invoice.pk
        assert data["number"] == "FA-2026-001"
        assert data["issue_date"] == "2026-09-15"
        assert data["due_date"] == "2026-10-15"
        assert data["seller"]["siren"] == "123456789"
        assert data["buyer"]["name"] == "LunettesPlus SA"
        assert data["payment"]["iban"] == "FR7630001007941234567890185"
        assert data["has_xml"] is False
        assert data["has_pdf"] is False
        assert len(data["lines"]) == 2
        assert data["created_at"] == sample_invoice.created_at.isoformat()

    def test_without_due_date(self, sample_invoice):
        sample_invoice.due_date = None
        assert invoice_to_dict(sample_invoice)["due_date"] is None


@pytest.mark.django_db
def test_invoice_line_to_dict(sample_invoice):
    """Les montants d'une ligne sont sérialisés en chaînes."""
    line = sample_invoice.lines.order_by("line_number").first()
    data = invoice_line_to_dict(line)

    assert data["line_number"] == 1
    assert data["description"] == "Monture Ray-Ban Aviator"
    assert Decimal(data["quantity"]) == Decimal("10")
    assert Decimal(data["unit_price"]) == Decimal("85.00")
    assert Decimal(data["line_total_excl_tax"]) == Decimal("850.00")
    assert Decimal(data["line_vat_amount"]) == Decimal("170.00")
    assert Decimal(data["line_total_incl_tax"]) == Decimal("1020.00")
