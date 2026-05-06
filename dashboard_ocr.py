"""
Dashboard Streamlit — Analyse statistique des résultats OCR (permis de conduire + cartes grises + profils unifiés).
Lancer : streamlit run dashboard_ocr.py
"""

import json
from pathlib import Path
from collections import defaultdict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Config ───────────────────────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).parent / "output"

# Tous les champs trackés dans les stats de null
CHAMPS_PAR_TYPE = {
    "permis_dz_nouveau_recto": ["nom", "prenom", "date_naissance", "date_expiration", "numero_permis"],
    "permis_dz_nouveau_verso": ["nom", "prenom", "sexe", "date_naissance", "date_expiration", "numero_permis", "obtention_B"],
    "permis_fr_nouveau_recto": ["nom", "prenom", "date_naissance", "date_expiration", "numero_permis"],
    "permis_fr_nouveau_verso": ["obtention_B"],
    "cg_normale": ["numero_immatriculation", "vin", "proprietaire_nom", "proprietaire_prenom", "conducteur", "marque", "modele", "puissance_fiscale"],
    "cg_provisoire": ["numero_immatriculation", "proprietaire_nom", "proprietaire_prenom", "marque", "modele", "puissance_fiscale"],
}

# Champs strictement requis pour qu'un document soit "utilisable"
# Pour les CG : plaque + marque + modèle + puissance fiscale suffisent.
# Le reste (VIN, propriétaire, conducteur) est du bonus pour la réconciliation future permis ↔ CG.
CHAMPS_REQUIS_PAR_TYPE = {
    **{k: v for k, v in CHAMPS_PAR_TYPE.items() if k not in ("cg_normale", "cg_provisoire")},
    "cg_normale": ["numero_immatriculation", "marque", "modele", "puissance_fiscale"],
    "cg_provisoire": ["numero_immatriculation", "marque", "modele", "puissance_fiscale"],
}

RECTO_TYPES = {"permis_dz_nouveau_recto", "permis_fr_nouveau_recto"}
VERSO_TYPES = {"permis_dz_nouveau_verso", "permis_fr_nouveau_verso"}

FAMILLE_PAR_TYPE = {
    "permis_dz_nouveau_recto": "Permis",
    "permis_dz_nouveau_verso": "Permis",
    "permis_fr_nouveau_recto": "Permis",
    "permis_fr_nouveau_verso": "Permis",
    "cg_normale": "Carte grise",
    "cg_provisoire": "Carte grise",
}

CG_TYPES = {"cg_normale", "cg_provisoire"}

COLORS = px.colors.qualitative.Set2

# Champs présents dans un profil unifié
CHAMPS_PROFIL = [
    "nom", "prenom", "date_naissance", "sexe",
    "numero_permis", "pays_permis", "date_expiration_permis", "obtention_B",
    "numero_immatriculation", "vin", "marque", "modele", "puissance_fiscale",
    "proprietaire_nom", "proprietaire_prenom", "conducteur",
]

# Champs qui déterminent l'utilisabilité d'un profil en assurance.
# Chaque champ présent ajoute 1/9 au taux d'utilisabilité (0–100 %).
# Un profil est "complet" (100 %) si tous sont renseignés ; il reste
# partiellement utilisable même s'il en manque un ou plusieurs.
CHAMPS_REQUIS_PROFIL = [
    "nom", "prenom", "date_naissance", "obtention_B",
    "numero_immatriculation", "marque", "modele", "puissance_fiscale",
    "numero_permis",
]

# ─── Data loading ─────────────────────────────────────────────────────────────

def load_data():
    records = []
    for path in sorted(OUTPUT_DIR.glob("*_parsed.json")):
        stem = path.stem.replace("_parsed", "")
        parsed = json.loads(path.read_text(encoding="utf-8"))
        parsed["_fichier"] = path.name
        parsed["_stem"] = stem

        res_path = OUTPUT_DIR / f"{stem}_res.json"
        if res_path.exists():
            res = json.loads(res_path.read_text(encoding="utf-8"))
            scores = res.get("rec_scores", [])
            texts = res.get("rec_texts", [])
            parsed["_scores"] = scores
            parsed["_texts"] = texts
            parsed["_score_mean"] = sum(scores) / len(scores) if scores else None
            parsed["_score_min"] = min(scores) if scores else None
            parsed["_n_texts"] = len(texts)
        else:
            parsed["_scores"] = []
            parsed["_texts"] = []
            parsed["_score_mean"] = None
            parsed["_score_min"] = None
            parsed["_n_texts"] = 0

        records.append(parsed)
    return records


def load_profiles():
    profiles = []
    for path in sorted(OUTPUT_DIR.glob("*/*_profil.json")):
        profil = json.loads(path.read_text(encoding="utf-8"))
        profil["_dossier"] = path.parent.name
        profil["_fichier"] = path.name
        profiles.append(profil)
    return profiles


