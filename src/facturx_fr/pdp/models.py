"""Modèles de données pour les réponses PDP."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from facturx_fr.models.enums import CDARRoleCode, InvoiceStatus


class SubmissionResponse(BaseModel):
    """Réponse à la soumission d'une facture à une PDP.

    FR: Contient l'identifiant attribué par la PDP et le statut initial.
    EN: Contains the ID assigned by the PDP and the initial status.
    """

    invoice_id: str
    status: InvoiceStatus
    submitted_at: datetime
    raw_response: dict | None = None


class LifecycleEvent(BaseModel):
    """Événement du cycle de vie d'une facture.

    FR: Représente un changement de statut horodaté, avec les métadonnées
        associées (motif de refus, producteur, montant encaissé, réf. CDAR).
    EN: Represents a timestamped status change, with associated metadata
        (refusal reason, producer, cashed amount, CDAR reference).
    """

    timestamp: datetime
    status: InvoiceStatus
    reason: str | None = None
    reason_code: str | None = None
    """Code motif de refus (liste XP Z12-012)."""
    producer: CDARRoleCode | None = None
    """Rôle de la partie ayant émis ce statut."""
    amount: Decimal | None = None
    """Montant pour encaissement partiel (retenue de garantie)."""
    cdar_message_id: str | None = None
    """Référence au message CDAR associé."""


class LifecycleResponse(BaseModel):
    """Historique du cycle de vie d'une facture.

    FR: Liste ordonnée des événements de statut.
    EN: Ordered list of status events.
    """

    invoice_id: str
    current_status: InvoiceStatus
    events: list[LifecycleEvent]
