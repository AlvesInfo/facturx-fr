"""API HTTP stateless de génération et validation de factures électroniques.

FR: Vues Django sans base de données, destinées à être exposées par un
    serveur dédié (micro-service) : un client envoie une facture au format
    JSON (schéma ``facturx_fr.models.Invoice``) accompagnée du PDF source,
    et reçoit en retour le PDF Factur-X (PDF/A-3 + XML CII embarqué).
    Aucun modèle Django n'est utilisé : ces vues peuvent être montées via
    ``facturx_fr.contrib.django.api_urls`` sans ajouter l'app à INSTALLED_APPS.
EN: Stateless Django views (no database) meant to be served by a dedicated
    micro-service: the client posts a JSON invoice plus the source PDF and
    gets the Factur-X PDF back.

Authentification : clé d'API transmise dans l'en-tête ``Authorization: Bearer <clé>``
ou ``X-API-Key: <clé>``. Les clés acceptées sont listées dans
``settings.FACTURX_FR["API_KEYS"]``.
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
import re
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from lxml import etree
from pydantic import ValidationError

from facturx_fr import __version__
from facturx_fr.contrib.django.conf import get_setting
from facturx_fr.generators.cii import CIIGenerator
from facturx_fr.generators.facturx import FacturXGenerator
from facturx_fr.generators.ubl import UBLGenerator
from facturx_fr.models.invoice import Invoice
from facturx_fr.validators import validate_xml

logger = logging.getLogger(__name__)

PROFILES: tuple[str, ...] = ("MINIMUM", "BASICWL", "BASIC", "EN16931", "EXTENDED")
XML_FORMATS: tuple[str, ...] = ("cii", "ubl")
OUTPUTS: tuple[str, ...] = ("pdf", "json")

_TRUE_VALUES = {"1", "true", "yes", "oui", "on"}
_FALSE_VALUES = {"0", "false", "no", "non", "off"}
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_FORM_CONTENT_TYPES = ("multipart/form-data", "application/x-www-form-urlencoded")


class APIError(Exception):
    """Erreur applicative renvoyée au client sous forme JSON."""

    def __init__(self, message: str, status: int = 400, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details

    def to_response(self) -> JsonResponse:
        """Construit la réponse JSON correspondante."""
        payload: dict[str, Any] = {"error": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return JsonResponse(payload, status=self.status)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _extract_api_key(request: HttpRequest) -> str | None:
    """Extrait la clé d'API des en-têtes de la requête."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    key = request.headers.get("X-API-Key", "")
    return key.strip() or None


def check_api_key(request: HttpRequest) -> None:
    """Vérifie la clé d'API de la requête.

    FR: Lève APIError 401 si la clé est absente ou invalide, 503 si aucune
        clé n'est configurée et que l'accès anonyme n'est pas autorisé.
    EN: Raises APIError 401 on missing/invalid key, 503 if no key configured.
    """
    configured = get_setting("API_KEYS") or ()
    keys = [str(k) for k in configured if str(k)]

    if not keys:
        if get_setting("API_ALLOW_ANONYMOUS"):
            return
        raise APIError(
            "API non configurée : définissez FACTURX_FR['API_KEYS'] "
            "ou FACTURX_FR['API_ALLOW_ANONYMOUS'] = True.",
            status=503,
        )

    provided = _extract_api_key(request)
    if provided is None:
        raise APIError("Clé d'API manquante.", status=401)

    for key in keys:
        if hmac.compare_digest(provided.encode(), key.encode()):
            return

    raise APIError("Clé d'API invalide.", status=401)


def _parse_bool(value: str | None, default: bool) -> bool:
    """Interprète un booléen transmis en formulaire / query string."""
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise APIError(f"Valeur booléenne invalide : {value!r}.")


def _parse_profile(value: str | None) -> str:
    """Normalise et valide le profil Factur-X demandé."""
    profile = (value or str(get_setting("DEFAULT_PROFILE"))).strip().upper()
    if profile not in PROFILES:
        raise APIError(
            f"Profil inconnu : {profile!r}. Profils disponibles : {', '.join(PROFILES)}."
        )
    return profile


def _check_size(data: bytes, label: str) -> None:
    """Vérifie que la taille d'un contenu reste sous la limite configurée."""
    max_size = int(get_setting("API_MAX_UPLOAD_SIZE"))
    if max_size and len(data) > max_size:
        raise APIError(
            f"{label} trop volumineux : {len(data)} octets (maximum {max_size}).",
            status=413,
        )


