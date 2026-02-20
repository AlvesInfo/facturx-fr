"""Génération et parsing des messages CDAR (UN/CEFACT D22B).

FR: Implémente les messages Cross-industry Document and Application Response
    pour le cycle de vie des factures électroniques, conformément à la norme
    AFNOR XP Z12-012 et au schéma UN/CEFACT CDAR D22B.
EN: Implements Cross-industry Document and Application Response messages
    for e-invoice lifecycle, per AFNOR XP Z12-012 and UN/CEFACT CDAR D22B.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from lxml import etree
from pydantic import BaseModel

from facturx_fr.models.enums import CDARRoleCode, InvoiceStatus

# ---------------------------------------------------------------------------
# Namespaces CDAR (UN/CEFACT D22B)
# ---------------------------------------------------------------------------

NS_RSM = "urn:un:unece:uncefact:data:standard:CrossDomainAcknowledgementAndResponse:100"
NS_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
NS_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

NSMAP = {
    "rsm": NS_RSM,
    "ram": NS_RAM,
    "udt": NS_UDT,
}

_RSM = f"{{{NS_RSM}}}"
_RAM = f"{{{NS_RAM}}}"
_UDT = f"{{{NS_UDT}}}"

# Guideline ID pour les messages CDAR Factur-X
CDAR_GUIDELINE_ID = "urn:factur-x.eu:1p0:cdar"

# TypeCode pour les messages CDAR (acknowledgement/response)
CDAR_TYPE_CODE = "YC2"


# ---------------------------------------------------------------------------
# Modèles Pydantic
# ---------------------------------------------------------------------------


class CDARParty(BaseModel):
    """Partie impliquée dans un message CDAR.

    FR: Identifie un acteur du cycle de vie (PA, acheteur, vendeur, PPF).
    EN: Identifies a lifecycle actor (platform, buyer, seller, PPF).
    """

    identifier: str
    """Identifiant de la partie (SIREN, SIRET, GLN, Code_Routage)."""
    scheme_id: str
    """Schéma d'identification ("0002"=SIREN, "0009"=SIRET, "0224"=Code_Routage, "0088"=GLN)."""
    role_code: CDARRoleCode
    """Rôle de la partie dans le message CDAR."""


class CDARMessage(BaseModel):
    """Message CDAR (Cross-industry Document and Application Response).

    FR: Représente un message de cycle de vie conforme UN/CEFACT D22B.
        Chaque message référence une facture et porte un statut.
    EN: Represents a lifecycle message per UN/CEFACT D22B.
    """

    message_id: str
    """Identifiant unique du message CDAR."""
    issue_datetime: datetime
    """Date et heure d'émission du message."""
    status_code: InvoiceStatus
    """Code statut du cycle de vie."""
    invoice_reference: str
    """Numéro de la facture référencée."""
    sender: CDARParty
    """Émetteur du message."""
    recipients: list[CDARParty]
    """Destinataire(s) du message (peut être multiple : PA-E + PPF)."""
    reason: str | None = None
    """Motif (obligatoire pour REFUSEE)."""
    reason_code: str | None = None
    """Code motif (liste XP Z12-012)."""
    amount: Decimal | None = None
    """Montant pour encaissement partiel (retenue de garantie)."""


# ---------------------------------------------------------------------------
# Générateur XML CDAR
# ---------------------------------------------------------------------------


class CDARGenerator:
    """Génère un XML CDAR conforme UN/CEFACT D22B.

    FR: Produit un message XML de cycle de vie pour transmission
        entre les parties (PA, PPF, acheteur, vendeur).
    EN: Produces an XML lifecycle message for transmission
        between parties (platforms, PPF, buyer, seller).
    """

    def generate_xml(self, message: CDARMessage) -> bytes:
        """Génère le XML CDAR à partir d'un CDARMessage.

        Returns:
            Le XML sérialisé en bytes (UTF-8, avec déclaration XML).
        """
        root = etree.Element(f"{_RSM}CrossDomainAcknowledgementAndResponse", nsmap=NSMAP)

        self._build_context(root)
        self._build_exchanged_document(root, message)
        self._build_acknowledgement_document(root, message)

        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)

    def _build_context(self, root: etree._Element) -> None:
        """Construit ExchangedDocumentContext."""
        ctx = etree.SubElement(root, f"{_RSM}ExchangedDocumentContext")
        guideline = etree.SubElement(ctx, f"{_RAM}GuidelineSpecifiedDocumentContextParameter")
        guideline_id = etree.SubElement(guideline, f"{_RAM}ID")
        guideline_id.text = CDAR_GUIDELINE_ID

    def _build_exchanged_document(
        self, root: etree._Element, message: CDARMessage
    ) -> None:
        """Construit ExchangedDocument (ID, type, statut, date, parties)."""
        doc = etree.SubElement(root, f"{_RSM}ExchangedDocument")

        doc_id = etree.SubElement(doc, f"{_RAM}ID")
        doc_id.text = message.message_id

        type_code = etree.SubElement(doc, f"{_RAM}TypeCode")
        type_code.text = CDAR_TYPE_CODE

        status_code = etree.SubElement(doc, f"{_RAM}StatusCode")
        status_code.text = message.status_code.value

        issue_dt = etree.SubElement(doc, f"{_RAM}IssueDateTime")
        dt_string = etree.SubElement(issue_dt, f"{_UDT}DateTimeString")
        dt_string.set("format", "102")
        dt_string.text = message.issue_datetime.strftime("%Y%m%d")

        # Sender
        self._build_party(doc, f"{_RAM}SenderTradeParty", message.sender)

        # Recipients
        for recipient in message.recipients:
            self._build_party(doc, f"{_RAM}RecipientTradeParty", recipient)

    def _build_party(
        self, parent: etree._Element, tag: str, party: CDARParty
    ) -> None:
        """Construit un élément SenderTradeParty ou RecipientTradeParty."""
        elem = etree.SubElement(parent, tag)

        party_id = etree.SubElement(elem, f"{_RAM}ID")
        party_id.set("schemeID", party.scheme_id)
        party_id.text = party.identifier

        role_code = etree.SubElement(elem, f"{_RAM}RoleCode")
        role_code.text = party.role_code.value

    def _build_acknowledgement_document(
        self, root: etree._Element, message: CDARMessage
    ) -> None:
        """Construit AcknowledgementDocument (statut, motif, référence facture)."""
        ack = etree.SubElement(root, f"{_RSM}AcknowledgementDocument")

        status_code = etree.SubElement(ack, f"{_RAM}StatusCode")
        status_code.text = message.status_code.value

        if message.reason:
            reason_info = etree.SubElement(ack, f"{_RAM}ReasonInformation")
            reason_info.text = message.reason

        if message.reason_code:
            reason_code_elem = etree.SubElement(ack, f"{_RAM}ReasonCode")
            reason_code_elem.text = message.reason_code

        if message.amount is not None:
            amount_elem = etree.SubElement(ack, f"{_RAM}SpecifiedAmount")
            amount_elem.text = str(message.amount)

        ref_doc = etree.SubElement(ack, f"{_RAM}ReferenceReferencedDocument")
        issuer_id = etree.SubElement(ref_doc, f"{_RAM}IssuerAssignedID")
        issuer_id.text = message.invoice_reference


