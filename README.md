# RegWatch — Veille Réglementaire Decathlon Electronics

Plateforme de veille et classification réglementaire pilotée par agents IA.
Déployée sur [regwatch.streamlit.app](https://regwatch.streamlit.app)

---

## Architecture — 6 agents

| Agent | Statut | Rôle |
|---|---|---|
| Agent 1 — Regulatory Watcher | ✅ Actif | Surveille les sources officielles (Tavily + Jina.ai) |
| Agent 2 — Product Profiler | ✅ Actif | Extrait les specs produit depuis Decathlon.fr |
| Agent 3 — Regulatory Classifier | ✅ Actif | Classifie les produits selon le référentiel Decathlon |
| Agent 4 — Impact Analyzer | 🔜 Phase 2 | Croise veille × catalogue produits |
| Agent 5A — Legal Sheet Updater | 🔜 Phase 3 | Met à jour les fiches légales par catégorie |
| Agent 5B — Risk Mapper | 🔜 Phase 3 | Génère le risk mapping produit (mode audit) |

---

## Stack technique

| Besoin | Outil |
|---|---|
| Interface | Python + Streamlit (Streamlit Cloud) |
| Moteur IA | Claude Haiku (Anthropic API) |
| Recherche réglementaire | Tavily API |
| Lecture PDF / sites dynamiques | Jina.ai reader |
| Versioning | GitHub |

---

## Structure du projet

```
regwatch/
├── app.py                          ← Page d'accueil
├── agent1/
│   └── watcher.py                  ← Veille Tavily + Jina.ai
├── agent2/
│   └── profiler.py                 ← Profiler produit web
├── agent3/
│   └── classifier.py               ← Classificateur réglementaire
├── data/
│   └── sources.json                ← Domaines surveillés (configurable)
├── pages/
│   ├── 1_Agent3_Classificateur.py
│   ├── 2_Concordance.py
│   ├── 3_Agent2_Profiler.py
│   └── 4_Agent1_Veille.py
└── .streamlit/
    └── config.toml                 ← Thème Decathlon
```

---

## Secrets Streamlit requis

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
TAVILY_API_KEY    = "tvly-..."
```

---

## Résultats PoC — Agent 3 (Phase 1)

- **11 produits** testés sur le référentiel Decathlon Electronics
- **Concordance parfaite** : 6/11 (55%) avec prompt minimal (nom + type uniquement)
- **Zéro divergence totale** : 0/11
- **Recall parfait** : aucune catégorie manquante vs ground truth
- Avec Agent 2 (specs web) : concordance estimée 70%+

---

## Roadmap

- **Phase 1** ✅ — Agents 2 + 3 opérationnels, concordance validée
- **Phase 2** 🔜 — Agent 1 (veille) + Agent 4 (impact analyzer)
- **Phase 3** 🔜 — Agents 5A + 5B (fiches légales + risk mapping)
- **Phase 4** 🔜 — Présentation équipe + Go/No-Go déploiement
