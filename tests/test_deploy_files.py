"""Deploy files (audit item 2): the LaunchAgent template and the Keychain item list carry no secrets and no personal
paths, and the list names exactly the Keychain items the code reads."""
import plistlib
import re

from src import PROJECT_ROOT

D = PROJECT_ROOT / "deploy"


def test_plist_template_is_valid_has_placeholders_and_no_secrets_or_home_paths():
    t = (D / "local.trading-research.usdjpy-runner.plist.template").read_text()
    assert "/Users/" not in t and "{{ROOT}}" in t
    assert not re.search(r"(?i)token|secret|password|api[_-]?key|hc-ping", t)
    p = plistlib.loads(t.replace("{{ROOT}}", "/tmp/x").encode())
    assert p["Label"] == "local.trading-research.usdjpy-runner" and p["ProgramArguments"][-1] == "run"
    assert [d["Minute"] for d in p["StartCalendarInterval"]] == [2, 17, 32, 47] and p["RunAtLoad"] is False
    assert set(p["EnvironmentVariables"]) == {"PATH"}                       # no credential in the environment block


def test_keychain_list_matches_the_items_the_code_reads_and_holds_names_only():
    listed = {l.strip() for l in (D / "KEYCHAIN_ITEMS.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
    used = set()
    for p in list((PROJECT_ROOT / "src").rglob("*.py")) + list((PROJECT_ROOT / "tools").rglob("*.py")):
        used |= set(re.findall(r"trading-research-[a-z0-9-]+", p.read_text()))
    assert listed == used
    assert all(re.fullmatch(r"trading-research-[a-z0-9-]+", n) for n in listed)
