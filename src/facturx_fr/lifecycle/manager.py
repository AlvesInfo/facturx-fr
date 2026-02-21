"""Machine à états pour le cycle de vie des factures.

FR: Implémente le graphe complet des 14 statuts (5 obligatoires + 10 recommandés)
    conformément à la norme AFNOR XP Z12-012 et aux spécifications DGFiP v3.1.
    Chaque transition est validée, les contraintes métier sont vérifiées
    (motif obligatoire pour REFUSEE, montant optionnel pour ENCAISSEE),
    et un historique complet des événements est conservé.
EN: Implements the full 14-status graph (5 mandatory + 10 recommended)
    per AFNOR XP Z12-012 and DGFiP v3.1 specifications.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

from facturx_fr.models.enums import CDARRoleCode, InvoiceStatus, StatusCategory
from facturx_fr.pdp.models import LifecycleEvent

# ---------------------------------------------------------------------------
# Graphe de transitions autorisées
# ---------------------------------------------------------------------------

TRANSITIONS: dict[InvoiceStatus, list[InvoiceStatus]] = {
    # Émission
    InvoiceStatus.DEPOSEE: [
        InvoiceStatus.EMISE,
        InvoiceStatus.REJETEE_EMISSION,
    ],
    InvoiceStatus.EMISE: [
        InvoiceStatus.RECUE,
        InvoiceStatus.REJETEE_RECEPTION,
    ],
    # Réception
    InvoiceStatus.RECUE: [
        InvoiceStatus.MISE_A_DISPOSITION,
        InvoiceStatus.REJETEE_RECEPTION,
    ],
    InvoiceStatus.MISE_A_DISPOSITION: [
        InvoiceStatus.PRISE_EN_CHARGE,
        InvoiceStatus.REJETEE_RECEPTION,
    ],
    # Traitement acheteur
    InvoiceStatus.PRISE_EN_CHARGE: [
        InvoiceStatus.APPROUVEE,
        InvoiceStatus.PARTIELLEMENT_APPROUVEE,
        InvoiceStatus.REFUSEE,
        InvoiceStatus.EN_LITIGE,
        InvoiceStatus.SUSPENDUE,
    ],
    InvoiceStatus.APPROUVEE: [
        InvoiceStatus.PAIEMENT_TRANSMIS,
        InvoiceStatus.ENCAISSEE,
    ],
    InvoiceStatus.PARTIELLEMENT_APPROUVEE: [
        InvoiceStatus.PAIEMENT_TRANSMIS,
        InvoiceStatus.REFUSEE,
        InvoiceStatus.EN_LITIGE,
    ],
    InvoiceStatus.EN_LITIGE: [
        InvoiceStatus.APPROUVEE,
        InvoiceStatus.REFUSEE,
        InvoiceStatus.SUSPENDUE,
    ],
    InvoiceStatus.SUSPENDUE: [
        InvoiceStatus.COMPLETEE,
    ],
    InvoiceStatus.COMPLETEE: [
        InvoiceStatus.PRISE_EN_CHARGE,
    ],
    # Paiement
    InvoiceStatus.PAIEMENT_TRANSMIS: [
        InvoiceStatus.ENCAISSEE,
    ],
    # Terminaux (aucune transition sortante)
    InvoiceStatus.REJETEE_EMISSION: [],
    InvoiceStatus.REJETEE_RECEPTION: [],
    InvoiceStatus.REFUSEE: [],
    InvoiceStatus.ENCAISSEE: [],
}

# ---------------------------------------------------------------------------
# Métadonnées des statuts
# ---------------------------------------------------------------------------


class StatusInfo(NamedTuple):
    """Métadonnées d'un statut de cycle de vie."""

    category: StatusCategory
    default_producer: CDARRoleCode
    reason_required: bool = False


