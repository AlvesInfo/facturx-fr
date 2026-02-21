# Formats de factures

## Comparatif des 3 formats

| | Factur-X | UBL | CII |
|---|---|---|---|
| **Type** | PDF/A-3 + XML CII | XML pur | XML pur |
| **Standard** | EN 16931 (CII) | OASIS UBL 2.1 | UN/CEFACT D16B |
| **Lisibilité humaine** | Oui (PDF) | Non | Non |
| **Compatible PEPPOL** | Non | Oui | Non |
| **Usage principal** | PME, factures mixtes PDF+données | Grands comptes, PEPPOL, EDI | Base technique Factur-X |
| **Classe** | `FacturXGenerator` | `UBLGenerator` | `CIIGenerator` |

**Recommandation** : utilisez **Factur-X** si vos clients ont besoin d'un PDF lisible (cas le plus courant pour les PME françaises). Utilisez **UBL** pour les échanges PEPPOL ou avec des partenaires européens. Le **CII pur** est rarement utilisé directement — c'est le format XML embarqué dans Factur-X.

## Profils Factur-X

Les profils déterminent le niveau de détail du XML embarqué :

| Profil | Description | Lignes de détail | Recommandé |
|---|---|---|---|
| Minimum | Données minimales | Non | Non |
| BasicWL | Données de base | Non | Non |
| Basic | Données de base avec lignes | Oui | Non |
| **EN16931** | **Profil européen complet** | **Oui** | **Oui** |
| Extended | Données étendues (Factur-X 1.08) | Oui + sous-lignes | Cas spécifiques |

**Le profil EN16931 est le minimum exigé** par la réforme française 2026. Les profils Minimum et BasicWL ne sont pas suffisants car ils ne contiennent pas les lignes de détail.

## Génération CII

Le format CII produit un XML pur conforme au standard UN/CEFACT D16B.

```python
from facturx_fr.generators import CIIGenerator

generator = CIIGenerator(profile="EN16931")

# Générer uniquement le XML
xml_bytes = generator.generate_xml(invoice)

# Ou utiliser generate() qui retourne un GenerationResult
result = generator.generate(invoice)
result.save("facture.xml")
```

### Profils disponibles

```python
# Profils CII (même liste que Factur-X)
CIIGenerator(profile="MINIMUM")
CIIGenerator(profile="BASICWL")
CIIGenerator(profile="BASIC")
CIIGenerator(profile="EN16931")   # recommandé
CIIGenerator(profile="EXTENDED")
```

## Génération UBL

Le format UBL produit un XML conforme au standard OASIS UBL 2.1. Les avoirs (`CreditNote`) sont gérés automatiquement selon le `type_code`.

```python
from facturx_fr.generators import UBLGenerator
from facturx_fr.models.enums import InvoiceTypeCode

generator = UBLGenerator(profile="EN16931")
xml_bytes = generator.generate_xml(invoice)

# Pour un avoir, le générateur produit un CreditNote au lieu d'un Invoice
avoir = Invoice(
    type_code=InvoiceTypeCode.CREDIT_NOTE,
    preceding_invoice_reference="FA-2026-001",
    # ... autres champs
)
xml_avoir = generator.generate_xml(avoir)
```

### Profils UBL

```python
UBLGenerator(profile="EN16931")  # profil européen
UBLGenerator(profile="PEPPOL")   # PEPPOL BIS Invoice 3.0
```

## Génération Factur-X (PDF/A-3 + XML)

Factur-X combine un PDF lisible par l'humain et un XML CII structuré. Vous devez fournir un PDF source.

```python
from facturx_fr.generators import FacturXGenerator

generator = FacturXGenerator(profile="EN16931")

# Lire le PDF source
with open("facture.pdf", "rb") as f:
    pdf_source = f.read()

result = generator.generate(invoice, pdf_bytes=pdf_source)

# Accéder aux données
result.xml_bytes   # le XML CII embarqué
result.pdf_bytes   # le PDF/A-3 final
result.profile     # "EN16931"

# Sauvegarder (sauvegarde le PDF si disponible, sinon le XML)
result.save("facture_facturx.pdf")
```

Le PDF source peut être généré avec n'importe quel outil : WeasyPrint, ReportLab, wkhtmltopdf, ou même un PDF existant. La bibliothèque `factur-x` (Akretion) se charge de la conversion PDF/A-3 et de l'embarquement du XML.

## Cas particuliers

### Autoliquidation (reverse charge)

Pour les factures avec autoliquidation (sous-traitance BTP, intracommunautaire), utilisez la catégorie TVA `AE` :

