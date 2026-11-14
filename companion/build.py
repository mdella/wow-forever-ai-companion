"""Builds the character dashboard page from the add-on's saved snapshot and the plans file."""
import json, re, sys, html
import lupa.lua51 as lua51

SV, PLANS, TEMPLATE, OUT = sys.argv[1:5]

L = lua51.LuaRuntime(unpack_returned_tuples=True)
L.execute(open(SV, encoding="utf-8").read())

def conv(v):
    if lua51.lua_type(v) == "table":
        keys = list(v.keys())
        if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(1, len(keys) + 1)):
            return [conv(v[i]) for i in range(1, len(keys) + 1)]
        return {str(k): conv(v[k]) for k in keys}
    return v

db = conv(L.globals().AICompanionDB)
plans = json.load(open(PLANS, encoding="utf-8"))

def money(c):
    if not isinstance(c, (int, float)): return "?"
    c = int(c); g, s, cp = c // 10000, (c % 10000) // 100, c % 100
    parts = []
    if g: parts.append(f"{g} gold")
    if s: parts.append(f"{s} silver")
    if cp or not parts: parts.append(f"{cp} copper")
    return " ".join(parts)

def lst(x): return x if isinstance(x, list) else ([] if not x else list(x.values()))
SEX = {2: "Male", 3: "Female"}
ALL_SLOTS = ["Head","Neck","Shoulder","Chest","Waist","Legs","Feet","Wrist","Hands","Finger1","Finger2","Trinket1","Trinket2","Back","MainHand","OffHand","Ranged"]

