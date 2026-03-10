"""
Page 7 — Agent 5A : Legal Sheet Updater
Upload PDF fiche légale → analyse → workflow approbation/édition/rejet → export.
"""

import streamlit as st
import json
import re
from datetime import datetime
from pathlib import Path
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent5a.updater import (
    analyze_legal_sheet, FICHE_SECTIONS, STATUS_LABELS, SECTION_IDS
)
from agent4.impact import CAT_DEFINITIONS

st.set_page_config(page_title="Agent 5A — Fiche légale", page_icon="📋", layout="wide")

CAT_LABELS = {k: v["label"] for k, v in CAT_DEFINITIONS.items()}
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Statut")
    st.success("Anthropic ✓") if anthropic_key else st.error("ANTHROPIC_API_KEY manquante")
    st.divider()
    veille = st.session_state.get("veille_results", [])
    st.header("📡 Alertes disponibles")
    if veille:
        st.success(f"{len(veille)} alerte(s) en mémoire")
    else:
        st.warning("Aucune alerte.\nLancez l'Agent 1 d'abord.")
    st.divider()
    st.caption("Workflow : upload fiche → analyse → approuver / éditer / rejeter → exporter")

# ── Page principale ───────────────────────────────────────────────────────────
st.title("📋 Agent 5A — Legal Sheet Updater")
st.caption("Analyse et mise à jour des fiches légales · My Conformity Box")

# ── Étape 1 — Paramètres ─────────────────────────────────────────────────────
st.subheader("① Paramètres")

col1, col2, col3 = st.columns(3)
with col1:
    category = st.selectbox(
        "Catégorie",
        options=list(CAT_DEFINITIONS.keys()),
        format_func=lambda c: f"{c} — {CAT_LABELS[c]}",
        key="5a_category"
    )
with col2:
    market = st.selectbox(
        "Marché",
        ["Europe", "France", "Spain", "Italy", "Germany", "UK", "USA"],
        key="5a_market"
    )
with col3:
    urgency_filter = st.multiselect(
        "Alertes à inclure",
        ["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM"],
        key="5a_urgency"
    )

# Alertes filtrées par catégorie + urgence
veille = st.session_state.get("veille_results", [])
filtered_alerts = [
    e for e in veille
    if e.get("urgency") in urgency_filter
    and (category in e.get("categories_concerned", []) or not e.get("categories_concerned"))
]
st.caption(f"→ **{len(filtered_alerts)} alerte(s)** applicables pour {category} / {market}")

st.divider()

# ── Étape 2 — Upload ou saisie de la fiche ───────────────────────────────────
st.subheader("② Fiche légale actuelle")

input_mode = st.radio(
    "Source de la fiche",
    ["📄 Upload PDF", "📝 Coller le texte"],
    horizontal=True,
    key="5a_input_mode"
)

fiche_text = ""
fiche_title = ""

if input_mode == "📄 Upload PDF":
    uploaded_pdf = st.file_uploader(
        "Choisir la fiche légale (PDF)",
        type=["pdf"],
        key="5a_pdf_upload"
    )
    if uploaded_pdf:
        # Extraction texte du PDF via PyPDF2 (disponible dans requirements)
        try:
            import io
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(uploaded_pdf.read()))
            fiche_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            fiche_title = uploaded_pdf.name.replace(".pdf", "").replace("_", " ")
            st.success(f"✓ PDF lu — {len(reader.pages)} page(s) · {len(fiche_text):,} caractères")
            with st.expander("Aperçu du texte extrait"):
                st.text(fiche_text[:2000] + ("..." if len(fiche_text) > 2000 else ""))
        except Exception as e:
            st.error(f"Erreur lecture PDF : {e}")
            st.info("Essayez le mode 'Coller le texte' comme alternative.")

else:
    fiche_title = st.text_input(
        "Titre de la fiche",
        placeholder="ex: Electronic equipment using bluetooth — EUROPE",
        key="5a_title"
    )
    fiche_text = st.text_area(
        "Contenu de la fiche (copier-coller depuis le PDF)",
        height=300,
        placeholder="Collez ici le contenu de votre fiche légale...",
        key="5a_text"
    )
    if fiche_text:
        st.caption(f"{len(fiche_text):,} caractères")

