"""E-reporting pour les transactions B2C et internationales.

FR: Module de gestion du e-reporting conforme aux spécifications DGFiP v3.1
    et aux simplifications de septembre 2025. Couvre les transactions B2C
    domestiques, B2B internationales et les données de paiement.
EN: E-reporting management module conforming to DGFiP v3.1 specifications
    and September 2025 simplifications.
"""

from facturx_fr.ereporting.errors import (
    EReportingEmptyDeclarationError,
    EReportingError,
    EReportingValidationError,
)
from facturx_fr.ereporting.models import (
    AggregatedTransactionData,
    EReportingSubmission,
    PaymentData,
    TaxBreakdown,
    TransactionData,
    TransmissionSchedule,
)
from facturx_fr.ereporting.reporter import EReporter

__all__ = [
    "AggregatedTransactionData",
    "EReporter",
    "EReportingEmptyDeclarationError",
    "EReportingError",
    "EReportingSubmission",
    "EReportingValidationError",
    "PaymentData",
    "TaxBreakdown",
    "TransactionData",
    "TransmissionSchedule",
]
