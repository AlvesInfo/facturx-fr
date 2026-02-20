"""Hiérarchie d'exceptions pour les opérations PDP.

FR: Exceptions typées pour les erreurs d'authentification, de validation,
    de ressource introuvable et de connexion vers les Plateformes Agréées.
EN: Typed exceptions for authentication, validation, not-found and
    connection errors with certified platforms (PA).
"""


class PDPError(Exception):
    """Erreur de base pour toutes les opérations PDP.

    FR: Classe parente de toutes les exceptions liées aux échanges
        avec les Plateformes de Dématérialisation Partenaire.
    EN: Base class for all PDP-related exceptions.
    """


class PDPAuthenticationError(PDPError):
    """Échec d'authentification auprès de la PA.

    FR: Clé API invalide, token expiré ou droits insuffisants.
    EN: Invalid API key, expired token or insufficient permissions.
    """


class PDPValidationError(PDPError):
    """Facture rejetée pour non-conformité.

    FR: La facture soumise ne satisfait pas les contrôles de la PA
        (XSD, schématron, règles de gestion).
    EN: The submitted invoice failed PA validation checks.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []


class PDPNotFoundError(PDPError):
    """Ressource introuvable sur la PA.

    FR: Facture, entrée annuaire ou autre ressource non trouvée.
    EN: Invoice, directory entry or other resource not found.
    """


class PDPConnectionError(PDPError):
    """Erreur de connexion réseau vers la PA.

    FR: Timeout, DNS, TLS ou autre erreur de transport.
    EN: Timeout, DNS, TLS or other transport error.
    """