def _pydantic_errors(error: ValidationError) -> list[dict[str, Any]]:
    """Convertit les erreurs Pydantic en structure JSON-safe."""
    return json.loads(error.json(include_url=False))


def _read_invoice_payload(request: HttpRequest) -> bytes:
    """Récupère le JSON de la facture (champ ``invoice``, fichier ou corps brut)."""
    uploaded = request.FILES.get("invoice")
    if uploaded is not None:
        return uploaded.read()

    field = request.POST.get("invoice")
    if field:
        return field.encode("utf-8")

    content_type = request.content_type or ""
    if content_type.startswith("application/json") and request.body:
        return request.body

    raise APIError(
        "Facture manquante : transmettez le JSON dans le champ 'invoice' "
        "(multipart/form-data) ou dans le corps de la requête (application/json)."
    )


def parse_invoice(raw: bytes) -> Invoice:
    """Valide le JSON reçu contre le modèle Pydantic ``Invoice``."""
    _check_size(raw, "JSON de la facture")
    try:
        return Invoice.model_validate_json(raw)
    except ValidationError as error:
        raise APIError("Facture invalide.", status=400, details=_pydantic_errors(error)) from error
    except ValueError as error:
        raise APIError(f"JSON illisible : {error}", status=400) from error


def _read_pdf(request: HttpRequest) -> bytes:
    """Récupère le PDF source (fichier ``pdf`` ou champ ``pdf_base64``)."""
    uploaded = request.FILES.get("pdf")
    if uploaded is not None:
        data = uploaded.read()
    else:
        encoded = request.POST.get("pdf_base64")
        if not encoded:
            raise APIError(
                "PDF source manquant : transmettez le fichier dans le champ 'pdf' "
                "ou son contenu encodé dans 'pdf_base64'."
            )
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as error:
            raise APIError("Champ 'pdf_base64' invalide.") from error

    if not data.startswith(b"%PDF"):
        raise APIError("Le fichier transmis n'est pas un PDF.")
    _check_size(data, "PDF source")
    return data


def _safe_filename(number: str, extension: str) -> str:
    """Construit un nom de fichier sûr à partir du numéro de facture."""
    stem = _FILENAME_SAFE.sub("_", number).strip("._-") or "facture"
    return f"{stem}.{extension}"


def _validate_or_raise(xml_bytes: bytes, profile: str) -> None:
    """Valide le XML (XSD + schématrons) et lève APIError 422 en cas d'erreurs."""
    errors = validate_xml(xml_bytes, flavor="factur-x", profile=profile.lower())
    if errors:
        raise APIError("Le XML généré ne passe pas la validation.", status=422, details=errors)


# --------------------------------------------------------------------------- #
# Vues
# --------------------------------------------------------------------------- #


@method_decorator(csrf_exempt, name="dispatch")
class APIView(View):
    """Vue de base : authentification par clé d'API et gestion des erreurs."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Authentifie la requête puis délègue, en convertissant les APIError."""
        try:
            check_api_key(request)
            return super().dispatch(request, *args, **kwargs)
        except APIError as error:
            return error.to_response()
        except Exception:
            logger.exception("Erreur interne dans %s", self.__class__.__name__)
            return JsonResponse({"error": "Erreur interne du serveur."}, status=500)


class HealthView(APIView):
    """État du service (GET)."""

    def get(self, request: HttpRequest) -> JsonResponse:
        """Renvoie la version et les options supportées."""
        return JsonResponse(
            {
                "status": "ok",
                "service": "facturx-fr",
                "version": __version__,
                "profiles": list(PROFILES),
                "xml_formats": list(XML_FORMATS),
                "default_profile": get_setting("DEFAULT_PROFILE"),
            }
        )


