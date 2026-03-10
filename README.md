# RegWatch — Veille Réglementaire Decathlon Electronics

Plateforme de veille et classification réglementaire pilotée par agents IA.
Déployée sur [regwatch.streamlit.app](https://regwatch.streamlit.app)

---

## Architecture — 6 agents

| Agent | Statut | Rôle |
|---|---|---|
| Agent 1 — Regulatory Watcher | ✅ Actif | Surveille les sources officielles (Tavily + Jina.ai), multi-sujets, pré-remplissage par catégorie, historique persistant |
| Agent 2 — Product Profiler | ✅ Actif | Extrait les specs produit depuis le web par code modèle |
| Agent 3 — Regulatory Classifier | ✅ Actif | Classifie les produits selon le référentiel Decathlon (CAT1-CAT9) |
| Agent 4 — Impact Analyzer | ✅ Actif | Croise veille × catalogue (Mode Produit → Agent 5B) ou × catégories (Mode Catégorie → Agent 5A) |
| Agent 5A — Legal Sheet Updater | ✅ Actif | Analyse et propose des mises à jour des fiches légales "My Conformity Box" par catégorie |
| Agent 5B — Risk Mapper | ✅ Actif | Génère le risk mapping produit avec comparaison avant/après mise à jour 5A |

---

## Stack technique

| Besoin | Outil |
|---|---|
| Interface | Python + Streamlit (Streamlit Cloud) |
| Moteur IA | Claude Haiku (Agents 1-4) · Claude Sonnet (Agent 5A) |
| Recherche réglementaire | Tavily API |
| Lecture PDF / sites dynamiques | Jina.ai reader (r.jina.ai) · PyPDF2 |
| Versioning | GitHub (Ju2222022/regwatch) |

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
├── agent4/
│   └── impact.py                   ← Impact Analyzer (Mode Produit + Mode Catégorie)
├── agent5a/
│   └── updater.py                  ← Legal Sheet Updater — analyse + workflow validation
├── data/
│   ├── sources.json                ← Domaines surveillés par marché (configurable via UI)
│   └── watch_history.json          ← Historique des veilles (persistance PoC)
├── pages/
│   ├── 1_Agent3_Classificateur.py
│   ├── 2_Concordance.py
│   ├── 3_Agent2_Profiler.py
│   ├── 4_Agent1_Veille.py
│   ├── 5_Configuration.py          ← Gestion des sources de veille par marché
│   ├── 6_Agent4_Impact.py          ← Impact Analyzer UI
│   └── 7_Agent5A_Fiche.py          ← Legal Sheet Updater UI
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

**Pré-remplissage par catégorie** : l'utilisateur sélectionne ses catégories actives, l'agent génère automatiquement les requêtes de veille correspondantes.

**Criticité :**
- 🔴 HIGH — texte en vigueur ou échéance < 6 mois
- 🟡 MEDIUM — échéance 6-18 mois
- 🟢 LOW — consultation ou échéance > 18 mois

---

## Agent 2 — Product Profiler

Extrait automatiquement les spécifications techniques d'un produit à partir de son code modèle.

1. L'utilisateur saisit un **code modèle** (ex: *8595153 Kalenji Run 500 GPS*)
2. **Tavily** recherche les fiches produit sur le web (site Decathlon, revendeurs, bases techniques)
3. **Claude Haiku** extrait et structure les specs pertinentes pour la classification réglementaire :
   - Type de produit et fonction principale
   - Protocoles de communication (Bluetooth, ANT+, GPS, WiFi...)
   - Présence de batterie intégrée / rechargeable
   - Caractéristiques électriques
4. Le profil produit enrichit la classification Agent 3 et peut être transmis à Agent 4

> Sans Agent 2, la concordance Agent 3 est de ~27% (nom + type uniquement). Avec Agent 2, elle monte à ~70%+.

---

## Agent 3 — Regulatory Classifier

Classifie un produit dans le référentiel Decathlon Electronics (CAT1-CAT9) à partir de sa description ou du profil Agent 2.

**Règles de classification :**
- Chaque produit reçoit **CAT3 par défaut** (parachute universel — tout équipement électronique)
- Les sous-catégories s'ajoutent uniquement si le protocole est **explicitement confirmé** dans le profil produit
- Plusieurs catégories peuvent s'appliquer simultanément (ex: CAT3 + CAT9 pour une montre Bluetooth)

**Exemple :**
```
Produit : Montre GPS Bluetooth avec capteur cardiaque
→ CAT3 (équipement électronique)        ← toujours
→ CAT7 (GPS confirmé)                   ← protocole détecté
→ CAT9 (Bluetooth confirmé)             ← protocole détecté
```

**Page Concordance** : compare la classification IA avec la classification manuelle Decathlon sur les 11 produits du PoC. Permet de valider la fiabilité du modèle avant déploiement.

---

## Agent 4 — Impact Analyzer

Croise les alertes Agent 1 avec le catalogue produits ou les catégories actives.

**Mode Produit** → identifie les produits du catalogue impactés → prépare le risk mapping pour Agent 5B.

**Mode Catégorie** → identifie les catégories impactées et le type de changement (NEW / UPDATE / DEADLINE / WITHDRAWAL) → prépare la mise à jour des fiches légales pour Agent 5A.

---

## Agent 5A — Legal Sheet Updater

Analyse une fiche légale "My Conformity Box" (upload PDF) et propose des mises à jour section par section, croisées avec les alertes réglementaires.

### Profils d'analyse

| Profil | Sections | Appels API | Coût ~estimé |
|---|---|---|---|
| ⚡ Veille rapide | ~8 (high uniquement) | 1 | ~$0.03 |
| 📋 Standard | ~16 (high + medium) | 2 | ~$0.05 |
| 🔍 Complet | ~25 (toutes) | 3 | ~$0.08 |
| ✏️ Personnalisé | au choix | variable | variable |

### Workflow de validation

```
IA analyse chaque section → statut par section
        ↓
Responsable réglementaire :
  ✅ Approuver  — texte IA tel quel
  ✏️ Éditer     — modifier le texte puis valider
  ❌ Rejeter
        ↓
Export Markdown + JSON avec métadonnées de traçabilité
(section, texte final, alerte source, raison, priorité, date)
```

### Spécificités Europe

La zone Europe couvre l'EEE par défaut. Une mention nationale n'est ajoutée que si un État membre a une exigence supplémentaire (ex: AGEC France, Décret espagnol recyclage).

---

## Agent 5B — Risk Mapper

Génère un risk mapping réglementaire par produit à partir des résultats Agent 4 (Mode Produit),
avec comparaison avant/après les mises à jour approuvées par Agent 5A.

**Flux :**
```
Agent 4 Mode Produit → session_state["impact_product_result"]
Agent 5A export JSON → session_state["5a_export_approved"] (optionnel)
        ↓
Agent 5B — risk mapping 3 niveaux
```

**3 niveaux de lecture (3 onglets) :**
- 📊 **Vue Exécutive** — tableau produits × niveau de risque, pour la direction
- 📦 **Vue Produit** — non-conformités + actions correctives + délais, pour les chefs de produit
- 📋 **Vue Réglementaire** — par réglementation, taux de conformité avant/après, pour le responsable réglementaire

**Comparaison avant/après :**
- AVANT = état actuel basé sur les alertes Agent 4
- APRÈS = simulation post-implémentation des mises à jour Agent 5A approuvées
- Clairement signalé comme simulation dans l'interface

**Export :** JSON complet + CSV synthétique (vue exécutive)

---

## Page Configuration

Gestion des sources de veille par marché. Édition par onglet, import/export `sources.json`.

---

## Roadmap

| Phase | Statut | Contenu |
|---|---|---|
| Phase 1 | ✅ Terminée | Agents 2 + 3 opérationnels, concordance validée |
| Phase 2 | ✅ Terminée | Agent 1 · Agent 4 · Page Configuration |
| Phase 3 | ✅ Terminée | Agent 5A (fiches légales) · Agent 5B (risk mapping) opérationnels |
| Phase 4 | 🔜 Planifiée | Présentation équipe · Go/No-Go · Google Sheets · Scheduling automatique |

---

## Notes PoC

- **Persistance** : `watch_history.json` local — réinitialisé à chaque redéploiement. Migration Google Sheets Phase 4.
- **Coût estimé** : ~$0.001/classification · ~$0.006/session veille · ~$0.05/analyse fiche (profil Standard)
- **Scheduling** : veille manuelle en PoC · automatisation GitHub Actions Phase 4
- **Sidebar** : affichage de code interne Streamlit connu — traitement lors de la revue design finale (Phase 4)
