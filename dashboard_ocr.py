"""
Dashboard Streamlit — Analyse statistique des résultats OCR permis de conduire.
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

CHAMPS_PAR_TYPE = {
    "permis_dz_nouveau_recto": ["nom", "prenom", "date_naissance", "date_expiration", "numero_permis"],
    "permis_dz_nouveau_verso": ["nom", "prenom", "sexe", "date_naissance", "date_expiration", "numero_permis"],
    "permis_fr_nouveau_recto": ["nom", "prenom", "date_naissance", "date_expiration", "numero_permis"],
    "permis_fr_nouveau_verso": ["obtention_B"],
}

RECTO_TYPES = {"permis_dz_nouveau_recto", "permis_fr_nouveau_recto"}
VERSO_TYPES = {"permis_dz_nouveau_verso", "permis_fr_nouveau_verso"}

COLORS = px.colors.qualitative.Set2

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
    df_null = pd.DataFrame(null_rows).sort_values("pct_null", ascending=False)

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

    # ── 3. Utilisabilité (tous champs attendus non-null)
    usable_rows = []
    for r in structured:
        doc_type = r.get("type", "")
        champs = CHAMPS_PAR_TYPE.get(doc_type, [])
        manquants = [c for c in champs if is_null(r.get(c))]
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

    # ── 5. Confiance vs null (corrélation score moyen ↔ champs null)
    conf_rows = []
    for r in structured:
        doc_type = r.get("type", "")
        champs = CHAMPS_PAR_TYPE.get(doc_type, [])
        n_null = sum(1 for c in champs if is_null(r.get(c)))
        conf_rows.append({
            "fichier": r["_fichier"],
            "type": doc_type,
            "score_moyen": r["_score_mean"],
            "n_null": n_null,
            "utilisable": n_null == 0,
        })
    df_conf = pd.DataFrame(conf_rows).dropna(subset=["score_moyen"])

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
        if any(k in text_join for k in ["REPUBLIQUE ALGER", "DZ", "ALGERIE"]):
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

    return df_null, df_type_null, df_usable, df_scores, df_conf, df_pairs, df_inconnus


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


# ─── Page renderers ───────────────────────────────────────────────────────────

def page_overview(records):
    st.header("Vue d'ensemble")

    total = len(records)
    structured = [r for r in records if r.get("type") != "inconnu"]
    inconnus = [r for r in records if r.get("type") == "inconnu"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Documents analysés", total)
    c2.metric("Documents structurés", len(structured))
    c3.metric("Documents inconnus", len(inconnus), delta=f"{len(inconnus)/total*100:.0f}%", delta_color="inverse")

    type_counts = defaultdict(int)
    for r in records:
        type_counts[r.get("type", "inconnu")] += 1
    df_types = pd.DataFrame([{"type": k, "count": v} for k, v in type_counts.items()])

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(df_types, names="type", values="count", title="Répartition par type",
                     color_discrete_sequence=COLORS)
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Dashboard OCR Permis",
        page_icon="🪪",
        layout="wide",
    )
    st.title("🪪 Dashboard OCR — Permis de conduire")
    st.caption(f"Dossier analysé : `{OUTPUT_DIR}`")

    records = load_data()
    df_null, df_type_null, df_usable, df_scores, df_conf, df_pairs, df_inconnus = compute_frames(records)

    pages = {
        "Vue d'ensemble": lambda: page_overview(records),
        "Champs null": lambda: page_null_fields(df_null, df_type_null),
        "Utilisabilité": lambda: page_usability(df_usable),
        "Scores OCR": lambda: page_ocr_confidence(df_scores, df_conf),
        "Documents inconnus": lambda: page_inconnus(df_inconnus),
        "Cohérence recto/verso": lambda: page_recto_verso(df_pairs),
    }

    with st.sidebar:
        st.header("Navigation")
        choice = st.radio("Page", list(pages.keys()))
        st.divider()
        if st.button("🔄 Rafraîchir les données"):
            st.rerun()
        st.caption(f"{len(records)} fichiers chargés")

    pages[choice]()


if __name__ == "__main__":
    main()
