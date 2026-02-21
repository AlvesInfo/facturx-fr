# Intégration PDP

## Le modèle à 5 coins

La réforme française utilise un modèle à **5 coins** : l'émetteur et le récepteur passent chacun par une **Plateforme de Dématérialisation Partenaire (PDP)** agréée par l'administration. Le **Portail Public de Facturation (PPF)** joue le rôle d'annuaire central et de concentrateur des données fiscales.

```
Vendeur → PA émettrice → PA réceptrice → Acheteur
                  ↘          ↙
                    PPF (DGFiP)
```

Les PDP sont des prestataires privés agréés (Pennylane, Sage, Cegid, etc.). Chaque entreprise choisit sa PDP. La bibliothèque `facturx-fr` fournit une interface abstraite pour communiquer avec n'importe quelle PDP.

## L'interface abstraite `BasePDP`

La classe `BasePDP` définit l'interface commune conforme à la norme **AFNOR XP Z12-013**. Toutes les méthodes sont **async**.

```python
from facturx_fr.pdp.base import BasePDP
```

### Méthodes disponibles

| Méthode | Description |
|---|---|
| `submit(invoice, xml_bytes, pdf_bytes)` | Soumettre une facture |
| `get_status(invoice_id)` | Récupérer le statut courant |
| `get_lifecycle(invoice_id)` | Historique complet du cycle de vie |
| `get_invoice(invoice_id)` | Récupérer le XML d'une facture |
| `search_invoices(filters)` | Rechercher des factures |
| `update_status(invoice_id, status, reason, ...)` | Mettre à jour le statut |
| `lookup_directory(siren)` | Consulter l'annuaire central |
| `submit_ereporting_transaction(submission)` | Soumettre des données e-reporting transaction |
| `submit_ereporting_payment(submission)` | Soumettre des données e-reporting paiement |
| `get_ereporting_status(submission_id)` | Statut d'une soumission e-reporting |

## Le connecteur `MemoryPDP` (tests)

Pour les tests et le développement, utilisez `MemoryPDP` qui stocke tout en mémoire :

```python
import asyncio
from facturx_fr.pdp.connectors.memory import MemoryPDP

async def main():
    pdp = MemoryPDP()

    # Soumettre une facture
    response = await pdp.submit(invoice, xml_bytes=xml_bytes)
    print(f"ID : {response.invoice_id}")      # "MEM-000001"
    print(f"Statut : {response.status}")       # InvoiceStatus.DEPOSEE

    # Consulter le statut
    status = await pdp.get_status(response.invoice_id)
    print(f"Statut courant : {status}")        # InvoiceStatus.DEPOSEE

    # Faire avancer le cycle de vie
    from facturx_fr.models.enums import InvoiceStatus

    await pdp.update_status(response.invoice_id, InvoiceStatus.EMISE)
    await pdp.update_status(response.invoice_id, InvoiceStatus.RECUE)
    await pdp.update_status(response.invoice_id, InvoiceStatus.MISE_A_DISPOSITION)
    await pdp.update_status(response.invoice_id, InvoiceStatus.PRISE_EN_CHARGE)
    await pdp.update_status(response.invoice_id, InvoiceStatus.APPROUVEE)

    # Consulter le cycle de vie complet
    lifecycle = await pdp.get_lifecycle(response.invoice_id)
    for event in lifecycle.events:
        print(f"  {event.timestamp}: {event.status}")

asyncio.run(main())
```

### Annuaire simulé

`MemoryPDP` fournit un annuaire en mémoire :

```python
from facturx_fr.pdp.models import DirectoryEntry

pdp = MemoryPDP()

# Ajouter une entrée à l'annuaire simulé
pdp.add_directory_entry(DirectoryEntry(
    siren="987654321",
    company_name="Client SA",
    platform_id="PDP-001",
    platform_name="MaPDP",
    electronic_address="987654321@pdp.fr",
))

# Consulter l'annuaire
entry = await pdp.lookup_directory("987654321")
print(f"{entry.company_name} → {entry.platform_name}")
```

## Créer un connecteur pour sa PDP

Pour connecter une PDP réelle, créez une classe qui hérite de `BasePDP` et implémentez toutes les méthodes abstraites.

### Exemple : connecteur minimal