def build_char(key, store):
    s = store["snapshot"]; c = s.get("character", {}); loc = s.get("location", {})
    first = c.get("name", key.split("@")[0])
    plan = plans["characters"].get(first, {})
    out = {
        "id": re.sub(r"[^a-z0-9]", "", first.lower()),
        "first": first, "last": c.get("lastName") or "", "cls": c.get("class"), "clsFile": c.get("classFile"),
        "race": c.get("race"), "sex": SEX.get(c.get("sex"), ""), "faction": c.get("faction"),
        "level": c.get("level"), "xp": c.get("xp"), "xpMax": c.get("xpMax"), "rested": c.get("restedXP") or 0,
        "money": c.get("money"), "moneyText": money(c.get("money")),
        "zone": loc.get("mapName") or loc.get("zone"), "place": (loc.get("subZone") or loc.get("zone") or ""),
        "x": loc.get("x"), "y": loc.get("y"), "hearth": loc.get("hearthstone"), "resting": c.get("isResting"),
        "takenAt": s.get("takenAtText"), "addonVersion": (s.get("client") or {}).get("addonVersion"),
        "pet": c.get("pet"),
    }
    # stats
    out["stats"] = {k: v.get("total") for k, v in (c.get("stats") or {}).items()}
    # equipment
    eq, have = [], set()
    for it in lst(s.get("equipment")):
        have.add(it.get("slotName"))
        eq.append({"slot": it.get("slotName"), "name": it.get("name"), "q": it.get("quality"),
                   "dur": it.get("durability"), "durMax": it.get("durabilityMax"), "tip": lst(it.get("tooltip"))[1:]})
    out["equipment"] = eq
    out["emptySlots"] = [x for x in ALL_SLOTS if x not in have]
    # bags + items
    item_plans = plan.get("items", {})
    bags, items, sell_total = [], [], 0
    for b in lst(s.get("bags")):
        bags.append({"name": b.get("name"), "slots": b.get("slots"), "free": b.get("free"), "reagent": b.get("bag") == 5})
        for it in lst(b.get("items")):
            nm = it.get("name") or "Unknown item"
            p = item_plans.get(nm)
            if not p:
                if it.get("quality") == 0: p = {"action": "sell", "note": "Poor quality. Vendor it."}
                elif it.get("type") == "Quest": p = {"action": "quest", "note": "Quest item."}
                else: p = {"action": "check", "note": "No recommendation yet. Ask me about it."}
            each = it.get("sellPriceEach") or 0; cnt = it.get("count") or 1
            if p["action"] == "sell": sell_total += each * cnt
            items.append({"name": nm, "count": cnt, "q": it.get("quality"), "type": it.get("type"), "sub": it.get("subType"),
                          "each": each, "totalText": money(each * cnt) if each else "No vendor value", "bag": b.get("name"),
                          "action": p["action"], "note": p.get("note", ""), "tip": lst(it.get("tooltip"))[1:]})
    # merge identical stacks
    merged = {}
    for it in items:
        k = (it["name"], it["action"])
        if k in merged:
            merged[k]["count"] += it["count"]
            merged[k]["totalText"] = money(merged[k]["each"] * merged[k]["count"]) if merged[k]["each"] else "No vendor value"
        else: merged[k] = it
    out["items"] = list(merged.values()); out["bags"] = bags; out["sellTotalText"] = money(sell_total)
    # quests
    qs = []
    for q in lst(s.get("quests")):
        objs = [{"text": o.get("text"), "done": bool(o.get("finished"))} for o in lst(q.get("objectives")) if isinstance(o, dict)]
        counted = [o for o in objs if re.match(r"^\d+/\d+ ", o["text"] or "")]
        if q.get("complete") and counted: status = "ready"
        elif q.get("complete"): status = "deliver"
        elif any(o["done"] for o in objs) or any(re.match(r"^[1-9]\d*/", o["text"] or "") for o in objs): status = "progress"
        else: status = "todo"
        qs.append({"title": q.get("title"), "level": q.get("level"), "cat": q.get("category"), "status": status,
                   "objs": objs if counted else [], "text": (q.get("objectiveText") or "").strip(),
                   "xp": q.get("rewardXP") or 0, "moneyText": money(q["rewardMoney"]) if q.get("rewardMoney") else "",
                   "rewards": [r[0] for r in lst(q.get("rewardItems")) if lst(r)], "choices": [r[0] for r in lst(q.get("rewardChoices")) if lst(r)]})
    out["quests"] = qs
    # completed
    cq = s.get("completedQuests")
    if cq:
        counts = {}
        for q in lst(cq.get("quests")):
            t = q.get("title")
            if t: counts[t] = counts.get(t, 0) + 1
        out["completed"] = {"count": cq.get("count"), "titles": sorted([[t, n] for t, n in counts.items()], key=lambda x: x[0].lower())}
    else:
        out["completed"] = None
    # professions and skills
    profs = []
    for p in lst((s.get("skills") or {}).get("professions")):
        profs.append({"name": p.get("name"), "rank": p.get("rank"), "max": p.get("max")})
    known = {p["name"] for p in profs}
    all_skills = {k.get("name"): k for k in lst((s.get("skillsModern") or {}).get("allSkills")) if isinstance(k, dict) and not k.get("isHeader")}
    for name in plan.get("professions", {}):
        if name not in known:
            k = all_skills.get(name)
            profs.append({"name": name, "rank": k.get("rank") if k else None, "max": k.get("maxRank") if k else None})
    for p in profs: p.update({"plan": plan.get("professions", {}).get(p["name"])})
    out["professions"] = profs
    weapon, header = [], None
    for k in lst((s.get("skillsModern") or {}).get("allSkills")):
        if not isinstance(k, dict): continue
        if k.get("isHeader"): header = k.get("name"); continue
        if header == "Weapon Skills": weapon.append({"name": k.get("name"), "rank": k.get("rank"), "max": k.get("maxRank")})
    out["weaponSkills"] = weapon
    # talents
    t = s.get("talents") or {}; trees = lst(t.get("trees"))
    tal = {"groups": [], "unspent": None, "firstRow": []}
    if trees:
        tree = trees[0]; cur = lst(tree.get("currencies"))
        if cur: tal["unspent"] = cur[0].get("quantity"); tal["spent"] = cur[0].get("spent")
        for g in lst(tree.get("groupDisplay")):
            gid = g.get("groupID"); picks = []; spent = 0
            for n in lst(tree.get("nodes")):
                if gid in lst(n.get("groupIDs")):
                    r = n.get("rank") or 0
                    if r > 0: picks.append({"name": n.get("name"), "rank": r, "max": n.get("maxRank"), "desc": n.get("description")}); spent += r
                    elif n.get("available") and (tal.get("spent") or 0) == 0:
                        tal["firstRow"].append({"tree": g.get("displayName"), "name": n.get("name"), "max": n.get("maxRank"), "desc": n.get("description")})
            tal["groups"].append({"name": g.get("displayName"), "spent": spent, "picks": picks})
    seen = set(); fr = []
    for x in tal["firstRow"]:
        if (x["tree"], x["name"]) not in seen: seen.add((x["tree"], x["name"])); fr.append(x)
    tal["firstRow"] = fr
    out["talents"] = tal
    # legacy
    leg = s.get("legacy") or {}
    out["legacy"] = [{"name": tr.get("label"), "perks": [{"name": n.get("name"), "rank": n.get("rank") or 0, "max": n.get("maxRank"), "desc": n.get("description")} for n in lst(tr.get("nodes")) if n.get("name") != "Unknown"]} for tr in lst(leg.get("trees"))]
    out["rep"] = [{"name": r.get("name"), "standing": r.get("standing")} for r in lst(s.get("reputation")) if not r.get("isHeader")]
    out["buffs"] = [a.get("name") for a in lst((s.get("auras") or {}).get("buffs"))]
    out["recipesCaptured"] = sorted((store.get("recipes") or {}).keys())
    # which plan steps the snapshot can confirm on its own
    active = {q["title"] for q in qs}
    done_titles = {t for t, _ in (out["completed"] or {}).get("titles", [])} if out["completed"] else None
    equipped = {e["name"]: e for e in eq}
    in_bags = {i["name"] for i in out["items"]}
    skills = {p["name"]: p for p in profs}
    free_slots = sum((b.get("free") or 0) for b in bags)
    def check(rule):
        (kind, arg), = rule.items()
        if kind == "all": return all(check(r) for r in arg)
        if kind == "equipped": return arg in equipped
        if kind == "notEquipped": return arg not in equipped
        if kind == "slotFilled": return arg not in out["emptySlots"]
        if kind == "notInBags": return not any(n in in_bags for n in arg)
        if kind == "questDone": return arg not in active and (done_titles is None or arg in done_titles)
        if kind == "skill": return (skills.get(arg[0], {}).get("rank") or 0) >= arg[1]
        if kind == "skillCapAbove": return (skills.get(arg[0], {}).get("max") or 0) > arg[1]
        if kind == "talentsSpent": return (tal.get("spent") or 0) >= arg
        if kind == "freeSlots": return free_slots >= arg
        if kind == "repaired":
            pcts = [e["dur"] / e["durMax"] * 100 for e in eq if e.get("durMax")]
            return bool(pcts) and min(pcts) >= arg
        if kind == "captured":
            if arg == "completed": return out["completed"] is not None
            if arg.startswith("recipes:"): return arg.split(":", 1)[1] in (store.get("recipes") or {})
            if arg == "trainers": return bool(store.get("trainers") or store.get("trainerRaw"))
            return bool(store.get(arg))
        raise ValueError("unknown rule " + kind)
    def resolve(o):
        if isinstance(o, list): return [resolve(x) for x in o]
        if isinstance(o, dict):
            o = {k: resolve(v) for k, v in o.items() if k != "done"} | ({"auto": check(o["done"])} if "done" in o else {})
        return o
    plan = resolve(plan)
    # plan with placeholders filled
    def fill(o):
        if isinstance(o, str): return o.replace("{sellTotal}", out["sellTotalText"])
        if isinstance(o, list): return [fill(x) for x in o]
        if isinstance(o, dict): return {k: fill(v) for k, v in o.items()}
        return o
    out["plan"] = fill({k: v for k, v in plan.items() if k != "items"}) if plan else None
    return out

chars = [build_char(k, st) for k, st in db.get("characters", {}).items() if isinstance(st, dict) and st.get("snapshot")]
captured = {(c["first"] + " " + c["last"]).strip() for c in chars}
order = {n: i for i, n in enumerate(plans["roster"])}
chars.sort(key=lambda c: order.get((c["first"] + " " + c["last"]).strip(), 99))
pending = [n for n in plans["roster"] if n not in captured]
data = {"chars": chars, "pending": pending, "sources": plans["sources"], "built": max((c["takenAt"] or "") for c in chars)}
page = open(TEMPLATE, encoding="utf-8").read().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
open(OUT, "w", encoding="utf-8").write(page)
print("built", OUT, len(page), "bytes;", [(c["first"], c["level"], len(c["items"]), len(c["quests"]), c["sellTotalText"]) for c in chars], "pending", pending)
