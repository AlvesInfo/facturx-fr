"""Générateur UBL (XML pur, standard OASIS)."""

from facturx_fr.generators.base import BaseGenerator, GenerationResult
from facturx_fr.models.invoice import Invoice


class UBLGenerator(BaseGenerator):
    """Générateur de factures au format UBL.

    FR: Produit un XML conforme au standard OASIS UBL 2.1.
    EN: Produces an XML conforming to the OASIS UBL 2.1 standard.
    """

    def generate(self, invoice: Invoice, **kwargs: object) -> GenerationResult:
        """Génère une facture UBL."""
        raise NotImplementedError("Générateur UBL en cours de développement")

    def generate_xml(self, invoice: Invoice) -> bytes:
        """Génère le XML UBL de la facture."""
        raise NotImplementedError("Génération XML UBL en cours de développement")
