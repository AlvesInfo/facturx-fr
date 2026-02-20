# facturx-fr

[![PyPI version](https://img.shields.io/pypi/v/facturx-fr.svg)](https://pypi.org/project/facturx-fr/)
[![Python](https://img.shields.io/pypi/pyversions/facturx-fr.svg)](https://pypi.org/project/facturx-fr/)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Tests](https://github.com/facturx-fr/facturx-fr/actions/workflows/tests.yml/badge.svg)](https://github.com/facturx-fr/facturx-fr/actions)

Bibliothèque Python pour la **facturation électronique française**, conforme à la réforme obligatoire au 1er septembre 2026.

## Fonctionnalités

- **Factur-X** : génération de factures hybrides PDF/A-3 + XML CII
- **UBL & CII** : génération XML pur aux formats standards européens
- **Validation** : validation XSD et schématrons français (BR-FR-CTC)
- **Connecteurs PDP** : interface abstraite multi-connecteurs conforme à la norme AFNOR XP Z12-013
- **Cycle de vie** : gestion des statuts obligatoires (déposée → approuvée → encaissée…)
- **E-reporting** : transactions B2C et internationales
- **Django & FastAPI** : intégrations prêtes à l'emploi

## Installation

```bash
uv pip install facturx-fr
```

Avec les extras :

```bash
# Génération PDF (WeasyPrint)
uv pip install "facturx-fr[pdf]"

# Intégration Django
uv pip install "facturx-fr[django]"

# Intégration FastAPI
uv pip install "facturx-fr[fastapi]"

# Développement
uv pip install "facturx-fr[dev]"
```

## Démarrage rapide

```python
from decimal import Decimal
from datetime import date
from facturx_fr.models import Invoice, InvoiceLine, Party, Address
from facturx_fr.models.enums import OperationCategory

# Créer une facture
invoice = Invoice(
    number="FA-2026-042",
    issue_date=date(2026, 9, 15),
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
    lines=[
        InvoiceLine(
            description="Prestation de conseil",
            quantity=Decimal("5"),
            unit_price=Decimal("500.00"),
            vat_rate=Decimal("20.0"),
        ),
    ],
    operation_category=OperationCategory.SERVICE,
    currency="EUR",
)

print(f"Facture {invoice.number} — Total TTC : {invoice.total_incl_tax} EUR")
```

## Formats supportés

| Format    | Type              | Standard     | Statut       |
|-----------|-------------------|--------------|--------------|
| Factur-X  | PDF/A-3 + XML CII | EN 16931     | En cours     |
| UBL       | XML pur           | OASIS UBL    | Planifié     |
| CII       | XML pur           | UN/CEFACT    | Planifié     |

## Documentation

- [Guide de démarrage](docs/getting_started.md)
- [Formats de factures](docs/formats.md)
- [Intégration PDP](docs/pdp_integration.md)
- [Intégration Django](docs/django_integration.md)

## Licence

Ce projet est distribué sous licence [LGPL-3.0-or-later](LICENSE).
