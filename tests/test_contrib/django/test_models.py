"""Tests des modèles Django pour la facturation électronique."""

from datetime import date
from decimal import Decimal

import pytest

from facturx_fr.contrib.django.models import Invoice, InvoiceLine
from facturx_fr.models.enums import (
    InvoiceTypeCode,
    OperationCategory,
    VATCategory,
)
from facturx_fr.models.invoice import Invoice as PydanticInvoice
from facturx_fr.models.invoice import InvoiceLine as PydanticInvoiceLine
from facturx_fr.models.party import Address, Party


class TestInvoiceModel:
    """Tests du modèle Invoice."""

    def test_create_with_lines(self, sample_invoice):
        """Vérifie la création transactionnelle Invoice + lignes."""
        assert sample_invoice.pk is not None
        assert sample_invoice.number == "FA-2026-001"
        assert sample_invoice.lines.count() == 2

    def test_str(self, sample_invoice):
        """Vérifie la représentation textuelle."""
        assert str(sample_invoice) == "Facture FA-2026-001"

    def test_to_pydantic(self, sample_invoice):
        """Vérifie la conversion Django → Pydantic."""
        pydantic = sample_invoice.to_pydantic()

        assert isinstance(pydantic, PydanticInvoice)
        assert pydantic.number == "FA-2026-001"
        assert pydantic.issue_date == date(2026, 9, 15)
        assert pydantic.type_code == InvoiceTypeCode.INVOICE
        assert pydantic.currency == "EUR"
        assert pydantic.operation_category == OperationCategory.DELIVERY

        # Vendeur
        assert pydantic.seller.name == "OptiPaulo SARL"
        assert pydantic.seller.siren == "123456789"
        assert pydantic.seller.address.city == "Créteil"

        # Acheteur
        assert pydantic.buyer.name == "LunettesPlus SA"
        assert pydantic.buyer.siren == "987654321"

        # Lignes
        assert len(pydantic.lines) == 2
        assert pydantic.lines[0].description == "Monture Ray-Ban Aviator"
        assert pydantic.lines[1].description == "Verres progressifs"

        # Paiement
        assert pydantic.payment_means is not None
        assert pydantic.payment_means.bank_account.iban == "FR7630001007941234567890185"

    def test_to_pydantic_totals_consistent(self, sample_invoice):
        """Vérifie que les totaux Pydantic sont cohérents."""
        pydantic = sample_invoice.to_pydantic()

        # Ligne 1 : 10 × 85.00 = 850.00 HT
        # Ligne 2 : 20 × 45.50 = 910.00 HT
        # Total HT = 1760.00
        expected_total_ht = Decimal("1760.00")
        assert pydantic.total_excl_tax == expected_total_ht

        # TVA 20% = 352.00
        expected_vat = Decimal("352.00")
        assert pydantic.total_vat == expected_vat

        # TTC = 2112.00
        assert pydantic.total_incl_tax == expected_total_ht + expected_vat

    def test_from_pydantic(self, db, sample_pydantic_invoice):
        """Vérifie la conversion Pydantic → Django (non sauvée)."""
        django_invoice = Invoice.from_pydantic(sample_pydantic_invoice)

        assert django_invoice.pk is None  # non sauvée
        assert django_invoice.number == "FA-2026-001"
        assert django_invoice.seller_name == "OptiPaulo SARL"
        assert django_invoice.seller_siren == "123456789"
        assert django_invoice.buyer_name == "LunettesPlus SA"
        assert django_invoice.payment_iban == "FR7630001007941234567890185"
        assert django_invoice.payment_bic == "BDFEFRPP"

    def test_from_pydantic_no_payment(self, db):
        """Vérifie from_pydantic sans moyen de paiement."""
        invoice = PydanticInvoice(
            number="FA-2026-002",
            issue_date=date(2026, 9, 15),
            operation_category=OperationCategory.SERVICE,
            seller=Party(
                name="Vendeur",
                siren="111222333",
                address=Address(
                    street="1 rue",
                    city="Paris",
                    postal_code="75001",
                ),
            ),
            buyer=Party(
                name="Acheteur",
                siren="444555666",
                address=Address(
                    street="2 rue",
                    city="Lyon",
                    postal_code="69001",
                ),
            ),
            lines=[
                PydanticInvoiceLine(
                    description="Service",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100"),
                ),
            ],
        )

        django_invoice = Invoice.from_pydantic(invoice)
        assert django_invoice.payment_iban == ""
        assert django_invoice.payment_bic == ""

    @pytest.mark.django_db
    def test_siren_check_constraint(self):
        """Vérifie que la CheckConstraint SIREN est active."""
        from django.db import IntegrityError

        invoice = Invoice(
            number="FA-BAD",
            issue_date=date(2026, 1, 1),
            operation_category="delivery",
            seller_name="Test",
            seller_siren="ABCDEFGHI",  # invalide
            seller_street="1 rue",
            seller_city="Paris",
            seller_postal_code="75001",
            buyer_name="Test",
            buyer_siren="123456789",
            buyer_street="2 rue",
            buyer_city="Lyon",
            buyer_postal_code="69001",
        )
        with pytest.raises(IntegrityError):
            invoice.save()

    @pytest.mark.django_db
    def test_unique_number(self, sample_invoice, sample_pydantic_invoice):
        """Vérifie l'unicité du numéro de facture."""
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Invoice.create_with_lines(sample_pydantic_invoice)


class TestInvoiceLineModel:
    """Tests du modèle InvoiceLine."""

    def test_line_totals(self, sample_invoice):
        """Vérifie les totaux calculés d'une ligne."""
        line = sample_invoice.lines.first()

        # Ligne 1 : 10 × 85.00 = 850.00 HT
        assert line.line_total_excl_tax == Decimal("850.0000")
        assert line.line_vat_amount == Decimal("170.00")
        assert line.line_total_incl_tax == Decimal("1020.00")

    def test_str(self, sample_invoice):
        """Vérifie la représentation textuelle."""
        line = sample_invoice.lines.first()
        assert "Ligne 1" in str(line)

    def test_ordering(self, sample_invoice):
        """Vérifie que les lignes sont ordonnées par numéro."""
        lines = list(sample_invoice.lines.all())
        assert lines[0].line_number < lines[1].line_number

    def test_to_pydantic(self, sample_invoice):
        """Vérifie la conversion ligne Django → Pydantic."""
        line = sample_invoice.lines.first()
        pydantic_line = line.to_pydantic()

        assert isinstance(pydantic_line, PydanticInvoiceLine)
        assert pydantic_line.line_number == 1
        assert pydantic_line.description == "Monture Ray-Ban Aviator"
        assert pydantic_line.vat_category == VATCategory.STANDARD

    def test_from_pydantic(self, sample_invoice):
        """Vérifie la conversion ligne Pydantic → Django."""
        pydantic_line = PydanticInvoiceLine(
            description="Nouveau produit",
            quantity=Decimal("5"),
            unit_price=Decimal("30.00"),
        )

        django_line = InvoiceLine.from_pydantic(
            pydantic_line, invoice=sample_invoice, idx=3
        )

        assert django_line.pk is None
        assert django_line.line_number == 3
        assert django_line.description == "Nouveau produit"
        assert django_line.invoice == sample_invoice