st.divider()

# ── Étape 3 — Lancement analyse ───────────────────────────────────────────────
st.subheader("③ Analyse")

ready = anthropic_key and fiche_text.strip() and bool(filtered_alerts or True)
# Note: on autorise l'analyse même sans alertes (audit pur de la fiche)

if not fiche_text.strip():
    st.info("Uploadez ou collez le contenu de la fiche légale pour continuer.")

col_launch, col_info = st.columns([2, 3])
with col_info:
    if not filtered_alerts:
        st.warning(f"Aucune alerte {category} en mémoire — l'analyse portera uniquement sur la qualité de la fiche existante.")
    else:
        st.info(f"{len(filtered_alerts)} alerte(s) seront croisées avec la fiche.")

with col_launch:
    launch = st.button(
        "🔍 Analyser la fiche",
        disabled=not (anthropic_key and fiche_text.strip()),
        type="primary",
        use_container_width=True
    )

if launch:
    with st.status("🔍 Analyse en cours...", expanded=True) as status:
        try:
            chars = len(fiche_text)
            st.write(f"📄 Texte extrait : {chars:,} caractères")
            if chars > 12000:
                st.write(f"⚠️ Texte tronqué à 12 000 caractères pour l'analyse (taille optimale)")
            st.write(f"🔀 Croisement avec {len(filtered_alerts)} alerte(s) · {category} / {market}...")

            result, token_usage = analyze_legal_sheet(
                anthropic_key=anthropic_key,
                fiche_text=fiche_text,
                alerts=filtered_alerts,
                category=category,
                fiche_title=fiche_title,
                market=market,
            )
            st.session_state["5a_result"] = result
            st.session_state["5a_decisions"] = {}  # reset décisions
            sections = result.get("sections", [])
            n_update = sum(1 for s in sections if s.get("status") in ["MISSING","ENRICH","OBSOLETE"])
            n_ok     = sum(1 for s in sections if s.get("status") in ["OK","NA_OK"])
            # Mettre à jour les compteurs dans le résultat
            result["sections_to_update"] = n_update
            result["sections_ok"] = n_ok
            status.update(
                label=f"✅ Analyse terminée · {n_update} section(s) à mettre à jour · "
                      f"{n_ok} à jour · "
                      f"{token_usage['input_tokens']+token_usage['output_tokens']:,} tokens · "
                      f"${token_usage['cost_usd']:.4f}",
                state="complete"
            )
        except ValueError as e:
            # Erreur JSON ou réponse vide — afficher le détail
            status.update(label=f"❌ Erreur d'analyse : {e}", state="error")
            st.error(str(e))
            st.info("💡 Conseil : essayez avec un texte plus court (mode 'Coller le texte' avec les sections les plus importantes) ou relancez l'analyse.")
            st.stop()
        except Exception as e:
            status.update(label=f"❌ Erreur : {e}", state="error")
            st.error(str(e))
            st.stop()