def is_null(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


# ─── Computed frames ──────────────────────────────────────────────────────────

def compute_frames(records):
    structured = [r for r in records if r.get("type") != "inconnu"]
    inconnus = [r for r in records if r.get("type") == "inconnu"]

    # ── 1. Null par attribut global
    champ_stats = defaultdict(lambda: {"total": 0, "null": 0})
    for r in structured:
        doc_type = r.get("type", "")
        champs = CHAMPS_PAR_TYPE.get(doc_type, [])
        for c in champs:
            champ_stats[c]["total"] += 1
            if is_null(r.get(c)):
                champ_stats[c]["null"] += 1

    null_rows = []
    for champ, s in champ_stats.items():
        pct = s["null"] / s["total"] * 100 if s["total"] else 0
        null_rows.append({"champ": champ, "null": s["null"], "total": s["total"], "pct_null": round(pct, 1)})
    df_null_raw = pd.DataFrame(null_rows)
    df_null = df_null_raw.sort_values("pct_null", ascending=False) if not df_null_raw.empty else df_null_raw

    # ── 2. Null par type × attribut
    rows_type = []
    for r in structured:
        doc_type = r.get("type", "")
        champs = CHAMPS_PAR_TYPE.get(doc_type, [])
        for c in champs:
            rows_type.append({
                "type": doc_type,
                "champ": c,
                "null": is_null(r.get(c)),
                "fichier": r["_fichier"],
            })
    df_type_null = pd.DataFrame(rows_type)

    # ── 3. Utilisabilité (champs requis non-null — pour les CG, bonus exclus)
    usable_rows = []
    for r in structured:
        doc_type = r.get("type", "")
        champs_requis = CHAMPS_REQUIS_PAR_TYPE.get(doc_type, [])
        manquants = [c for c in champs_requis if is_null(r.get(c))]
        usable_rows.append({
            "fichier": r["_fichier"],
            "type": doc_type,
            "utilisable": len(manquants) == 0,
            "champs_manquants": ", ".join(manquants) if manquants else "—",
            "n_manquants": len(manquants),
        })
    df_usable = pd.DataFrame(usable_rows)

    # ── 4. Scores OCR
    score_rows = []
    for r in records:
        if r["_score_mean"] is not None:
            score_rows.append({
                "fichier": r["_fichier"],
                "type": r.get("type", "inconnu"),
                "score_moyen": round(r["_score_mean"], 4),
                "score_min": round(r["_score_min"], 4),
                "n_textes": r["_n_texts"],
            })
    df_scores = pd.DataFrame(score_rows)

    # ── 5. Confiance vs null (corrélation score moyen ↔ champs requis null)
    conf_rows = []
    for r in structured:
        doc_type = r.get("type", "")
        champs_requis = CHAMPS_REQUIS_PAR_TYPE.get(doc_type, [])
        n_null = sum(1 for c in champs_requis if is_null(r.get(c)))
        conf_rows.append({
            "fichier": r["_fichier"],
            "type": doc_type,
            "score_moyen": r["_score_mean"],
            "n_null": n_null,
            "utilisable": n_null == 0,
        })
    df_conf_raw = pd.DataFrame(conf_rows)
    df_conf = df_conf_raw.dropna(subset=["score_moyen"]) if not df_conf_raw.empty else df_conf_raw

    # ── 6. Recto / verso : appariement par numéro consécutif
    # On suppose que les fichiers sont nommés de façon ordonnée et que
    # recto et verso sont des photos consécutives d'un même lot.
    sorted_recs = sorted(records, key=lambda r: r["_stem"])
    pairs = []
    i = 0
    while i < len(sorted_recs) - 1:
        a = sorted_recs[i]
        b = sorted_recs[i + 1]
        ta, tb = a.get("type", ""), b.get("type", "")
        if ta in RECTO_TYPES and tb in VERSO_TYPES:
            # vérifier même famille (dz/fr)
            famille_a = "dz" if "dz" in ta else "fr"
            famille_b = "dz" if "dz" in tb else "fr"
            if famille_a == famille_b:
                paire = {"recto": a, "verso": b}
                shared = ["nom", "prenom", "numero_permis"]
                for c in shared:
                    va, vb = a.get(c), b.get(c)
                    if va and vb:
                        concordance = str(va).strip().upper() == str(vb).strip().upper()
                        paire[f"match_{c}"] = concordance
                        paire[f"val_recto_{c}"] = va
                        paire[f"val_verso_{c}"] = vb
                    else:
                        paire[f"match_{c}"] = None
                        paire[f"val_recto_{c}"] = va
                        paire[f"val_verso_{c}"] = vb
                pairs.append(paire)
                i += 2
                continue
        i += 1
    df_pairs = _build_pairs_df(pairs)

    # ── 7. Analyse inconnus
    inconnu_rows = []
    for r in inconnus:
        texts = r.get("textes_bruts", [])
        text_join = " ".join(texts).upper()
        hint = "—"
        if "CRFRA" in text_join or "CERTIFICAT D'IMMATRICULATION" in text_join or "IMMATRICUL" in text_join:
            hint = "Probablement carte grise FR"
        elif any(k in text_join for k in ["WW-", "CERTIFICAT PROVISOIRE"]):
            hint = "Probablement CG provisoire"
        elif any(k in text_join for k in ["REPUBLIQUE ALGER", "DZ", "ALGERIE"]):
            hint = "Probablement permis DZ"
        elif "REPUBLIQUE FRANCAISE" in text_join or "PREFET" in text_join:
            hint = "Probablement permis FR"
        elif "PERMIS DE CONDUIRE" in text_join:
            hint = "Permis (pays inconnu)"
        elif "DRIVING LICENCE" in text_join or "FÜHRERSCHEIN" in text_join:
            hint = "Permis étranger"
        inconnu_rows.append({
            "fichier": r["_fichier"],
            "n_textes": len(texts),
            "indice": hint,
            "score_moyen": round(r["_score_mean"], 3) if r["_score_mean"] else None,
            "textes_bruts": " | ".join(texts[:8]),
        })
    df_inconnus = pd.DataFrame(inconnu_rows)

    # ── 8. Statistiques cartes grises
    df_cg = _compute_cg_frame(records)

    return df_null, df_type_null, df_usable, df_scores, df_conf, df_pairs, df_inconnus, df_cg


def _compute_cg_frame(records):
    rows = []
    for r in records:
        if r.get("type") not in CG_TYPES:
            continue
        rows.append({
            "fichier": r["_fichier"],
            "type": r.get("type"),
            "numero_immatriculation": r.get("numero_immatriculation"),
            "vin": r.get("vin"),
            "proprietaire_nom": r.get("proprietaire_nom"),
            "proprietaire_prenom": r.get("proprietaire_prenom"),
            "conducteur": r.get("conducteur"),
            "marque": r.get("marque"),
            "modele": r.get("modele"),
            "puissance_fiscale": r.get("puissance_fiscale"),
            "score_moyen": r.get("_score_mean"),
        })
    return pd.DataFrame(rows)


def _build_pairs_df(pairs):
    rows = []
    for p in pairs:
        row = {
            "recto": p["recto"]["_fichier"],
            "verso": p["verso"]["_fichier"],
        }
        for c in ["nom", "prenom", "numero_permis"]:
            row[f"match_{c}"] = p.get(f"match_{c}")
            row[f"recto_{c}"] = p.get(f"val_recto_{c}")
            row[f"verso_{c}"] = p.get(f"val_verso_{c}")
        rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def compute_profile_frames(profiles):
    if not profiles:
        return pd.DataFrame(), pd.DataFrame()

    profil_rows = []
    conflit_rows = []

    for p in profiles:
        pt = p.get("profil_type", "inconnu")
        pays = "FR" if "fr" in pt else ("DZ" if "dz" in pt else "?")
        type_cg = "normale" if "normale" in pt else ("provisoire" if "provisoire" in pt else "?")

        conflits = p.get("_conflits", []) or []
        n_conflits = len(conflits)
        n_majeur = sum(1 for c in conflits if c.get("type") == "majeur")

        manquants = [c for c in CHAMPS_REQUIS_PROFIL if is_null(p.get(c))]
        n_requis = len(CHAMPS_REQUIS_PROFIL)
        n_presents = n_requis - len(manquants)
        taux = round(n_presents / n_requis * 100, 1) if n_requis else 0.0
        utilisable = taux == 100.0

        row = {
            "_dossier": p["_dossier"],
            "_fichier": p["_fichier"],
            "profil_type": pt,
            "pays": pays,
            "type_cg": type_cg,
            "n_conflits": n_conflits,
            "n_conflits_majeur": n_majeur,
            "taux_utilisabilite": taux,
            "utilisable": utilisable,
            "champs_manquants": ", ".join(manquants) if manquants else "—",
        }
        for champ in CHAMPS_PROFIL:
            row[champ] = p.get(champ)
        profil_rows.append(row)

        for c in conflits:
            conflit_rows.append({
                "_dossier": p["_dossier"],
                "profil_type": pt,
                "pays": pays,
                "champ": c.get("champ"),
                "type_conflit": c.get("type"),
                "source": c.get("source", "?"),
                "similitude": c.get("similitude"),
                "decision": c.get("decision"),
            })

    return pd.DataFrame(profil_rows), pd.DataFrame(conflit_rows)


# ─── Page renderers ───────────────────────────────────────────────────────────

def page_overview(records):
    st.header("Vue d'ensemble")

    if not records:
        st.info("Aucun document individuel trouvé (pas de fichiers `*_parsed.json` dans `output/`). Utilisez les pages **Profils** pour analyser les résultats.")
        return

    total = len(records)
    structured = [r for r in records if r.get("type") != "inconnu"]
    inconnus = [r for r in records if r.get("type") == "inconnu"]
    permis = [r for r in structured if r.get("type") not in CG_TYPES]
    cartes_grises = [r for r in structured if r.get("type") in CG_TYPES]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Documents analysés", total)
    c2.metric("Documents structurés", len(structured))
    c3.metric("Permis", len(permis))
    c4.metric("Cartes grises", len(cartes_grises))
    c5.metric("Inconnus", len(inconnus),
              delta=f"{len(inconnus)/total*100:.0f}%" if total else "—",
              delta_color="inverse")

    # Répartition famille
    famille_counts = defaultdict(int)
    for r in records:
        doc_type = r.get("type", "inconnu")
        famille = FAMILLE_PAR_TYPE.get(doc_type, "Inconnu")
        famille_counts[famille] += 1
    df_famille = pd.DataFrame([{"famille": k, "count": v} for k, v in famille_counts.items()])

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fig_f = px.pie(df_famille, names="famille", values="count",
                       title="Répartition par famille de document",
                       color_discrete_sequence=COLORS)
        fig_f.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_f, use_container_width=True)

    type_counts = defaultdict(int)
    for r in records:
        type_counts[r.get("type", "inconnu")] += 1
    df_types = pd.DataFrame([{"type": k, "count": v} for k, v in type_counts.items()])

    with col_f2:
        fig2 = px.bar(df_types.sort_values("count", ascending=True),
                      x="count", y="type", orientation="h",
                      title="Nombre de documents par type",
                      color="type", color_discrete_sequence=COLORS)
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    # Taux null global
    total_vals, total_nulls = 0, 0
    for r in structured:
        doc_type = r.get("type", "")
        champs = CHAMPS_PAR_TYPE.get(doc_type, [])
        for c in champs:
            total_vals += 1
            if is_null(r.get(c)):
                total_nulls += 1

    if total_vals:
        pct = total_nulls / total_vals * 100
        st.subheader("Taux de null global")
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(pct, 1),
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#EF553B" if pct > 30 else "#00CC96"},
                "steps": [
                    {"range": [0, 15], "color": "#d4edda"},
                    {"range": [15, 35], "color": "#fff3cd"},
                    {"range": [35, 100], "color": "#f8d7da"},
                ],
            },
            title={"text": f"Champs null sur {total_vals} valeurs attendues"},
        ))
        fig3.update_layout(height=250)
        st.plotly_chart(fig3, use_container_width=True)


