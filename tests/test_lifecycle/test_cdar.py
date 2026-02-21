"""Tests de la génération et du parsing des messages CDAR.

FR: Vérifie la création de CDARMessage, la génération XML conforme
    UN/CEFACT D22B, le parsing XML et le roundtrip generate→parse.
EN: Verifies CDARMessage creation, XML generation per UN/CEFACT D22B,
    XML parsing and the generate→parse roundtrip.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from lxml import etree

from facturx_fr.lifecycle.cdar import (
    CDAR_GUIDELINE_ID,
    CDAR_TYPE_CODE,
    NS_RAM,
    NS_RSM,
    NS_UDT,
    CDARGenerator,
    CDARMessage,
    CDARParser,
    CDARParty,
)
from facturx_fr.models.enums import CDARRoleCode, InvoiceStatus

NS = {"rsm": NS_RSM, "ram": NS_RAM, "udt": NS_UDT}


@pytest.fixture
def sample_cdar_message() -> CDARMessage:
    """Message CDAR de test : statut APPROUVEE."""
    return CDARMessage(
        message_id="CDAR-2026-001",
        issue_datetime=datetime(2026, 9, 16, 9, 30, 0, tzinfo=UTC),
        status_code=InvoiceStatus.APPROUVEE,
        invoice_reference="FA-2026-042",
        sender=CDARParty(
            identifier="987654321",
            scheme_id="0002",
            role_code=CDARRoleCode.BUYER,
        ),
        recipients=[
            CDARParty(
                identifier="123456789",
                scheme_id="0002",
                role_code=CDARRoleCode.PLATFORM,
            ),
        ],
    )


@pytest.fixture
def refusal_cdar_message() -> CDARMessage:
    """Message CDAR de test : statut REFUSEE avec motif."""
    return CDARMessage(
        message_id="CDAR-2026-002",
        issue_datetime=datetime(2026, 9, 17, 14, 0, 0, tzinfo=UTC),
        status_code=InvoiceStatus.REFUSEE,
        invoice_reference="FA-2026-043",
        sender=CDARParty(
            identifier="987654321",
            scheme_id="0002",
            role_code=CDARRoleCode.BUYER,
        ),
        recipients=[
            CDARParty(
                identifier="123456789",
                scheme_id="0002",
                role_code=CDARRoleCode.PLATFORM,
            ),
        ],
        reason="Marchandise non conforme à la commande",
        reason_code="RC01",
    )


class TestCDARMessage:
    """Tests de création du modèle CDARMessage."""

    def test_create_message(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie la création d'un CDARMessage."""
        assert sample_cdar_message.message_id == "CDAR-2026-001"
        assert sample_cdar_message.status_code == InvoiceStatus.APPROUVEE
        assert sample_cdar_message.invoice_reference == "FA-2026-042"
        assert sample_cdar_message.reason is None

    def test_create_message_with_reason(self, refusal_cdar_message: CDARMessage) -> None:
        """Vérifie la création d'un CDARMessage avec motif."""
        assert refusal_cdar_message.reason == "Marchandise non conforme à la commande"
        assert refusal_cdar_message.reason_code == "RC01"

    def test_create_message_with_amount(self) -> None:
        """Vérifie la création d'un CDARMessage avec montant."""
        msg = CDARMessage(
            message_id="CDAR-2026-003",
            issue_datetime=datetime(2026, 10, 15, tzinfo=UTC),
            status_code=InvoiceStatus.ENCAISSEE,
            invoice_reference="FA-2026-044",
            sender=CDARParty(
                identifier="123456789",
                scheme_id="0002",
                role_code=CDARRoleCode.SELLER,
            ),
            recipients=[
                CDARParty(
                    identifier="PA-001",
                    scheme_id="0224",
                    role_code=CDARRoleCode.PLATFORM,
                ),
            ],
            amount=Decimal("9500.00"),
        )
        assert msg.amount == Decimal("9500.00")

    def test_party_model(self) -> None:
        """Vérifie les champs d'un CDARParty."""
        party = CDARParty(
            identifier="123456789",
            scheme_id="0002",
            role_code=CDARRoleCode.SELLER,
        )
        assert party.identifier == "123456789"
        assert party.scheme_id == "0002"
        assert party.role_code == CDARRoleCode.SELLER


