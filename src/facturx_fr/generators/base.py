"""Interface abstraite pour les générateurs de factures."""

from abc import ABC, abstractmethod

from facturx_fr.models.invoice import Invoice


class GenerationResult:
    """Résultat de la génération d'une facture.

    FR: Contient les données générées (XML, PDF) et les métadonnées.
    EN: Contains generated data (XML, PDF) and metadata.
    """

    def __init__(
        self,
        xml_bytes: bytes,
        pdf_bytes: bytes | None = None,
        profile: str = "",
    ) -> None:
        self.xml_bytes = xml_bytes
        self.pdf_bytes = pdf_bytes
        self.profile = profile

    def save(self, path: str) -> None:
        """Sauvegarde le résultat dans un fichier."""
        data = self.pdf_bytes if self.pdf_bytes else self.xml_bytes
        with open(path, "wb") as f:
            f.write(data)


class BaseGenerator(ABC):
    """Classe de base abstraite pour les générateurs de factures.

    FR: Tous les générateurs (Factur-X, UBL, CII) héritent de cette classe.
    EN: All generators (Factur-X, UBL, CII) inherit from this class.
    """

    def __init__(self, profile: str = "EN16931") -> None:
        self.profile = profile

    @abstractmethod
    def generate(self, invoice: Invoice, **kwargs: object) -> GenerationResult:
        """Génère la facture dans le format cible.

        Args:
            invoice: Le modèle de facture à générer.
            **kwargs: Options spécifiques au générateur.

        Returns:
            GenerationResult contenant les données générées.
        """
        ...

    @abstractmethod
    def generate_xml(self, invoice: Invoice) -> bytes:
        """Génère uniquement le XML de la facture.

        Args:
            invoice: Le modèle de facture.

        Returns:
            Le contenu XML en bytes.
        """
        ...
