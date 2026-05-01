"""Tests end-to-end contre un vrai bot Telegram (PLACEHOLDER).

Ces tests ne sont pas encore implémentés. Ils vérifieront le comportement
de cam.py (Python) ET de l'app Android contre un bot Telegram dédié au test.

Pour les implémenter, il faudra :
1. Créer un second bot via @BotFather, indépendant du bot de production
2. Définir TEST_BOT_TOKEN et TEST_CHAT_ID en variables d'environnement
3. Faire tourner une instance de cam.py (ou l'app Android) configurée sur le test bot
4. Utiliser une bibliothèque de client Telegram (telethon, pyrogram) pour
   envoyer des commandes au bot et lire ses réponses
5. Comparer aux comportements définis dans BEHAVIOR_SPEC.md

Quand ces tests passeront sur les deux implémentations, on aura la garantie
formelle que macOS et Android se comportent identiquement.
"""

import os

import pytest


pytestmark = pytest.mark.skipif(
    "TEST_BOT_TOKEN" not in os.environ,
    reason="TEST_BOT_TOKEN not configured — see this file's docstring",
)


def test_help_command_lists_all_commands():
    """Envoyer /help doit retourner un message contenant chaque commande de commands.json."""
    pytest.skip("not implemented yet")


def test_alarm_starts_and_stops():
    """/alarm démarre l'alarme, /alarm pendant qu'elle tourne renvoie 'déjà en cours',
    /stopalarm l'arrête et restaure le volume."""
    pytest.skip("not implemented yet")


def test_sensitivity_updates_min_area():
    """/sensitivity 4000 met à jour la valeur, /sensitivity sans arg la lit en retour."""
    pytest.skip("not implemented yet")


def test_pause_releases_camera():
    """/pause libère la caméra ; /status indique 'caméra éteinte' ;
    /snapshot répond avec le message d'erreur de pause."""
    pytest.skip("not implemented yet")


def test_recording_alarm_replaces_file():
    """/recordalarm + envoi d'un message vocal remplace le alarm.m4a."""
    pytest.skip("not implemented yet")