```python
"""Connecteur pour la PDP MaPDP (exemple)."""

import httpx

from facturx_fr.models.enums import InvoiceStatus
from facturx_fr.models.invoice import Invoice
from facturx_fr.ereporting.models import EReportingSubmission
from facturx_fr.pdp.base import BasePDP
from facturx_fr.pdp.errors import (
    PDPAuthenticationError,
    PDPConnectionError,
    PDPNotFoundError,
    PDPValidationError,
)
from facturx_fr.pdp.models import (
    DirectoryEntry,
    EReportingSubmissionResponse,
    InvoiceSearchFilters,
    InvoiceSearchResponse,
    LifecycleResponse,
    StatusUpdateResponse,
    SubmissionResponse,
)


class MaPDP(BasePDP):
    """Connecteur pour la PDP MaPDP."""

    BASE_URLS = {
        "sandbox": "https://api.sandbox.mapdp.fr/v1",
        "production": "https://api.mapdp.fr/v1",
    }

    def __init__(
        self,
        api_key: str,
        environment: str = "sandbox",
    ) -> None:
        base_url = self.BASE_URLS[environment]
        super().__init__(api_key=api_key, environment=environment, base_url=base_url)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def submit(
        self,
        invoice: Invoice,
        xml_bytes: bytes | None = None,
        pdf_bytes: bytes | None = None,
    ) -> SubmissionResponse:
        """Soumet une facture à MaPDP."""
        try:
            response = await self._client.post(
                "/invoices",
                content=xml_bytes,
                headers={"Content-Type": "application/xml"},
            )
        except httpx.HTTPError as e:
            raise PDPConnectionError(str(e)) from e

        if response.status_code == 401:
            raise PDPAuthenticationError("Clé API invalide")
        if response.status_code == 422:
            data = response.json()
            raise PDPValidationError(
                "Facture non conforme",
                errors=data.get("errors", []),
            )

        data = response.json()
        return SubmissionResponse(**data)

    async def get_status(self, invoice_id: str) -> InvoiceStatus:
        """Récupère le statut courant."""
        response = await self._client.get(f"/invoices/{invoice_id}/status")
        if response.status_code == 404:
            raise PDPNotFoundError(f"Facture introuvable : {invoice_id}")
        data = response.json()
        return InvoiceStatus(data["status"])

    # ... implémenter les autres méthodes abstraites
```

### Méthodes à implémenter

Votre connecteur doit implémenter **toutes** les méthodes abstraites de `BasePDP` :

1. `submit()` — Dépôt de facture
2. `get_status()` — Statut courant
3. `get_lifecycle()` — Historique complet
4. `get_invoice()` — Récupération du XML
5. `search_invoices()` — Recherche avec filtres
6. `update_status()` — Mise à jour de statut
7. `lookup_directory()` — Annuaire central
8. `submit_ereporting_transaction()` — E-reporting transactions
9. `submit_ereporting_payment()` — E-reporting paiements
10. `get_ereporting_status()` — Statut e-reporting

## Dépôt de facture

Le flux complet pour déposer une facture :

```python
import asyncio
from facturx_fr.generators import CIIGenerator
from facturx_fr.validators import validate_xml
from facturx_fr.pdp.connectors.memory import MemoryPDP

async def deposer_facture(invoice):
    # 1. Générer le XML
    generator = CIIGenerator(profile="EN16931")
    xml_bytes = generator.generate_xml(invoice)

    # 2. Valider avant envoi
    errors = validate_xml(xml_bytes)
    if errors:
        raise ValueError(f"Facture non conforme : {errors}")

    # 3. Soumettre à la PDP
    pdp = MemoryPDP()
    response = await pdp.submit(invoice, xml_bytes=xml_bytes)

    print(f"Facture déposée : {response.invoice_id}")
    print(f"Statut : {response.status}")
    return response

asyncio.run(deposer_facture(invoice))
```

## Consultation de statut et cycle de vie

```python
async def suivre_facture(pdp, invoice_id):
    # Statut courant
    status = await pdp.get_status(invoice_id)
    print(f"Statut : {status}")

    # Historique complet
    lifecycle = await pdp.get_lifecycle(invoice_id)
    print(f"Statut courant : {lifecycle.current_status}")
    for event in lifecycle.events:
        print(f"  {event.timestamp} → {event.status}")
        if event.reason:
            print(f"    Motif : {event.reason}")
```

## Recherche de factures

```python
from facturx_fr.pdp.models import InvoiceSearchFilters
from facturx_fr.models.enums import InvoiceStatus

filters = InvoiceSearchFilters(
    status=InvoiceStatus.APPROUVEE,
    seller_siren="123456789",
    direction="sent",
    page=1,
    page_size=50,
)

results = await pdp.search_invoices(filters)
print(f"{results.total_count} factures trouvées")
for r in results.results:
    print(f"  {r.number} — {r.total_incl_tax} {r.currency} — {r.status}")
```

## E-reporting via PDP

L'e-reporting concerne les transactions hors e-invoicing (B2C, international). Voir aussi les détails dans la section cycle de vie.

