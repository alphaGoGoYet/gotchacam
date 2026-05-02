# Plan de déploiement public

Plan d'action pour faire passer `gotchacam` du statut "script Python perso sur 2 Macs" à projet open source publié, avec monétisation potentielle via GitHub Sponsors. Pensé pour un effort minimal, sans création de société, en gardant la souplesse de monter en puissance plus tard.

## Stratégie générale

**Approche choisie** : *crawl → walk → run*. On déroule par phases, chacune testant l'eau avant d'engager la suivante. À chaque palier, on évalue si ça vaut le coup de continuer.

**Objectif réaliste an 1** : 50-2000 stars GitHub, 0-30 sponsors, 0-300 €/an de dons. Aucune société créée. Bénéfice annexe assuré quoi qu'il arrive : une vitrine pro pour ton CV.

**Objectif optimiste an 2-3** : 5000+ stars, 50+ sponsors, 1-3 K€/an. Bascule en micro-entrepreneur si le seuil est dépassé.

## Les 3 angles différenciants à garder en tête

C'est ce qui doit ressortir partout (README, post Reddit, billet de blog) — ce qui rend `gotchacam` reconnaissable parmi les concurrents (Alfred, Kasa, Frigate) :

1. **Alarme avec ta voix en boucle** — gimmick mémorable. Personne d'autre ne le fait. À partager en démo vidéo : "écoute mon enregistrement transformé en pitch -25% qui hurle dans mon salon"
2. **Interface 100% Telegram** — pas d'app à installer pour l'utilisateur, tout depuis sa conversation Telegram habituelle
3. **Self-hosted, zéro cloud, zéro abonnement** — tes images n'atterrissent jamais sur un serveur tiers (sauf Telegram qui transite, modifiable)

Slogan-direction (à ne pas mettre tel quel mais à inspirer) :
> *"La caméra de surveillance qui ne te trahit pas — tes images restent chez toi, et tu peux gueuler dans ton appart à un cambrioleur depuis le métro."*

## Phase 0 — Préparer le projet pour publication (1 weekend)

État actuel : projet fonctionnel sur 2 Macs, code propre, 5 docs (`README.md`, `AUTOSTART.md`, `ANDROID_PORT.md`, `WINDOWS_PORT.md`, `PACKAGING.md`).

À faire avant publication :

### Polish minimum

