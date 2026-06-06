# Automatisation iOS avec l'app Raccourcis

Active la surveillance quand tu pars de chez toi, met en pause quand tu rentres — automatiquement, via l'app Raccourcis d'Apple et un accès direct au bot sans passer par Telegram.

## Principe

gotchacam expose un mini serveur HTTP local protégé par un token secret. Tailscale crée un réseau privé virtuel entre ton iPhone et le Mac de surveillance — quel que soit l'endroit où tu te trouves. Le Raccourci iOS envoie une requête HTTP directement au Mac.

```
iPhone (lieu détecté) → Tailscale (réseau privé) → Mac → gotchacam pause/resume
```

Avantages par rapport à l'ancienne méthode Telegram :
- Aucun bot tiers à créer ni à maintenir
- Fonctionne depuis n'importe où (4G, étranger, etc.)
- Rien n'est exposé sur internet public — seuls les appareils de ton compte Tailscale peuvent atteindre le Mac

## Prérequis

- gotchacam en cours d'exécution sur le Mac de surveillance
- `HTTP_TOKEN` configuré dans le `.env` du Mac (voir ci-dessous)
- Tailscale installé et connecté sur le Mac **et** sur l'iPhone (même compte)

---

## Étape 1 — Configurer le serveur HTTP sur le Mac

Dans le fichier `.env` sur le Mac de surveillance, ajoute :

```env
HTTP_PORT=8765
HTTP_TOKEN=<un_token_secret_long>
```

Pour générer un token aléatoire solide :

```bash
openssl rand -hex 20
```

Redémarre le service :

```bash
launchctl stop com.goyet.cam && launchctl start com.goyet.cam
```

Vérifie que le serveur répond en local :

```bash
curl "http://127.0.0.1:8765/cmd/status?token=<ton_token>"
# → {"ok": true, "state": "active"}
```

---

## Étape 2 — Installer Tailscale

### Sur le Mac de surveillance

1. Télécharge le `.pkg` depuis **tailscale.com/download/mac**
2. Lance l'installeur → approuve l'extension réseau dans **Réglages Système → Général → Extensions**
3. Tailscale apparaît dans la barre de menus → clique → **Log in** → crée un compte gratuit
4. Note l'IP Tailscale du Mac (visible dans le menu Tailscale ou via `tailscale ip -4`)

Tailscale est enregistré comme service système : il redémarre automatiquement au reboot du Mac.

### Sur l'iPhone

1. App Store → cherche **"Tailscale"** → installe
2. Connecte-toi avec le **même compte** que sur le Mac
3. Accepte la configuration VPN quand iOS le demande

Vérifie dans **Réglages iPhone → VPN et gestion des appareils → VPN** que Tailscale est activé (vert). Il se reconnecte automatiquement au redémarrage de l'iPhone.

### Tester la connexion

Dans Safari sur l'iPhone, ouvre :

```
http://<IP_TAILSCALE_DU_MAC>:8765/cmd/status?token=<ton_token>
```

Tu dois voir : `{"ok": true, "state": "active"}`

---

## Étape 3 — Créer les deux automations dans Raccourcis

### Automatisation "Quitter domicile → activer la cam"

1. Ouvre l'app **Raccourcis** → onglet **Automatisation**
2. Appuie sur **+** → **Nouvelle automatisation personnelle**
3. Choisis **Lieu**
   - Lieu : sélectionne ton domicile
   - Quand : **Je pars**
4. Appuie sur **Ajouter une action** → cherche **"Obtenir le contenu de l'URL"**
5. Configure l'action :
   - **URL** : `http://<IP_TAILSCALE_DU_MAC>:8765/cmd/resume?token=<ton_token>`
   - **Méthode** : GET
6. Désactive **"Demander avant d'exécuter"** pour que ça se déclenche sans confirmation
7. Appuie sur **Suivant** puis **OK**

### Automatisation "Arriver domicile → mettre en pause"

Répète les mêmes étapes avec :
- Quand : **J'arrive**
- URL : `http://<IP_TAILSCALE_DU_MAC>:8765/cmd/pause?token=<ton_token>`

---

## Commandes disponibles

| URL | Effet |
|-----|-------|
| `/cmd/pause?token=…` | Met la détection en pause (caméra éteinte) |
| `/cmd/resume?token=…` | Reprend la détection |
| `/cmd/status?token=…` | Retourne l'état actuel (`active` ou `paused`) |

Toutes les commandes envoient aussi une confirmation sur Telegram.

---

## Dépannage

| Symptôme | Cause probable | Solution |
|----------|---------------|----------|
| Timeout / pas de réponse | Tailscale non connecté sur l'iPhone | Vérifie que le VPN Tailscale est actif dans les Réglages |
| `{"ok": false, "error": "unauthorized"}` | Token incorrect dans l'URL | Vérifie `HTTP_TOKEN` dans le `.env` et dans le Raccourci |
| `{"ok": false, "error": "unknown command"}` | Faute de frappe dans l'URL (`/cmd/pasue`) | Corrige l'URL dans le Raccourci |
| L'automatisation ne se déclenche pas | Localisation désactivée pour Raccourcis | Réglages → Confidentialité → Localisation → Raccourcis → Toujours |
| Déclenchement erratique | Rayon du lieu trop petit | Dans l'automatisation, agrandis le rayon de détection |

---

## Notes

- Le token est stocké dans les Raccourcis iOS et dans le `.env` du Mac — si tu le changes, mets à jour les deux
- L'IP Tailscale du Mac (`100.x.x.x`) est permanente et ne change pas au redémarrage
- Cette automatisation fonctionne en WiFi, 4G/5G, depuis n'importe quel pays
- Le serveur HTTP n'écoute pas sur internet public — uniquement via le réseau Tailscale
