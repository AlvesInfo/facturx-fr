# Serveur API Factur-X (micro-service)

`facturx_fr.contrib.django.api_urls` expose une **API HTTP stateless** (sans base de
données) qui permet à n'importe quelle application, quel que soit son langage ou sa
version de Python, de produire des factures Factur-X en déléguant la génération à un
serveur Django dédié.

Cas d'usage typique : une application existante (Django 3.x / Python 3.11 / Pydantic v1…)
ne peut pas installer `facturx-fr` dans son propre environnement. Elle génère son PDF
comme d'habitude, puis envoie ce PDF et les données de la facture au serveur, qui renvoie
le PDF/A-3 avec le XML CII embarqué.

```
Application métier ──(JSON facture + PDF)──▶ Serveur facturx-fr ──(PDF Factur-X)──▶ Application
```

## Installation du serveur

```bash
uv pip install "facturx-fr[django,schematron]" gunicorn
```

Dans un projet Django minimal (aucune app, aucune base de données nécessaire) :

```python
# settings.py
INSTALLED_APPS = []          # aucune app requise
DATABASES = {}               # aucune base requise
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
FACTURX_FR = {
    "API_KEYS": ["une-cle-longue-et-aleatoire"],
    "DEFAULT_PROFILE": "EN16931",
    "API_VALIDATE_DEFAULT": True,
    "API_MAX_UPLOAD_SIZE": 25 * 1024 * 1024,
}

# urls.py
from django.urls import include, path

urlpatterns = [
    path("facturx/", include("facturx_fr.contrib.django.api_urls")),
]
```

Un projet prêt à l'emploi est fourni dans le dépôt voisin `facturx_server`
(voir son README : `.env`, gunicorn, supervisor, nginx).

## Authentification

Chaque requête doit porter une clé d'API présente dans `FACTURX_FR["API_KEYS"]` :

```
Authorization: Bearer <clé>
```
ou
```
X-API-Key: <clé>
```

| Situation                                  | Réponse |
|--------------------------------------------|---------|
| Clé absente                                | 401     |
| Clé inconnue                               | 401     |
| Aucune clé configurée (anonyme interdit)   | 503     |

Pour un usage local uniquement, `FACTURX_FR["API_ALLOW_ANONYMOUS"] = True` désactive
l'authentification.

## Endpoints

### `GET /facturx/health/`

État du service :

```json
{
  "status": "ok",
  "service": "facturx-fr",
  "version": "0.1.0",
  "profiles": ["MINIMUM", "BASICWL", "BASIC", "EN16931", "EXTENDED"],
  "xml_formats": ["cii", "ubl"],
  "default_profile": "EN16931"
}
```

### `POST /facturx/generate/` — PDF Factur-X

Requête `multipart/form-data` :

| Champ        | Obligatoire | Description                                                        |
|--------------|-------------|--------------------------------------------------------------------|
| `invoice`    | oui         | JSON de la facture (champ texte **ou** fichier)                    |
| `pdf`        | oui*        | PDF source (fichier)                                               |
| `pdf_base64` | oui*        | Alternative à `pdf` : contenu du PDF encodé en base64              |
| `profile`    | non         | `MINIMUM`, `BASICWL`, `BASIC`, `EN16931` (défaut), `EXTENDED`      |
| `validate`   | non         | `true`/`false` : valider le XML (XSD + schématrons) avant embarquement |
| `output`     | non         | `pdf` (défaut) ou `json`                                           |

