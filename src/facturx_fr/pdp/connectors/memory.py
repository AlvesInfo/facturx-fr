"""Connecteur PDP en mémoire pour les tests et le développement.

FR: Stocke les factures en mémoire, simule le cycle de vie complet
    via LifecycleManager, et fournit un annuaire simulé. Utile pour
    le développement, les tests unitaires et la démonstration.
EN: Stores invoices in memory, simulates the full lifecycle via
    LifecycleManager, and provides a simulated directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from facturx_fr.lifecycle.manager import LifecycleManager
from facturx_fr.models.enums import InvoiceStatus
from facturx_fr.models.invoice import Invoice
from facturx_fr.pdp.base import BasePDP
from facturx_fr.pdp.errors import PDPNotFoundError
from facturx_fr.pdp.models import (
    DirectoryEntry,
    InvoiceSearchFilters,
    InvoiceSearchResponse,
    InvoiceSearchResult,
    LifecycleEvent,
    LifecycleResponse,
    StatusUpdateResponse,
    SubmissionResponse,
)


@dataclass
class _StoredInvoice:
    """Facture stockée en mémoire avec son cycle de vie."""

    invoice_id: str
    invoice: Invoice
    xml_bytes: bytes
    lifecycle: LifecycleManager
    submitted_at: datetime
    direction: Literal["sent", "received"]
    # Événement initial de dépôt (pas dans LifecycleManager.history
    # car c'est le statut initial, pas une transition)
    initial_event: LifecycleEvent = field(init=False)

    def __post_init__(self) -> None:
        self.initial_event = LifecycleEvent(
            timestamp=self.submitted_at,
            status=InvoiceStatus.DEPOSEE,
        )


class MemoryPDP(BasePDP):
    """Connecteur PDP en mémoire pour les tests et le développement.

    FR: Implémente l'interface BasePDP complète en stockant tout en mémoire.
        Utilise le LifecycleManager pour simuler le cycle de vie.
    EN: Implements the full BasePDP interface with in-memory storage.
        Uses LifecycleManager for lifecycle simulation.
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(api_key="memory", environment="test")
        self._invoices: dict[str, _StoredInvoice] = {}
        self._directory: dict[str, DirectoryEntry] = {}
        self._counter: int = 0

    def _next_id(self) -> str:
        """Génère un identifiant séquentiel."""
        self._counter += 1
        return f"MEM-{self._counter:06d}"

    def _get_stored(self, invoice_id: str) -> _StoredInvoice:
        """Récupère une facture stockée ou lève PDPNotFoundError."""
        stored = self._invoices.get(invoice_id)
        if stored is None:
            msg = f"Facture introuvable : {invoice_id}"
            raise PDPNotFoundError(msg)
        return stored

    # --- Dépôt de facture ---

    async def submit(
        self,
        invoice: Invoice,
        xml_bytes: bytes | None = None,
        pdf_bytes: bytes | None = None,
    ) -> SubmissionResponse:
        """Soumet une facture (stockage en mémoire)."""
        invoice_id = self._next_id()
        now = datetime.now(timezone.utc)

        lifecycle = LifecycleManager(
            invoice_reference=invoice.number,
            initial_status=InvoiceStatus.DEPOSEE,
        )

        stored = _StoredInvoice(
            invoice_id=invoice_id,
            invoice=invoice,
            xml_bytes=xml_bytes or b"<placeholder/>",
            lifecycle=lifecycle,
            submitted_at=now,
            direction="sent",
        )
        self._invoices[invoice_id] = stored

        return SubmissionResponse(
            invoice_id=invoice_id,
            status=InvoiceStatus.DEPOSEE,
            submitted_at=now,
        )

    # --- Consultation statuts ---

    async def get_status(self, invoice_id: str) -> InvoiceStatus:
        """Retourne le statut courant de la facture."""
        stored = self._get_stored(invoice_id)
        return stored.lifecycle.status

    async def get_lifecycle(self, invoice_id: str) -> LifecycleResponse:
        """Retourne l'historique complet du cycle de vie."""
        stored = self._get_stored(invoice_id)
        events = [stored.initial_event, *stored.lifecycle.history]
        return LifecycleResponse(
            invoice_id=invoice_id,
            current_status=stored.lifecycle.status,
            events=events,
        )

    # --- Récupération de facture ---

    async def get_invoice(self, invoice_id: str) -> bytes:
        """Retourne le XML de la facture."""
        stored = self._get_stored(invoice_id)
        return stored.xml_bytes

    # --- Recherche de factures ---

    async def search_invoices(
        self,
        filters: InvoiceSearchFilters | None = None,
    ) -> InvoiceSearchResponse:
        """Recherche des factures avec filtres en mémoire."""
        if filters is None:
            filters = InvoiceSearchFilters()

        results: list[InvoiceSearchResult] = []

        for stored in self._invoices.values():
            inv = stored.invoice
            status = stored.lifecycle.status

            # Filtrage par statut
            if filters.status is not None and status != filters.status:
                continue

            # Filtrage par date
            if filters.date_from is not None and inv.issue_date < filters.date_from:
                continue
            if filters.date_to is not None and inv.issue_date > filters.date_to:
                continue

            # Filtrage par SIREN vendeur
            if (
                filters.seller_siren is not None
                and inv.seller.siren != filters.seller_siren
            ):
                continue

            # Filtrage par SIREN acheteur
            if (
                filters.buyer_siren is not None
                and inv.buyer.siren != filters.buyer_siren
            ):
                continue

            # Filtrage par direction
            if filters.direction is not None and stored.direction != filters.direction:
                continue

            results.append(
                InvoiceSearchResult(
                    invoice_id=stored.invoice_id,
                    number=inv.number,
                    issue_date=inv.issue_date,
                    seller_name=inv.seller.name,
                    buyer_name=inv.buyer.name,
                    total_incl_tax=inv.total_incl_tax,
                    currency=inv.currency,
                    status=status,
                    direction=stored.direction,
                )
            )

        # Pagination
        total_count = len(results)
        start = (filters.page - 1) * filters.page_size
        end = start + filters.page_size
        page_results = results[start:end]

        return InvoiceSearchResponse(
            results=page_results,
            total_count=total_count,
            page=filters.page,
            page_size=filters.page_size,
        )

    # --- Mise à jour de statut ---

    async def update_status(
        self,
        invoice_id: str,
        status: InvoiceStatus,
        *,
        reason: str | None = None,
        reason_code: str | None = None,
        amount: Decimal | None = None,
    ) -> StatusUpdateResponse:
        """Met à jour le statut via le LifecycleManager."""
        stored = self._get_stored(invoice_id)

        # LifecycleManager.transition() valide la transition et le motif
        stored.lifecycle.transition(
            target=status,
            reason=reason,
            reason_code=reason_code,
            amount=amount,
        )

        return StatusUpdateResponse(
            invoice_id=invoice_id,
            status=status,
            updated_at=datetime.now(timezone.utc),
        )

    # --- Consultation annuaire ---

    async def lookup_directory(self, siren: str) -> DirectoryEntry:
        """Consulte l'annuaire simulé."""
        entry = self._directory.get(siren)
        if entry is None:
            msg = f"SIREN introuvable dans l'annuaire : {siren}"
            raise PDPNotFoundError(msg)
        return entry

    # --- Méthodes utilitaires (propres au connecteur mémoire) ---

    def add_directory_entry(self, entry: DirectoryEntry) -> None:
        """Ajoute une entrée à l'annuaire simulé."""
        self._directory[entry.siren] = entry

    def add_received_invoice(self, invoice: Invoice, xml_bytes: bytes) -> str:
        """Simule la réception d'une facture entrante.

        Returns:
            L'identifiant attribué à la facture reçue.
        """
        invoice_id = self._next_id()
        now = datetime.now(timezone.utc)

        lifecycle = LifecycleManager(
            invoice_reference=invoice.number,
            initial_status=InvoiceStatus.DEPOSEE,
        )

        stored = _StoredInvoice(
            invoice_id=invoice_id,
            invoice=invoice,
            xml_bytes=xml_bytes,
            lifecycle=lifecycle,
            submitted_at=now,
            direction="received",
        )
        self._invoices[invoice_id] = stored
        return invoice_id
