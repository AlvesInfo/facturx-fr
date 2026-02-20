"""Clients API pour les Plateformes de Dématérialisation Partenaire (PDP).

FR: Interface abstraite conforme à la norme AFNOR XP Z12-013
    et modèles de données pour les échanges avec les PA.
EN: Abstract interface conforming to the AFNOR XP Z12-013 standard
    and data models for exchanges with certified platforms.
"""

from facturx_fr.pdp.base import BasePDP
from facturx_fr.pdp.errors import (
    PDPAuthenticationError,
    PDPConnectionError,
    PDPError,
    PDPNotFoundError,
    PDPValidationError,
)
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

__all__ = [
    "BasePDP",
    "DirectoryEntry",
    "InvoiceSearchFilters",
    "InvoiceSearchResponse",
    "InvoiceSearchResult",
    "LifecycleEvent",
    "LifecycleResponse",
    "PDPAuthenticationError",
    "PDPConnectionError",
    "PDPError",
    "PDPNotFoundError",
    "PDPValidationError",
    "StatusUpdateResponse",
    "SubmissionResponse",
]
