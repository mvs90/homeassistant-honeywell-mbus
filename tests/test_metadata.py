"""Validate shipped translations and the installable HA/HACS package contract."""

import json
import re
from pathlib import Path

import pytest

from custom_components.honeywell_mbus.sensor import PARALLEL_UPDATES, SENSORS

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components/honeywell_mbus"
LANGUAGES = sorted((COMPONENT / "translations").glob("*.json"))


def flatten(value, prefix=""):
    return {
        path: text
        for key, item in value.items()
        for path, text in (
            flatten(item, f"{prefix}{key}.").items()
            if isinstance(item, dict)
            else [(f"{prefix}{key}", item)]
        )
    }


@pytest.mark.parametrize("path", LANGUAGES, ids=lambda p: p.stem)
def test_complete_locale_and_placeholders(path):
    source = json.loads((COMPONENT / "strings.json").read_text())
    translated = json.loads(path.read_text())
    canonical = flatten(source)
    localized = flatten(translated)
    assert set(localized) == set(canonical)
    for key, text in localized.items():
        assert isinstance(text, str) and text.strip(), (path.stem, key)
        assert re.findall(r"\{[^{}]+\}", text) == re.findall(r"\{[^{}]+\}", canonical[key])
    assert set(translated["entity"]["sensor"]) == {s.translation_key for s in SENSORS}


def test_installable_package_contract():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == COMPONENT.name
    assert manifest["config_flow"] and manifest["iot_class"] == "local_polling"
    assert manifest["requirements"] == []
    assert hacs["homeassistant"] == "2026.11.0"
    assert PARALLEL_UPDATES == 0
    assert len(LANGUAGES) >= 18
    assert (COMPONENT / "translations/en.json").read_text() == (
        COMPONENT / "strings.json"
    ).read_text()
