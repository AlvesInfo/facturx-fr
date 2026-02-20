"""Tests d'intégration pour le connecteur PDP en mémoire."""

from datetime import date
from decimal import Decimal

import pytest

from facturx_fr.models.enums import InvoiceStatus
from facturx_fr.models.invoice import Invoice
from facturx_fr.pdp.connectors.memory import MemoryPDP
from facturx_fr.pdp.errors import PDPNotFoundError
from facturx_fr.pdp.models import (
    DirectoryEntry,
    InvoiceSearchFilters,
    InvoiceSearchResponse,
    LifecycleResponse,
    StatusUpdateResponse,
    SubmissionResponse,
)


class TestSubmit:
    """Tests de soumission de facture."""

    async def test_submit_returns_submission_response(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        assert isinstance(result, SubmissionResponse)

    async def test_submit_initial_status_deposee(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        assert result.status == InvoiceStatus.DEPOSEE

    async def test_submit_generates_unique_ids(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        r1 = await memory_pdp.submit(sample_invoice)
        r2 = await memory_pdp.submit(sample_invoice)
        assert r1.invoice_id != r2.invoice_id

    async def test_submit_stores_xml(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        xml = b"<Invoice>test</Invoice>"
        result = await memory_pdp.submit(sample_invoice, xml_bytes=xml)
        stored_xml = await memory_pdp.get_invoice(result.invoice_id)
        assert stored_xml == xml

    async def test_submit_without_xml_uses_placeholder(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        stored_xml = await memory_pdp.get_invoice(result.invoice_id)
        assert stored_xml == b"<placeholder/>"

    async def test_submit_has_timestamp(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        assert result.submitted_at is not None


class TestGetStatus:
    """Tests de consultation du statut courant."""

    async def test_get_status_after_submit(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        status = await memory_pdp.get_status(result.invoice_id)
        assert status == InvoiceStatus.DEPOSEE

    async def test_get_status_unknown_id(self, memory_pdp: MemoryPDP) -> None:
        with pytest.raises(PDPNotFoundError):
            await memory_pdp.get_status("UNKNOWN-ID")

    async def test_get_status_returns_invoice_status(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        status = await memory_pdp.get_status(result.invoice_id)
        assert isinstance(status, InvoiceStatus)


class TestGetLifecycle:
    """Tests de récupération du cycle de vie."""

    async def test_lifecycle_after_submit(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        lifecycle = await memory_pdp.get_lifecycle(result.invoice_id)
        assert isinstance(lifecycle, LifecycleResponse)
        assert lifecycle.invoice_id == result.invoice_id
        assert lifecycle.current_status == InvoiceStatus.DEPOSEE

    async def test_lifecycle_initial_event(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        lifecycle = await memory_pdp.get_lifecycle(result.invoice_id)
        assert len(lifecycle.events) == 1
        assert lifecycle.events[0].status == InvoiceStatus.DEPOSEE

    async def test_lifecycle_after_transitions(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.EMISE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.RECUE)

        lifecycle = await memory_pdp.get_lifecycle(result.invoice_id)
        assert lifecycle.current_status == InvoiceStatus.RECUE
        # 1 initial (DEPOSEE) + 2 transitions
        assert len(lifecycle.events) == 3
        assert lifecycle.events[0].status == InvoiceStatus.DEPOSEE
        assert lifecycle.events[1].status == InvoiceStatus.EMISE
        assert lifecycle.events[2].status == InvoiceStatus.RECUE

    async def test_lifecycle_unknown_id(self, memory_pdp: MemoryPDP) -> None:
        with pytest.raises(PDPNotFoundError):
            await memory_pdp.get_lifecycle("UNKNOWN-ID")


class TestGetInvoice:
    """Tests de récupération du XML d'une facture."""

    async def test_get_invoice_xml(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        xml = b"<Invoice><ID>FA-2026-042</ID></Invoice>"
        result = await memory_pdp.submit(sample_invoice, xml_bytes=xml)
        stored_xml = await memory_pdp.get_invoice(result.invoice_id)
        assert stored_xml == xml

    async def test_get_invoice_unknown_id(self, memory_pdp: MemoryPDP) -> None:
        with pytest.raises(PDPNotFoundError):
            await memory_pdp.get_invoice("UNKNOWN-ID")


class TestSearchInvoices:
    """Tests de recherche de factures."""

    async def test_search_all(
        self,
        memory_pdp: MemoryPDP,
        sample_invoice: Invoice,
        second_invoice: Invoice,
    ) -> None:
        await memory_pdp.submit(sample_invoice)
        await memory_pdp.submit(second_invoice)
        response = await memory_pdp.search_invoices()
        assert isinstance(response, InvoiceSearchResponse)
        assert response.total_count == 2
        assert len(response.results) == 2

    async def test_search_by_status(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.EMISE)

        # La facture est maintenant EMISE, pas DEPOSEE
        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(status=InvoiceStatus.DEPOSEE)
        )
        assert response.total_count == 0

        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(status=InvoiceStatus.EMISE)
        )
        assert response.total_count == 1

    async def test_search_by_date_range(
        self,
        memory_pdp: MemoryPDP,
        sample_invoice: Invoice,
        second_invoice: Invoice,
    ) -> None:
        await memory_pdp.submit(sample_invoice)  # issue_date=2026-09-15
        await memory_pdp.submit(second_invoice)  # issue_date=2026-10-01

        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(
                date_from=date(2026, 9, 20),
                date_to=date(2026, 10, 31),
            )
        )
        assert response.total_count == 1
        assert response.results[0].number == "FA-2026-099"

    async def test_search_by_seller_siren(
        self,
        memory_pdp: MemoryPDP,
        sample_invoice: Invoice,
        second_invoice: Invoice,
    ) -> None:
        await memory_pdp.submit(sample_invoice)
        await memory_pdp.submit(second_invoice)

        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(seller_siren="123456789")
        )
        assert response.total_count == 1
        assert response.results[0].seller_name == "OptiPaulo SARL"

    async def test_search_by_buyer_siren(
        self,
        memory_pdp: MemoryPDP,
        sample_invoice: Invoice,
        second_invoice: Invoice,
    ) -> None:
        await memory_pdp.submit(sample_invoice)
        await memory_pdp.submit(second_invoice)

        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(buyer_siren="987654321")
        )
        assert response.total_count == 1
        assert response.results[0].buyer_name == "LunettesPlus SA"

    async def test_search_by_direction(
        self,
        memory_pdp: MemoryPDP,
        sample_invoice: Invoice,
        second_invoice: Invoice,
    ) -> None:
        await memory_pdp.submit(sample_invoice)  # direction="sent"
        memory_pdp.add_received_invoice(second_invoice, b"<xml/>")  # direction="received"

        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(direction="sent")
        )
        assert response.total_count == 1
        assert response.results[0].direction == "sent"

        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(direction="received")
        )
        assert response.total_count == 1
        assert response.results[0].direction == "received"

    async def test_search_pagination(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        # Soumettre 5 factures
        for i in range(5):
            inv = sample_invoice.model_copy(update={"number": f"FA-{i:03d}"})
            await memory_pdp.submit(inv)

        # Page 1, taille 2
        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(page=1, page_size=2)
        )
        assert response.total_count == 5
        assert len(response.results) == 2
        assert response.page == 1

        # Page 3, taille 2 → 1 résultat
        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(page=3, page_size=2)
        )
        assert len(response.results) == 1

    async def test_search_empty(self, memory_pdp: MemoryPDP) -> None:
        response = await memory_pdp.search_invoices()
        assert response.total_count == 0
        assert response.results == []

    async def test_search_no_filters(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        await memory_pdp.submit(sample_invoice)
        response = await memory_pdp.search_invoices(None)
        assert response.total_count == 1


class TestUpdateStatus:
    """Tests de mise à jour de statut."""

    async def test_valid_transition(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        update = await memory_pdp.update_status(result.invoice_id, InvoiceStatus.EMISE)
        assert isinstance(update, StatusUpdateResponse)
        assert update.status == InvoiceStatus.EMISE
        assert update.invoice_id == result.invoice_id

    async def test_status_updated_in_get_status(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.EMISE)
        status = await memory_pdp.get_status(result.invoice_id)
        assert status == InvoiceStatus.EMISE

    async def test_invalid_transition(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        # DEPOSEE → APPROUVEE n'est pas une transition valide
        with pytest.raises(ValueError, match="Transition non autorisée"):
            await memory_pdp.update_status(result.invoice_id, InvoiceStatus.APPROUVEE)

    async def test_refusee_requires_reason(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        # Avancer jusqu'à PRISE_EN_CHARGE
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.EMISE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.RECUE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.MISE_A_DISPOSITION)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.PRISE_EN_CHARGE)

        # REFUSEE sans motif → erreur
        with pytest.raises(ValueError, match="motif"):
            await memory_pdp.update_status(result.invoice_id, InvoiceStatus.REFUSEE)

    async def test_refusee_with_reason(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.EMISE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.RECUE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.MISE_A_DISPOSITION)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.PRISE_EN_CHARGE)

        update = await memory_pdp.update_status(
            result.invoice_id,
            InvoiceStatus.REFUSEE,
            reason="Montant incorrect",
            reason_code="REF-001",
        )
        assert update.status == InvoiceStatus.REFUSEE

    async def test_encaissee_with_amount(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        result = await memory_pdp.submit(sample_invoice)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.EMISE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.RECUE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.MISE_A_DISPOSITION)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.PRISE_EN_CHARGE)
        await memory_pdp.update_status(result.invoice_id, InvoiceStatus.APPROUVEE)

        update = await memory_pdp.update_status(
            result.invoice_id,
            InvoiceStatus.ENCAISSEE,
            amount=Decimal("1200.00"),
        )
        assert update.status == InvoiceStatus.ENCAISSEE

    async def test_update_unknown_id(self, memory_pdp: MemoryPDP) -> None:
        with pytest.raises(PDPNotFoundError):
            await memory_pdp.update_status("UNKNOWN-ID", InvoiceStatus.EMISE)


class TestLookupDirectory:
    """Tests de consultation de l'annuaire."""

    async def test_lookup_existing(self, memory_pdp: MemoryPDP) -> None:
        entry = DirectoryEntry(
            siren="123456789",
            company_name="OptiPaulo SARL",
            platform_id="PDP-001",
            platform_name="Pennylane",
            electronic_address="0009:12345678900015",
        )
        memory_pdp.add_directory_entry(entry)

        found = await memory_pdp.lookup_directory("123456789")
        assert found.siren == "123456789"
        assert found.company_name == "OptiPaulo SARL"
        assert found.platform_name == "Pennylane"

    async def test_lookup_unknown_siren(self, memory_pdp: MemoryPDP) -> None:
        with pytest.raises(PDPNotFoundError, match="SIREN introuvable"):
            await memory_pdp.lookup_directory("000000000")


class TestReceivedInvoices:
    """Tests de réception de factures entrantes."""

    async def test_add_received_invoice(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        xml = b"<Invoice>received</Invoice>"
        invoice_id = memory_pdp.add_received_invoice(sample_invoice, xml)
        assert invoice_id.startswith("MEM-")

        # Vérifier le XML
        stored_xml = await memory_pdp.get_invoice(invoice_id)
        assert stored_xml == xml

    async def test_received_direction(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        memory_pdp.add_received_invoice(sample_invoice, b"<xml/>")

        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(direction="received")
        )
        assert response.total_count == 1
        assert response.results[0].direction == "received"

    async def test_received_initial_status(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        invoice_id = memory_pdp.add_received_invoice(sample_invoice, b"<xml/>")
        status = await memory_pdp.get_status(invoice_id)
        assert status == InvoiceStatus.DEPOSEE


class TestFullFlow:
    """Tests de parcours complet du cycle de vie."""

    async def test_full_lifecycle(
        self, memory_pdp: MemoryPDP, sample_invoice: Invoice
    ) -> None:
        """Parcours complet : submit → transitions → get_lifecycle → get_invoice."""
        xml = b"<Invoice>full-flow</Invoice>"

        # 1. Soumission
        submission = await memory_pdp.submit(sample_invoice, xml_bytes=xml)
        assert submission.status == InvoiceStatus.DEPOSEE

        # 2. Transitions du cycle de vie
        await memory_pdp.update_status(submission.invoice_id, InvoiceStatus.EMISE)
        await memory_pdp.update_status(submission.invoice_id, InvoiceStatus.RECUE)
        await memory_pdp.update_status(
            submission.invoice_id, InvoiceStatus.MISE_A_DISPOSITION
        )
        await memory_pdp.update_status(
            submission.invoice_id, InvoiceStatus.PRISE_EN_CHARGE
        )
        await memory_pdp.update_status(submission.invoice_id, InvoiceStatus.APPROUVEE)
        await memory_pdp.update_status(
            submission.invoice_id, InvoiceStatus.PAIEMENT_TRANSMIS
        )
        await memory_pdp.update_status(
            submission.invoice_id,
            InvoiceStatus.ENCAISSEE,
            amount=Decimal("1200.00"),
        )

        # 3. Vérifier le statut final
        status = await memory_pdp.get_status(submission.invoice_id)
        assert status == InvoiceStatus.ENCAISSEE

        # 4. Vérifier l'historique complet
        lifecycle = await memory_pdp.get_lifecycle(submission.invoice_id)
        assert lifecycle.current_status == InvoiceStatus.ENCAISSEE
        assert len(lifecycle.events) == 8  # initial + 7 transitions

        expected_statuses = [
            InvoiceStatus.DEPOSEE,
            InvoiceStatus.EMISE,
            InvoiceStatus.RECUE,
            InvoiceStatus.MISE_A_DISPOSITION,
            InvoiceStatus.PRISE_EN_CHARGE,
            InvoiceStatus.APPROUVEE,
            InvoiceStatus.PAIEMENT_TRANSMIS,
            InvoiceStatus.ENCAISSEE,
        ]
        for event, expected in zip(lifecycle.events, expected_statuses, strict=True):
            assert event.status == expected

        # 5. Vérifier le XML
        stored_xml = await memory_pdp.get_invoice(submission.invoice_id)
        assert stored_xml == xml

    async def test_submit_and_search(
        self,
        memory_pdp: MemoryPDP,
        sample_invoice: Invoice,
        second_invoice: Invoice,
    ) -> None:
        """Soumission de plusieurs factures et recherche."""
        await memory_pdp.submit(sample_invoice, xml_bytes=b"<xml1/>")
        await memory_pdp.submit(second_invoice, xml_bytes=b"<xml2/>")

        # Recherche par SIREN vendeur
        response = await memory_pdp.search_invoices(
            InvoiceSearchFilters(seller_siren="123456789")
        )
        assert response.total_count == 1
        assert response.results[0].number == "FA-2026-042"

        # Recherche globale
        response = await memory_pdp.search_invoices()
        assert response.total_count == 2

    async def test_mixed_sent_received(
        self,
        memory_pdp: MemoryPDP,
        sample_invoice: Invoice,
        second_invoice: Invoice,
    ) -> None:
        """Factures envoyées et reçues dans le même connecteur."""
        await memory_pdp.submit(sample_invoice)
        memory_pdp.add_received_invoice(second_invoice, b"<xml/>")

        all_invoices = await memory_pdp.search_invoices()
        assert all_invoices.total_count == 2

        sent = await memory_pdp.search_invoices(
            InvoiceSearchFilters(direction="sent")
        )
        assert sent.total_count == 1

        received = await memory_pdp.search_invoices(
            InvoiceSearchFilters(direction="received")
        )
        assert received.total_count == 1
