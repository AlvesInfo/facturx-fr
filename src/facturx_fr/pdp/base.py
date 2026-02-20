"""Interface abstraite pour les connecteurs PDP."""

from abc import ABCMeta, abstractmethod

from facturx_fr.models.invoice import Invoice
from facturx_fr.pdp.models import LifecycleResponse, SubmissionResponse


class BasePDP(metaclass=ABCMeta):
    """Classe de base abstraite pour les connecteurs PDP.

    FR: Définit l'interface commune conforme à la norme AFNOR XP Z12-013
        pour l'échange avec les Plateformes de Dématérialisation Partenaire.
    EN: Defines the common interface conforming to the AFNOR XP Z12-013 standard
        for exchanging with Partner Dematerialization Platforms.
    """

    def __init__(self, api_key: str, environment: str = "sandbox") -> None:
        self.api_key = api_key
        self.environment = environment

    @abstractmethod
    async def submit(
        self,
        invoice: Invoice,
        pdf_bytes: bytes | None = None,
    ) -> SubmissionResponse:
        """Soumet une facture à la PDP.

        Args:
            invoice: La facture à soumettre.
            pdf_bytes: Le PDF de la facture (optionnel).

        Returns:
            Réponse de soumission avec l'identifiant et le statut.
        """
        ...

    @abstractmethod
    async def get_lifecycle(self, invoice_id: str) -> LifecycleResponse:
        """Récupère le cycle de vie d'une facture.

        Args:
            invoice_id: L'identifiant de la facture côté PDP.

        Returns:
            Historique des événements du cycle de vie.
        """
        ...

    @abstractmethod
    async def get_status(self, invoice_id: str) -> str:
        """Récupère le statut courant d'une facture.

        Args:
            invoice_id: L'identifiant de la facture côté PDP.

        Returns:
            Le statut courant (ex: "deposee", "approuvee").
        """
        ...
