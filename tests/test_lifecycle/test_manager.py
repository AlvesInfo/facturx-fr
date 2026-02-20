"""Tests du gestionnaire de cycle de vie des factures.

FR: Vérifie le graphe de transitions, les contraintes métier,
    l'historique des événements et les métadonnées des statuts.
EN: Verifies the transition graph, business constraints,
    event history and status metadata.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from facturx_fr.lifecycle.manager import (
    TERMINAL_STATUSES,
    TRANSITIONS,
    STATUS_METADATA,
    LifecycleManager,
)
from facturx_fr.models.enums import (
    CDARRoleCode,
    InvoiceStatus,
    StatusCategory,
)


class TestTransitions:
    """Tests des transitions valides et invalides."""

    @pytest.mark.parametrize(
        "source,target",
        [
            # Émission
            (InvoiceStatus.DEPOSEE, InvoiceStatus.EMISE),
            (InvoiceStatus.DEPOSEE, InvoiceStatus.REJETEE_EMISSION),
            (InvoiceStatus.EMISE, InvoiceStatus.RECUE),
            (InvoiceStatus.EMISE, InvoiceStatus.REJETEE_RECEPTION),
            # Réception
            (InvoiceStatus.RECUE, InvoiceStatus.MISE_A_DISPOSITION),
            (InvoiceStatus.RECUE, InvoiceStatus.REJETEE_RECEPTION),
            (InvoiceStatus.MISE_A_DISPOSITION, InvoiceStatus.PRISE_EN_CHARGE),
            (InvoiceStatus.MISE_A_DISPOSITION, InvoiceStatus.REJETEE_RECEPTION),
            # Traitement acheteur
            (InvoiceStatus.PRISE_EN_CHARGE, InvoiceStatus.APPROUVEE),
            (InvoiceStatus.PRISE_EN_CHARGE, InvoiceStatus.PARTIELLEMENT_APPROUVEE),
            (InvoiceStatus.PRISE_EN_CHARGE, InvoiceStatus.REFUSEE),
            (InvoiceStatus.PRISE_EN_CHARGE, InvoiceStatus.EN_LITIGE),
            (InvoiceStatus.PRISE_EN_CHARGE, InvoiceStatus.SUSPENDUE),
            (InvoiceStatus.APPROUVEE, InvoiceStatus.PAIEMENT_TRANSMIS),
            (InvoiceStatus.APPROUVEE, InvoiceStatus.ENCAISSEE),
            (InvoiceStatus.PARTIELLEMENT_APPROUVEE, InvoiceStatus.PAIEMENT_TRANSMIS),
            (InvoiceStatus.PARTIELLEMENT_APPROUVEE, InvoiceStatus.REFUSEE),
            (InvoiceStatus.PARTIELLEMENT_APPROUVEE, InvoiceStatus.EN_LITIGE),
            (InvoiceStatus.EN_LITIGE, InvoiceStatus.APPROUVEE),
            (InvoiceStatus.EN_LITIGE, InvoiceStatus.REFUSEE),
            (InvoiceStatus.EN_LITIGE, InvoiceStatus.SUSPENDUE),
            (InvoiceStatus.SUSPENDUE, InvoiceStatus.COMPLETEE),
            (InvoiceStatus.COMPLETEE, InvoiceStatus.PRISE_EN_CHARGE),
            # Paiement
            (InvoiceStatus.PAIEMENT_TRANSMIS, InvoiceStatus.ENCAISSEE),
        ],
    )
    def test_valid_transition(self, source: InvoiceStatus, target: InvoiceStatus) -> None:
        """Vérifie que chaque transition valide du graphe fonctionne."""
        mgr = LifecycleManager("FA-TEST-001", initial_status=source)
        # REFUSEE exige un motif
        if target == InvoiceStatus.REFUSEE:
            event = mgr.transition(target, reason="Motif de test")
        else:
            event = mgr.transition(target)
        assert mgr.status == target
        assert event.status == target

    def test_invalid_transition_raises(self) -> None:
        """Vérifie qu'une transition invalide lève ValueError."""
        mgr = LifecycleManager("FA-TEST-001")
        with pytest.raises(ValueError, match="Transition non autorisée"):
            mgr.transition(InvoiceStatus.ENCAISSEE)

    def test_invalid_transition_from_terminal(self) -> None:
        """Vérifie qu'on ne peut pas sortir d'un état terminal."""
        mgr = LifecycleManager("FA-TEST-001", initial_status=InvoiceStatus.ENCAISSEE)
        with pytest.raises(ValueError, match="Transition non autorisée"):
            mgr.transition(InvoiceStatus.APPROUVEE)

    def test_can_transition_true(self) -> None:
        """Vérifie can_transition pour une transition valide."""
        mgr = LifecycleManager("FA-TEST-001")
        assert mgr.can_transition(InvoiceStatus.EMISE) is True

    def test_can_transition_false(self) -> None:
        """Vérifie can_transition pour une transition invalide."""
        mgr = LifecycleManager("FA-TEST-001")
        assert mgr.can_transition(InvoiceStatus.ENCAISSEE) is False

    def test_all_statuses_have_transitions(self) -> None:
        """Vérifie que tous les statuts InvoiceStatus sont dans le graphe."""
        for status in InvoiceStatus:
            assert status in TRANSITIONS, f"{status} manquant dans TRANSITIONS"

    def test_all_statuses_have_metadata(self) -> None:
        """Vérifie que tous les statuts ont des métadonnées."""
        for status in InvoiceStatus:
            assert status in STATUS_METADATA, f"{status} manquant dans STATUS_METADATA"


