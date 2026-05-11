import re

# Mots-clés d'en-tête — leur présence indique qu'on est dans la zone titre, pas dans les données
_HEADER_RE = re.compile(
    r"PERMIS|CONDUIRE|FRANC[AEH]ISE?|FRAHSAISE|REPUBLIQUE", re.IGNORECASE
)
# Préfixes de champs numérotés (3. à 9., 4a, 4b, 5., D1FRA) — stoppent la collecte des noms
_FIELD_RE = re.compile(r"^[3-9]|^4[a-c]|^5[.\s]|^D1FRA", re.IGNORECASE)


def parse(texts: list[str], scores: list[float]) -> dict:
    """
    Parser pour permis de conduire français nouvelle génération recto (post-2013, format EU).
    Signature : 'REPUBLIQUE FRANCAISE' + labels 4a./4b./4c. + MRZ 'D1FRA...'
    """
    data = {
        "type": "permis_fr_nouveau_recto",
        "nom": None,
        "prenom": None,
        "date_naissance": None,
        "date_expiration": None,
        "numero_permis": None,
    }

    date_delivre_permis = None
    past_header = False  # True une fois qu'on a vu les tokens d'en-tête
    mrz_nom = None     # Nom complet extrait du MRZ (quand '<' présent)
    mrz_prefix = None  # Préfixe du nom MRZ (pour correction artefact en début)

    for i, (text, score) in enumerate(zip(texts, scores)):
        if score < 0.5:
            continue

        t = text.strip()

        # ── En-tête (REPUBLIQUE FRANCAISE, PERMIS DE CONDUIRE, variantes OCR)
        if _HEADER_RE.search(t):
            past_header = True
            continue

        # ── Ligne MRZ : D1FRA<NUMERO(9)>...<NOM<<
        if re.match(r"^D1FRA[A-Z0-9]", t) and len(t) > 10:
            if data["numero_permis"] is None:
                m = re.search(r"D1FRA([A-Z0-9]{9})", t)
                if m:
                    data["numero_permis"] = m.group(1)
            _pref = _extract_mrz_name_prefix(t)
            if _pref:
                mrz_prefix = _pref
            if "<" in t:
                _extrait = _extract_nom_mrz(t)
                if _extrait:
                    mrz_nom = _extrait
                    if data["nom"] is None:
                        data["nom"] = mrz_nom

        # ── Nom — champ 1.
        elif data["nom"] is None and re.match(r"^1[.\s]", t):
            # Ignorer les lignes-labels multi-champs : "1.Nom2.Prenom 3.Date..."
            if re.search(r"[2-6][a-z]?[.\s]", t[2:]):
                continue
            s = re.sub(r"^\d+[a-z]?[.\s]\d*\s*", "", t).strip()
            s = re.sub(r"^[^A-Za-zÀ-ÿ]{1,2}", "", s).strip()
            s = re.sub(r"[^A-Za-zÀ-ÿ\-']{1,2}$", "", s).strip()
            s = re.sub(r"^[a-zà-ÿ](?=[A-ZÀ-Ÿ])", "", s).strip()
            s = re.sub(r"(?<=[A-ZÀ-Ÿ])[a-zà-ÿ]$", "", s).strip()
            data["nom"] = s.upper() or None

        # ── Nom — fallback positionnel (après l'en-tête, avant les champs datés)
        elif data["nom"] is None and past_header and len(t) > 2 and t.upper() not in {"F", "EU"}:
            if not _FIELD_RE.match(t) and not _parse_date(t):
                clean = re.sub(r"^[^A-Za-zÀ-ÿ]{1,2}(?=[A-Za-zÀ-ÿ]{3})", "", t)
                alpha = len(re.findall(r"[A-Za-zÀ-ÿ]", clean))
                if alpha >= 3 and alpha / len(clean) >= 0.75:
                    s = re.sub(r"[^A-Za-zÀ-ÿ\-' ]", "", clean)
                    s = re.sub(r"^[a-zà-ÿ](?=[A-ZÀ-Ÿ])", "", s).strip()
                    s = re.sub(r"(?<=[A-ZÀ-Ÿ])[a-zà-ÿ]$", "", s).strip()
                    data["nom"] = s.upper() or None

        # ── Prénom — champ 2. (point bien lu ou mal lu comme lettre par OCR)
        elif data["prenom"] is None and re.match(r"^2[.\s]", t):
            s = re.sub(r"^\d+[a-z]?[.\s]\d*\s*", "", t).strip()
            s = re.sub(r"^[^A-Za-zÀ-ÿ]{1,2}", "", s).strip()
            s = re.sub(r"[^A-Za-zÀ-ÿ\-']{1,2}$", "", s).strip()
            s = re.sub(r"^[a-zà-ÿ](?=[A-ZÀ-Ÿ])", "", s).strip()
            s = re.sub(r"(?<=[A-ZÀ-Ÿ])[a-zà-ÿ]$", "", s).strip()
            data["prenom"] = s or None

        elif data["prenom"] is None and re.match(r"^2[A-Z](?=[A-Z]{2,})", t):
            # OCR a lu "2." comme "2A" (ex : "2ARACHIDA" → prénom "RACHIDA")
            s = re.sub(r"^2[A-Z]", "", t).strip()
            s = re.sub(r"[^A-Za-zÀ-ÿ\-']{1,2}$", "", s).strip()
            data["prenom"] = s or None

        # ── Prénom — fallback positionnel (après nom, avant les champs datés)
        elif (
            data["nom"] is not None
            and data["prenom"] is None
            and past_header
            and len(t) > 2
            and t.upper() not in {"F", "EU"}
            and not re.match(r"^\d", t)
        ):
            if not _FIELD_RE.match(t) and not _parse_date(t):
                clean = re.sub(r"^[^A-Za-zÀ-ÿ]{1,2}(?=[A-Za-zÀ-ÿ]{3})", "", t)
                alpha = len(re.findall(r"[A-Za-zÀ-ÿ]", clean))
                if alpha >= 3 and alpha / len(clean) >= 0.6:
                    s = re.sub(r"[^A-Za-zÀ-ÿ\-' ]", "", clean)
                    s = re.sub(r"^[a-zà-ÿ](?=[A-ZÀ-Ÿ])", "", s).strip()
                    s = re.sub(r"(?<=[A-ZÀ-Ÿ])[a-zà-ÿ]$", "", s).strip()
                    data["prenom"] = s or None

        # ── Numéro permis — champ 5. (fallback si MRZ absent/illisible)
        elif data["numero_permis"] is None and re.match(r"^5[.\s]", t):
            m = re.search(r"([A-Z0-9]{6,12})", t[2:])
            if m:
                data["numero_permis"] = m.group(1)

        # ── Date obtention — champ 4a.
        elif date_delivre_permis is None and re.match(r"^4a[.\s]?", t, re.IGNORECASE) and re.search(r"\d{2}[./]\d{2}[./]\d{4}", t):
            date_delivre_permis = _parse_date(t)

        # ── Date expiration — champ 4b.
        elif data["date_expiration"] is None and re.match(r"^4b[.\s]?", t, re.IGNORECASE):
            d = _parse_date(t)
            if d:
                data["date_expiration"] = d
            else:
                for j in range(i + 1, min(i + 3, len(texts))):
                    d = _parse_date(texts[j])
                    if d:
                        data["date_expiration"] = d
                        break

        # ── Date naissance — champ 3. (toute date antérieure à la date d'obtention)
        elif data["date_naissance"] is None:
            date = _parse_date(t)
            if date is not None and (date_delivre_permis is None or date < date_delivre_permis):
                data["date_naissance"] = date

    # ── Récupération date expiration si absente (date > date_obtention dans les textes restants)
    if data["date_expiration"] is None and date_delivre_permis is not None:
        for t in texts:
            d = _parse_date(t.strip())
            if d and d > date_delivre_permis:
                data["date_expiration"] = d
                break

    # ── Le nom MRZ complet est autoritaire
    if mrz_nom is not None:
        if data["nom"] is None:
            data["nom"] = mrz_nom
        elif _similar_to_mrz(data["nom"], mrz_nom):
            # Même nom avec artefacts OCR → MRZ fait foi
            data["nom"] = mrz_nom
        else:
            # Aucune similitude : le prénom s'est retrouvé dans le champ nom → on permute
            data["prenom"] = _clean_prenom_from_swap(data["nom"])
            data["nom"] = mrz_nom
    elif data["nom"] is not None and mrz_prefix is not None:
        # Pas de '<' dans le MRZ : vérification du début seulement via le préfixe
        correction = _artefact_am_debut(data["nom"], mrz_prefix)
        if correction is not None:
            data["nom"] = correction

    # ── Normalisation OCR : 1→I et 0→O au sein des noms (confusables fréquents)
    data["nom"] = _fix_ocr_confusables(data["nom"])
    data["prenom"] = _fix_ocr_confusables(data["prenom"])

    return data


