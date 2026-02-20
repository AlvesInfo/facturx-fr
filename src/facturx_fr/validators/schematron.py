"""Validation par schématrons français (BR-FR-CTC)."""


def validate_schematron(
    xml_bytes: bytes,
    profile: str = "EN16931",
) -> list[str]:
    """Valide un XML de facture contre les schématrons français.

    FR: Applique les règles de gestion BR-FR-CTC de la FNFE-MPE.
    EN: Applies the BR-FR-CTC business rules from FNFE-MPE.

    Args:
        xml_bytes: Le contenu XML à valider.
        profile: Le profil de validation ("EN16931", "EXTENDED-CTC-FR").

    Returns:
        Liste des messages d'erreur.
    """
    raise NotImplementedError("Validation schématron en cours de développement")
