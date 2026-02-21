"""Gestion du cycle de vie des factures électroniques.

FR: Machine à états des 14 statuts (XP Z12-012) et messages CDAR (UN/CEFACT D22B).
EN: 14-status state machine (XP Z12-012) and CDAR messages (UN/CEFACT D22B).
"""

from facturx_fr.lifecycle.cdar import CDARGenerator, CDARMessage, CDARParser, CDARParty
from facturx_fr.lifecycle.manager import (
    STATUS_METADATA,
    TERMINAL_STATUSES,
    TRANSITIONS,
    LifecycleManager,
    StatusInfo,
)

__all__ = [
    "CDARGenerator",
    "CDARMessage",
    "CDARParser",
    "CDARParty",
    "LifecycleManager",
    "STATUS_METADATA",
    "StatusInfo",
    "TERMINAL_STATUSES",
    "TRANSITIONS",
]
