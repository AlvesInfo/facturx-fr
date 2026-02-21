"""Configuration pytest pour les tests Django.

FR: Configure Django avec SQLite in-memory pour les tests.
EN: Configures Django with in-memory SQLite for tests.
"""

from datetime import date
from decimal import Decimal

import django
from django.conf import settings


def pytest_configure() -> None:
    """Configure Django pour les tests."""
    if not settings.configured:
        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                },
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "facturx_fr.contrib.django",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )
        django.setup()


import pytest  # noqa: E402

from facturx_fr.models.enums import (  # noqa: E402
    InvoiceTypeCode,
    OperationCategory,
    PaymentMeansCode,
    VATCategory,
)
from facturx_fr.models.invoice import Invoice as PydanticInvoice  # noqa: E402
from facturx_fr.models.invoice import InvoiceLine as PydanticInvoiceLine  # noqa: E402
from facturx_fr.models.party import Address, Party  # noqa: E402
from facturx_fr.models.payment import BankAccount, PaymentMeans  # noqa: E402


@pytest.fixture
def sample_pydantic_invoice() -> PydanticInvoice:
    """Fixture : facture Pydantic de test."""
    return PydanticInvoice(
        number="FA-2026-001",
        issue_date=date(2026, 9, 15),
        due_date=date(2026, 10, 15),
        type_code=InvoiceTypeCode.INVOICE,
        currency="EUR",
        operation_category=OperationCategory.DELIVERY,
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
            PydanticInvoiceLine(
                line_number=1,
                description="Monture Ray-Ban Aviator",
                quantity=Decimal("10"),
                unit_price=Decimal("85.00"),
                vat_rate=Decimal("20.0"),
                vat_category=VATCategory.STANDARD,
            ),
            PydanticInvoiceLine(
                line_number=2,
                description="Verres progressifs",
                quantity=Decimal("20"),
                unit_price=Decimal("45.50"),
                vat_rate=Decimal("20.0"),
                vat_category=VATCategory.STANDARD,
            ),
        ],
        payment_means=PaymentMeans(
            code=PaymentMeansCode.SEPA_CREDIT_TRANSFER,
            bank_account=BankAccount(
                iban="FR7630001007941234567890185",
                bic="BDFEFRPP",
            ),
        ),
    )


@pytest.fixture
def sample_invoice(db, sample_pydantic_invoice):
    """Fixture : facture Django sauvée en base (avec lignes)."""
    from facturx_fr.contrib.django.models import Invoice

    return Invoice.create_with_lines(sample_pydantic_invoice)
