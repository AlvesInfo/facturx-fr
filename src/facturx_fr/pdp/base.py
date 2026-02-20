"""Interface abstraite pour les connecteurs PDP.

FR: Définit l'interface complète conforme à la norme AFNOR XP Z12-013
    pour l'échange avec les Plateformes Agréées (PA) : dépôt de facture,
    consultation de statuts et cycle de vie, récupération de factures,
    recherche, mise à jour de statut et consultation de l'annuaire.
EN: Defines the complete interface conforming to the AFNOR XP Z12-013
    standard for exchanging with certified platforms (PA).
"""

from abc import ABCMeta, abstractmethod
from decimal import Decimal

from facturx_fr.models.enums import InvoiceStatus
from facturx_fr.models.invoice import Invoice
from facturx_fr.ereporting.models import EReportingSubmission
from facturx_fr.pdp.models import (
    DirectoryEntry,
    EReportingSubmissionResponse,
    InvoiceSearchFilters,
    InvoiceSearchResponse,
    LifecycleResponse,
    StatusUpdateResponse,
    SubmissionResponse,
)


class BasePDP(metaclass=ABCMeta):
    """Classe de base abstraite pour les connecteurs PDP.

    FR: Définit l'interface commune conforme à la norme AFNOR XP Z12-013
        pour l'échange avec les Plateformes de Dématérialisation Partenaire.
        Les connecteurs concrets (Pennylane, Sage, etc.) héritent de cette classe.
    EN: Defines the common interface conforming to the AFNOR XP Z12-013 standard
        for exchanging with Partner Dematerialization Platforms.
    """

    def __init__(
        self,
        api_key: str,
        environment: str = "sandbox",
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.environment = environment
        self.base_url = base_url

    # --- Dépôt de facture ---

    @abstractmethod
    async def submit(
        self,
        invoice: Invoice,
        xml_bytes: bytes | None = None,
        pdf_bytes: bytes | None = None,
    ) -> SubmissionResponse:
        """Soumet une facture à la PA.

        Args:
            invoice: La facture à soumettre.
            xml_bytes: XML pré-généré (optionnel, sinon la PA génère).
            pdf_bytes: Le PDF de la facture (optionnel).

        Returns:
            Réponse de soumission avec l'identifiant et le statut.

        Raises:
            PDPValidationError: Si la facture est non conforme.
            PDPAuthenticationError: Si l'authentification échoue.
            PDPConnectionError: Si la connexion réseau échoue.
        """
        ...

    # --- Consultation statuts ---

    @abstractmethod
    async def get_status(self, invoice_id: str) -> InvoiceStatus:
        """Récupère le statut courant d'une facture.

        Args:
            invoice_id: L'identifiant de la facture côté PA.

        Returns:
            Le statut courant de la facture.

        Raises:
            PDPNotFoundError: Si la facture n'existe pas.
        """
        ...

    @abstractmethod
    async def get_lifecycle(self, invoice_id: str) -> LifecycleResponse:
        """Récupère le cycle de vie complet d'une facture.

        Args:
            invoice_id: L'identifiant de la facture côté PA.

        Returns:
            Historique des événements du cycle de vie.

        Raises:
            PDPNotFoundError: Si la facture n'existe pas.
        """
        ...

    # --- Récupération de facture ---

    @abstractmethod
    async def get_invoice(self, invoice_id: str) -> bytes:
        """Récupère le XML d'une facture.

        Args:
            invoice_id: L'identifiant de la facture côté PA.

        Returns:
            Le contenu XML de la facture.

        Raises:
            PDPNotFoundError: Si la facture n'existe pas.
        """
        ...

    # --- Recherche de factures ---

    @abstractmethod
    async def search_invoices(
        self,
        filters: InvoiceSearchFilters | None = None,
    ) -> InvoiceSearchResponse:
        """Recherche des factures avec filtres optionnels.

        Args:
            filters: Critères de filtrage et pagination.

        Returns:
            Réponse paginée avec les factures correspondantes.
        """
        ...

    # --- Mise à jour de statut (cycle de vie) ---

    @abstractmethod
    async def update_status(
        self,
        invoice_id: str,
        status: InvoiceStatus,
        *,
        reason: str | None = None,
        reason_code: str | None = None,
        amount: Decimal | None = None,
    ) -> StatusUpdateResponse:
        """Met à jour le statut d'une facture dans le cycle de vie.

        Args:
            invoice_id: L'identifiant de la facture côté PA.
            status: Le nouveau statut cible.
            reason: Motif (obligatoire pour REFUSEE).
            reason_code: Code motif (liste XP Z12-012).
            amount: Montant pour encaissement partiel.

        Returns:
            Confirmation de la mise à jour.

        Raises:
            PDPNotFoundError: Si la facture n'existe pas.
            ValueError: Si la transition est invalide ou le motif manquant.
        """
        ...

    # --- Consultation annuaire ---

    @abstractmethod
    async def lookup_directory(self, siren: str) -> DirectoryEntry:
        """Consulte l'annuaire central pour un SIREN donné.

        Args:
            siren: Le numéro SIREN de l'entreprise recherchée.

        Returns:
            L'entrée annuaire avec la PA de réception.

        Raises:
            PDPNotFoundError: Si le SIREN n'est pas trouvé dans l'annuaire.
        """
        ...

    # --- E-reporting ---

    @abstractmethod
    async def submit_ereporting_transaction(
        self, submission: EReportingSubmission
    ) -> EReportingSubmissionResponse:
        """Soumet des données de transaction e-reporting à la PA.

        Args:
            submission: La soumission préparée (transaction ou agrégat).

        Returns:
            Réponse de soumission avec statut de traitement.

        Raises:
            PDPValidationError: Si les données sont non conformes.
        """
        ...

    @abstractmethod
    async def submit_ereporting_payment(
        self, submission: EReportingSubmission
    ) -> EReportingSubmissionResponse:
        """Soumet des données de paiement e-reporting à la PA.

        Args:
            submission: La soumission préparée (données de paiement).

        Returns:
            Réponse de soumission avec statut de traitement.

        Raises:
            PDPValidationError: Si les données sont non conformes.
        """
        ...

    @abstractmethod
    async def get_ereporting_status(
        self, submission_id: str
    ) -> EReportingSubmissionResponse:
        """Récupère le statut d'une soumission e-reporting.

        Args:
            submission_id: L'identifiant de la soumission.

        Returns:
            Réponse avec le statut courant de la soumission.

        Raises:
            PDPNotFoundError: Si la soumission n'existe pas.
        """
        ...