Le JSON de la facture suit exactement le schéma Pydantic `facturx_fr.models.Invoice`
(les champs calculés comme `total_excl_tax` sont ignorés s'ils sont présents) :

```json
{
  "number": "FA-2026-042",
  "issue_date": "2026-09-15",
  "due_date": "2026-10-15",
  "type_code": "380",
  "currency": "EUR",
  "operation_category": "delivery",
  "seller": {
    "name": "Ma Société SAS",
    "siren": "123456789",
    "siret": "12345678900012",
    "vat_number": "FR12345678901",
    "address": {"street": "12 rue du Commerce", "city": "Paris",
                "postal_code": "75011", "country_code": "FR"}
  },
  "buyer": {
    "name": "Client SA",
    "siren": "987654321",
    "address": {"street": "5 avenue de la République", "city": "Lyon",
                "postal_code": "69001", "country_code": "FR"}
  },
  "lines": [
    {"line_number": 1, "description": "Monture", "quantity": "2",
     "unit": "C62", "unit_price": "85.00", "vat_rate": "20.0", "vat_category": "S"}
  ],
  "payment_means": {"code": "58", "bank_account": {"iban": "FR76...", "bic": "BREDFRPP"}}
}
```

Réponse `200` : corps `application/pdf`, en-têtes `Content-Disposition`,
`X-FacturX-Profile`, `X-Invoice-Number`.

Avec `output=json` :

```json
{
  "number": "FA-2026-042",
  "profile": "EN16931",
  "validated": true,
  "total_excl_tax": "170.00",
  "total_vat": "34.00",
  "total_incl_tax": "204.00",
  "pdf_base64": "...",
  "xml_base64": "..."
}
```

Erreurs :

| Code | Signification                                                     |
|------|-------------------------------------------------------------------|
| 400  | Paramètre manquant / JSON invalide (`details` = erreurs Pydantic)  |
| 413  | Fichier trop volumineux (`API_MAX_UPLOAD_SIZE`)                    |
| 422  | Le XML généré ne passe pas la validation (`details` = liste)       |
| 500  | Échec de la génération                                             |

Exemple `curl` :

```bash
curl -s -o facture_facturx.pdf \
  -H "Authorization: Bearer $FACTURX_API_KEY" \
  -F "invoice=@facture.json;type=application/json" \
  -F "pdf=@facture.pdf;type=application/pdf" \
  -F "profile=EN16931" \
  https://facturx.example.com/facturx/generate/
```

Exemple Python (`requests`, aucune dépendance à facturx-fr côté client) :

```python
import json
import requests

response = requests.post(
    "https://facturx.example.com/facturx/generate/",
    headers={"Authorization": f"Bearer {API_KEY}"},
    data={"invoice": json.dumps(invoice_dict, default=str), "profile": "EN16931"},
    files={"pdf": ("facture.pdf", pdf_bytes, "application/pdf")},
    timeout=120,
)
response.raise_for_status()
facturx_pdf = response.content
```

### `POST /facturx/generate-xml/` — XML seul

- Corps `application/json` = la facture, **ou** `multipart/form-data` avec le champ `invoice`.
- `format=cii` (défaut) ou `format=ubl` (formulaire ou query string).
- `profile`, `validate` : comme pour `/generate/` (la validation ne s'applique qu'au CII).

Réponse `200` : corps `application/xml`.

### `POST /facturx/validate/` — validation d'un XML CII

- Fichier `xml` (multipart) **ou** corps brut `application/xml`.
- `profile` optionnel (`autodetect` par défaut).

```json
{"valid": false, "errors": ["[BR-CO-10] ..."]}
```

## Réglages `FACTURX_FR`

| Clé                     | Défaut              | Rôle                                                   |
|-------------------------|---------------------|--------------------------------------------------------|
| `API_KEYS`              | `()`                | Clés d'API acceptées                                   |
| `API_ALLOW_ANONYMOUS`   | `False`             | Autoriser l'accès sans clé                             |
| `API_VALIDATE_DEFAULT`  | `True`              | Valider le XML par défaut avant embarquement           |
| `API_MAX_UPLOAD_SIZE`   | `26214400` (25 Mo)  | Taille max d'un PDF / JSON / XML                       |
| `DEFAULT_PROFILE`       | `"EN16931"`         | Profil utilisé quand `profile` n'est pas transmis      |

## Sécurité

- Servez l'API en HTTPS (reverse proxy nginx) et limitez l'accès réseau aux applications
  clientes.
- Les vues sont `csrf_exempt` (API machine-à-machine) : la seule protection est la clé.
- Aucune donnée n'est conservée côté serveur : les PDF et JSON ne vivent que le temps
  de la requête.