```python
from facturx_fr.ereporting.reporter import EReporter
from facturx_fr.models.enums import (
    VATRegime,
    EReportingTransactionType,
)

# Créer le reporter
reporter = EReporter(
    seller_siren="123456789",
    vat_regime=VATRegime.REAL_NORMAL_MONTHLY,
)

# Préparer une transaction depuis une facture B2C
transaction = reporter.transaction_from_invoice(
    invoice,
    transaction_type=EReportingTransactionType.B2C_DOMESTIC,
)
submission = reporter.prepare_transaction(transaction)

# Soumettre via la PDP
response = await pdp.submit_ereporting_transaction(submission)
print(f"Soumission : {response.submission_id} — {response.status}")
```

## Gestion des erreurs

Les erreurs PDP sont typées dans `facturx_fr.pdp.errors` :

```python
from facturx_fr.pdp.errors import (
    PDPError,                # classe de base
    PDPAuthenticationError,  # clé API invalide, token expiré
    PDPValidationError,      # facture non conforme
    PDPNotFoundError,        # facture/ressource introuvable
    PDPConnectionError,      # erreur réseau (timeout, DNS, TLS)
)

try:
    response = await pdp.submit(invoice)
except PDPValidationError as e:
    print(f"Facture rejetée : {e}")
    for error in e.errors:
        print(f"  - {error}")
except PDPAuthenticationError:
    print("Vérifiez votre clé API")
except PDPConnectionError:
    print("Erreur de connexion — réessayez plus tard")
except PDPError as e:
    print(f"Erreur PDP : {e}")
```

## Cycle de vie : les 14 statuts

Le cycle de vie d'une facture comprend **5 statuts obligatoires** (transmis à la DGFiP) et **10 statuts recommandés** (échangés entre les parties).

### Statuts obligatoires

| Code | Statut | Producteur |
|---|---|---|
| 200 | Déposée | PA émettrice |
| 209 | Rejetée (émission) | PA émettrice |
| 210 | Refusée | Acheteur |
| 212 | Rejetée (réception) | PA réceptrice |
| 213 | Encaissée | Vendeur |

### Statuts recommandés

| Code | Statut | Phase |
|---|---|---|
| 201 | Émise | Transmission |
| 202 | Reçue | Réception |
| 203 | Mise à disposition | Réception |
| 204 | Prise en charge | Traitement |
| 205 | Approuvée | Traitement |
| 206 | Partiellement approuvée | Traitement |
| 207 | En litige | Traitement |
| 208 | Suspendue | Traitement |
| 211 | Paiement transmis | Paiement |
| 214 | Complétée | Transmission |

### Transitions autorisées

```
Déposée → Émise → Reçue → Mise à disposition → Prise en charge
                                                       ↓
                                          Approuvée / Part. approuvée / Refusée
                                          En litige / Suspendue
                                                       ↓
                                          Paiement transmis → Encaissée
```

Les statuts terminaux (aucune transition sortante) sont : **Rejetée émission**, **Rejetée réception**, **Refusée**, **Encaissée**.

### Utiliser le LifecycleManager

Le `LifecycleManager` valide les transitions et conserve l'historique :

```python
from facturx_fr.lifecycle.manager import LifecycleManager, TRANSITIONS
from facturx_fr.models.enums import InvoiceStatus

manager = LifecycleManager(
    invoice_reference="FA-2026-001",
    initial_status=InvoiceStatus.DEPOSEE,
)

# Vérifier si une transition est possible
print(manager.can_transition(InvoiceStatus.EMISE))      # True
print(manager.can_transition(InvoiceStatus.ENCAISSEE))   # False

# Effectuer une transition
event = manager.transition(target=InvoiceStatus.EMISE)
print(f"{event.timestamp} → {event.status}")

# Refuser une facture (motif obligatoire)
manager.transition(target=InvoiceStatus.RECUE)
manager.transition(target=InvoiceStatus.MISE_A_DISPOSITION)
manager.transition(target=InvoiceStatus.PRISE_EN_CHARGE)
manager.transition(
    target=InvoiceStatus.REFUSEE,
    reason="Montant incorrect",
)

# Consulter l'historique
for event in manager.history:
    print(f"  {event.status} — {event.reason or ''}")

# Vérifier si le statut est terminal
print(manager.is_terminal())  # True (REFUSEE est terminal)
```

**Attention** : le statut `REFUSEE` exige un `reason` (motif de refus). Sans motif, une `ValueError` est levée.

## Voir aussi

- [Guide de démarrage](getting_started.md) — Installation et premier exemple
- [Formats de factures](formats.md) — Factur-X, UBL, CII
- [Intégration Django](django_integration.md) — App Django, Celery