class TestTerminalStates:
    """Tests des états terminaux."""

    def test_terminal_statuses_count(self) -> None:
        """Vérifie le nombre d'états terminaux (4)."""
        assert len(TERMINAL_STATUSES) == 4

    def test_terminal_statuses_are_correct(self) -> None:
        """Vérifie les 4 états terminaux."""
        expected = {
            InvoiceStatus.REJETEE_EMISSION,
            InvoiceStatus.REJETEE_RECEPTION,
            InvoiceStatus.REFUSEE,
            InvoiceStatus.ENCAISSEE,
        }
        assert TERMINAL_STATUSES == expected

    def test_is_terminal_true(self) -> None:
        """Vérifie is_terminal pour un état terminal."""
        mgr = LifecycleManager("FA-TEST-001", initial_status=InvoiceStatus.ENCAISSEE)
        assert mgr.is_terminal() is True

    def test_is_terminal_false(self) -> None:
        """Vérifie is_terminal pour un état non terminal."""
        mgr = LifecycleManager("FA-TEST-001")
        assert mgr.is_terminal() is False


class TestMandatoryStatuses:
    """Tests des statuts obligatoires."""

    def test_mandatory_statuses_count(self) -> None:
        """Vérifie le nombre de statuts obligatoires (5)."""
        mandatory = [
            s for s, info in STATUS_METADATA.items()
            if info.category == StatusCategory.MANDATORY
        ]
        assert len(mandatory) == 5

    def test_mandatory_statuses_are_correct(self) -> None:
        """Vérifie les 5 statuts obligatoires."""
        mandatory = {
            s for s, info in STATUS_METADATA.items()
            if info.category == StatusCategory.MANDATORY
        }
        expected = {
            InvoiceStatus.DEPOSEE,
            InvoiceStatus.REJETEE_EMISSION,
            InvoiceStatus.REFUSEE,
            InvoiceStatus.REJETEE_RECEPTION,
            InvoiceStatus.ENCAISSEE,
        }
        assert mandatory == expected

    def test_is_mandatory(self) -> None:
        """Vérifie is_mandatory pour un statut obligatoire."""
        mgr = LifecycleManager("FA-TEST-001")
        assert mgr.is_mandatory(InvoiceStatus.DEPOSEE) is True
        assert mgr.is_mandatory(InvoiceStatus.ENCAISSEE) is True

    def test_is_not_mandatory(self) -> None:
        """Vérifie is_mandatory pour un statut recommandé."""
        mgr = LifecycleManager("FA-TEST-001")
        assert mgr.is_mandatory(InvoiceStatus.EMISE) is False
        assert mgr.is_mandatory(InvoiceStatus.APPROUVEE) is False

    def test_mandatory_events_filter(self) -> None:
        """Vérifie que mandatory_events filtre correctement."""
        mgr = LifecycleManager("FA-TEST-001")
        # Parcours : DEPOSEE → EMISE → RECUE → MISE_A_DISPO → PRISE_EN_CHARGE → REFUSEE
        mgr.transition(InvoiceStatus.EMISE)
        mgr.transition(InvoiceStatus.RECUE)
        mgr.transition(InvoiceStatus.MISE_A_DISPOSITION)
        mgr.transition(InvoiceStatus.PRISE_EN_CHARGE)
        mgr.transition(InvoiceStatus.REFUSEE, reason="Marchandise non conforme")

        mandatory = mgr.mandatory_events()
        # Seul REFUSEE est obligatoire parmi les transitions effectuées
        assert len(mandatory) == 1
        assert mandatory[0].status == InvoiceStatus.REFUSEE


