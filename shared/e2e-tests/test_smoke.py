"""Smoke tests — vérifient l'intégrité des assets partagés et de l'implémentation Python.

Ne nécessitent ni bot Telegram, ni réseau, ni caméra. À lancer à chaque commit :
    .venv/bin/python -m pytest shared/e2e-tests/test_smoke.py -v
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
SHARED = PROJECT_ROOT / "shared"


@pytest.fixture(scope="module")
def defaults():
    return json.loads((SHARED / "defaults.json").read_text())


@pytest.fixture(scope="module")
def strings():
    return json.loads((SHARED / "strings.fr.json").read_text())


@pytest.fixture(scope="module")
def commands():
    return json.loads((SHARED / "commands.json").read_text())


@pytest.fixture(scope="module")
def cam_source():
    return (PROJECT_ROOT / "cam.py").read_text()


# ---------------------------------------------------------------------------
# Validité des assets partagés
# ---------------------------------------------------------------------------


def test_defaults_is_valid_json(defaults):
    assert isinstance(defaults, dict)


def test_defaults_has_expected_sections(defaults):
    for section in ("camera", "motion", "burst", "alarm", "captures"):
        assert section in defaults, f"missing section '{section}' in defaults.json"


def test_defaults_values_are_correct_types(defaults):
    assert isinstance(defaults["camera"]["index"], int)
    assert isinstance(defaults["camera"]["warmupSeconds"], (int, float))
    assert isinstance(defaults["motion"]["threshold"], int)
    assert isinstance(defaults["motion"]["minArea"], int)
    assert isinstance(defaults["motion"]["cooldownSeconds"], (int, float))
    assert isinstance(defaults["burst"]["count"], int)
    assert isinstance(defaults["burst"]["intervalSeconds"], (int, float))
    assert isinstance(defaults["alarm"]["pitch"], (int, float))
    assert isinstance(defaults["alarm"]["recordMaxSeconds"], int)
    assert isinstance(defaults["alarm"]["voicePlaybackMaxSeconds"], int)
    assert isinstance(defaults["alarm"]["voice"], str)
    assert isinstance(defaults["captures"]["retentionDays"], int)


def test_strings_is_valid_json(strings):
    assert isinstance(strings, dict)


def test_strings_has_expected_sections(strings):
    expected_sections = (
        "service", "alarm", "record_alarm", "voice", "pause",
        "status", "snapshot", "motion", "site_prefix", "help",
        "sensitivity", "history",
    )
    for section in expected_sections:
        assert section in strings, f"missing section '{section}' in strings.fr.json"


def test_commands_is_valid_json(commands):
    assert isinstance(commands, dict)
    assert "commands" in commands
    assert isinstance(commands["commands"], list)
    assert len(commands["commands"]) > 0


def test_every_command_has_name_and_description(commands):
    for cmd in commands["commands"]:
        assert "name" in cmd
        assert "description" in cmd
        assert isinstance(cmd["name"], str)
        assert isinstance(cmd["description"], str)


# ---------------------------------------------------------------------------
# Cohérence entre commands.json et l'implémentation cam.py
# ---------------------------------------------------------------------------


def test_every_command_in_json_is_registered_in_cam_py(commands, cam_source):
    """Pour chaque commande déclarée dans commands.json, vérifier qu'elle est enregistrée
    via add_handler(CommandHandler(...)) dans cam.py."""
    skip = {"start"}  # /start est aliasé sur cmd_help, pas de cmd_start dédié
    for cmd in commands["commands"]:
        name = cmd["name"]
        if name in skip:
            continue
        pattern = rf'CommandHandler\(\s*["\']{name}["\']'
        assert re.search(pattern, cam_source), \
            f"command /{name} declared in commands.json but not registered in cam.py"


def test_help_text_contains_all_user_commands(strings, commands):
    """Le texte d'aide doit lister chaque commande utilisateur (hors aliases)."""
    skip = {"start"}
    help_lines = strings["help"]["commands"]
    help_text = "\n".join(help_lines)
    for cmd in commands["commands"]:
        if cmd["name"] in skip:
            continue
        assert f"/{cmd['name']}" in help_text, \
            f"command /{cmd['name']} missing from strings.fr.json help.commands"


# ---------------------------------------------------------------------------
# Cohérence entre placeholders dans strings.fr.json et leur usage dans cam.py
# ---------------------------------------------------------------------------


def _walk_strings(node, prefix=""):
    """Yield (key_path, value) pour chaque feuille string du JSON."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{prefix}[{i}]")
    elif isinstance(node, str):
        yield prefix, node


def test_no_string_has_unbalanced_braces(strings):
    """Détecte les placeholders mal formés (ex: {name au lieu de {name})."""
    for key, value in _walk_strings(strings):
        assert value.count("{") == value.count("}"), \
            f"unbalanced braces in strings.fr.json at {key!r}: {value!r}"


# ---------------------------------------------------------------------------
# cam.py s'importe sans erreur (à condition d'avoir TELEGRAM_BOT_TOKEN défini)
# ---------------------------------------------------------------------------


def test_cam_py_compiles():
    """cam.py est syntaxiquement valide (pas d'import ni d'exécution réelle)."""
    import py_compile
    py_compile.compile(str(PROJECT_ROOT / "cam.py"), doraise=True)
