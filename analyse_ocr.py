"""
Script d'analyse statistique des résultats OCR (fichiers *_parsed.json).
"""

import json
import os
from pathlib import Path
from collections import defaultdict

OUTPUT_DIR = Path(__file__).parent / "output"

# Champs attendus par type de document
CHAMPS_PAR_TYPE = {
    "permis_dz_nouveau_recto": ["nom", "prenom", "date_naissance", "date_expiration", "numero_permis"],
    "permis_dz_nouveau_verso": ["nom", "prenom", "sexe", "date_naissance", "date_expiration", "numero_permis"],
    "permis_fr_nouveau_recto": ["nom", "prenom", "date_naissance", "date_expiration", "numero_permis"],
    "permis_fr_nouveau_verso": ["obtention_B"],
    "inconnu": [],
}


def is_null(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def load_parsed_files() -> list[dict]:
    records = []
    for path in sorted(OUTPUT_DIR.glob("*_parsed.json")):
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
                data["_fichier"] = path.name
                records.append(data)
            except json.JSONDecodeError as e:
                print(f"[ERREUR] {path.name}: {e}")
    return records


def print_separator(char="─", width=60):
    print(char * width)


def analyse_globale(records: list[dict]):
    print_separator("═")
    print("ANALYSE GLOBALE")
    print_separator("═")

    total_docs = len(records)
    types_count = defaultdict(int)
    for r in records:
        types_count[r.get("type", "inconnu")] += 1

    print(f"\nNombre total de documents : {total_docs}")
    print("\nRépartition par type :")
    for t, count in sorted(types_count.items(), key=lambda x: -x[1]):
        pct = count / total_docs * 100
        print(f"  {t:<35} {count:>3}  ({pct:.1f}%)")

    # Taux de null global (tous champs hors _fichier, type, textes_bruts)
    total_valeurs = 0
    total_nulls = 0
    for r in records:
        for k, v in r.items():
            if k.startswith("_") or k in ("type", "textes_bruts"):
                continue
            total_valeurs += 1
            if is_null(v):
                total_nulls += 1

    if total_valeurs > 0:
        pct_null_global = total_nulls / total_valeurs * 100
        print(f"\nTaux de null global (tous champs extraits) : "
              f"{total_nulls}/{total_valeurs} = {pct_null_global:.1f}%")


def analyse_par_type(records: list[dict]):
    print_separator("═")
    print("TAUX DE NULL PAR TYPE ET PAR ATTRIBUT")
    print_separator("═")

    # Regrouper par type
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_type[r.get("type", "inconnu")].append(r)

    for doc_type, docs in sorted(by_type.items()):
        champs_attendus = CHAMPS_PAR_TYPE.get(doc_type)

        print(f"\n[{doc_type}]  —  {len(docs)} document(s)")
        print_separator()

        if doc_type == "inconnu" or not champs_attendus:
            print("  (pas de champs structurés attendus)")
            continue

        # Collecter toutes les clés présentes dans ces docs
        all_keys = set()
        for d in docs:
            all_keys.update(k for k in d.keys() if not k.startswith("_") and k not in ("type", "textes_bruts"))
        champs = sorted(all_keys, key=lambda k: (k not in champs_attendus, k))

        for champ in champs:
            valeurs = [d.get(champ) for d in docs]
            present = [v for v in valeurs if v is not None or champ in d for d in docs[:1]]  # always count
            present_count = sum(1 for d in docs if champ in d)
            null_count = sum(1 for d in docs if is_null(d.get(champ)))
            manquant_count = len(docs) - present_count  # champ absent du JSON

            tag = " ⚠ attendu" if champ in champs_attendus else ""
            print(f"  {champ:<25} "
                  f"null: {null_count:>2}/{len(docs)}  "
                  f"absent: {manquant_count:>2}/{len(docs)}  "
                  f"({(null_count + manquant_count) / len(docs) * 100:.0f}% manquant){tag}")


def analyse_par_attribut_global(records: list[dict]):
    print_separator("═")
    print("TAUX DE NULL PAR ATTRIBUT (tous types confondus, hors 'inconnu')")
    print_separator("═")

    docs_structures = [r for r in records if r.get("type") != "inconnu"]
    if not docs_structures:
        print("Aucun document structuré.")
        return

    all_keys: set[str] = set()
    for r in docs_structures:
        all_keys.update(k for k in r.keys() if not k.startswith("_") and k not in ("type", "textes_bruts"))

    print(f"\nSur {len(docs_structures)} documents structurés :\n")
    stats = []
    for champ in sorted(all_keys):
        docs_avec_champ = [r for r in docs_structures if champ in r]
        if not docs_avec_champ:
            continue
        null_count = sum(1 for r in docs_avec_champ if is_null(r[champ]))
        pct = null_count / len(docs_avec_champ) * 100
        stats.append((champ, null_count, len(docs_avec_champ), pct))

    stats.sort(key=lambda x: -x[3])
    for champ, nulls, total, pct in stats:
        bar = "█" * int(pct / 5)
        print(f"  {champ:<25} {nulls:>2}/{total:<3}  {pct:5.1f}%  {bar}")


def main():
    print(f"\nDossier analysé : {OUTPUT_DIR}\n")
    records = load_parsed_files()
    if not records:
        print("Aucun fichier *_parsed.json trouvé.")
        return

    analyse_globale(records)
    print()
    analyse_par_attribut_global(records)
    print()
    analyse_par_type(records)
    print()
    print_separator("═")
    print("Analyse terminée.")
    print_separator("═")


if __name__ == "__main__":
    main()
