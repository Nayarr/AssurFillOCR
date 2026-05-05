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
            if data["nom"] is None and "<" in t:
                nom_part = re.sub(r"0", "O", t[20:]) if len(t) > 20 else t
                matches = re.findall(r"([A-Z]{2,})<", nom_part)
                if matches:
                    data["nom"] = matches[-1]

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

        # ── Prénom — champ 2.
        elif data["prenom"] is None and re.match(r"^2[.\s]", t):
            s = re.sub(r"^\d+[a-z]?[.\s]\d*\s*", "", t).strip()
            s = re.sub(r"^[^A-Za-zÀ-ÿ]{1,2}", "", s).strip()
            s = re.sub(r"[^A-Za-zÀ-ÿ\-']{1,2}$", "", s).strip()
            s = re.sub(r"^[a-zà-ÿ](?=[A-ZÀ-Ÿ])", "", s).strip()
            s = re.sub(r"(?<=[A-ZÀ-Ÿ])[a-zà-ÿ]$", "", s).strip()
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

    return data


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YYYY ou DD/MM/YYYY et retourne YYYY-MM-DD."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None

