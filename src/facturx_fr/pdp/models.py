"""Modèles de données pour les réponses PDP.

FR: Modèles Pydantic pour les échanges avec les Plateformes Agréées (PA),
    conformes à la norme AFNOR XP Z12-013.
EN: Pydantic models for exchanges with certified platforms (PA),
    conforming to the AFNOR XP Z12-013 standard.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

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


class StatusUpdateResponse(BaseModel):
    """Confirmation de mise à jour de statut.

    FR: Réponse de la PA après une demande de changement de statut
        sur le cycle de vie d'une facture.
    EN: PA response after a status change request on an invoice lifecycle.
    """

    invoice_id: str
    status: InvoiceStatus
    updated_at: datetime


class InvoiceSearchFilters(BaseModel):
    """Filtres de recherche de factures.

    FR: Critères de filtrage pour la recherche de factures sur la PA,
        avec pagination intégrée.
    EN: Filter criteria for invoice search on the PA, with built-in pagination.
    """

    status: InvoiceStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    seller_siren: str | None = None
    buyer_siren: str | None = None
    direction: Literal["sent", "received"] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


class InvoiceSearchResult(BaseModel):
    """Résultat unitaire dans une recherche de factures.

    FR: Résumé d'une facture retournée par la recherche.
    EN: Invoice summary returned by a search.
    """

    invoice_id: str
    number: str
    issue_date: date
    seller_name: str
    buyer_name: str
    total_incl_tax: Decimal
    currency: str
    status: InvoiceStatus
    direction: Literal["sent", "received"]


class InvoiceSearchResponse(BaseModel):
    """Réponse paginée de recherche de factures.

    FR: Contient les résultats et les informations de pagination.
    EN: Contains results and pagination information.
    """

    results: list[InvoiceSearchResult]
    total_count: int
    page: int
    page_size: int


class EReportingSubmissionResponse(BaseModel):
    """Réponse à la soumission de données e-reporting à une PA.

    FR: Contient l'identifiant de la soumission, le statut de traitement
        et les éventuelles erreurs retournées par la PA.
    EN: Contains the submission ID, processing status and any errors
        returned by the PA.
    """

    submission_id: str
    status: Literal["accepted", "rejected", "pending"]
    submitted_at: datetime
    errors: list[str] | None = None
    raw_response: dict | None = None


class DirectoryEntry(BaseModel):
    """Entrée de l'annuaire central (SIREN -> PA de réception).

    FR: Représente le mapping entre un SIREN et sa Plateforme Agréée
        de réception, tel que publié dans l'annuaire central du PPF.
    EN: Represents the mapping between a SIREN and its receiving
        certified platform, as published in the PPF central directory.
    """

    siren: str
    company_name: str
    platform_id: str
    """Identifiant de la PA de réception."""
    platform_name: str
    electronic_address: str
    """Adresse de facturation électronique."""
    registration_date: date | None = None
