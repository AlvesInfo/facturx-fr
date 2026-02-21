"""Tests pour les modèles de données PDP."""

from datetime import UTC, date, datetime
from decimal import Decimal

from facturx_fr.models.enums import InvoiceStatus
from facturx_fr.pdp.models import (
    DirectoryEntry,
    InvoiceSearchFilters,
    InvoiceSearchResponse,
    InvoiceSearchResult,
    StatusUpdateResponse,
)


class TestInvoiceSearchFilters:
    """Vérifie les valeurs par défaut et la validation des filtres."""

    def test_defaults(self) -> None:
        filters = InvoiceSearchFilters()
        assert filters.status is None
        assert filters.date_from is None
        assert filters.date_to is None
        assert filters.seller_siren is None
        assert filters.buyer_siren is None
        assert filters.direction is None
        assert filters.page == 1
        assert filters.page_size == 50

    def test_custom_values(self) -> None:
        filters = InvoiceSearchFilters(
            status=InvoiceStatus.APPROUVEE,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            seller_siren="123456789",
            buyer_siren="987654321",
            direction="sent",
            page=3,
            page_size=25,
        )
        assert filters.status == InvoiceStatus.APPROUVEE
        assert filters.date_from == date(2026, 1, 1)
        assert filters.direction == "sent"
        assert filters.page == 3
        assert filters.page_size == 25


class TestInvoiceSearchResult:
    """Vérifie la création d'un résultat de recherche."""

    def test_all_fields(self) -> None:
        result = InvoiceSearchResult(
            invoice_id="MEM-000001",
            number="FA-2026-042",
            issue_date=date(2026, 9, 15),
            seller_name="OptiPaulo SARL",
            buyer_name="LunettesPlus SA",
            total_incl_tax=Decimal("1200.00"),
            currency="EUR",
            status=InvoiceStatus.DEPOSEE,
            direction="sent",
        )
        assert result.invoice_id == "MEM-000001"
        assert result.number == "FA-2026-042"
        assert result.total_incl_tax == Decimal("1200.00")
        assert result.status == InvoiceStatus.DEPOSEE
        assert result.direction == "sent"


class TestInvoiceSearchResponse:
    """Vérifie la pagination de la réponse de recherche."""

    def test_pagination(self) -> None:
        response = InvoiceSearchResponse(
            results=[],
            total_count=150,
            page=2,
            page_size=50,
        )
        assert response.total_count == 150
        assert response.page == 2
        assert response.page_size == 50
        assert response.results == []


class TestStatusUpdateResponse:
    """Vérifie la réponse de mise à jour de statut."""

    def test_creation(self) -> None:
        now = datetime.now(UTC)
        response = StatusUpdateResponse(
            invoice_id="MEM-000001",
            status=InvoiceStatus.APPROUVEE,
            updated_at=now,
        )
        assert response.invoice_id == "MEM-000001"
        assert response.status == InvoiceStatus.APPROUVEE
        assert response.updated_at == now


class TestDirectoryEntry:
    """Vérifie la création d'une entrée annuaire."""

    def test_creation(self) -> None:
        entry = DirectoryEntry(
            siren="123456789",
            company_name="OptiPaulo SARL",
            platform_id="PDP-001",
            platform_name="Pennylane",
            electronic_address="0009:12345678900015",
            registration_date=date(2026, 6, 1),
        )
        assert entry.siren == "123456789"
        assert entry.company_name == "OptiPaulo SARL"
        assert entry.platform_id == "PDP-001"
        assert entry.electronic_address == "0009:12345678900015"
        assert entry.registration_date == date(2026, 6, 1)

    def test_without_registration_date(self) -> None:
        entry = DirectoryEntry(
            siren="123456789",
            company_name="OptiPaulo SARL",
            platform_id="PDP-001",
            platform_name="Pennylane",
            electronic_address="0009:12345678900015",
        )
        assert entry.registration_date is None
