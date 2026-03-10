# RegWatch — Veille Réglementaire Decathlon Electronics

Plateforme de veille et classification réglementaire pilotée par agents IA.
Déployée sur [regwatch.streamlit.app](https://regwatch.streamlit.app)

---

## Architecture — 6 agents

| Agent | Statut | Rôle |
|---|---|---|
| Agent 1 — Regulatory Watcher | ✅ Actif | Surveille les sources officielles (Tavily + Jina.ai), multi-sujets, historique persistant |
| Agent 2 — Product Profiler | ✅ Actif | Extrait les specs produit depuis le web par code modèle |
| Agent 3 — Regulatory Classifier | ✅ Actif | Classifie les produits selon le référentiel Decathlon (CAT1-CAT9) |
| Agent 4 — Impact Analyzer | 🔜 Phase 2 | Croise veille × catalogue produits via les catégories |
| Agent 5A — Legal Sheet Updater | 🔜 Phase 3 | Met à jour les fiches légales par catégorie |
| Agent 5B — Risk Mapper | 🔜 Phase 3 | Génère le risk mapping produit (mode audit) |

---

## Stack technique

| Besoin | Outil |
|---|---|
| Interface | Python + Streamlit (Streamlit Cloud) |
| Moteur IA | Claude Haiku (Anthropic API) |
| Recherche réglementaire | Tavily API |
| Lecture PDF / sites dynamiques | Jina.ai reader (r.jina.ai) |
| Versioning | GitHub |

---

## Structure du projet

```
regwatch/
├── app.py                          ← Page d'accueil
├── agent1/
│   └── watcher.py                  ← Veille Tavily + Jina.ai, compteur tokens
├── agent2/
│   └── profiler.py                 ← Profiler produit par code modèle
├── agent3/
│   └── classifier.py               ← Classificateur réglementaire CAT1-CAT9
├── data/
│   ├── sources.json                ← Domaines surveillés (configurable via UI)
│   └── watch_history.json          ← Historique des veilles (persistance PoC)
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

## Référentiel Decathlon Electronics (CAT1-CAT9)

| Code | Catégorie | Logique |
|---|---|---|
| CAT1 | Batteries & accumulateurs | Uniquement si le produit EST une batterie |
| CAT2 | Lampes & éclairage | Fonction primaire = éclairage |
| CAT3 | Équipements électroniques | Parachute universel — tout produit électronique |
| CAT4 | Chargeurs & produits rechargeables | Inclut USB-C, chargeur solaire |
| CAT5 | Caméra / ANT+ | Protocole ANT+ explicitement confirmé |
| CAT6 | Lecteur MP3 | Fonction audio principale |
| CAT7 | GPS / Radio / Talkie / Télémètre | Protocole confirmé |
| CAT8 | Téléphone / Wifi / GSM | Wifi ou cellulaire confirmé |
| CAT9 | Équipement Bluetooth | Bluetooth explicitement confirmé |

> **Règle parachute** : CAT3 est assigné à tout produit électronique. Les sous-catégories (CAT5-CAT9) s'ajoutent uniquement si le protocole est explicitement confirmé.

---

## Agent 1 — Fonctionnement

1. L'utilisateur définit un ou plusieurs **sujets de veille** (ex: *EN 18031 cybersecurity radio equipment EU*)
2. **Tavily** recherche sur les domaines officiels configurés (EUR-Lex, Legifrance, CENELEC...)
3. **Jina.ai** enrichit les résultats prioritaires (PDFs, sites dynamiques EUR-Lex)
4. **Claude Haiku** extrait les entrées réglementaires structurées et les tague CAT1-CAT9
5. Les résultats sont affichés par criticité ou par thématique, exportables en CSV
6. L'historique est persisté dans `data/watch_history.json`

**Criticité :**
- 🔴 HIGH — texte en vigueur ou échéance < 6 mois
- 🟡 MEDIUM — échéance 6-18 mois
- 🟢 LOW — consultation ou échéance > 18 mois

> Les actions suggérées sont générées par IA et doivent être validées par le responsable réglementaire.

---

## Résultats PoC — Agent 3 (Phase 1)

- **11 produits** testés sur le référentiel Decathlon Electronics
- **Concordance** : 3/11 (27%) avec nom + type uniquement — 6/11 (55%) avec description enrichie
- **Zéro divergence totale** sur l'ensemble des tests
- Avec Agent 2 (specs web) : concordance estimée 70%+

---

## Roadmap

| Phase | Statut | Contenu |
|---|---|---|
| Phase 1 | ✅ Terminée | Agents 2 + 3 opérationnels, concordance validée |
| Phase 2 | 🔄 En cours | Agent 1 (veille) opérationnel · Agent 4 (impact analyzer) à venir |
| Phase 3 | 🔜 Planifiée | Agents 5A (fiches légales) + 5B (risk mapping) |
| Phase 4 | 🔜 Planifiée | Présentation équipe · Go/No-Go déploiement · Google Sheets persistance |

---

## Notes PoC

- **Persistance** : l'historique `watch_history.json` est local — réinitialisé à chaque redéploiement GitHub. Migration Google Sheets prévue en Phase 4.
- **Coût estimé** : ~$0.001 par classification · ~$0.006 par session de veille (3 sujets) · $5 de crédit ≈ 4000 classifications
- **Scheduling** : veille manuelle en PoC · automatisation GitHub Actions prévue en Phase 4
