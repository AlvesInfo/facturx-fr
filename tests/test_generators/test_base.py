"""Tests de GenerationResult et des garde-fous du FacturXGenerator."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from facturx_fr.generators.base import GenerationResult
from facturx_fr.generators.facturx import FacturXGenerator
from facturx_fr.models import Address, Invoice, InvoiceLine, Party
from facturx_fr.models.enums import OperationCategory


@pytest.fixture
def minimal_invoice() -> Invoice:
    """Facture minimale pour les tests de génération."""
    return Invoice(
        number="FA-BASE-001",
        issue_date=date(2026, 9, 15),
        seller=Party(
            name="Vendeur",
            address=Address(street="1 rue", city="Paris", postal_code="75001"),
        ),
        buyer=Party(
            name="Acheteur",
            address=Address(street="2 rue", city="Lyon", postal_code="69001"),
        ),
        lines=[
            InvoiceLine(
                description="Produit",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
            ),
        ],
        operation_category=OperationCategory.DELIVERY,
    )


class TestGenerationResult:
    """Tests de la sauvegarde du résultat de génération."""

    def test_save_writes_pdf_when_present(self, tmp_path: Path) -> None:
        """Le PDF est privilégié quand il est disponible."""
        result = GenerationResult(xml_bytes=b"<xml/>", pdf_bytes=b"%PDF-1.7")
        target = tmp_path / "facture.pdf"

        result.save(str(target))

        assert target.read_bytes() == b"%PDF-1.7"

    def test_save_writes_xml_without_pdf(self, tmp_path: Path) -> None:
        """Sans PDF, c'est le XML qui est écrit."""
        result = GenerationResult(xml_bytes=b"<xml/>")
        target = tmp_path / "facture.xml"

        result.save(str(target))

        assert target.read_bytes() == b"<xml/>"


class TestFacturXGeneratorErrors:
    """Tests des erreurs du générateur Factur-X."""

    @pytest.mark.parametrize("kwargs", [{}, {"pdf_bytes": "pas-des-bytes"}])
    def test_generate_requires_pdf_bytes(
        self, minimal_invoice: Invoice, kwargs: dict[str, object]
    ) -> None:
        """L'absence (ou le mauvais type) de pdf_bytes lève ValueError."""
        generator = FacturXGenerator()
        with pytest.raises(ValueError, match="pdf_bytes"):
            generator.generate(minimal_invoice, **kwargs)