def page_null_fields(df_null, df_type_null):
    st.header("Analyse des champs null")

    st.subheader("Taux de null par attribut (tous types)")
    fig = px.bar(df_null, x="champ", y="pct_null",
                 text="pct_null", color="pct_null",
                 color_continuous_scale=["#00CC96", "#FFA15A", "#EF553B"],
                 labels={"pct_null": "% null", "champ": "Attribut"},
                 title="% de valeurs null par attribut")
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_coloraxes(showscale=False)
    fig.update_layout(yaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df_null.rename(columns={"champ": "Attribut", "null": "Null",
                                          "total": "Total", "pct_null": "% Null"}),
                 use_container_width=True, hide_index=True)

    st.subheader("Taux de null par type × attribut")
    if not df_type_null.empty:
        pivot = df_type_null.groupby(["type", "champ"])["null"].mean().reset_index()
        pivot["pct_null"] = (pivot["null"] * 100).round(1)
        fig2 = px.bar(pivot, x="champ", y="pct_null", color="type",
                      barmode="group",
                      color_discrete_sequence=COLORS,
                      labels={"pct_null": "% null", "champ": "Attribut", "type": "Type"},
                      title="% null par attribut, groupé par type")
        fig2.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig2, use_container_width=True)

        # Heatmap
        heatmap_data = pivot.pivot(index="type", columns="champ", values="pct_null").fillna(0)
        fig3 = px.imshow(heatmap_data, text_auto=True,
                         color_continuous_scale=["#d4edda", "#fff3cd", "#f8d7da"],
                         aspect="auto", title="Heatmap null % (type × attribut)")
        st.plotly_chart(fig3, use_container_width=True)


