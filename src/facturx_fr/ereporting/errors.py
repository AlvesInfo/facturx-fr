"""Hiérarchie d'exceptions pour les opérations e-reporting.

FR: Exceptions typées pour les erreurs de validation des données e-reporting
    et les déclarations vides (interdites depuis les simplifications DGFiP sept. 2025).
EN: Typed exceptions for e-reporting data validation errors
    and empty declarations (forbidden since DGFiP Sept. 2025 simplifications).
"""


class EReportingError(Exception):
    """Erreur de base pour toutes les opérations e-reporting.

    FR: Classe parente de toutes les exceptions liées au e-reporting.
    EN: Base class for all e-reporting exceptions.
    """


class EReportingValidationError(EReportingError):
    """Données e-reporting invalides (champs manquants, incohérences).

    FR: Levée quand les données de transaction, paiement ou agrégat
        ne satisfont pas les règles de validation.
    EN: Raised when transaction, payment or aggregate data
        fail validation rules.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []


class EReportingEmptyDeclarationError(EReportingError):
    """Déclaration vide — interdit depuis les simplifications DGFiP sept. 2025.

    FR: Depuis septembre 2025, les déclarations e-reporting vierges sont
        supprimées : pas d'opérations = pas de transmission.
    EN: Since September 2025, empty e-reporting declarations are
        no longer required: no transactions = no submission.
    """