def _extract_nom_mrz(mrz: str) -> str | None:
    """
    Extrait le nom depuis la ligne MRZ d'un permis FR (format D1FRA...).
    Gère les noms composés : AIT<IDIR → 'AIT IDIR', AZIRI<<< → 'AZIRI'.
    """
    zone = mrz[20:] if len(mrz) > 20 else mrz
    zone = zone.replace("0", "O")
    zone = re.sub(r"^[^A-Z<]*", "", zone)
    zone = re.sub(r"[^A-Z<].*$", "", zone)
    if not zone:
        return None
    surname_part = zone.split("<<")[0]
    nom = surname_part.replace("<", " ").strip()
    return nom or None


def _extract_mrz_name_prefix(mrz: str, min_len: int = 4) -> str | None:
    """Extrait le préfixe alphabétique du nom dans la zone MRZ (position 20+)."""
    zone = mrz[20:] if len(mrz) > 20 else mrz
    zone = re.sub(r"0", "O", zone)
    zone = re.sub(r"^[^A-Z]+", "", zone)
    m = re.match(r"([A-Z]+)", zone)
    prefix = m.group(1) if m else ""
    return prefix if len(prefix) >= min_len else None


def _artefact_am_debut(nom_recto: str, mrz_prefix: str) -> str | None:
    """
    Supprime un 'A' ou 'M' artéfact en début de nom_recto si recto[1:]
    commence par le préfixe MRZ (MRZ sans '<', vérification début uniquement).
    """
    r = nom_recto.upper().strip()
    p = mrz_prefix.upper().strip()
    if r and r[0] in "AM" and r[1:].startswith(p):
        return nom_recto[1:]
    return None