def page_usability(df_usable):
    st.header("Utilisabilité des documents")
    st.caption("Un document est *utilisable* si tous ses champs attendus sont renseignés.")

    if df_usable.empty:
        st.info("Aucun document structuré.")
        return

    total = len(df_usable)
    n_ok = df_usable["utilisable"].sum()
    pct_ok = n_ok / total * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Documents utilisables", f"{n_ok}/{total}")
    c2.metric("Taux d'utilisabilité", f"{pct_ok:.1f}%")
    c3.metric("Documents incomplets", f"{total - n_ok}")

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(values=[n_ok, total - n_ok],
                     names=["Utilisable ✓", "Incomplet ✗"],
                     color_discrete_sequence=["#00CC96", "#EF553B"],
                     title="Utilisabilité globale")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        by_type = df_usable.groupby("type")["utilisable"].agg(["sum", "count"]).reset_index()
        by_type["pct"] = (by_type["sum"] / by_type["count"] * 100).round(1)
        fig2 = px.bar(by_type, x="type", y="pct", text="pct",
                      color="pct", color_continuous_scale=["#EF553B", "#FFA15A", "#00CC96"],
                      title="% utilisables par type")
        fig2.update_traces(texttemplate="%{text}%", textposition="outside")
        fig2.update_coloraxes(showscale=False)
        fig2.update_layout(yaxis_range=[0, 110])
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Détail des documents incomplets")
    incomplets = df_usable[~df_usable["utilisable"]].sort_values("n_manquants", ascending=False)
    if incomplets.empty:
        st.success("Tous les documents sont utilisables !")
    else:
        st.dataframe(incomplets[["fichier", "type", "champs_manquants", "n_manquants"]]
                     .rename(columns={"fichier": "Fichier", "type": "Type",
                                      "champs_manquants": "Champs manquants", "n_manquants": "Nb manquants"}),
                     use_container_width=True, hide_index=True)


def page_ocr_confidence(df_scores, df_conf):
    st.header("Scores de confiance OCR")

    if df_scores.empty:
        st.info("Aucun fichier _res.json trouvé.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Score moyen global", f"{df_scores['score_moyen'].mean():.3f}")
    c2.metric("Score min médian", f"{df_scores['score_min'].median():.3f}")
    c3.metric("Docs avec score < 0.5", int((df_scores["score_moyen"] < 0.5).sum()))

    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(df_scores, x="score_moyen", color="type",
                           nbins=20, barmode="overlay",
                           color_discrete_sequence=COLORS,
                           title="Distribution des scores moyens OCR",
                           labels={"score_moyen": "Score moyen", "type": "Type"})
        fig.add_vline(x=0.7, line_dash="dash", line_color="red",
                      annotation_text="Seuil 0.7", annotation_position="top right")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        box_df = df_scores.melt(id_vars=["type"], value_vars=["score_moyen", "score_min"],
                                var_name="métrique", value_name="score")
        fig2 = px.box(box_df, x="type", y="score", color="métrique",
                      color_discrete_sequence=COLORS,
                      title="Distribution score moyen vs min par type")
        fig2.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Corrélation score OCR ↔ champs null")
    if not df_conf.empty:
        fig3 = px.scatter(df_conf, x="score_moyen", y="n_null",
                          color="utilisable", symbol="type",
                          color_discrete_map={True: "#00CC96", False: "#EF553B"},
                          labels={"score_moyen": "Score OCR moyen", "n_null": "Nbre de champs null",
                                  "utilisable": "Utilisable", "type": "Type"},
                          title="Score moyen OCR vs nombre de champs null")
        fig3.add_vline(x=0.7, line_dash="dash", line_color="gray", annotation_text="0.7")
        st.plotly_chart(fig3, use_container_width=True)

        seuil = st.slider("Seuil de score moyen", 0.0, 1.0, 0.7, 0.05)
        sous_seuil = df_conf[df_conf["score_moyen"] < seuil]
        col_a, col_b = st.columns(2)
        col_a.metric(f"Docs sous le seuil {seuil}", len(sous_seuil))
        if not sous_seuil.empty:
            col_b.metric("Dont inutilisables",
                         int((~sous_seuil["utilisable"]).sum()),
                         delta=f"{(~sous_seuil['utilisable']).mean()*100:.0f}%",
                         delta_color="inverse")

    st.subheader("Tableau des scores")
    st.dataframe(df_scores.rename(columns={
        "fichier": "Fichier", "type": "Type",
        "score_moyen": "Score moyen", "score_min": "Score min", "n_textes": "Nb textes"
    }), use_container_width=True, hide_index=True)


