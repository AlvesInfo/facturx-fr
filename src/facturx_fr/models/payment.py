"""Modèles pour les conditions et moyens de paiement.

FR: Représentation des modalités de paiement conformes à EN16931
    et aux obligations du Code de Commerce (pénalités, escompte,
    indemnité forfaitaire de recouvrement).
EN: Representation of payment terms conforming to EN16931 and
    French Commercial Code obligations.
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from facturx_fr.models.enums import PaymentMeansCode


class BankAccount(BaseModel):
    """Coordonnées bancaires.

    FR: IBAN et BIC du bénéficiaire pour les virements.
    EN: Beneficiary IBAN and BIC for credit transfers.
    """

    iban: str = Field(
        ...,
        description="IBAN du bénéficiaire / Beneficiary IBAN",
    )
    bic: str | None = Field(
        default=None,
        description="BIC/SWIFT du bénéficiaire / Beneficiary BIC/SWIFT",
    )


class PaymentTerms(BaseModel):
    """Conditions de paiement.

    FR: Termes de paiement incluant les mentions obligatoires du
        Code de Commerce (art. L441-9) :
        - pénalités de retard
        - escompte pour paiement anticipé (ou mention « Néant »)
        - indemnité forfaitaire de recouvrement (40€)
    EN: Payment terms including mandatory French Commercial Code mentions.
    """

    description: str | None = Field(
        default=None,
        description=(
            "Description des conditions de paiement / "
            "Payment terms description (e.g. '30 jours fin de mois')"
        ),
    )
    late_penalty_rate: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Taux des pénalités de retard en % (mention obligatoire L441-9) / "
            "Late payment penalty rate in %"
        ),
    )
    early_discount: str | None = Field(
        default=None,
        description=(
            "Conditions d'escompte (mention obligatoire L441-9, 'Néant' si aucun) / "
            "Early payment discount terms"
        ),
    )
    recovery_fee: Decimal = Field(
        default=Decimal("40.00"),
        ge=0,
        description=(
            "Indemnité forfaitaire de recouvrement en € (mention obligatoire L441-9, "
            "minimum légal 40€) / Fixed recovery fee in EUR"
        ),
    )


class PaymentMeans(BaseModel):
    """Moyen de paiement.

    FR: Identifie le mode de règlement (virement, prélèvement, etc.)
        avec les coordonnées bancaires associées.
    EN: Identifies the payment method (transfer, direct debit, etc.)
        with associated banking details.
    """

    code: PaymentMeansCode = Field(
        ...,
        description="Code du moyen de paiement (UNTDID 4461) / Payment means code",
    )
    bank_account: BankAccount | None = Field(
        default=None,
        description="Coordonnées bancaires / Bank account details",
    )
    payment_reference: str | None = Field(
        default=None,
        description="Référence de paiement / Payment reference",
    )
