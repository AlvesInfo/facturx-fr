"""Fixtures partagées pour les tests PDP."""

from datetime import date
from decimal import Decimal

import pytest

from facturx_fr.models.enums import (
    InvoiceTypeCode,
    OperationCategory,
    PaymentMeansCode,
    UnitOfMeasure,
    VATCategory,
)
from facturx_fr.models.invoice import Invoice, InvoiceLine
from facturx_fr.models.party import Address, Party
from facturx_fr.models.payment import BankAccount, PaymentMeans, PaymentTerms
from facturx_fr.pdp.connectors.memory import MemoryPDP


@pytest.fixture
def sample_invoice() -> Invoice:
    """Facture de test conforme EN16931."""
    return Invoice(
        number="FA-2026-042",
        issue_date=date(2026, 9, 15),
        due_date=date(2026, 10, 15),
        type_code=InvoiceTypeCode.INVOICE,
        currency="EUR",
        operation_category=OperationCategory.DELIVERY,
        vat_on_debits=False,
        seller=Party(
            name="OptiPaulo SARL",
            siren="123456789",
            vat_number="FR12345678901",
            address=Address(
                street="12 rue des Opticiens",
                city="Créteil",
                postal_code="94000",
                country_code="FR",
            ),
        ),
        buyer=Party(
            name="LunettesPlus SA",
            siren="987654321",
            vat_number="FR98765432101",
            address=Address(
                street="5 avenue de la Vision",
                city="Paris",
                postal_code="75011",
                country_code="FR",
            ),
        ),
        lines=[
            InvoiceLine(
                description="Monture Ray-Ban Aviator",
                quantity=Decimal("10"),
                unit=UnitOfMeasure.UNIT,
                unit_price=Decimal("85.00"),
                vat_rate=Decimal("20.0"),
                vat_category=VATCategory.STANDARD,
            ),
            InvoiceLine(
                description="Verres progressifs Essilor",
                quantity=Decimal("10"),
                unit=UnitOfMeasure.UNIT,
                unit_price=Decimal("35.00"),
                vat_rate=Decimal("20.0"),
                vat_category=VATCategory.STANDARD,
            ),
        ],
        payment_terms=PaymentTerms(
            description="30 jours fin de mois",
            late_penalty_rate=Decimal("3.0"),
            early_discount="Néant",
            recovery_fee=Decimal("40.00"),
        ),
        payment_means=PaymentMeans(
            code=PaymentMeansCode.CREDIT_TRANSFER,
            bank_account=BankAccount(
                iban="FR7630001007941234567890185",
                bic="BDFEFRPP",
            ),
        ),
    )


@pytest.fixture
def second_invoice() -> Invoice:
    """Seconde facture de test (vendeur/acheteur différents)."""
    return Invoice(
        number="FA-2026-099",
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 11, 1),
        type_code=InvoiceTypeCode.INVOICE,
        currency="EUR",
        operation_category=OperationCategory.SERVICE,
        seller=Party(
            name="TechConsult SAS",
            siren="111222333",
            vat_number="FR11122233301",
            address=Address(
                street="8 boulevard Tech",
                city="Lyon",
                postal_code="69001",
                country_code="FR",
            ),
        ),
        buyer=Party(
            name="ClientCorp SA",
            siren="444555666",
            vat_number="FR44455566601",
            address=Address(
                street="3 place du Commerce",
                city="Bordeaux",
                postal_code="33000",
                country_code="FR",
            ),
        ),
        lines=[
            InvoiceLine(
                description="Prestation de conseil",
                quantity=Decimal("5"),
                unit=UnitOfMeasure.DAY,
                unit_price=Decimal("800.00"),
                vat_rate=Decimal("20.0"),
                vat_category=VATCategory.STANDARD,
            ),
        ],
    )


@pytest.fixture
def memory_pdp() -> MemoryPDP:
    """Connecteur PDP en mémoire."""
    return MemoryPDP()