def page_inconnus(df_inconnus):
    st.header("Analyse des documents 'inconnu'")

    if df_inconnus.empty:
        st.success("Aucun document inconnu.")
        return

    st.metric("Documents non reconnus", len(df_inconnus))

    fig = px.pie(df_inconnus, names="indice",
                 color_discrete_sequence=COLORS,
                 title="Indices de type pour les documents inconnus")
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig2 = px.histogram(df_inconnus.dropna(subset=["score_moyen"]),
                            x="score_moyen", nbins=10,
                            title="Distribution des scores OCR (inconnus)",
                            labels={"score_moyen": "Score moyen"})
        st.plotly_chart(fig2, use_container_width=True)
    with col2:
        fig3 = px.bar(df_inconnus.groupby("indice").size().reset_index(name="count"),
                      x="indice", y="count", text="count",
                      title="Regroupement par indice",
                      color="indice", color_discrete_sequence=COLORS)
        fig3.update_layout(showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Détail")
    st.dataframe(df_inconnus[["fichier", "indice", "score_moyen", "n_textes", "textes_bruts"]]
                 .rename(columns={"fichier": "Fichier", "indice": "Indice",
                                  "score_moyen": "Score moy.", "n_textes": "Nb textes",
                                  "textes_bruts": "Textes (aperçu)"}),
                 use_container_width=True, hide_index=True)


def page_recto_verso(df_pairs):
    st.header("Cohérence recto / verso")
    st.caption("Paires détectées par ordre alphabétique des fichiers (recto suivi d'un verso de même famille).")

    if df_pairs.empty:
        st.warning("Aucune paire recto/verso détectée.")
        return

    champs_communs = ["nom", "prenom", "numero_permis"]
    st.metric("Paires identifiées", len(df_pairs))

    # Taux de concordance par champ
    conc_rows = []
    for c in champs_communs:
        col = f"match_{c}"
        if col in df_pairs.columns:
            valid = df_pairs[col].dropna()
            if not valid.empty:
                pct = valid.mean() * 100
                conc_rows.append({"champ": c, "concordance (%)": round(pct, 1),
                                  "paires comparables": len(valid)})

    if conc_rows:
        df_conc = pd.DataFrame(conc_rows)
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(df_conc, x="champ", y="concordance (%)", text="concordance (%)",
                         color="concordance (%)",
                         color_continuous_scale=["#EF553B", "#FFA15A", "#00CC96"],
                         title="Taux de concordance recto/verso par champ")
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            fig.update_coloraxes(showscale=False)
            fig.update_layout(yaxis_range=[0, 110])
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.dataframe(df_conc, use_container_width=True, hide_index=True)

    st.subheader("Détail des paires")
    rows_display = []
    for _, row in df_pairs.iterrows():
        for c in champs_communs:
            mc = f"match_{c}"
            if mc in df_pairs.columns:
                match_val = row.get(mc)
                if match_val is True:
                    icon = "✅"
                elif match_val is False:
                    icon = "❌"
                else:
                    icon = "—"
                rows_display.append({
                    "Recto": row["recto"],
                    "Verso": row["verso"],
                    "Champ": c,
                    "Valeur recto": row.get(f"recto_{c}"),
                    "Valeur verso": row.get(f"verso_{c}"),
                    "Concordance": icon,
                })
    if rows_display:
        st.dataframe(pd.DataFrame(rows_display), use_container_width=True, hide_index=True)


def page_cartes_grises(df_cg):
    st.header("Analyse des cartes grises")

    if df_cg.empty:
        st.info("Aucune carte grise trouvée dans les données.")
        return

    total = len(df_cg)
    n_normale = int((df_cg["type"] == "cg_normale").sum())
    n_provisoire = int((df_cg["type"] == "cg_provisoire").sum())
    n_avec_vin = int(df_cg["vin"].notna().sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total cartes grises", total)
    c2.metric("CG définitives", n_normale)
    c3.metric("CG provisoires (WW)", n_provisoire)
    c4.metric("Avec VIN renseigné", n_avec_vin)

    col1, col2 = st.columns(2)
    with col1:
        fig_type = px.pie(
            values=[n_normale, n_provisoire],
            names=["CG définitive", "CG provisoire (WW)"],
            color_discrete_sequence=["#636EFA", "#EF553B"],
            title="Répartition CG définitives / provisoires",
        )
        fig_type.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_type, use_container_width=True)

    with col2:
        marque_counts = df_cg["marque"].dropna().value_counts().reset_index()
        marque_counts.columns = ["marque", "count"]
        fig_marque = px.bar(
            marque_counts.head(15),
            x="count", y="marque", orientation="h",
            title="Top marques (cartes grises)",
            color="count", color_continuous_scale=["#c7e9fb", "#1f77b4"],
        )
        fig_marque.update_coloraxes(showscale=False)
        fig_marque.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_marque, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        modele_counts = df_cg["modele"].dropna().value_counts().reset_index()
        modele_counts.columns = ["modele", "count"]
        fig_modele = px.bar(
            modele_counts.head(15),
            x="count", y="modele", orientation="h",
            title="Top modèles (cartes grises)",
            color="count", color_continuous_scale=["#d4f1d4", "#2ca02c"],
        )
        fig_modele.update_coloraxes(showscale=False)
        fig_modele.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_modele, use_container_width=True)

    with col4:
        pf_df = df_cg["puissance_fiscale"].dropna().astype(int)
        if not pf_df.empty:
            fig_pf = px.histogram(
                pf_df, nbins=20,
                title="Distribution des puissances fiscales (CV)",
                labels={"value": "Puissance fiscale (CV)", "count": "Nombre"},
                color_discrete_sequence=["#FFA15A"],
            )
            fig_pf.update_layout(bargap=0.1)
            st.plotly_chart(fig_pf, use_container_width=True)

    st.subheader("Taux de remplissage des champs")
    fill_rows = []
    for col_name in ["numero_immatriculation", "vin", "proprietaire_nom", "proprietaire_prenom",
                     "marque", "modele", "puissance_fiscale"]:
        total_possible = len(df_cg) if col_name != "vin" else n_normale
        n_rempli = int(df_cg[col_name].notna().sum())
        pct = n_rempli / total_possible * 100 if total_possible else 0
        fill_rows.append({"champ": col_name, "rempli": n_rempli, "total": total_possible, "pct_rempli": round(pct, 1)})
    df_fill = pd.DataFrame(fill_rows)
    fig_fill = px.bar(
        df_fill, x="champ", y="pct_rempli", text="pct_rempli",
        color="pct_rempli",
        color_continuous_scale=["#EF553B", "#FFA15A", "#00CC96"],
        labels={"pct_rempli": "% rempli", "champ": "Champ"},
        title="Taux de remplissage par champ (cartes grises)",
    )
    fig_fill.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_fill.update_coloraxes(showscale=False)
    fig_fill.update_layout(yaxis_range=[0, 110])
    st.plotly_chart(fig_fill, use_container_width=True)

    st.subheader("Tableau des cartes grises")
    display_cols = ["fichier", "type", "numero_immatriculation", "vin", "proprietaire_nom",
                    "proprietaire_prenom", "marque", "modele", "puissance_fiscale"]
    rename_map = {
        "fichier": "Fichier", "type": "Type",
        "numero_immatriculation": "Immatriculation", "vin": "VIN",
        "proprietaire_nom": "Propriétaire (nom)", "proprietaire_prenom": "Propriétaire (prénom)",
        "marque": "Marque", "modele": "Modèle", "puissance_fiscale": "CV fiscaux",
    }
    st.dataframe(
        df_cg[display_cols].rename(columns=rename_map),
        use_container_width=True, hide_index=True,
    )


