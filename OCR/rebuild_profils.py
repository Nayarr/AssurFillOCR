"""
Reconstruit tous les profils unifiés depuis les _res.json déjà présents dans output/.
Ne re-OCRise pas : relit rec_texts/rec_scores, re-parse, re-merge, sauvegarde _profil.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from detector import detecter_et_parser
from profils import construire_profil

_ROLES = {
    "permis_fr_nouveau_recto": "recto",
    "permis_dz_nouveau_recto": "recto",
    "permis_fr_nouveau_verso": "verso",
    "permis_dz_nouveau_verso": "verso",
    "cg_normale": "cg",
    "cg_provisoire": "cg",
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def _reconstruire_dossier(nom: str, chemin: str) -> None:
    res_files = sorted(f for f in os.listdir(chemin) if f.endswith("_res.json"))
    if not res_files:
        print(f"  [SKIP] Aucun _res.json dans {nom}")
        return

    roles: dict[str, dict] = {}

    for fname in res_files:
        with open(os.path.join(chemin, fname), encoding="utf-8") as fh:
            raw = json.load(fh)

        texts = raw.get("rec_texts", [])
        scores = raw.get("rec_scores", [])
        parsed = detecter_et_parser(texts, scores)
        type_doc = parsed.get("type", "inconnu")
        role = _ROLES.get(type_doc)

        if role is None:
            print(f"  [AVERT] {fname} → type '{type_doc}' non reconnu, ignoré")
            continue
        if role in roles:
            print(f"  [AVERT] Rôle '{role}' dupliqué ({fname}), ignoré")
            continue

        roles[role] = parsed

    manquants = [r for r in ("recto", "verso", "cg") if r not in roles]
    if manquants:
        print(f"  [ERREUR] Rôles manquants {manquants}, profil ignoré")
        return

    profil = construire_profil(roles["recto"], roles["verso"], roles["cg"])

    nom_sortie = nom + "_profil.json"
    chemin_sortie = os.path.join(chemin, nom_sortie)
    with open(chemin_sortie, "w", encoding="utf-8") as fh:
        json.dump(profil, fh, ensure_ascii=False, indent=2)

    suspecte = "  [PAIRE SUSPECTE]" if profil.get("_paire_suspecte") else ""
    print(f"  ✓ {profil['profil_type']}  nom={profil['nom']!r}  prenom={profil['prenom']!r}{suspecte}")


def main() -> None:
    dossiers = sorted(
        d for d in os.listdir(OUTPUT_DIR)
        if os.path.isdir(os.path.join(OUTPUT_DIR, d))
    )
    print(f"Rebuild de {len(dossiers)} dossier(s)...\n")

    for nom in dossiers:
        chemin = os.path.join(OUTPUT_DIR, nom)
        print(f"=== {nom} ===")
        _reconstruire_dossier(nom, chemin)


if __name__ == "__main__":
    main()
