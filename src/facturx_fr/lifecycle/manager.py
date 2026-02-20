"""Machine à états pour le cycle de vie des factures."""

from facturx_fr.models.enums import InvoiceStatus

# Transitions autorisées : {statut_source: [statuts_cibles]}
TRANSITIONS: dict[InvoiceStatus, list[InvoiceStatus]] = {
    InvoiceStatus.DEPOSEE: [InvoiceStatus.MISE_A_DISPOSITION],
    InvoiceStatus.MISE_A_DISPOSITION: [InvoiceStatus.PRISE_EN_CHARGE],
    InvoiceStatus.PRISE_EN_CHARGE: [
        InvoiceStatus.APPROUVEE,
        InvoiceStatus.REFUSEE,
        InvoiceStatus.PARTIELLEMENT_APPROUVEE,
    ],
    InvoiceStatus.APPROUVEE: [InvoiceStatus.ENCAISSEE],
    InvoiceStatus.PARTIELLEMENT_APPROUVEE: [InvoiceStatus.ENCAISSEE],
    InvoiceStatus.REFUSEE: [],
    InvoiceStatus.ENCAISSEE: [],
}


class LifecycleManager:
    """Gestionnaire du cycle de vie d'une facture.

    FR: Implémente la machine à états des statuts obligatoires
        conformément à la norme AFNOR XP Z12-012.
    EN: Implements the mandatory status state machine
        in compliance with the AFNOR XP Z12-012 standard.
    """

    def __init__(self, initial_status: InvoiceStatus = InvoiceStatus.DEPOSEE) -> None:
        self.status = initial_status

    def can_transition(self, target: InvoiceStatus) -> bool:
        """Vérifie si la transition vers le statut cible est autorisée."""
        allowed = TRANSITIONS.get(self.status, [])
        return target in allowed

    def transition(self, target: InvoiceStatus) -> None:
        """Effectue la transition vers le statut cible.

        Raises:
            ValueError: Si la transition n'est pas autorisée.
        """
        if not self.can_transition(target):
            msg = (
                f"Transition non autorisée : {self.status.value} → {target.value}. "
                f"Transitions possibles : {[s.value for s in TRANSITIONS.get(self.status, [])]}"
            )
            raise ValueError(msg)
        self.status = target
