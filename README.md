# RegWatch — Veille Réglementaire Decathlon

PoC de plateforme de veille et classification réglementaire pilotée par agents IA.

## Architecture
- **Agent 3** (actif) — Classificateur réglementaire produits
- **Agent 1** (Phase 2) — Veille réglementaire multi-sources
- **Agent 4** (Phase 3) — Analyse d'impact

## Stack
- Python + Streamlit (interface)
- Gemini 1.5 Pro (moteur IA)
- Déployé sur Streamlit Cloud (gratuit)

## Lancer en local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déployer sur Streamlit Cloud
1. Pusher ce dépôt sur GitHub
2. Connecter sur share.streamlit.io
3. Renseigner la clé API dans les Secrets

## Configuration clé API
Dans Streamlit Cloud > Settings > Secrets :
```toml
GEMINI_API_KEY = "AIza..."
```
