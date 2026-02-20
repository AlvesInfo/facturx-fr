"""Modèles de données pour les réponses PDP."""

from datetime import datetime

from pydantic import BaseModel

from facturx_fr.models.enums import InvoiceStatus


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

    FR: Représente un changement de statut horodaté.
    EN: Represents a timestamped status change.
    """

    timestamp: datetime
    status: InvoiceStatus
    reason: str | None = None


class LifecycleResponse(BaseModel):
    """Historique du cycle de vie d'une facture.

    FR: Liste ordonnée des événements de statut.
    EN: Ordered list of status events.
    """

    invoice_id: str
    current_status: InvoiceStatus
    events: list[LifecycleEvent]