# ---------------------------------------------------------------------------
# Parseur XML CDAR
# ---------------------------------------------------------------------------


class CDARParser:
    """Parse un XML CDAR et retourne un CDARMessage.

    FR: Extrait les informations d'un message de cycle de vie reçu.
    EN: Extracts information from a received lifecycle message.
    """

    def parse(self, xml_bytes: bytes) -> CDARMessage:
        """Parse un XML CDAR et retourne un CDARMessage.

        Args:
            xml_bytes: Le XML CDAR en bytes.

        Returns:
            Le CDARMessage extrait.

        Raises:
            ValueError: Si le XML est invalide ou manque des éléments obligatoires.
        """
        root = etree.fromstring(xml_bytes)
        ns = {"rsm": NS_RSM, "ram": NS_RAM, "udt": NS_UDT}

        # ExchangedDocument
        doc = root.find("rsm:ExchangedDocument", ns)
        if doc is None:
            msg = "Élément ExchangedDocument manquant dans le XML CDAR."
            raise ValueError(msg)

        message_id = self._get_text(doc, "ram:ID", ns)
        status_code_text = self._get_text(doc, "ram:StatusCode", ns)
        status_code = InvoiceStatus(status_code_text)

        dt_string = doc.find("ram:IssueDateTime/udt:DateTimeString", ns)
        if dt_string is None:
            msg = "Élément IssueDateTime manquant dans le XML CDAR."
            raise ValueError(msg)
        issue_datetime = datetime.strptime(dt_string.text, "%Y%m%d")

        # Sender
        sender_elem = doc.find("ram:SenderTradeParty", ns)
        if sender_elem is None:
            msg = "Élément SenderTradeParty manquant dans le XML CDAR."
            raise ValueError(msg)
        sender = self._parse_party(sender_elem, ns)

        # Recipients
        recipient_elems = doc.findall("ram:RecipientTradeParty", ns)
        recipients = [self._parse_party(r, ns) for r in recipient_elems]

        # AcknowledgementDocument
        ack = root.find("rsm:AcknowledgementDocument", ns)
        if ack is None:
            msg = "Élément AcknowledgementDocument manquant dans le XML CDAR."
            raise ValueError(msg)

        reason = self._get_text_optional(ack, "ram:ReasonInformation", ns)
        reason_code = self._get_text_optional(ack, "ram:ReasonCode", ns)

        amount_text = self._get_text_optional(ack, "ram:SpecifiedAmount", ns)
        amount = Decimal(amount_text) if amount_text else None

        ref_doc = ack.find("ram:ReferenceReferencedDocument", ns)
        if ref_doc is None:
            msg = "Élément ReferenceReferencedDocument manquant dans le XML CDAR."
            raise ValueError(msg)
        invoice_reference = self._get_text(ref_doc, "ram:IssuerAssignedID", ns)

        return CDARMessage(
            message_id=message_id,
            issue_datetime=issue_datetime,
            status_code=status_code,
            invoice_reference=invoice_reference,
            sender=sender,
            recipients=recipients,
            reason=reason,
            reason_code=reason_code,
            amount=amount,
        )

    def _parse_party(self, elem: etree._Element, ns: dict[str, str]) -> CDARParty:
        """Parse un élément TradeParty en CDARParty."""
        id_elem = elem.find("ram:ID", ns)
        if id_elem is None:
            msg = "Élément ID manquant dans TradeParty."
            raise ValueError(msg)

        return CDARParty(
            identifier=id_elem.text or "",
            scheme_id=id_elem.get("schemeID", ""),
            role_code=CDARRoleCode(self._get_text(elem, "ram:RoleCode", ns)),
        )

    def _get_text(self, parent: etree._Element, path: str, ns: dict[str, str]) -> str:
        """Extrait le texte d'un élément obligatoire."""
        elem = parent.find(path, ns)
        if elem is None or not elem.text:
            msg = f"Élément obligatoire manquant : {path}"
            raise ValueError(msg)
        return elem.text

    def _get_text_optional(
        self, parent: etree._Element, path: str, ns: dict[str, str]
    ) -> str | None:
        """Extrait le texte d'un élément optionnel."""
        elem = parent.find(path, ns)
        if elem is None:
            return None
        return elem.text
