"""
Constructeur de profils unifiés AssurFill.

Fusionne les données de 3 documents parsés :
  - permis recto  (permis_fr_nouveau_recto | permis_dz_nouveau_recto)
  - permis verso  (permis_fr_nouveau_verso | permis_dz_nouveau_verso)
  - carte grise   (cg_normale | cg_provisoire)

En sortie : un seul dict « profil » avec résolution intelligente des conflits.

Règles de fusion :
  - Non-null > null
  - Champs texte similaires (ratio ≥ 0.80) → préférer la valeur la plus longue
    (l'OCR peut amputer une lettre en fin de mot)
  - Champs texte trop différents (ratio < 0.80) → conflit majeur signalé dans _conflits
  - Dates : la source la plus fiable est prioritaire (MRZ > OCR libre)
  - Permis DZ : le verso (MRZ ICAO) est plus fiable que le recto pour noms et dates
  - Permis FR : recto seul porte les données d'identité, verso apporte obtention_B
  - Croisement permis ↔ CG : si nom du permis ≈ propriétaire CG, préférer le plus long ;
    si trop différents, les deux sont conservés séparément.
"""
from .merger import fusionner_texte, fusionner_date

_TYPES_FR_RECTO = {"permis_fr_nouveau_recto"}
_TYPES_FR_VERSO = {"permis_fr_nouveau_verso"}
_TYPES_DZ_RECTO = {"permis_dz_nouveau_recto"}
_TYPES_DZ_VERSO = {"permis_dz_nouveau_verso"}
_TYPES_CG_NORMALE = {"cg_normale"}
_TYPES_CG_PROVISOIRE = {"cg_provisoire"}


# ---------------------------------------------------------------------------
# Profils permis
# ---------------------------------------------------------------------------

def _profil_permis_fr(recto: dict, verso: dict) -> tuple[dict, list[dict]]:
    """
    Permis FR nouveau : recto porte toute l'identité, verso apporte uniquement obtention_B.
    Aucun champ ne se chevauche → pas de conflit interne.
    """
    return {
        "nom": recto.get("nom"),
        "prenom": recto.get("prenom"),
        "date_naissance": recto.get("date_naissance"),
        "sexe": None,
        "numero_permis": recto.get("numero_permis"),
        "pays_permis": "FR",
        "date_expiration_permis": recto.get("date_expiration"),
        "obtention_B": verso.get("obtention_B"),
    }, []


def _profil_permis_dz(recto: dict, verso: dict) -> tuple[dict, list[dict]]:
    """
    Permis DZ nouveau : le verso (MRZ ICAO) est la source prioritaire pour tous les champs
    partagés (nom, prénom, dates, numéro de permis). Le recto sert de fallback.
    """
    conflits: list[dict] = []

    nom, c = fusionner_texte(
        verso.get("nom"), recto.get("nom"),
        "verso_mrz", "recto_ocr", "nom",
        priorite="source_a",
    )
    if c:
        conflits.append(c)

    prenom, c = fusionner_texte(
        verso.get("prenom"), recto.get("prenom"),
        "verso_mrz", "recto_ocr", "prenom",
        priorite="source_a",
    )
    if c:
        conflits.append(c)

    date_naissance, c = fusionner_date(
        verso.get("date_naissance"), recto.get("date_naissance"),
        "date_naissance", priorite="source_a",
    )
    if c:
        conflits.append(c)

    date_expiration, c = fusionner_date(
        verso.get("date_expiration"), recto.get("date_expiration"),
        "date_expiration_permis", priorite="source_a",
    )
    if c:
        conflits.append(c)

    numero_permis, c = fusionner_texte(
        verso.get("numero_permis"), recto.get("numero_permis"),
        "verso_mrz", "recto_ocr", "numero_permis",
        priorite="source_a",
    )
    if c:
        conflits.append(c)

    return {
        "nom": nom,
        "prenom": prenom,
        "date_naissance": date_naissance,
        "sexe": verso.get("sexe"),
        "numero_permis": numero_permis,
        "pays_permis": "DZ",
        "date_expiration_permis": date_expiration,
        "obtention_B": None,
    }, conflits


# ---------------------------------------------------------------------------
# Profil CG
# ---------------------------------------------------------------------------

def _profil_cg(cg: dict) -> dict:
    type_raw = cg.get("type", "")
    return {
        "numero_immatriculation": cg.get("numero_immatriculation"),
        "vin": cg.get("vin"),
        "marque": cg.get("marque"),
        "modele": cg.get("modele"),
        "puissance_fiscale": cg.get("puissance_fiscale"),
        "type_cg": "normale" if "normale" in type_raw else "provisoire",
        "proprietaire_nom": cg.get("proprietaire_nom"),
        "proprietaire_prenom": cg.get("proprietaire_prenom"),
        "conducteur": cg.get("conducteur"),
    }