- [x] ~Choisir un nom~ → **`gotchacam`** validé (ref: gotcha = "je t'ai eu", aligné avec l'alarme dissuasive)
- [ ] Vérifier la dispo du nom : repo GitHub libre, package PyPI libre, domaine `.com` libre (rapide check)
- [ ] **LICENSE** : choisir entre MIT (permissif, max diffusion) et AGPLv3 (copyleft fort, empêche un concurrent de héberger ton code en SaaS). **Recommandation : MIT** pour ce projet (max adoption, pas un risque commercial)
- [ ] Ajouter un fichier `LICENSE` à la racine
- [ ] Ajouter un `CONTRIBUTING.md` simple (comment proposer une PR, lancer les tests)
- [ ] Ajouter un `CODE_OF_CONDUCT.md` (template Contributor Covenant)

### README orienté pitch

Le README actuel est un manuel d'installation. Pour la publication, il doit aussi **vendre** en 30 secondes. Restructure :

```markdown
# cam — surveillance maison anti-intrusion, 100% chez toi

> [Tagline accrocheuse en 1 ligne]

[GIF animé : photo qui arrive sur Telegram en réaction à un mouvement] ← capital
[GIF animé : alarme avec voix grave qui se déclenche] ← capital

## Pourquoi cam est différent
- 🔒 **Aucun cloud** — tes images ne transitent jamais par un serveur tiers
- 🗣️ **Alarme dissuasive avec ta voix** — enregistre ton message, l'app le diffuse en boucle au volume max, en pitch grave
- 💬 **Tout via Telegram** — aucune app à installer, contrôle depuis n'importe où
- 💰 **Gratuit, open source, pas d'abonnement** — utilise ton vieux Mac/PC qui dort

## Installation
[reprend ton README actuel ici]
```

- [ ] **Enregistrer un GIF de démo** (Kap, GIPHY Capture, ou QuickTime → conversion ffmpeg). 5-10 secondes max, 800px max, < 5 MB
- [ ] Ajouter 2-3 **badges en haut** : License MIT, Made for macOS, Stars (GitHub Actions le génère gratuitement)

### Sécurité avant push

- [ ] Vérifier que `.env` est dans `.gitignore` (oui, déjà fait)
- [ ] Vérifier qu'aucun token, IP, chat_id, ou nom personnel n'est dans le code source
- [ ] **Révoquer ton token Telegram** via BotFather → `/revoke` → choisir ton bot. Recréer avec un nouveau token, le mettre dans `.env`. (À faire si le token a fui à un moment ou à un autre — le `.env` est dans `.gitignore` mais une mauvaise manip historique pourrait l'avoir exposé.)
- [ ] `grep -rE "<TON_TOKEN>|<TON_CHAT_ID>|<NOM_DE_TON_BOT>" .` → vérifier zéro résultat hors du `.env` local avant le push

## Phase 1 — Publication GitHub (~1 heure)

- [ ] Créer un compte GitHub si pas déjà fait
- [ ] `git init && git add . && git commit -m "initial public release"`
- [ ] Créer le repo sur GitHub (Public)
- [ ] `git remote add origin ... && git push -u origin main`
- [ ] Configurer "About" du repo : description, topics (tags), website (optionnel)
- [ ] Créer 5-10 **issues** "good first issue" pour attirer des contribs : ex. *"Add Linux audio backend"*, *"Add SITE_NAME tag in EXIF metadata"*, *"Add /history command to list last N captures"*…
- [ ] Activer **GitHub Discussions** sur le repo (forum communautaire intégré)

## Phase 2 — Marketing initial (~1 weekend de prep + suivi)

L'objectif n'est pas la viralité mais d'**enclencher la première vague** d'utilisateurs cibles. Trois canaux à activer dans cet ordre :

### Canal 1 : Reddit r/selfhosted (~350K membres)
- Public ultra-aligné avec le pitch "anti-cloud, self-hosted"
- Format de post qui marche : titre court + GIF animé + 3-4 puces qui mettent en avant les angles différenciants + lien GitHub
- Préparer le post à l'avance, le poster un **mardi-mercredi 10h-13h heure US** (max audience)

### Canal 2 : Hacker News (Show HN)
- Audience tech mondiale plus large
- Format `Show HN: cam – self-hosted home security with custom voice alarm`
- Attendre d'avoir un début de retours de Reddit avant pour avoir du contenu à montrer
- Idéal : 1-2 semaines après Reddit

### Canal 3 : article de blog
- Sur ton propre blog ou dev.to (gratuit, audience native dev)
- Story-telling : "comment j'ai construit ma cam de surveillance sur un weekend pour ne plus payer Alfred"
- Inclure le code, les problèmes rencontrés (Voice Memos sandbox, xattr SMB pour SSH, etc.)
- Lien vers le repo en bas

### Canaux secondaires (si Phase 2 marche)
- Mastodon (#opensource, #selfhosted)
- LinkedIn (post personnel)
- Twitter/X
- ProductHunt (si tu as une vraie release packagée)

### Métriques à suivre
- Stars / jour sur GitHub (via Star History)
- Visiteurs uniques sur le repo (Insights → Traffic)
- Issues / PRs ouvertes
- Téléchargements (si releases binaires)

## Phase 3 — Activer GitHub Sponsors (~30 min)

À faire après que le projet a passé la barre des **~50-100 stars** (sinon zero traction, autant attendre).

- [ ] [github.com/sponsors/start](https://github.com/sponsors/start) → demander l'éligibilité
- [ ] Remplir le profil Sponsors :
  - Photo / logo
  - Bio courte (3-5 lignes)
  - Quelques tiers de sponsoring (1 €, 5 €, 10 €, 25 €) avec ce que ça finance ("1 € = un café et un merci dans les release notes")
- [ ] Configurer Stripe Connect avec ton IBAN perso français
- [ ] Ajouter `.github/FUNDING.yml` au repo :
  ```yaml
  github: [ton-username]
  ```
- [ ] Pousser → bouton "❤️ Sponsor" apparaît automatiquement sur le repo

## Phase 4 — Gestion fiscale (au fil de l'eau)

Tant que les revenus restent **< 3 000 €/an** :
- ✅ **Aucune démarche** à faire en avance
- À ta déclaration de revenus annuelle (avril-mai), reporte le total versé par GitHub Sponsors en case **« BNC non-professionnels »** (formulaire 2042-C-PRO, case 5KU)
- Imposition au barème progressif IR de ton foyer (~0-30% selon TMI)
- Pas d'URSSAF, pas de SIRET

Quand les revenus dépassent **~3-5 K€/an** ou deviennent **réguliers sur 2+ ans** :
- ⚠️ Inscription **micro-entrepreneur** recommandée
- 15 min en ligne sur [formalites.entreprises.gouv.fr](https://formalites.entreprises.gouv.fr)
- Code APE `62.01Z` (programmation informatique)
- Déclaration mensuelle/trimestrielle, ~22% URSSAF
- ACRE -50% charges 1ère année si éligible

Quand le projet se développe vers une **équipe / communauté** :
- Envisager une **association loi 1901** (cf. discussion fiscale)
- Permet déduction d'impôt pour donateurs (statut IEG à demander) et continuité collective
- Demande 2 personnes minimum

## Phase 5 — Évolutions techniques optionnelles (par ordre de ROI)

À ne déclencher que **si la Phase 2 fonctionne** et qu'il y a une vraie demande exprimée dans les issues.

### Phase 5A — Cross-platform (si demande Linux/Windows)
- Refactor `audio_backend.py` (cf. [WINDOWS_PORT.md](WINDOWS_PORT.md))
- ~1 weekend
- Élargit la cible × 3-5

### Phase 5B — Wizard d'installation
- PySide6 multi-écrans (cf. [PACKAGING.md](PACKAGING.md))
- ~2 weekends
- Ouvre la cible aux non-développeurs (×10 d'utilisateurs potentiels)

### Phase 5C — Bundling .dmg / .exe
- PyInstaller + Inno Setup
- ~1 weekend
- Distribution simple sans Python à installer

### Phase 5D — Code signing (90 € + 300 €/an)
- Apple Developer + cert EV Windows
- ~1 weekend setup
- Indispensable seulement si la Phase 5C atteint > quelques centaines de téléchargements

### Phase 5E — Portage Android natif
- Refonte complète Kotlin (cf. [ANDROID_PORT.md](ANDROID_PORT.md))
- ~5 weekends
- À envisager seulement si la base macOS plafonne et qu'il y a demande explicite (ex: "je voudrais utiliser mon vieux Galaxy" dans des issues)

## Phase 6 — Modèles de revenus alternatifs (si Phase 5 stabilise)

Si après ~6 mois la Phase 4 montre que les Sponsors plafonnent à ~30-100 €/mois et que tu veux pousser :

### Option A — Version "Pro" payante sur App Store
- L'open source reste, MAIS une version `cam-pro` packagée avec Wizard + auto-update + support sur App Store à 9.99 € one-shot ou 1.99 €/mois
- Demande Apple Developer 99 $/an
- Cible : non-développeurs qui ne savent pas installer la version libre

### Option B — Service hosted (cam.cloud ou autre)
- L'utilisateur installe une "lite" cam sur son tel/PC qui pointe vers ton serveur
- Tu héberges la logique de détection/Telegram/storage
- Abonnement 3-5 €/mois
- ⚠️ Demande infra à maintenir, RGPD lourd, support 24/7
- À éviter en solo, mieux porté par une asso ou société à terme

### Option C — Vente de fonctionnalités spécifiques
- Pack "alarme premium" avec 10 voix custom pré-faites
- Pack "intégrations" (HomeAssistant, MQTT, Zapier)
- Soutien commercial : aider qq pour 50-100 €/h à customiser pour son usage perso

## Tableau récapitulatif "qu'est-ce que je fais cette semaine"

| Étape | Effort | Quand |
|-------|--------|-------|
| Choisir un nom + check disponibilité | 30 min | semaine 1 |
| Polish README + LICENSE + CONTRIBUTING | 4-6 h | semaine 1 |
| Enregistrer GIF démo | 1-2 h | semaine 1 |
| Révoquer / régénérer token Telegram | 5 min | semaine 1 |
| Push initial GitHub | 1 h | semaine 1 |
| Préparer post Reddit r/selfhosted | 2 h | semaine 2 |
| Poster sur Reddit | 5 min | semaine 2 (mardi 10h US) |
| Suivre les retours, répondre aux commentaires | 2-4 h | semaine 2 |
| Demander GitHub Sponsors si > 50 stars | 30 min | semaine 3-4 |
| Show HN | 30 min prep | semaine 3-4 |
| Article de blog | 4-8 h | semaine 4-6 |
| Suivre la jauge stars/sponsors | en continu | tout le temps |

## Critères pour avancer / arrêter

**Continue si après 2 mois** :
- ≥ 100 stars GitHub
- ≥ 1 contribution externe (issue avec discussion productive, ou PR)
- ≥ 1 sponsor

**Bascule en mode "side-project tranquille"** si après 2 mois :
- Pas de traction (< 30 stars, pas de feedback)
- Tu y es indifférent
- Tu peux laisser le repo public, juste arrêter d'y mettre de l'énergie

**Repense le projet si après 6 mois** :
- Quelques utilisateurs actifs mais zéro sponsor
- → soit pivot vers un modèle plus payant explicite (App Store)
- → soit accepte que c'est un "cadeau open source" sans monétisation

## Bénéfices garantis quoi qu'il arrive

Indépendamment du succès commercial :
1. **Ligne forte sur ton CV** — projet open source maintenu, montre tes compétences plus que n'importe quel diplôme
2. **Apprentissage** — Git public, gestion d'issues, communication communautaire, marketing minimal
3. **Vitrine** — un repo propre est plus convaincant qu'une "section projets" abstraite
4. **Service rendu** — même 5 utilisateurs trouvent l'outil utile, c'est suffisant pour justifier le travail
5. **Optionalité** — à tout moment tu peux raviver le projet, l'archiver, le pivoter, ou en démarrer un autre dans la foulée avec ces apprentissages

## Documents de référence du projet

- [README.md](README.md) — usage et installation actuels
- [AUTOSTART.md](AUTOSTART.md) — démarrage automatique macOS
- [ANDROID_PORT.md](ANDROID_PORT.md) — portage natif Android (option future)
- [WINDOWS_PORT.md](WINDOWS_PORT.md) — portage Windows (option future)
- [PACKAGING.md](PACKAGING.md) — packaging et installation assistée
- [DEPLOYMENT.md](DEPLOYMENT.md) — ce document, plan de mise en public et de monétisation

## Décisions à prendre par toi avant de démarrer

1. ~~**Nom du projet final**~~ → **`gotchacam`** ✓
2. **Pseudonyme ou vrai nom GitHub** : public en tant que "Stéphane Goyet" ou pseudonyme ?
3. **License** : MIT (recommandé) ou AGPL ?
4. **Ambition** : "side-project tranquille" ou "essayer de pousser à 1000+ stars" ?
5. **Temps disponible** : 2 h/semaine ou 10 h/semaine de maintenance ?
6. **Acceptation du fail** : tu es OK pour publier et que ça reste à 5 stars ?

Une fois ces 6 réponses claires, le plan ci-dessus se déroule.
