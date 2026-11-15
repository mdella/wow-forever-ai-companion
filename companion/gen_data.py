"""Writes the AICompanion_Data add-on file (shopping lists, per-item advice and the plan shown in
the in-game panel) from the plan file.
Usage: python3 gen_data.py plans.json <path to AICompanion_Data.lua>"""
import json, sys, datetime, os
plans, target = sys.argv[1], sys.argv[2]
d = json.load(open(plans, encoding="utf-8"))
ACTIONS = {"equip", "use", "craft", "sell", "auction", "mail", "bank", "quest", "carry", "check"}
REPL = {"\u2014": ", ", "\u2013": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u00d7": "x", "\u2026": "...", "\u00a0": " "}
def q(s):
    for a, b in REPL.items(): s = s.replace(a, b)
    s = s.encode("ascii", "ignore").decode().replace("|", "/")  # the game treats | as a formatting escape
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'
PLAN_KEYS = ["headline", "headlineShort", "next", "questing", "professions", "gear", "talents", "bags", "blindspots"]
def lua(v, indent="    "):
    """A JSON value as a Lua literal. Strings go through q(), so they are plain ASCII."""
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return repr(v)
    if isinstance(v, str): return q(v)
    if isinstance(v, list): return "{ " + ", ".join(lua(x, indent) for x in v if x is not None) + " }"
    if isinstance(v, dict):
        inner = indent + "    "
        parts = ["%s[%s] = %s," % (inner, q(str(k)), lua(x, inner)) for k, x in v.items() if x is not None]
        return "{\n" + "\n".join(parts) + "\n" + indent + "}" if parts else "{}"
    raise ValueError("cannot write %r to the data file" % (v,))
out = ["-- AI Companion data: shopping lists, per-item advice and plans for your characters.",
       "-- Generated from the plan file by gen_data.py. Do not edit by hand; regenerate instead.",
       "-- Keys are character first names, exactly as the game shows them.", "",
       "AICompanionShopping = {"]
for cname, c in d.get("characters", {}).items():
    names = c.get("shopping") or []
    if names: out.append("    [%s] = { %s }," % (q(cname), ", ".join(q(n) for n in names)))
out += ["}", "", "AICompanionAdvice = {",
        "    asOf = %s," % q(datetime.date.today().strftime("%b %d").replace(" 0", " ")),
        "    characters = {"]
n = 0
for cname, c in d.get("characters", {}).items():
    items = c.get("items") or {}
    if not items: continue
    out.append("        [%s] = {" % q(cname))
    for item, p in items.items():
        assert p["action"] in ACTIONS, (cname, item, p["action"])
        tip = p.get("tip") or p.get("note", "")
        assert len(tip) <= 48, "tooltip text over 48 characters for %s: add a short \"tip\"" % item
        out.append("            [%s] = { %s, %s }," % (q(item), q(p["action"]), q(tip)))
        n += 1
    out.append("        },")
out += ["    },", "}", ""]
plans = {}
for cname, c in d.get("characters", {}).items():
    p = {k: c[k] for k in PLAN_KEYS if c.get(k) not in (None, "", [], {})}
    assert len(p.get("headlineShort", "")) <= 100, "headlineShort over 100 characters for %s" % cname
    if p: plans[cname] = p
out += ["AICompanionPlans = {",
        "    asOf = %s," % q(datetime.date.today().strftime("%b %d").replace(" 0", " ")),
        "    sources = %s," % lua(d.get("sources") or {}, "    "),
        "    characters = %s," % lua(plans, "    "),
        "}", ""]
tmp = target + ".new"
open(tmp, "w", encoding="utf-8", newline="\n").write("\n".join(out))
os.replace(tmp, target)
print("wrote", target, "advice entries:", n, "plans:", len(plans))