class TestRefusalValidation:
    """Tests de la validation du motif pour REFUSEE."""

    def test_refusee_without_reason_raises(self) -> None:
        """Vérifie que REFUSEE sans motif lève ValueError."""
        mgr = LifecycleManager(
            "FA-TEST-001", initial_status=InvoiceStatus.PRISE_EN_CHARGE
        )
        with pytest.raises(ValueError, match="exige un motif"):
            mgr.transition(InvoiceStatus.REFUSEE)

    def test_refusee_with_reason_succeeds(self) -> None:
        """Vérifie que REFUSEE avec motif fonctionne."""
        mgr = LifecycleManager(
            "FA-TEST-001", initial_status=InvoiceStatus.PRISE_EN_CHARGE
        )
        event = mgr.transition(
            InvoiceStatus.REFUSEE,
            reason="Marchandise non conforme",
            reason_code="RC01",
        )
        assert mgr.status == InvoiceStatus.REFUSEE
        assert event.reason == "Marchandise non conforme"
        assert event.reason_code == "RC01"

    def test_refusee_from_partiellement_approuvee(self) -> None:
        """Vérifie REFUSEE depuis PARTIELLEMENT_APPROUVEE."""
        mgr = LifecycleManager(
            "FA-TEST-001", initial_status=InvoiceStatus.PARTIELLEMENT_APPROUVEE
        )
        event = mgr.transition(
            InvoiceStatus.REFUSEE, reason="Facture incomplète"
        )
        assert event.status == InvoiceStatus.REFUSEE

    def test_refusee_from_en_litige(self) -> None:
        """Vérifie REFUSEE depuis EN_LITIGE."""
        mgr = LifecycleManager(
            "FA-TEST-001", initial_status=InvoiceStatus.EN_LITIGE
        )
        event = mgr.transition(
            InvoiceStatus.REFUSEE, reason="Litige non résolu"
        )
        assert event.status == InvoiceStatus.REFUSEE


class TestEventHistory:
    """Tests de l'historique des événements."""

    def test_initial_empty_history(self) -> None:
        """Vérifie que l'historique est vide au départ."""
        mgr = LifecycleManager("FA-TEST-001")
        assert len(mgr.history) == 0

    def test_transition_adds_event(self) -> None:
        """Vérifie que chaque transition ajoute un événement."""
        mgr = LifecycleManager("FA-TEST-001")
        mgr.transition(InvoiceStatus.EMISE)
        assert len(mgr.history) == 1
        assert mgr.history[0].status == InvoiceStatus.EMISE

    def test_multiple_transitions_history(self) -> None:
        """Vérifie l'historique après plusieurs transitions."""
        mgr = LifecycleManager("FA-TEST-001")
        mgr.transition(InvoiceStatus.EMISE)
        mgr.transition(InvoiceStatus.RECUE)
        mgr.transition(InvoiceStatus.MISE_A_DISPOSITION)

        assert len(mgr.history) == 3
        statuses = [e.status for e in mgr.history]
        assert statuses == [
            InvoiceStatus.EMISE,
            InvoiceStatus.RECUE,
            InvoiceStatus.MISE_A_DISPOSITION,
        ]

    def test_event_timestamp_default(self) -> None:
        """Vérifie que le timestamp est généré automatiquement."""
        mgr = LifecycleManager("FA-TEST-001")
        before = datetime.now(timezone.utc)
        mgr.transition(InvoiceStatus.EMISE)
        after = datetime.now(timezone.utc)

        event = mgr.history[0]
        assert before <= event.timestamp <= after

    def test_event_timestamp_custom(self) -> None:
        """Vérifie qu'on peut fournir un timestamp personnalisé."""
        mgr = LifecycleManager("FA-TEST-001")
        custom_ts = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)
        mgr.transition(InvoiceStatus.EMISE, timestamp=custom_ts)

        assert mgr.history[0].timestamp == custom_ts

    def test_event_producer_default(self) -> None:
        """Vérifie que le producteur par défaut est utilisé."""
        mgr = LifecycleManager("FA-TEST-001")
        mgr.transition(InvoiceStatus.EMISE)
        # EMISE a default_producer = PLATFORM
        assert mgr.history[0].producer == CDARRoleCode.PLATFORM

    def test_event_producer_custom(self) -> None:
        """Vérifie qu'on peut fournir un producteur personnalisé."""
        mgr = LifecycleManager("FA-TEST-001")
        mgr.transition(InvoiceStatus.EMISE, producer=CDARRoleCode.SELLER)
        assert mgr.history[0].producer == CDARRoleCode.SELLER


