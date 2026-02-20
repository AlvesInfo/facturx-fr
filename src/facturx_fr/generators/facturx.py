"""Générateur Factur-X (PDF/A-3 + XML CII).

FR: Produit un PDF/A-3 avec XML CII embarqué, conforme au profil choisi.
    Délègue la génération XML au CIIGenerator, puis utilise la bibliothèque
    factur-x (Akretion) pour embarquer le XML dans un PDF.
EN: Produces a PDF/A-3 with embedded CII XML, conforming to the chosen profile.
"""

import logging

from facturx import generate_from_binary

from facturx_fr.generators.base import BaseGenerator, GenerationResult
from facturx_fr.generators.cii import CIIGenerator
from facturx_fr.models.invoice import Invoice

logger = logging.getLogger(__name__)

# Mapping des profils vers les noms attendus par la lib factur-x
_PROFILE_MAP = {
    "MINIMUM": "minimum",
    "BASICWL": "basicwl",
    "BASIC": "basic",
    "EN16931": "en16931",
    "EXTENDED": "extended",
}


class FacturXGenerator(BaseGenerator):
    """Générateur de factures au format Factur-X.

    FR: Produit un PDF/A-3 avec XML CII embarqué, conforme au profil choisi.
        Délègue la génération XML au CIIGenerator, puis utilise la bibliothèque
        factur-x pour embarquer le XML dans le PDF.
    EN: Produces a PDF/A-3 with embedded CII XML, conforming to the chosen profile.
    """

    def __init__(self, profile: str = "EN16931") -> None:
        super().__init__(profile=profile)
        self._cii_generator = CIIGenerator(profile=profile)

    def generate_xml(self, invoice: Invoice) -> bytes:
        """Génère le XML CII de la facture (délègue au CIIGenerator)."""
        return self._cii_generator.generate_xml(invoice)

    def generate(self, invoice: Invoice, **kwargs: object) -> GenerationResult:
        """Génère une facture Factur-X complète (PDF/A-3 + XML CII).

        Args:
            invoice: Le modèle de facture.
            **kwargs: Doit contenir 'pdf_bytes' (bytes du PDF source).

        Returns:
            GenerationResult avec pdf_bytes et xml_bytes.

        Raises:
            ValueError: Si pdf_bytes n'est pas fourni.
        """
        pdf_bytes = kwargs.get("pdf_bytes")
        if not isinstance(pdf_bytes, bytes):
            msg = "pdf_bytes (bytes du PDF source) est requis pour générer du Factur-X"
            raise ValueError(msg)

        xml_bytes = self.generate_xml(invoice)
        fx_level = _PROFILE_MAP.get(self.profile.upper(), "en16931")

        logger.info(
            "Génération Factur-X profil %s pour facture %s",
            fx_level,
            invoice.number,
        )

        facturx_pdf = generate_from_binary(
            pdf_bytes,
            xml_bytes,
            flavor="factur-x",
            level=fx_level,
        )

        return GenerationResult(
            xml_bytes=xml_bytes,
            pdf_bytes=facturx_pdf,
            profile=self.profile,
        )
