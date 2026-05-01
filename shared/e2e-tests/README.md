# Tests d'intégration end-to-end

Tests qui vérifient que **toute implémentation** de `gotchacam` (Python sur macOS, Kotlin sur Android) respecte la spec définie dans [../BEHAVIOR_SPEC.md](../BEHAVIOR_SPEC.md).

Ces tests sont la **garantie ultime** que les deux versions ont le même comportement, en plus d'être la grille de validation de toute évolution.

## Deux niveaux

### Niveau 1 — Smoke tests (sans bot, sans réseau)

Ces tests vérifient l'**intégrité** des assets partagés et de l'implémentation Python sans avoir besoin d'un bot Telegram. Lancement instantané, à exécuter à chaque commit.

```bash
cd <projet-root>
.venv/bin/python -m pytest shared/e2e-tests/test_smoke.py -v
```

Ce qui est testé :
- Les fichiers `defaults.json`, `strings.fr.json`, `commands.json` sont du JSON valide
- Tous les placeholders `{name}` mentionnés dans le code Python existent dans `strings.fr.json`
- `cam.py` s'importe sans erreur
- `HELP_TEXT` contient toutes les commandes listées dans `commands.json`
- Toutes les valeurs de `defaults.json` sont du bon type

### Niveau 2 — Tests against real bot (à venir)

Ces tests parlent à un **bot Telegram dédié au test** (token séparé du bot de production), envoient des commandes, vérifient les réponses. Nécessitent :

1. Un second bot créé via `@BotFather` réservé aux tests
2. Variables d'env `TEST_BOT_TOKEN` et `TEST_CHAT_ID`
3. Une instance de `cam.py` (ou de l'app Android sur émulateur) qui tourne sur ce token de test

```bash
TEST_BOT_TOKEN=... TEST_CHAT_ID=... .venv/bin/python -m pytest shared/e2e-tests/test_telegram.py -v
```

**Ces tests ne sont pas encore implémentés** — ce dossier contient leur scaffold, à étoffer après le portage Android pour pouvoir valider les deux implémentations contre la même grille.

## Structure

```
shared/e2e-tests/
├── README.md                  ← ce fichier
├── conftest.py                ← fixtures pytest communes
├── test_smoke.py              ← tests qui n'exigent rien d'externe
└── test_telegram.py           ← tests bot (à étoffer)
```

## Discipline

À chaque ajout de fonctionnalité dans `BEHAVIOR_SPEC.md` :
1. Décris le comportement dans la spec
2. Modifie l'implémentation Python
3. **Ajoute un test ici** qui vérifie la conformité
4. Quand l'app Android sera là, les mêmes tests s'y appliqueront

Sans cette discipline, la spec devient un wishful-thinking document que personne ne respecte plus en pratique.
