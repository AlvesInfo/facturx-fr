"""Énumérations pour la facturation électronique française.

FR: Codes et catégories conformes aux normes EN16931, AFNOR XP Z12-012
    et réforme française 2026.
EN: Codes and categories conforming to EN16931, AFNOR XP Z12-012
    and the French 2026 reform.
"""

from enum import StrEnum


class InvoiceTypeCode(StrEnum):
    """Code du type de facture (UNTDID 1001).

    FR: Types de documents commerciaux autorisés.
    EN: Allowed commercial document types.
    """

    INVOICE = "380"
    """Facture commerciale / Commercial invoice"""

    CREDIT_NOTE = "381"
    """Avoir / Credit note"""

    DEBIT_NOTE = "383"
    """Note de débit / Debit note"""

    CORRECTED_INVOICE = "384"
    """Facture rectificative / Corrected invoice"""

    PREPAYMENT_INVOICE = "386"
    """Facture d'acompte / Prepayment invoice"""

    SELF_BILLED_INVOICE = "389"
    """Autofacturation / Self-billed invoice"""


class OperationCategory(StrEnum):
    """Catégorie de l'opération (mention obligatoire sept. 2026).

    FR: Indique si la facture concerne une livraison de biens,
        une prestation de services, ou les deux.
    EN: Indicates whether the invoice covers goods delivery,
        services, or both.
    """

    DELIVERY = "delivery"
    """Livraison de biens / Goods delivery"""

    SERVICE = "service"
    """Prestation de services / Service provision"""

    MIXED = "mixed"
    """Livraison de biens et prestation de services / Both goods and services"""


class VATCategory(StrEnum):
    """Catégorie de TVA (UNTDID 5305).

    FR: Codes de catégorie TVA conformes au standard européen.
    EN: VAT category codes conforming to the European standard.
    """

    STANDARD = "S"
    """Taux normal / Standard rate"""

    ZERO_RATED = "Z"
    """Taux zéro / Zero rated"""

    EXEMPT = "E"
    """Exonéré / Exempt"""

    REVERSE_CHARGE = "AE"
    """Autoliquidation / Reverse charge"""

    INTRA_COMMUNITY = "K"
    """Intracommunautaire / Intra-community"""

    EXPORT = "G"
    """Export hors UE / Export outside EU"""

    NOT_SUBJECT = "O"
    """Non soumis / Not subject to VAT"""

    IGIC = "L"
    """IGIC (Canaries) / Canary Islands General Indirect Tax"""

    IPSI = "M"
    """IPSI (Ceuta et Melilla) / Tax for production, services and importation"""


class UnitOfMeasure(StrEnum):
    """Code unité de mesure (UN/ECE Rec. 20).

    FR: Codes d'unités les plus courants en facturation française.
    EN: Most common unit codes in French invoicing.
    """

    UNIT = "C62"
    """Unité / One (unit)"""

    HOUR = "HUR"
    """Heure / Hour"""

    DAY = "DAY"
    """Jour / Day"""

    MONTH = "MON"
    """Mois / Month"""

    YEAR = "ANN"
    """Année / Year"""

    KILOGRAM = "KGM"
    """Kilogramme / Kilogram"""

    METRE = "MTR"
    """Mètre / Metre"""

    SQUARE_METRE = "MTK"
    """Mètre carré / Square metre"""

    LITRE = "LTR"
    """Litre / Litre"""

    PIECE = "XPP"
    """Pièce / Piece"""

    SET = "SET"
    """Ensemble / Set"""

    PAIR = "PR"
    """Paire / Pair"""


class PaymentMeansCode(StrEnum):
    """Code moyen de paiement (UNTDID 4461).

    FR: Modes de règlement conformes au standard EN16931.
    EN: Payment methods conforming to the EN16931 standard.
    """

    CASH = "10"
    """Espèces / Cash"""

    CHEQUE = "20"
    """Chèque / Cheque"""

    CREDIT_TRANSFER = "30"
    """Virement bancaire / Credit transfer"""

    PAYMENT_TO_BANK_ACCOUNT = "42"
    """Paiement sur compte bancaire / Payment to bank account"""

    BANK_CARD = "48"
    """Carte bancaire / Bank card"""

    DIRECT_DEBIT = "49"
    """Prélèvement / Direct debit"""

    SEPA_CREDIT_TRANSFER = "58"
    """Virement SEPA / SEPA credit transfer"""

    SEPA_DIRECT_DEBIT = "59"
    """Prélèvement SEPA / SEPA direct debit"""