class TestCDARGenerator:
    """Tests de la génération XML CDAR."""

    def test_xml_well_formed(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie que le XML généré est bien formé."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        # Ne doit pas lever d'exception
        root = etree.fromstring(xml_bytes)
        assert root is not None

    def test_root_element(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie l'élément racine et les namespaces."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        root = etree.fromstring(xml_bytes)

        assert root.tag == f"{{{NS_RSM}}}CrossDomainAcknowledgementAndResponse"
        assert root.nsmap["rsm"] == NS_RSM
        assert root.nsmap["ram"] == NS_RAM
        assert root.nsmap["udt"] == NS_UDT

    def test_context_guideline(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie ExchangedDocumentContext et le guideline ID."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        root = etree.fromstring(xml_bytes)

        guideline = root.find(
            "rsm:ExchangedDocumentContext/"
            "ram:GuidelineSpecifiedDocumentContextParameter/"
            "ram:ID",
            NS,
        )
        assert guideline is not None
        assert guideline.text == CDAR_GUIDELINE_ID

    def test_exchanged_document(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie ExchangedDocument (ID, type, statut, date)."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        root = etree.fromstring(xml_bytes)

        doc = root.find("rsm:ExchangedDocument", NS)
        assert doc is not None

        assert doc.find("ram:ID", NS).text == "CDAR-2026-001"
        assert doc.find("ram:TypeCode", NS).text == CDAR_TYPE_CODE
        assert doc.find("ram:StatusCode", NS).text == "205"  # APPROUVEE

        dt = doc.find("ram:IssueDateTime/udt:DateTimeString", NS)
        assert dt is not None
        assert dt.text == "20260916"
        assert dt.get("format") == "102"

    def test_sender_party(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie SenderTradeParty."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        root = etree.fromstring(xml_bytes)

        sender = root.find("rsm:ExchangedDocument/ram:SenderTradeParty", NS)
        assert sender is not None

        sender_id = sender.find("ram:ID", NS)
        assert sender_id.text == "987654321"
        assert sender_id.get("schemeID") == "0002"

        role = sender.find("ram:RoleCode", NS)
        assert role.text == "BY"

    def test_recipient_party(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie RecipientTradeParty."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        root = etree.fromstring(xml_bytes)

        recipients = root.findall(
            "rsm:ExchangedDocument/ram:RecipientTradeParty", NS
        )
        assert len(recipients) == 1

        recip_id = recipients[0].find("ram:ID", NS)
        assert recip_id.text == "123456789"
        assert recip_id.get("schemeID") == "0002"

        role = recipients[0].find("ram:RoleCode", NS)
        assert role.text == "WK"

    def test_acknowledgement_document(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie AcknowledgementDocument (statut + référence facture)."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        root = etree.fromstring(xml_bytes)

        ack = root.find("rsm:AcknowledgementDocument", NS)
        assert ack is not None

        assert ack.find("ram:StatusCode", NS).text == "205"

        ref = ack.find("ram:ReferenceReferencedDocument/ram:IssuerAssignedID", NS)
        assert ref is not None
        assert ref.text == "FA-2026-042"

        # Pas de motif pour APPROUVEE
        assert ack.find("ram:ReasonInformation", NS) is None

    def test_acknowledgement_no_amount_by_default(
        self, sample_cdar_message: CDARMessage
    ) -> None:
        """Vérifie l'absence de SpecifiedAmount par défaut."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)
        root = etree.fromstring(xml_bytes)

        ack = root.find("rsm:AcknowledgementDocument", NS)
        assert ack.find("ram:SpecifiedAmount", NS) is None


class TestCDARRefusal:
    """Tests du message CDAR de refus."""

    def test_refusal_reason(self, refusal_cdar_message: CDARMessage) -> None:
        """Vérifie que le motif de refus est présent dans le XML."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(refusal_cdar_message)
        root = etree.fromstring(xml_bytes)

        ack = root.find("rsm:AcknowledgementDocument", NS)
        assert ack is not None

        reason = ack.find("ram:ReasonInformation", NS)
        assert reason is not None
        assert reason.text == "Marchandise non conforme à la commande"

        reason_code = ack.find("ram:ReasonCode", NS)
        assert reason_code is not None
        assert reason_code.text == "RC01"

    def test_refusal_status_code(self, refusal_cdar_message: CDARMessage) -> None:
        """Vérifie le code statut REFUSEE (210)."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(refusal_cdar_message)
        root = etree.fromstring(xml_bytes)

        ack = root.find("rsm:AcknowledgementDocument", NS)
        assert ack.find("ram:StatusCode", NS).text == "210"


class TestCDARMultipleRecipients:
    """Tests avec plusieurs destinataires."""

    def test_multiple_recipients(self) -> None:
        """Vérifie plusieurs RecipientTradeParty (PA-E + PPF)."""
        msg = CDARMessage(
            message_id="CDAR-MULTI-001",
            issue_datetime=datetime(2026, 9, 16, tzinfo=UTC),
            status_code=InvoiceStatus.DEPOSEE,
            invoice_reference="FA-2026-042",
            sender=CDARParty(
                identifier="PA-EMIT-001",
                scheme_id="0224",
                role_code=CDARRoleCode.PLATFORM,
            ),
            recipients=[
                CDARParty(
                    identifier="PA-RECEP-002",
                    scheme_id="0224",
                    role_code=CDARRoleCode.PLATFORM,
                ),
                CDARParty(
                    identifier="PPF-001",
                    scheme_id="0009",
                    role_code=CDARRoleCode.PPF,
                ),
            ],
        )

        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(msg)
        root = etree.fromstring(xml_bytes)

        recipients = root.findall(
            "rsm:ExchangedDocument/ram:RecipientTradeParty", NS
        )
        assert len(recipients) == 2

        roles = [r.find("ram:RoleCode", NS).text for r in recipients]
        assert "WK" in roles
        assert "DFH" in roles


class TestCDAREncaissement:
    """Tests du message CDAR d'encaissement avec montant."""

    def test_encaissement_with_amount(self) -> None:
        """Vérifie SpecifiedAmount pour un encaissement partiel."""
        msg = CDARMessage(
            message_id="CDAR-ENC-001",
            issue_datetime=datetime(2026, 10, 15, tzinfo=UTC),
            status_code=InvoiceStatus.ENCAISSEE,
            invoice_reference="FA-2026-042",
            sender=CDARParty(
                identifier="123456789",
                scheme_id="0002",
                role_code=CDARRoleCode.SELLER,
            ),
            recipients=[
                CDARParty(
                    identifier="PA-001",
                    scheme_id="0224",
                    role_code=CDARRoleCode.PLATFORM,
                ),
            ],
            amount=Decimal("9500.00"),
        )

        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(msg)
        root = etree.fromstring(xml_bytes)

        ack = root.find("rsm:AcknowledgementDocument", NS)
        amount_elem = ack.find("ram:SpecifiedAmount", NS)
        assert amount_elem is not None
        assert amount_elem.text == "9500.00"


class TestCDARParser:
    """Tests du parsing XML CDAR."""

    def test_parse_basic_message(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie le parsing d'un message CDAR basique."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert parsed.message_id == "CDAR-2026-001"
        assert parsed.status_code == InvoiceStatus.APPROUVEE
        assert parsed.invoice_reference == "FA-2026-042"
        assert parsed.reason is None

    def test_parse_refusal_message(self, refusal_cdar_message: CDARMessage) -> None:
        """Vérifie le parsing d'un message de refus."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(refusal_cdar_message)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert parsed.status_code == InvoiceStatus.REFUSEE
        assert parsed.reason == "Marchandise non conforme à la commande"
        assert parsed.reason_code == "RC01"

    def test_parse_sender(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie le parsing du sender."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert parsed.sender.identifier == "987654321"
        assert parsed.sender.scheme_id == "0002"
        assert parsed.sender.role_code == CDARRoleCode.BUYER

    def test_parse_recipients(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie le parsing des destinataires."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert len(parsed.recipients) == 1
        assert parsed.recipients[0].identifier == "123456789"
        assert parsed.recipients[0].role_code == CDARRoleCode.PLATFORM

    def test_parse_amount(self) -> None:
        """Vérifie le parsing du montant."""
        msg = CDARMessage(
            message_id="CDAR-AMT-001",
            issue_datetime=datetime(2026, 10, 15, tzinfo=UTC),
            status_code=InvoiceStatus.ENCAISSEE,
            invoice_reference="FA-2026-042",
            sender=CDARParty(
                identifier="123456789",
                scheme_id="0002",
                role_code=CDARRoleCode.SELLER,
            ),
            recipients=[
                CDARParty(
                    identifier="PA-001",
                    scheme_id="0224",
                    role_code=CDARRoleCode.PLATFORM,
                ),
            ],
            amount=Decimal("9500.00"),
        )

        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(msg)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)
        assert parsed.amount == Decimal("9500.00")

    def test_parse_invalid_xml(self) -> None:
        """Vérifie qu'un XML invalide lève une exception."""
        parser = CDARParser()
        with pytest.raises(Exception):
            parser.parse(b"<invalid>xml</invalid>")

    def test_parse_missing_exchanged_document(self) -> None:
        """Vérifie qu'un XML sans ExchangedDocument lève ValueError."""
        xml = (
            b'<?xml version="1.0"?>'
            b"<rsm:CrossDomainAcknowledgementAndResponse"
            b" xmlns:rsm="
            b'"urn:un:unece:uncefact:data:standard:CrossDomainAcknowledgementAndResponse:100"'
            b" xmlns:ram="
            b'"urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"'
            b">"
            b"</rsm:CrossDomainAcknowledgementAndResponse>"
        )
        parser = CDARParser()
        with pytest.raises(ValueError, match="ExchangedDocument manquant"):
            parser.parse(xml)


class TestCDARRoundtrip:
    """Tests du roundtrip generate → parse."""

    def test_roundtrip_basic(self, sample_cdar_message: CDARMessage) -> None:
        """Vérifie le roundtrip complet pour un message basique."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(sample_cdar_message)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert parsed.message_id == sample_cdar_message.message_id
        assert parsed.status_code == sample_cdar_message.status_code
        assert parsed.invoice_reference == sample_cdar_message.invoice_reference
        assert parsed.sender.identifier == sample_cdar_message.sender.identifier
        assert parsed.sender.scheme_id == sample_cdar_message.sender.scheme_id
        assert parsed.sender.role_code == sample_cdar_message.sender.role_code
        assert len(parsed.recipients) == len(sample_cdar_message.recipients)

    def test_roundtrip_refusal(self, refusal_cdar_message: CDARMessage) -> None:
        """Vérifie le roundtrip pour un message de refus."""
        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(refusal_cdar_message)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert parsed.reason == refusal_cdar_message.reason
        assert parsed.reason_code == refusal_cdar_message.reason_code

    def test_roundtrip_multiple_recipients(self) -> None:
        """Vérifie le roundtrip avec plusieurs destinataires."""
        msg = CDARMessage(
            message_id="CDAR-RT-MULTI",
            issue_datetime=datetime(2026, 9, 16, tzinfo=UTC),
            status_code=InvoiceStatus.DEPOSEE,
            invoice_reference="FA-2026-050",
            sender=CDARParty(
                identifier="PA-001",
                scheme_id="0224",
                role_code=CDARRoleCode.PLATFORM,
            ),
            recipients=[
                CDARParty(
                    identifier="PA-002",
                    scheme_id="0224",
                    role_code=CDARRoleCode.PLATFORM,
                ),
                CDARParty(
                    identifier="PPF-001",
                    scheme_id="0009",
                    role_code=CDARRoleCode.PPF,
                ),
            ],
        )

        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(msg)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert len(parsed.recipients) == 2
        roles = {r.role_code for r in parsed.recipients}
        assert CDARRoleCode.PLATFORM in roles
        assert CDARRoleCode.PPF in roles

    def test_roundtrip_encaissement_with_amount(self) -> None:
        """Vérifie le roundtrip pour un encaissement avec montant."""
        msg = CDARMessage(
            message_id="CDAR-RT-ENC",
            issue_datetime=datetime(2026, 10, 15, tzinfo=UTC),
            status_code=InvoiceStatus.ENCAISSEE,
            invoice_reference="FA-2026-042",
            sender=CDARParty(
                identifier="123456789",
                scheme_id="0002",
                role_code=CDARRoleCode.SELLER,
            ),
            recipients=[
                CDARParty(
                    identifier="PA-001",
                    scheme_id="0224",
                    role_code=CDARRoleCode.PLATFORM,
                ),
            ],
            amount=Decimal("9500.00"),
        )

        gen = CDARGenerator()
        xml_bytes = gen.generate_xml(msg)

        parser = CDARParser()
        parsed = parser.parse(xml_bytes)

        assert parsed.amount == Decimal("9500.00")
        assert parsed.status_code == InvoiceStatus.ENCAISSEE