def _similar_to_mrz(nom_recto: str, mrz_nom: str) -> bool:
    """Retourne True si nom_recto et mrz_nom désignent vraisemblablement le même nom."""
    r, m = nom_recto.upper().strip(), mrz_nom.upper().strip()
    if r == m:
        return True
    # MRZ contenu dans le recto (artefacts autour)
    if m in r:
        return True
    # Préfixe commun ≥ 4 chars (ou toute la longueur du nom MRZ si plus court)
    min_pref = min(4, len(m))
    return len(r) >= min_pref and r[:min_pref] == m[:min_pref]


def _clean_prenom_from_swap(prenom: str) -> str:
    """Supprime un artefact A/M isolé en début et fin d'un prénom mal classé comme nom."""
    s = prenom.strip()
    if len(s) > 2 and s[0] in "AM" and s[1].isupper():
        s = s[1:]
    if len(s) > 2 and s[-1] in "AM" and s[-2].isupper():
        s = s[:-1]
    return s


def _fix_ocr_confusables(s: str | None) -> str | None:
    """Corrige les confusions chiffre/lettre fréquentes dans les noms OCR."""
    if s is None:
        return None
    s = re.sub(r"(?<=[A-Za-z])1(?=[A-Za-z])", "I", s)
    s = re.sub(r"(?<=[A-Za-z])0(?=[A-Za-z])", "O", s)
    return s


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YYYY ou DD/MM/YYYY et retourne YYYY-MM-DD."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None

