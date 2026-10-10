"""Tests de la subdivision de pays (région) dans les adresses CII et UBL."""

from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from facturx_fr.generators.cii import CIIGenerator
from facturx_fr.generators.ubl import UBLGenerator
from facturx_fr.models import Address, Invoice, InvoiceLine, Party
from facturx_fr.models.enums import OperationCategory

RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"


@pytest.fixture
def invoice_with_subdivision() -> Invoice:
    """Facture dont l'adresse vendeur comporte une subdivision de pays."""
    return Invoice(
        number="FA-SUBDIV-001",
        issue_date=date(2026, 9, 15),
        seller=Party(
            name="Vendeur",
            address=Address(
                street="10 rue Complète",
                city="Marseille",
                postal_code="13001",
                country_subdivision="Provence-Alpes-Côte d'Azur",
            ),
        ),
        buyer=Party(
            name="Acheteur",
            address=Address(street="2 rue", city="Lyon", postal_code="69001"),
        ),
        lines=[
            InvoiceLine(
                description="Produit",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
            ),
        ],
        operation_category=OperationCategory.DELIVERY,
    )


def test_cii_country_subdivision(invoice_with_subdivision: Invoice) -> None:
    """Le CII émet ram:CountrySubDivisionName."""
    root = etree.fromstring(CIIGenerator().generate_xml(invoice_with_subdivision))
    found = [el.text for el in root.iter(f"{{{RAM}}}CountrySubDivisionName")]
    assert found == ["Provence-Alpes-Côte d'Azur"]


def test_ubl_country_subdivision(invoice_with_subdivision: Invoice) -> None:
    """L'UBL émet cbc:CountrySubentity."""
    root = etree.fromstring(UBLGenerator().generate_xml(invoice_with_subdivision))
    found = [el.text for el in root.iter(f"{{{CBC}}}CountrySubentity")]
    assert found == ["Provence-Alpes-Côte d'Azur"]