class GenerateFacturXView(APIView):
    """Génère un PDF Factur-X à partir d'une facture JSON et d'un PDF source (POST).

    Paramètres (multipart/form-data) :
        invoice     : JSON de la facture (champ texte ou fichier)
        pdf         : PDF source (fichier) — ou ``pdf_base64``
        profile     : MINIMUM | BASICWL | BASIC | EN16931 | EXTENDED (défaut : réglage)
        validate    : valider le XML avant embarquement (défaut : réglage)
        output      : ``pdf`` (défaut, réponse application/pdf) ou ``json``
                      (réponse JSON avec ``pdf_base64`` et ``xml_base64``)
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        """Produit le Factur-X."""
        invoice = parse_invoice(_read_invoice_payload(request))
        pdf_bytes = _read_pdf(request)
        profile = _parse_profile(request.POST.get("profile"))
        validate = _parse_bool(
            request.POST.get("validate"), bool(get_setting("API_VALIDATE_DEFAULT"))
        )
        output = (request.POST.get("output") or "pdf").strip().lower()
        if output not in OUTPUTS:
            raise APIError(f"Sortie inconnue : {output!r}. Valeurs : {', '.join(OUTPUTS)}.")

        generator = FacturXGenerator(profile=profile)

        if validate:
            _validate_or_raise(generator.generate_xml(invoice), profile)

        try:
            result = generator.generate(invoice, pdf_bytes=pdf_bytes)
        except Exception as error:
            logger.exception("Échec de génération Factur-X pour %s", invoice.number)
            raise APIError(f"Échec de la génération Factur-X : {error}", status=500) from error

        logger.info(
            "Factur-X généré : facture %s, profil %s, %d octets",
            invoice.number,
            profile,
            len(result.pdf_bytes or b""),
        )

        if output == "json":
            return JsonResponse(
                {
                    "number": invoice.number,
                    "profile": profile,
                    "validated": validate,
                    "total_excl_tax": str(invoice.total_excl_tax),
                    "total_vat": str(invoice.total_vat),
                    "total_incl_tax": str(invoice.total_incl_tax),
                    "pdf_base64": base64.b64encode(result.pdf_bytes or b"").decode(),
                    "xml_base64": base64.b64encode(result.xml_bytes).decode(),
                }
            )

        response = HttpResponse(result.pdf_bytes, content_type="application/pdf")
        filename = _safe_filename(invoice.number, "pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-FacturX-Profile"] = profile
        response["X-Invoice-Number"] = invoice.number
        return response


class GenerateXMLView(APIView):
    """Génère uniquement le XML (CII ou UBL) d'une facture JSON (POST).

    Paramètres (corps application/json = facture, ou multipart avec ``invoice``) :
        format   : ``cii`` (défaut) ou ``ubl`` (query string ou formulaire)
        profile  : profil Factur-X pour le CII (défaut : réglage)
        validate : valider le XML CII (défaut : réglage ; ignoré pour UBL)
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        """Produit le XML."""
        params = request.POST if request.POST else request.GET
        xml_format = (params.get("format") or request.GET.get("format") or "cii").lower()
        if xml_format not in XML_FORMATS:
            raise APIError(f"Format inconnu : {xml_format!r}. Formats : {', '.join(XML_FORMATS)}.")

        invoice = parse_invoice(_read_invoice_payload(request))
        profile = _parse_profile(params.get("profile") or request.GET.get("profile"))

        if xml_format == "ubl":
            xml_bytes = UBLGenerator(profile=profile).generate_xml(invoice)
        else:
            xml_bytes = CIIGenerator(profile=profile).generate_xml(invoice)
            validate = _parse_bool(
                params.get("validate") or request.GET.get("validate"),
                bool(get_setting("API_VALIDATE_DEFAULT")),
            )
            if validate:
                _validate_or_raise(xml_bytes, profile)

        response = HttpResponse(xml_bytes, content_type="application/xml")
        filename = _safe_filename(invoice.number, "xml")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-FacturX-Profile"] = profile
        response["X-Invoice-Number"] = invoice.number
        return response


class ValidateXMLView(APIView):
    """Valide un XML CII (XSD + schématrons EN16931) (POST).

    Paramètres : fichier ``xml`` (multipart) ou corps brut application/xml.
    Réponse : ``{"valid": bool, "errors": [...]}``.
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        """Valide le XML transmis."""
        xml_bytes: bytes | None = None
        if request.content_type in _FORM_CONTENT_TYPES:
            uploaded = request.FILES.get("xml")
            if uploaded is not None:
                xml_bytes = uploaded.read()
            elif request.POST.get("xml"):
                xml_bytes = request.POST["xml"].encode("utf-8")
        else:
            xml_bytes = request.body or None

        if not xml_bytes:
            raise APIError(
                "XML manquant : transmettez le fichier dans le champ 'xml' "
                "ou dans le corps de la requête (application/xml)."
            )

        _check_size(xml_bytes, "XML")
        profile = request.POST.get("profile") or request.GET.get("profile") or "autodetect"
        try:
            errors = validate_xml(xml_bytes, flavor="factur-x", profile=profile.lower())
        except (ValueError, etree.XMLSyntaxError) as error:
            errors = [str(error)]
        return JsonResponse({"valid": not errors, "errors": errors})