STATUS_METADATA: dict[InvoiceStatus, StatusInfo] = {
    # --- Obligatoires (transmis au CDD/PPF) ---
    InvoiceStatus.DEPOSEE: StatusInfo(
        category=StatusCategory.MANDATORY,
        default_producer=CDARRoleCode.PLATFORM,
    ),
    InvoiceStatus.REJETEE_EMISSION: StatusInfo(
        category=StatusCategory.MANDATORY,
        default_producer=CDARRoleCode.PLATFORM,
    ),
    InvoiceStatus.REFUSEE: StatusInfo(
        category=StatusCategory.MANDATORY,
        default_producer=CDARRoleCode.BUYER,
        reason_required=True,
    ),
    InvoiceStatus.REJETEE_RECEPTION: StatusInfo(
        category=StatusCategory.MANDATORY,
        default_producer=CDARRoleCode.PLATFORM,
    ),
    InvoiceStatus.ENCAISSEE: StatusInfo(
        category=StatusCategory.MANDATORY,
        default_producer=CDARRoleCode.SELLER,
    ),
    # --- Recommandés (entre les parties) ---
    InvoiceStatus.EMISE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.PLATFORM,
    ),
    InvoiceStatus.RECUE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.PLATFORM,
    ),
    InvoiceStatus.MISE_A_DISPOSITION: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.PLATFORM,
    ),
    InvoiceStatus.PRISE_EN_CHARGE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.BUYER,
    ),
    InvoiceStatus.APPROUVEE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.BUYER,
    ),
    InvoiceStatus.PARTIELLEMENT_APPROUVEE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.BUYER,
    ),
    InvoiceStatus.EN_LITIGE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.BUYER,
    ),
    InvoiceStatus.SUSPENDUE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.BUYER,
    ),
    InvoiceStatus.PAIEMENT_TRANSMIS: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.BUYER,
    ),
    InvoiceStatus.COMPLETEE: StatusInfo(
        category=StatusCategory.RECOMMENDED,
        default_producer=CDARRoleCode.SELLER,
    ),
}

# Statuts terminaux (aucune transition sortante)
TERMINAL_STATUSES: frozenset[InvoiceStatus] = frozenset(
    status for status, targets in TRANSITIONS.items() if not targets
)


class LifecycleManager:
    """Gestionnaire du cycle de vie d'une facture.

    FR: Implémente la machine à états complète des 14 statuts
        conformément à la norme AFNOR XP Z12-012. Conserve un
        historique horodaté de tous les événements.
    EN: Implements the full 14-status state machine per AFNOR
        XP Z12-012. Maintains a timestamped event history.
    """

    def __init__(
        self,
        invoice_reference: str,
        initial_status: InvoiceStatus = InvoiceStatus.DEPOSEE,
    ) -> None:
        self.invoice_reference = invoice_reference
        self.status = initial_status
        self.history: list[LifecycleEvent] = []

    def can_transition(self, target: InvoiceStatus) -> bool:
        """Vérifie si la transition vers le statut cible est autorisée."""
        return target in TRANSITIONS.get(self.status, [])

    def transition(
        self,
        target: InvoiceStatus,
        *,
        reason: str | None = None,
        reason_code: str | None = None,
        producer: CDARRoleCode | None = None,
        amount: Decimal | None = None,
        timestamp: datetime | None = None,
    ) -> LifecycleEvent:
        """Effectue la transition vers le statut cible.

        FR: Valide les contraintes métier, enregistre l'événement dans
            l'historique et met à jour le statut courant.
        EN: Validates business constraints, records the event in history
            and updates the current status.

        Args:
            target: Statut cible.
            reason: Motif (obligatoire pour REFUSEE).
            reason_code: Code motif (liste XP Z12-012).
            producer: Rôle du producteur du statut.
            amount: Montant pour encaissement partiel.
            timestamp: Horodatage (UTC now par défaut).

        Returns:
            L'événement de cycle de vie créé.

        Raises:
            ValueError: Si la transition est invalide ou qu'un motif
                obligatoire est manquant.
        """
        if not self.can_transition(target):
            allowed = [s.value for s in TRANSITIONS.get(self.status, [])]
            msg = (
                f"Transition non autorisée : {self.status.value} → {target.value}. "
                f"Transitions possibles : {allowed}"
            )
            raise ValueError(msg)

        # Validation : REFUSEE exige un motif
        metadata = STATUS_METADATA.get(target)
        if metadata and metadata.reason_required and not reason:
            msg = (
                f"Le statut {target.value} ({target.name}) exige un motif "
                f"(paramètre 'reason' obligatoire)."
            )
            raise ValueError(msg)

        if producer is None and metadata is not None:
            producer = metadata.default_producer

        if timestamp is None:
            timestamp = datetime.now(UTC)

        event = LifecycleEvent(
            timestamp=timestamp,
            status=target,
            reason=reason,
            reason_code=reason_code,
            producer=producer,
            amount=amount,
        )

        self.status = target
        self.history.append(event)
        return event

    def is_terminal(self) -> bool:
        """Vérifie si le statut courant est terminal (aucune transition sortante)."""
        return self.status in TERMINAL_STATUSES

    def is_mandatory(self, status: InvoiceStatus) -> bool:
        """Vérifie si un statut est obligatoire (transmis au CDD/PPF)."""
        metadata = STATUS_METADATA.get(status)
        return metadata is not None and metadata.category == StatusCategory.MANDATORY

    def mandatory_events(self) -> list[LifecycleEvent]:
        """Retourne les événements obligatoires de l'historique."""
        return [e for e in self.history if self.is_mandatory(e.status)]
