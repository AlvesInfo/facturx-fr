"""Modèles pour les parties (vendeur, acheteur) et adresses.

FR: Représentation des entités impliquées dans une facture,
    avec les mentions obligatoires de la réforme 2026 (SIREN, etc.).
EN: Representation of entities involved in an invoice,
    with mandatory fields from the 2026 reform (SIREN, etc.).
"""

from pydantic import BaseModel, Field


class Address(BaseModel):
    """Adresse postale.

    FR: Adresse complète d'une partie. L'adresse de livraison est obligatoire
        si elle diffère de l'adresse de facturation (réforme sept. 2026).
    EN: Full postal address. Delivery address is mandatory if different from
        billing address (Sept. 2026 reform).
    """

    street: str = Field(..., description="Rue et numéro / Street and number")
    additional_street: str | None = Field(
        default=None,
        description="Complément d'adresse / Additional street info",
    )
    city: str = Field(..., description="Ville / City")
    postal_code: str = Field(..., description="Code postal / Postal code")
    country_code: str = Field(
        default="FR",
        min_length=2,
        max_length=2,
        description="Code pays ISO 3166-1 alpha-2 / Country code",
    )
    country_subdivision: str | None = Field(
        default=None,
        description="Subdivision du pays (département, région) / Country subdivision",
    )


class Party(BaseModel):
    """Partie impliquée dans une facture (vendeur ou acheteur).

    FR: Représente le vendeur ou l'acheteur avec toutes les informations
        d'identification requises par la réforme française 2026.
    EN: Represents the seller or buyer with all identification information
        required by the French 2026 reform.
    """

    name: str = Field(..., description="Raison sociale / Legal name")
    siren: str | None = Field(
        default=None,
        min_length=9,
        max_length=9,
        pattern=r"^\d{9}$",
        description="Numéro SIREN (9 chiffres, obligatoire sept. 2026) / SIREN number",
    )
    siret: str | None = Field(
        default=None,
        min_length=14,
        max_length=14,
        pattern=r"^\d{14}$",
        description="Numéro SIRET (14 chiffres) / SIRET number",
    )
    vat_number: str | None = Field(
        default=None,
        description="Numéro de TVA intracommunautaire / VAT identification number",
    )
    registration_id: str | None = Field(
        default=None,
        description="Identifiant d'enregistrement légal / Legal registration ID",
    )
    address: Address = Field(..., description="Adresse principale / Main address")
    delivery_address: Address | None = Field(
        default=None,
        description="Adresse de livraison si différente / Delivery address if different",
    )
    email: str | None = Field(
        default=None,
        description="Adresse email / Email address",
    )
    phone: str | None = Field(
        default=None,
        description="Numéro de téléphone / Phone number",
    )