def page_profiles_overview(profiles, df_profils, df_conflits):
    st.header("Profils unifiés — Vue d'ensemble")
    st.caption("Un profil = recto + verso permis + carte grise fusionnés en un seul dict.")

    if df_profils.empty:
        st.info("Aucun profil trouvé dans le dossier output/.")
        return

    total = len(df_profils)
    n_fr = int((df_profils["pays"] == "FR").sum())
    n_dz = int((df_profils["pays"] == "DZ").sum())
    n_complets = int(df_profils["utilisable"].sum())
    n_avec_conflits = int((df_profils["n_conflits"] > 0).sum())
    taux_moyen = df_profils["taux_utilisabilite"].mean()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Profils générés", total)
    c2.metric("Permis FR", n_fr)
    c3.metric("Permis DZ", n_dz)
    c4.metric("Profils complets (100 %)", f"{n_complets}/{total}")
    c5.metric("Taux moy. utilisabilité", f"{taux_moyen:.1f}%")
    c6.metric("Avec conflits", n_avec_conflits,
              delta=f"{n_avec_conflits/total*100:.0f}%", delta_color="inverse")

    col1, col2 = st.columns(2)
    with col1:
        type_counts = df_profils["profil_type"].value_counts().reset_index()
        type_counts.columns = ["profil_type", "count"]
        fig = px.pie(type_counts, names="profil_type", values="count",
                     title="Répartition par type de profil",
                     color_discrete_sequence=COLORS)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        taux_par_type = df_profils.groupby("profil_type")["taux_utilisabilite"].mean().reset_index()
        taux_par_type["taux_utilisabilite"] = taux_par_type["taux_utilisabilite"].round(1)
        fig2 = px.bar(taux_par_type, x="profil_type", y="taux_utilisabilite",
                      text="taux_utilisabilite",
                      color="taux_utilisabilite",
                      color_continuous_scale=["#EF553B", "#FFA15A", "#00CC96"],
                      title="Taux d'utilisabilité moyen par type de profil",
                      labels={"profil_type": "Type", "taux_utilisabilite": "Taux moyen (%)"})
        fig2.update_traces(texttemplate="%{text}%", textposition="outside")
        fig2.update_coloraxes(showscale=False)
        fig2.update_layout(yaxis_range=[0, 110])
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Distribution du taux d'utilisabilité")
    fig_dist = px.histogram(
        df_profils, x="taux_utilisabilite", nbins=10,
        color_discrete_sequence=["#636EFA"],
        labels={"taux_utilisabilite": "Taux d'utilisabilité (%)"},
        title="Répartition des profils par taux d'utilisabilité",
    )
    fig_dist.add_vline(x=100, line_dash="dash", line_color="#00CC96",
                       annotation_text="Complet", annotation_position="top left")
    fig_dist.update_layout(bargap=0.1)
    st.plotly_chart(fig_dist, use_container_width=True)

    st.subheader("Taux de null par champ (tous profils)")
    null_rows = []
    for champ in CHAMPS_PROFIL:
        total_champ = len(df_profils)
        n_null = int(df_profils[champ].isna().sum())
        null_rows.append({
            "champ": champ,
            "null": n_null,
            "total": total_champ,
            "pct_null": round(n_null / total_champ * 100, 1),
            "requis": champ in CHAMPS_REQUIS_PROFIL,
        })
    df_null_profil = pd.DataFrame(null_rows).sort_values("pct_null", ascending=False)

    fig3 = px.bar(df_null_profil, x="champ", y="pct_null", text="pct_null",
                  color="pct_null", color_continuous_scale=["#00CC96", "#FFA15A", "#EF553B"],
                  pattern_shape="requis", pattern_shape_map={True: "", False: "/"},
                  labels={"pct_null": "% null", "champ": "Champ", "requis": "Requis"},
                  title="% de valeurs null par champ de profil (hachuré = optionnel)")
    fig3.update_traces(texttemplate="%{text}%", textposition="outside")
    fig3.update_coloraxes(showscale=False)
    fig3.update_layout(yaxis_range=[0, 110])
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Profils non complets (taux < 100 %)")
    st.caption("Ces profils restent partiellement utilisables selon leur taux.")
    incomplets = df_profils[~df_profils["utilisable"]][
        ["_dossier", "profil_type", "taux_utilisabilite", "champs_manquants"]
    ].sort_values("taux_utilisabilite", ascending=False).rename(columns={
        "_dossier": "Dossier", "profil_type": "Type",
        "taux_utilisabilite": "Taux (%)", "champs_manquants": "Champs manquants",
    })
    if incomplets.empty:
        st.success("Tous les profils sont complets à 100 % !")
    else:
        st.dataframe(incomplets, use_container_width=True, hide_index=True)