class InvoiceStatus(StrEnum):
    """Statut du cycle de vie d'une facture (norme AFNOR XP Z12-012).

    FR: 5 statuts obligatoires (transmis au CDD/PPF) et 10 statuts
        recommandés (entre les parties). Codes conformes à XP Z12-012.
    EN: 5 mandatory statuses (sent to CDD/PPF) and 10 recommended
        statuses (between parties). Codes from XP Z12-012.
    """

    # --- Statuts OBLIGATOIRES (transmis au CDD/PPF pour la DGFiP) ---

    DEPOSEE = "200"
    """Facture déposée et validée par la PA émettrice / Invoice deposited"""

    REJETEE_EMISSION = "209"
    """Facture rejetée à l'émission (non-conformité technique) / Rejected at emission"""

    REFUSEE = "210"
    """Facture refusée par le destinataire (motif obligatoire) / Refused by recipient"""

    REJETEE_RECEPTION = "212"
    """Facture rejetée à la réception (non-conformité technique) / Rejected at reception"""

    ENCAISSEE = "213"
    """Facture encaissée (paiement reçu) / Invoice cashed"""

    # --- Statuts RECOMMANDÉS (entre les parties, non transmis à la DGFiP) ---

    EMISE = "201"
    """Facture émise par la PA émettrice / Issued by issuing platform"""

    RECUE = "202"
    """Facture reçue par la PA réceptrice / Received by receiving platform"""

    MISE_A_DISPOSITION = "203"
    """Facture mise à disposition de l'acheteur / Made available to buyer"""

    PRISE_EN_CHARGE = "204"
    """Facture prise en charge par l'acheteur / Acknowledged by buyer"""

    APPROUVEE = "205"
    """Facture approuvée intégralement / Fully approved"""

    PARTIELLEMENT_APPROUVEE = "206"
    """Facture approuvée partiellement / Partially approved"""

    EN_LITIGE = "207"
    """Facture en litige (contestation en cours) / Under dispute"""

    SUSPENDUE = "208"
    """Facture suspendue (infos manquantes) / Suspended"""

    PAIEMENT_TRANSMIS = "211"
    """Paiement transmis par l'acheteur / Payment initiated by buyer"""

    COMPLETEE = "214"
    """Facture complétée après suspension / Completed after suspension"""


class StatusCategory(StrEnum):
    """Catégorie du statut de cycle de vie (XP Z12-012).

    FR: Indique si le statut est obligatoire (transmis au CDD/PPF)
        ou recommandé (entre les parties uniquement).
    EN: Indicates whether the status is mandatory (sent to CDD/PPF)
        or recommended (between parties only).
    """

    MANDATORY = "mandatory"
    """Statut obligatoire, transmis au CDD/PPF pour la DGFiP"""

    RECOMMENDED = "recommended"
    """Statut recommandé, échangé entre les parties uniquement"""


class CDARRoleCode(StrEnum):
    """Rôles des parties dans un message CDAR (XP Z12-012).

    FR: Codes de rôle utilisés dans les messages de cycle de vie
        (Cross-industry Document and Application Response).
    EN: Role codes used in lifecycle messages (CDAR).
    """

    BUYER = "BY"
    """Acheteur / Buyer"""

    SELLER = "SE"
    """Vendeur / Seller"""

    FACTOR = "DL"
    """Affactureur / Factor"""

    PLATFORM = "WK"
    """Plateforme agréée (PA) / Certified platform"""

    PPF = "DFH"
    """Portail Public de Facturation (concentrateur) / Public invoicing portal"""


class VATRegime(StrEnum):
    """Régime de TVA (détermine les fréquences de transmission e-reporting).

    FR: Le régime de TVA du vendeur conditionne la fréquence de transmission
        des données de transaction et de paiement au concentrateur.
    EN: The seller's VAT regime determines the transmission frequency
        for transaction and payment data to the concentrator.
    """

    REAL_NORMAL_MONTHLY = "real_normal_monthly"
    """Réel normal — déclaration mensuelle / Real normal — monthly filing"""

    REAL_NORMAL_QUARTERLY = "real_normal_quarterly"
    """Réel normal — déclaration trimestrielle / Real normal — quarterly filing"""

    SIMPLIFIED_REAL = "simplified_real"
    """Réel simplifié / Simplified real"""

    FRANCHISE = "franchise"
    """Franchise en base de TVA / VAT franchise (exempt)"""


class EReportingTransactionType(StrEnum):
    """Type de transaction e-reporting.

    FR: Catégorise les transactions hors e-invoicing soumises au e-reporting.
    EN: Categorizes non e-invoicing transactions subject to e-reporting.
    """

    B2C_DOMESTIC = "b2c_domestic"
    """Vente B2C domestique / Domestic B2C sale"""

    B2B_INTRA_EU = "b2b_intra_eu"
    """Intracommunautaire (LIC/AIC) / Intra-EU (IC supply/acquisition)"""

    B2B_EXTRA_EU = "b2b_extra_eu"
    """Hors UE (export/import) / Extra-EU (export/import)"""


class EReportingTransmissionMode(StrEnum):
    """Mode de transmission e-reporting.

    FR: Mode de soumission des données au concentrateur via la PA.
    EN: Data submission mode to the concentrator via the PA.
    """

    INDIVIDUAL = "individual"
    """Transaction par transaction / Transaction by transaction"""

    AGGREGATED = "aggregated"
    """Totaux quotidiens par SIREN (B2C) / Daily totals per SIREN (B2C)"""


class Currency(StrEnum):
    """Codes devise ISO 4217 courants.

    FR: Devises les plus utilisées dans la facturation française.
    EN: Most common currencies in French invoicing.
    """

    EUR = "EUR"
    """Euro"""

    USD = "USD"
    """Dollar américain / US Dollar"""

    GBP = "GBP"
    """Livre sterling / British Pound"""

    CHF = "CHF"
    """Franc suisse / Swiss Franc"""