# ---------------------------------------------------------------------------
# Croisement permis ↔ CG
# ---------------------------------------------------------------------------

def _croiser_identite(
    profil_permis: dict,
    profil_cg: dict,
    conflits: list[dict],
) -> tuple[str | None, str | None]:
    """
    Compare le nom/prénom du titulaire du permis avec le propriétaire CG.
    - Si similaires → préférer la valeur la plus longue (OCR peut amputer)
    - Si trop différents → conserver la valeur permis, signaler conflit majeur
    """
    nom_final, c = fusionner_texte(
        profil_permis.get("nom"), profil_cg.get("proprietaire_nom"),
        "permis", "cg_proprietaire", "nom",
        priorite="plus_long",
    )
    if c:
        c["source"] = "permis_vs_cg"
        conflits.append(c)

    prenom_final, c = fusionner_texte(
        profil_permis.get("prenom"), profil_cg.get("proprietaire_prenom"),
        "permis", "cg_proprietaire", "prenom",
        priorite="plus_long",
    )
    if c:
        c["source"] = "permis_vs_cg"
        conflits.append(c)

    return nom_final, prenom_final


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

def construire_profil(
    permis_recto: dict,
    permis_verso: dict,
    cg: dict,
) -> dict:
    """
    Construit un profil unifié depuis trois documents parsés.

    Args:
        permis_recto : dict retourné par le parser du recto du permis.
        permis_verso : dict retourné par le parser du verso du permis.
        cg           : dict retourné par le parser de la carte grise.

    Returns:
        Profil unifié (dict).  Le champ ``_conflits`` liste les divergences
        détectées entre sources, avec la décision prise.
    """
    conflits: list[dict] = []

    recto_type = permis_recto.get("type", "")
    cg_type = cg.get("type", "")

    # 1. Profil permis
    if recto_type in _TYPES_FR_RECTO:
        profil_permis, c_permis = _profil_permis_fr(permis_recto, permis_verso)
    else:
        profil_permis, c_permis = _profil_permis_dz(permis_recto, permis_verso)

    for c in c_permis:
        c.setdefault("source", "interne_permis")
    conflits.extend(c_permis)

    # 2. Profil CG
    profil_cg = _profil_cg(cg)

    # 3. Croisement nom/prénom permis ↔ CG propriétaire
    nom_final, prenom_final = _croiser_identite(profil_permis, profil_cg, conflits)

    # 4. Déduction du type de profil
    pays = "fr" if recto_type in _TYPES_FR_RECTO else "dz"
    type_cg_label = "normale" if "normale" in cg_type else "provisoire"
    profil_type = f"permis_{pays}_cg_{type_cg_label}"

    # 5. Détection de mauvaise paire recto/verso (DZ uniquement)
    # Si nom ET prénom sont tous les deux des conflits majeurs entre recto et verso,
    # les deux documents viennent probablement de personnes différentes.
    paire_suspecte = False
    if pays == "dz":
        champs_majeurs_internes = {
            c["champ"] for c in conflits
            if c.get("source") == "interne_permis" and c.get("type") == "majeur"
        }
        paire_suspecte = "nom" in champs_majeurs_internes and "prenom" in champs_majeurs_internes

    # 6. Assemblage final
    return {
        "profil_type": profil_type,

        # Identité du titulaire (fusionnée permis + CG)
        "nom": nom_final,
        "prenom": prenom_final,
        "date_naissance": profil_permis.get("date_naissance"),
        "sexe": profil_permis.get("sexe"),

        # Permis de conduire
        "numero_permis": profil_permis.get("numero_permis"),
        "pays_permis": profil_permis.get("pays_permis"),
        "date_expiration_permis": profil_permis.get("date_expiration_permis"),
        "obtention_B": profil_permis.get("obtention_B"),

        # Véhicule
        "numero_immatriculation": profil_cg.get("numero_immatriculation"),
        "vin": profil_cg.get("vin"),
        "marque": profil_cg.get("marque"),
        "modele": profil_cg.get("modele"),
        "puissance_fiscale": profil_cg.get("puissance_fiscale"),
        "type_cg": profil_cg.get("type_cg"),

        # Propriétaire du véhicule (données brutes CG, avant fusion)
        "proprietaire_nom": profil_cg.get("proprietaire_nom"),
        "proprietaire_prenom": profil_cg.get("proprietaire_prenom"),
        "conducteur": profil_cg.get("conducteur"),

        # Audit des conflits détectés
        "_conflits": conflits,
        "_paire_suspecte": paire_suspecte,
    }