class TestEncaissement:
    """Tests du statut ENCAISSEE."""

    def test_encaissee_with_amount(self) -> None:
        """Vérifie ENCAISSEE avec montant partiel (retenue de garantie)."""
        mgr = LifecycleManager(
            "FA-TEST-001", initial_status=InvoiceStatus.APPROUVEE
        )
        event = mgr.transition(
            InvoiceStatus.ENCAISSEE,
            amount=Decimal("9500.00"),
        )
        assert event.amount == Decimal("9500.00")
        assert event.status == InvoiceStatus.ENCAISSEE

    def test_encaissee_without_amount(self) -> None:
        """Vérifie ENCAISSEE sans montant (encaissement total)."""
        mgr = LifecycleManager(
            "FA-TEST-001", initial_status=InvoiceStatus.PAIEMENT_TRANSMIS
        )
        event = mgr.transition(InvoiceStatus.ENCAISSEE)
        assert event.amount is None
        assert mgr.is_terminal()


class TestFullLifecycle:
    """Tests de parcours complets du cycle de vie."""

    def test_full_lifecycle_happy_path(self) -> None:
        """Parcours complet : DEPOSEE → ... → ENCAISSEE."""
        mgr = LifecycleManager("FA-2026-042")
        assert mgr.status == InvoiceStatus.DEPOSEE

        mgr.transition(InvoiceStatus.EMISE)
        mgr.transition(InvoiceStatus.RECUE)
        mgr.transition(InvoiceStatus.MISE_A_DISPOSITION)
        mgr.transition(InvoiceStatus.PRISE_EN_CHARGE)
        mgr.transition(InvoiceStatus.APPROUVEE)
        mgr.transition(InvoiceStatus.PAIEMENT_TRANSMIS)
        mgr.transition(InvoiceStatus.ENCAISSEE)

        assert mgr.status == InvoiceStatus.ENCAISSEE
        assert mgr.is_terminal()
        assert len(mgr.history) == 7

    def test_lifecycle_with_dispute(self) -> None:
        """Parcours avec litige : ... → EN_LITIGE → APPROUVEE → ENCAISSEE."""
        mgr = LifecycleManager(
            "FA-TEST-002", initial_status=InvoiceStatus.PRISE_EN_CHARGE
        )
        mgr.transition(InvoiceStatus.EN_LITIGE)
        mgr.transition(InvoiceStatus.APPROUVEE)
        mgr.transition(InvoiceStatus.ENCAISSEE)

        assert mgr.status == InvoiceStatus.ENCAISSEE
        assert len(mgr.history) == 3

    def test_lifecycle_with_suspension(self) -> None:
        """Parcours avec suspension : ... → SUSPENDUE → COMPLETEE → PRISE_EN_CHARGE → ..."""
        mgr = LifecycleManager(
            "FA-TEST-003", initial_status=InvoiceStatus.PRISE_EN_CHARGE
        )
        mgr.transition(InvoiceStatus.SUSPENDUE)
        mgr.transition(InvoiceStatus.COMPLETEE)
        mgr.transition(InvoiceStatus.PRISE_EN_CHARGE)
        mgr.transition(InvoiceStatus.APPROUVEE)
        mgr.transition(InvoiceStatus.ENCAISSEE)

        assert mgr.status == InvoiceStatus.ENCAISSEE
        assert len(mgr.history) == 5

    def test_lifecycle_rejection_at_emission(self) -> None:
        """Parcours avec rejet à l'émission."""
        mgr = LifecycleManager("FA-TEST-004")
        mgr.transition(InvoiceStatus.REJETEE_EMISSION)

        assert mgr.status == InvoiceStatus.REJETEE_EMISSION
        assert mgr.is_terminal()
        assert len(mgr.history) == 1

    def test_lifecycle_rejection_at_reception(self) -> None:
        """Parcours avec rejet à la réception."""
        mgr = LifecycleManager("FA-TEST-005")
        mgr.transition(InvoiceStatus.EMISE)
        mgr.transition(InvoiceStatus.REJETEE_RECEPTION)

        assert mgr.status == InvoiceStatus.REJETEE_RECEPTION
        assert mgr.is_terminal()

    def test_invoice_reference_stored(self) -> None:
        """Vérifie que la référence facture est conservée."""
        mgr = LifecycleManager("FA-2026-042")
        assert mgr.invoice_reference == "FA-2026-042"