```python
from facturx_fr.models import InvoiceLine
from facturx_fr.models.enums import VATCategory

line = InvoiceLine(
    description="Travaux de sous-traitance",
    quantity=Decimal("1"),
    unit_price=Decimal("10000.00"),
    vat_rate=Decimal("0"),
    vat_category=VATCategory.REVERSE_CHARGE,
    vat_exemption_reason="Autoliquidation — Article 283-2 nonies du CGI",
    vat_exemption_reason_code="vatex-eu-ae",
)
```

### Multi-taux TVA

Une facture peut contenir des lignes à des taux différents. Les récapitulatifs TVA (`tax_summaries`) sont calculés automatiquement :

```python
invoice = Invoice(
    # ...
    lines=[
        InvoiceLine(
            description="Produit alimentaire",
            quantity=Decimal("100"),
            unit_price=Decimal("2.00"),
            vat_rate=Decimal("5.5"),
        ),
        InvoiceLine(
            description="Boisson alcoolisée",
            quantity=Decimal("50"),
            unit_price=Decimal("3.00"),
            vat_rate=Decimal("20.0"),
        ),
    ],
    operation_category=OperationCategory.DELIVERY,
)

# tax_summaries regroupe automatiquement par taux
for summary in invoice.tax_summaries:
    print(f"TVA {summary.vat_rate}% : base {summary.taxable_amount}, "
          f"TVA {summary.tax_amount}")
```

### Factures d'acompte et déduction

```python
from facturx_fr.models.enums import InvoiceTypeCode

# Facture d'acompte
acompte = Invoice(
    number="FA-2026-040",
    type_code=InvoiceTypeCode.PREPAYMENT_INVOICE,
    # ...
)

# Facture de solde avec déduction de l'acompte
solde = Invoice(
    number="FA-2026-042",
    type_code=InvoiceTypeCode.INVOICE,
    prepaid_amount=Decimal("1000.00"),  # acompte déjà versé
    # ...
)

print(f"Montant à payer : {solde.amount_due} EUR")  # TTC - acompte
```

### Périodes de facturation (situations de travaux BTP)

```python
from datetime import date

# Période au niveau facture
invoice = Invoice(
    billing_period_start=date(2026, 9, 1),
    billing_period_end=date(2026, 9, 30),
    # ...
)

# Période au niveau ligne
line = InvoiceLine(
    description="Travaux lot gros-oeuvre — situation n°3",
    quantity=Decimal("1"),
    unit_price=Decimal("25000.00"),
    billing_period_start=date(2026, 9, 1),
    billing_period_end=date(2026, 9, 30),
    # ...
)
```

## Validation

### Validation XSD

La validation XSD vérifie la structure du XML contre le schéma officiel :

```python
from facturx_fr.validators import validate_xsd

errors = validate_xsd(xml_bytes, flavor="factur-x", profile="EN16931")
if errors:
    for error in errors:
        print(f"Erreur XSD : {error}")
```

### Validation schématron (EN16931)

La validation schématron vérifie les règles de gestion européennes (nécessite `saxonche`) :

```python
from facturx_fr.validators import validate_schematron

errors = validate_schematron(xml_bytes, flavor="autodetect", profile="EN16931")
```

### Validation complète (XSD + schématron)

`validate_xml` combine les deux validations. Si le XSD échoue, les erreurs schématron ne sont pas ajoutées (pour éviter les faux positifs) :

```python
from facturx_fr.validators import validate_xml

errors = validate_xml(xml_bytes, flavor="factur-x", profile="EN16931")
if not errors:
    print("Facture conforme EN16931")
```

Le paramètre `profile` accepte `"autodetect"` pour détecter automatiquement le profil depuis le XML.

### Interprétation des erreurs

Les erreurs sont retournées sous forme de liste de chaînes. Les erreurs XSD indiquent des problèmes de structure (éléments manquants, ordre incorrect). Les erreurs schématron indiquent des violations de règles de gestion (ex : `[BR-CO-10]` — le montant total doit correspondre à la somme des lignes).

```python
errors = validate_xml(xml_bytes)
for error in errors:
    if error.startswith("[BR-"):
        print(f"Règle de gestion violée : {error}")
    else:
        print(f"Erreur de structure : {error}")
```

## Voir aussi

- [Guide de démarrage](getting_started.md) — Installation et premier exemple
- [Intégration PDP](pdp_integration.md) — Déposer les factures générées
- [Intégration Django](django_integration.md) — App Django prête à l'emploi
