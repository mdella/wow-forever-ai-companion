"""Writes the AICompanion_Data add-on file (shopping lists and per-item advice) from the plan file.
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
out = ["-- AI Companion data: shopping lists and per-item advice for your characters.",
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
tmp = target + ".new"
open(tmp, "w", encoding="utf-8", newline="\n").write("\n".join(out))
os.replace(tmp, target)
print("wrote", target, "advice entries:", n)
