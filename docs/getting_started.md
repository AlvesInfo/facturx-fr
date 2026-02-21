# Guide de démarrage

La réforme de la facturation électronique impose à toutes les entreprises françaises de recevoir des factures au format électronique à partir du 1er septembre 2026, puis d'en émettre à partir de 2027 (PME/micro). **facturx-fr** fournit tous les outils pour générer, valider et transmettre des factures conformes.

## Installation

```bash
# Installation de base (modèles + générateurs XML + validation)
pip install facturx-fr

# Avec UV (recommandé)
uv pip install facturx-fr
```

### Extras disponibles

```bash
# Génération PDF/A-3 (Factur-X)
pip install "facturx-fr[pdf]"

# Intégration Django
pip install "facturx-fr[django]"

# Intégration FastAPI
pip install "facturx-fr[fastapi]"

# Tâches asynchrones
pip install "facturx-fr[celery]"

# Validation schématron (EN16931)
pip install "facturx-fr[schematron]"

# Développement
pip install "facturx-fr[dev]"
```

## Première facture

### 1. Créer le modèle Invoice

```python
from decimal import Decimal
from datetime import date

from facturx_fr.models import Invoice, InvoiceLine, Party, Address
from facturx_fr.models.payment import PaymentTerms, PaymentMeans, BankAccount
from facturx_fr.models.enums import (
    InvoiceTypeCode,
    OperationCategory,
    VATCategory,
    PaymentMeansCode,
)

invoice = Invoice(
    # --- Identification ---
    number="FA-2026-001",
    issue_date=date(2026, 9, 15),
    due_date=date(2026, 10, 15),
    type_code=InvoiceTypeCode.INVOICE,
    currency="EUR",

    # --- Mention obligatoire sept. 2026 ---
    operation_category=OperationCategory.SERVICE,
    vat_on_debits=False,

    # --- Vendeur ---
    seller=Party(
        name="Ma Société SARL",
        siren="123456789",
        vat_number="FR12345678901",
        address=Address(
            street="12 rue du Commerce",
            city="Paris",
            postal_code="75011",
            country_code="FR",
        ),
    ),

    # --- Acheteur ---
    buyer=Party(
        name="Client SA",
        siren="987654321",
        vat_number="FR98765432101",
        address=Address(
            street="5 avenue de la République",
            city="Lyon",
            postal_code="69001",
            country_code="FR",
        ),
    ),

    # --- Lignes de facture (obligatoire, au moins une) ---
    lines=[
        InvoiceLine(
            description="Prestation de conseil — septembre 2026",
            quantity=Decimal("5"),
            unit_price=Decimal("500.00"),
            vat_rate=Decimal("20.0"),
            vat_category=VATCategory.STANDARD,
        ),
    ],

    # --- Paiement ---
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

# Les totaux sont calculés automatiquement
print(f"Total HT :  {invoice.total_excl_tax} EUR")   # 2500.00
print(f"Total TVA : {invoice.total_vat} EUR")          # 500.00
print(f"Total TTC : {invoice.total_incl_tax} EUR")     # 3000.00
print(f"À payer :   {invoice.amount_due} EUR")         # 3000.00
```

### 2. Générer le XML CII

```python
from facturx_fr.generators import CIIGenerator

generator = CIIGenerator(profile="EN16931")
xml_bytes = generator.generate_xml(invoice)

# Sauvegarder le XML
with open("facture.xml", "wb") as f:
    f.write(xml_bytes)
```

### 3. Générer le Factur-X (PDF/A-3 + XML)

Le format Factur-X combine un PDF lisible et un XML structuré. Vous devez fournir un PDF source (généré par WeasyPrint, ReportLab, ou tout autre outil).

```python
from facturx_fr.generators import FacturXGenerator

# Lire un PDF source existant
with open("facture_template.pdf", "rb") as f:
    pdf_source = f.read()

generator = FacturXGenerator(profile="EN16931")
result = generator.generate(invoice, pdf_bytes=pdf_source)

# result.xml_bytes contient le XML CII
# result.pdf_bytes contient le PDF/A-3 avec XML embarqué
result.save("facture_facturx.pdf")
```

### 4. Valider le XML

```python
from facturx_fr.validators import validate_xml, validate_xsd

# Validation XSD seule
xsd_errors = validate_xsd(xml_bytes, flavor="factur-x", profile="EN16931")

# Validation complète (XSD + schématrons EN16931)
errors = validate_xml(xml_bytes, flavor="factur-x", profile="EN16931")

if errors:
    for error in errors:
        print(f"Erreur : {error}")
else:
    print("XML valide !")
```

## Exemple complet de bout en bout

```python
"""Exemple complet : créer une facture, générer le XML, valider, déposer."""

from decimal import Decimal
from datetime import date

from facturx_fr.models import Invoice, InvoiceLine, Party, Address
from facturx_fr.models.payment import PaymentTerms, PaymentMeans, BankAccount
from facturx_fr.models.enums import (
    OperationCategory,
    VATCategory,
    PaymentMeansCode,
    UnitOfMeasure,
)
from facturx_fr.generators import CIIGenerator
from facturx_fr.validators import validate_xml

# 1. Créer la facture
invoice = Invoice(
    number="FA-2026-042",
    issue_date=date(2026, 9, 15),
    due_date=date(2026, 10, 15),
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
            quantity=Decimal("20"),
            unit=UnitOfMeasure.PAIR,
            unit_price=Decimal("45.50"),
            vat_rate=Decimal("20.0"),
            vat_category=VATCategory.STANDARD,
        ),
    ],
    payment_terms=PaymentTerms(
        description="30 jours fin de mois",
        late_penalty_rate=Decimal("3.0"),
        early_discount="Néant",
    ),
    payment_means=PaymentMeans(
        code=PaymentMeansCode.CREDIT_TRANSFER,
        bank_account=BankAccount(iban="FR7630001007941234567890185"),
    ),
)

# 2. Générer le XML CII
generator = CIIGenerator(profile="EN16931")
result = generator.generate(invoice)
xml_bytes = result.xml_bytes

# 3. Valider le XML
errors = validate_xml(xml_bytes)
if errors:
    print("Erreurs de validation :")
    for e in errors:
        print(f"  - {e}")
else:
    print(f"Facture {invoice.number} valide !")
    print(f"  Total HT :  {invoice.total_excl_tax} EUR")
    print(f"  Total TTC : {invoice.total_incl_tax} EUR")

    # 4. Sauvegarder
    result.save("facture.xml")
```

## Aller plus loin

- [Formats de factures](formats.md) — Factur-X vs UBL vs CII, profils, cas particuliers
- [Intégration PDP](pdp_integration.md) — Déposer des factures via une plateforme agréée
- [Intégration Django](django_integration.md) — App Django, admin, tâches Celery