def page_profiles_conflicts(df_conflits, df_profils):
    st.header("Conflits de fusion des profils")
    st.caption(
        "Un conflit est détecté quand deux sources donnent des valeurs différentes pour le même champ. "
        "**Majeur** : divergence forte (ratio < 0.80). **Mineur** : léger écart OCR. **Date divergente** : dates incohérentes entre sources."
    )

    if df_conflits.empty:
        st.success("Aucun conflit détecté dans les profils.")
        return

    total_conflits = len(df_conflits)
    n_majeur = int((df_conflits["type_conflit"] == "majeur").sum())
    n_mineur = int((df_conflits["type_conflit"] == "mineur").sum())
    n_date = int((df_conflits["type_conflit"] == "date_divergente").sum())
    n_profils_touches = df_conflits["_dossier"].nunique()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total conflits", total_conflits)
    c2.metric("Conflits majeurs", n_majeur)
    c3.metric("Conflits mineurs", n_mineur)
    c4.metric("Dates divergentes", n_date)
    c5.metric("Profils touchés", n_profils_touches)

    col1, col2 = st.columns(2)
    with col1:
        type_counts = df_conflits["type_conflit"].value_counts().reset_index()
        type_counts.columns = ["type_conflit", "count"]
        fig = px.pie(type_counts, names="type_conflit", values="count",
                     title="Répartition par type de conflit",
                     color_discrete_sequence=["#EF553B", "#FFA15A", "#636EFA"])
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        src_counts = df_conflits["source"].value_counts().reset_index()
        src_counts.columns = ["source", "count"]
        fig2 = px.bar(src_counts, x="source", y="count", text="count",
                      color="source", color_discrete_sequence=COLORS,
                      title="Conflits par source",
                      labels={"source": "Source", "count": "Nb conflits"})
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Champs les plus conflictuels")
    champ_counts = df_conflits.groupby(["champ", "type_conflit"]).size().reset_index(name="count")
    fig3 = px.bar(champ_counts, x="champ", y="count", color="type_conflit",
                  barmode="stack",
                  color_discrete_map={"majeur": "#EF553B", "mineur": "#FFA15A", "date_divergente": "#636EFA"},
                  title="Nombre de conflits par champ",
                  labels={"champ": "Champ", "count": "Nb conflits", "type_conflit": "Type"})
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Conflits par type de profil")
    if not df_conflits.empty and not df_profils.empty:
        conflits_par_profil = df_conflits.groupby(["_dossier", "profil_type"]).size().reset_index(name="n_conflits")
        fig4 = px.box(conflits_par_profil, x="profil_type", y="n_conflits",
                      color="profil_type", color_discrete_sequence=COLORS,
                      title="Distribution du nombre de conflits par profil",
                      labels={"profil_type": "Type de profil", "n_conflits": "Nb conflits"})
        fig4.update_layout(showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)

    st.subheader("Distribution de la similitude (conflits texte)")
    sim_df = df_conflits.dropna(subset=["similitude"])
    if not sim_df.empty:
        fig5 = px.histogram(sim_df, x="similitude", color="type_conflit", nbins=20,
                            barmode="overlay",
                            color_discrete_map={"majeur": "#EF553B", "mineur": "#FFA15A"},
                            title="Distribution du ratio de similitude",
                            labels={"similitude": "Ratio de similitude", "type_conflit": "Type"})
        fig5.add_vline(x=0.80, line_dash="dash", line_color="gray",
                       annotation_text="Seuil 0.80", annotation_position="top right")
        st.plotly_chart(fig5, use_container_width=True)

    st.subheader("Détail des conflits")
    display = df_conflits[["_dossier", "profil_type", "champ", "type_conflit", "source", "similitude", "decision"]].rename(columns={
        "_dossier": "Dossier", "profil_type": "Type", "champ": "Champ",
        "type_conflit": "Type conflit", "source": "Source",
        "similitude": "Similitude", "decision": "Décision retenue",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)


def page_profiles_browser(df_profils):
    st.header("Explorateur de profils")

    if df_profils.empty:
        st.info("Aucun profil disponible.")
        return

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        types = ["Tous"] + sorted(df_profils["profil_type"].unique().tolist())
        filtre_type = st.selectbox("Type de profil", types)
    with col_f2:
        filtre_utilisable = st.selectbox("Utilisabilité", ["Tous", "Complets (100 %)", "Partiels (<100 %)", "Critiques (<50 %)"])
    with col_f3:
        filtre_conflits = st.selectbox("Conflits", ["Tous", "Avec conflits", "Sans conflit"])

    df = df_profils.copy()
    if filtre_type != "Tous":
        df = df[df["profil_type"] == filtre_type]
    if filtre_utilisable == "Complets (100 %)":
        df = df[df["utilisable"]]
    elif filtre_utilisable == "Partiels (<100 %)":
        df = df[~df["utilisable"]]
    elif filtre_utilisable == "Critiques (<50 %)":
        df = df[df["taux_utilisabilite"] < 50]
    if filtre_conflits == "Avec conflits":
        df = df[df["n_conflits"] > 0]
    elif filtre_conflits == "Sans conflit":
        df = df[df["n_conflits"] == 0]

    st.caption(f"{len(df)} profil(s) affiché(s)")

    display_cols = [
        "_dossier", "profil_type", "nom", "prenom", "date_naissance",
        "numero_permis", "obtention_B",
        "numero_immatriculation", "marque", "modele", "puissance_fiscale", "type_cg",
        "n_conflits", "taux_utilisabilite",
    ]
    rename_map = {
        "_dossier": "Dossier", "profil_type": "Type", "nom": "Nom", "prenom": "Prénom",
        "date_naissance": "Naissance", "numero_permis": "N° permis",
        "obtention_B": "Obtention B",
        "numero_immatriculation": "Immatriculation", "marque": "Marque",
        "modele": "Modèle", "puissance_fiscale": "CV fisc.", "type_cg": "CG",
        "n_conflits": "Conflits", "taux_utilisabilite": "Taux (%)",
    }
    st.dataframe(
        df[display_cols].rename(columns=rename_map),
        use_container_width=True, hide_index=True,
    )

    st.subheader("Détail d'un profil")
    dossier_sel = st.selectbox("Choisir un dossier", df["_dossier"].tolist())
    if dossier_sel:
        row = df[df["_dossier"] == dossier_sel].iloc[0]

        taux = row["taux_utilisabilite"]
        couleur = "#00CC96" if taux == 100 else ("#FFA15A" if taux >= 50 else "#EF553B")
        st.markdown(
            f"**Taux d'utilisabilité : <span style='color:{couleur}'>{taux:.1f}%</span>**"
            + (" ✅" if taux == 100 else f" — champs manquants : *{row['champs_manquants']}*"),
            unsafe_allow_html=True,
        )

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.markdown("**Identité**")
            st.write(f"Nom : {row['nom'] or '—'}")
            st.write(f"Prénom : {row['prenom'] or '—'}")
            st.write(f"Naissance : {row['date_naissance'] or '—'}")
            st.write(f"Sexe : {row['sexe'] or '—'}")

        with col_b:
            st.markdown("**Permis**")
            st.write(f"N° : {row['numero_permis'] or '—'}")
            st.write(f"Pays : {row['pays_permis'] or '—'}")
            st.write(f"Expiration : {row['date_expiration_permis'] or '—'}")
            st.write(f"Obtention B : {row['obtention_B'] or '—'}")

        with col_c:
            st.markdown("**Véhicule**")
            st.write(f"Immat. : {row['numero_immatriculation'] or '—'}")
            st.write(f"VIN : {row['vin'] or '—'}")
            st.write(f"Marque : {row['marque'] or '—'}")
            st.write(f"Modèle : {row['modele'] or '—'}")
            st.write(f"CV fiscaux : {row['puissance_fiscale'] or '—'}")
            st.write(f"Type CG : {row['type_cg'] or '—'}")

        if row["n_conflits"] > 0:
            st.markdown(f"**{row['n_conflits']} conflit(s) détecté(s)**")
            profil_path = OUTPUT_DIR / dossier_sel / row["_fichier"]
            raw = json.loads(profil_path.read_text(encoding="utf-8"))
            for c in raw.get("_conflits", []):
                badge = "🔴" if c.get("type") == "majeur" else ("🟡" if c.get("type") == "mineur" else "🔵")
                st.write(f"{badge} **{c.get('champ')}** — {c.get('type')} | décision : `{c.get('decision')}` | sim : {c.get('similitude', '—')}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Dashboard OCR — Permis, CG & Profils",
        page_icon="🪪",
        layout="wide",
    )
    st.title("🪪 Dashboard OCR — Permis de conduire, Cartes grises & Profils")
    st.caption(f"Dossier analysé : `{OUTPUT_DIR}`")

    records = load_data()
    df_null, df_type_null, df_usable, df_scores, df_conf, df_pairs, df_inconnus, df_cg = compute_frames(records)

    profiles = load_profiles()
    df_profils, df_conflits = compute_profile_frames(profiles)

    n_permis = sum(1 for r in records if r.get("type") not in CG_TYPES and r.get("type") != "inconnu")
    n_cg = sum(1 for r in records if r.get("type") in CG_TYPES)
    n_profils = len(profiles)

    pages = {
        "Vue d'ensemble": lambda: page_overview(records),
        f"Profils ({n_profils})": lambda: page_profiles_overview(profiles, df_profils, df_conflits),
        f"Conflits de fusion": lambda: page_profiles_conflicts(df_conflits, df_profils),
        f"Explorateur de profils": lambda: page_profiles_browser(df_profils),
        f"Cartes grises ({n_cg})": lambda: page_cartes_grises(df_cg),
        "Champs null": lambda: page_null_fields(df_null, df_type_null),
        "Utilisabilité": lambda: page_usability(df_usable),
        "Scores OCR": lambda: page_ocr_confidence(df_scores, df_conf),
        "Documents inconnus": lambda: page_inconnus(df_inconnus),
        f"Cohérence recto/verso ({n_permis} permis)": lambda: page_recto_verso(df_pairs),
    }

    with st.sidebar:
        st.header("Navigation")
        st.markdown("**Profils unifiés**")
        choice = st.radio("Page", list(pages.keys()), label_visibility="collapsed")
        st.divider()
        if st.button("🔄 Rafraîchir les données"):
            st.rerun()
        st.caption(
            f"{len(records)} documents · {n_cg} CG\n\n"
            f"{n_profils} profil(s) · "
            f"{int(df_profils['utilisable'].sum()) if not df_profils.empty else 0} utilisable(s)"
        )

    pages[choice]()


if __name__ == "__main__":
    main()
