"""Market specialists (expansion plan): gold, usdjpy, gbpusd. Status comes from config.yaml `specialists`
(only listed `active` specialists may run pre-registered trading research; the others are monitoring only)."""
from src import load_config


def status(name, cfg=None):
    s = (cfg or load_config())["specialists"]
    if name in s["active"]:
        return "active"
    if name in s["monitoring"]:
        return "monitoring"
    raise KeyError(name)


def require_active(name, cfg=None):
    if status(name, cfg) != "active":
        raise PermissionError("specialist %r is in monitoring mode; trading research is not allowed" % name)