# ── Étape 4 — Workflow validation ────────────────────────────────────────────
if "5a_result" in st.session_state:
    result   = st.session_state["5a_result"]
    sections = result.get("sections", [])
    decisions = st.session_state.setdefault("5a_decisions", {})

    st.divider()
    st.subheader("④ Révision et validation")

    # Récapitulatif
    overall = result.get("overall_status", "")
    overall_icons = {"MAJOR_UPDATE": "🔴", "MINOR_UPDATE": "🟡", "UP_TO_DATE": "✅"}
    overall_labels = {
        "MAJOR_UPDATE": "Mise à jour majeure requise",
        "MINOR_UPDATE": "Enrichissement mineur recommandé",
        "UP_TO_DATE": "Fiche à jour"
    }

    m1, m2, m3, m4 = st.columns(4)
    sections_by_status = {}
    for s in sections:
        sections_by_status.setdefault(s.get("status",""), []).append(s)

    m1.metric("Statut global",
              f"{overall_icons.get(overall,'?')} {overall_labels.get(overall, overall)}")
    m2.metric("✅ À jour",   len(sections_by_status.get("OK", [])) + len(sections_by_status.get("NA_OK", [])))
    m3.metric("⚠️ À mettre à jour",
              len(sections_by_status.get("MISSING", [])) +
              len(sections_by_status.get("ENRICH", [])) +
              len(sections_by_status.get("OBSOLETE", [])))
    m4.metric("Validées",
              sum(1 for d in decisions.values() if d["action"] in ["approved", "edited"]))

    if result.get("summary"):
        st.info(result["summary"])

    # Spécificités nationales manquantes
    natl = result.get("national_specificities_missing", [])
    if natl:
        with st.expander(f"🌍 {len(natl)} spécificité(s) nationale(s) manquante(s)", expanded=True):
            for n in natl:
                st.warning(f"**{n.get('country','')}** — {n.get('missing_content','')} "
                           f"*(section : {n.get('section_id','')})*")

    st.divider()

    # Filtres d'affichage
    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        show_status = st.multiselect(
            "Afficher les statuts",
            ["MISSING", "ENRICH", "OBSOLETE", "OK", "NA_OK"],
            default=["MISSING", "ENRICH", "OBSOLETE"],
            key="5a_filter_status"
        )
    with col_f2:
        show_priority = st.multiselect(
            "Priorité",
            ["HIGH", "MEDIUM", "LOW", "NONE"],
            default=["HIGH", "MEDIUM", "LOW"],
            key="5a_filter_priority"
        )

    # Boutons globaux
    col_all1, col_all2, _ = st.columns([1, 1, 2])
    sections_to_act = [
        s for s in sections
        if s.get("status") in show_status
        and s.get("priority") in show_priority
        and s.get("proposed_update")
    ]
    if col_all1.button("✅ Tout approuver", key="approve_all"):
        for s in sections_to_act:
            sid = s["section_id"]
            decisions[sid] = {
                "action": "approved",
                "final_text": s.get("proposed_update", ""),
                "section_label": s.get("section_label", "")
            }
        st.rerun()
    if col_all2.button("❌ Tout rejeter", key="reject_all"):
        for s in sections_to_act:
            sid = s["section_id"]
            decisions[sid] = {
                "action": "rejected",
                "final_text": "",
                "section_label": s.get("section_label", "")
            }
        st.rerun()

    # Sections
    for sec in sections:
        status_code = sec.get("status", "OK")
        priority    = sec.get("priority", "NONE")

        if status_code not in show_status:
            continue
        if priority not in show_priority:
            continue

        sid         = sec.get("section_id", "")
        s_icon, s_label = STATUS_LABELS.get(status_code, ("?", ""))
        p_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "NONE": "⚪"}.get(priority, "")
        decision    = decisions.get(sid, {})
        action      = decision.get("action", "pending")

        # Couleur du header selon décision
        action_badge = {
            "approved": "✅ Approuvée",
            "edited":   "✏️ Éditée",
            "rejected": "❌ Rejetée",
            "pending":  "⏳ En attente"
        }.get(action, "")

        with st.expander(
            f"{s_icon} {sec.get('section_label','?')}  {p_icon}  —  {action_badge}",
            expanded=(action == "pending" and status_code in ["MISSING","OBSOLETE","ENRICH"])
        ):
            # Contenu actuel
            if sec.get("current_content_summary"):
                st.markdown("**Contenu actuel**")
                st.caption(sec["current_content_summary"])

            # Raison de la mise à jour
            if sec.get("update_reason"):
                st.markdown(f"**Pourquoi mettre à jour** : {sec['update_reason']}")
                if sec.get("alert_reference"):
                    st.caption(f"Alerte source : *{sec['alert_reference']}*")

            # Proposition IA — éditable
            if sec.get("proposed_update"):
                st.markdown("**Proposition IA** *(éditable)*")
                edited_text = st.text_area(
                    "Texte proposé",
                    value=decision.get("final_text", sec["proposed_update"]),
                    height=180,
                    key=f"edit_{sid}",
                    label_visibility="collapsed"
                )

                col_a, col_e, col_r = st.columns(3)
                if col_a.button("✅ Approuver", key=f"approve_{sid}"):
                    decisions[sid] = {
                        "action": "approved",
                        "final_text": edited_text,
                        "section_label": sec.get("section_label","")
                    }
                    st.rerun()
                if col_e.button("✏️ Approuver (édité)", key=f"edit_approve_{sid}"):
                    original = sec.get("proposed_update","")
                    decisions[sid] = {
                        "action": "edited" if edited_text != original else "approved",
                        "final_text": edited_text,
                        "section_label": sec.get("section_label","")
                    }
                    st.rerun()
                if col_r.button("❌ Rejeter", key=f"reject_{sid}"):
                    decisions[sid] = {
                        "action": "rejected",
                        "final_text": "",
                        "section_label": sec.get("section_label","")
                    }
                    st.rerun()
            else:
                st.success("Section couverte — aucune modification nécessaire.")

    # ── Étape 5 — Export ─────────────────────────────────────────────────────
    approved = {k: v for k, v in decisions.items() if v["action"] in ["approved", "edited"]}
    rejected = {k: v for k, v in decisions.items() if v["action"] == "rejected"}
    pending  = [s for s in sections
                if s.get("status") in ["MISSING","ENRICH","OBSOLETE"]
                and s.get("section_id") not in decisions]

    st.divider()
    st.subheader("⑤ Export")

    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("✅ Approuvées", len(approved))
    col_s2.metric("❌ Rejetées",   len(rejected))
    col_s3.metric("⏳ En attente", len(pending))

    if pending:
        st.warning(f"{len(pending)} section(s) non encore traitée(s).")

    if approved:
        # Export rapport de mise à jour
        rapport_lines = [
            f"# Rapport de mise à jour — {fiche_title or category}",
            f"**Marché** : {market}  |  **Catégorie** : {category}",
            f"**Date** : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"**Sections approuvées** : {len(approved)}  |  "
            f"**Rejetées** : {len(rejected)}  |  **En attente** : {len(pending)}",
            "",
            "---",
            ""
        ]
        for sid, dec in approved.items():
            action_label = "✏️ Éditée par le responsable" if dec["action"] == "edited" else "✅ Approuvée telle quelle"
            rapport_lines += [
                f"## {dec.get('section_label', sid)}",
                f"*{action_label}*",
                "",
                dec["final_text"],
                "",
                "---",
                ""
            ]

        rapport_md = "\n".join(rapport_lines)

        col_dl1, col_dl2 = st.columns(2)
        col_dl1.download_button(
            "⬇️ Exporter rapport Markdown",
            rapport_md.encode("utf-8"),
            f"regwatch_fiche_{category}_{market}_{datetime.now().strftime('%Y%m%d')}.md",
            "text/markdown"
        )

        # Export JSON complet
        export_json = {
            "category": category,
            "market": market,
            "fiche_title": fiche_title,
            "analysis_date": result.get("analysis_date",""),
            "export_date": datetime.now().isoformat(),
            "approved_updates": [
                {"section_id": sid, "section_label": dec["section_label"],
                 "action": dec["action"], "final_text": dec["final_text"]}
                for sid, dec in approved.items()
            ],
            "rejected": list(rejected.keys()),
            "pending": [s["section_id"] for s in pending]
        }
        col_dl2.download_button(
            "⬇️ Exporter JSON (intégration)",
            json.dumps(export_json, indent=2, ensure_ascii=False).encode("utf-8"),
            f"regwatch_fiche_{category}_{market}_{datetime.now().strftime('%Y%m%d')}.json",
            "application/json"
        )

        st.info("💾 Le rapport validé peut être transmis à votre système de gestion documentaire.")
    else:
        st.info("Approuvez au moins une section pour activer l'export.")
