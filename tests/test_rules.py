"""The built-in rules, run outside the game as pure functions over a saved snapshot."""

import itertools
import os
import sys
import unittest

from lupa import lua51

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import ROOT, to_py  # noqa: E402

CLASSES = ["WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID"]
LONGEST_NAME = "Abcdefghijkl"   # 12 letters, the longest name the game allows
PROFESSIONS = ["Alchemy", "Blacksmithing", "Enchanting", "Engineering", "Leatherworking", "Tailoring",
               "Cooking", "First Aid", "Fishing"]
WEAPONS = ["Bows", "Crossbows", "Guns", "Daggers", "Fist Weapons", "One-Handed Axes", "Two-Handed Axes",
           "One-Handed Maces", "Two-Handed Maces", "One-Handed Swords", "Two-Handed Swords", "Polearms",
           "Staves", "Wands", "Thrown"]
ARMOR = ["Cloth", "Leather", "Mail", "Plate"]


def rules():
    lua = lua51.LuaRuntime(unpack_returned_tuples=True)
    with open(os.path.join(ROOT, "AddOns/AICompanion/AICompanion_Rules.lua"), encoding="utf-8") as f:
        lua.execute(f.read())
    return lua


def item(name, **kw):
    d = dict(name=name, count=1, quality=1, sellPriceEach=100)
    d.update(kw)
    return d


def sweep_items():
    """Every kind of item the rules handle, with long names and the largest numbers likely."""
    out = [item("Junk Thing", quality=0, type="Miscellaneous", subType="Junk")]
    for q, bound in itertools.product((1, 2, 3), (False, True)):
        tag = "%d%s" % (q, "b" if bound else "")
        for kind in ARMOR:
            out.append(item("%s Helm %s" % (kind, tag), quality=q, bound=bound, type="Armor", subType=kind,
                            equipSlot="INVTYPE_HEAD", itemLevel=60, requiredLevel=60,
                            tooltip=["Head", "%d Armor" % 1234]))
            out.append(item("%s Gloves %s" % (kind, tag), quality=q, bound=bound, type="Armor", subType=kind,
                            equipSlot="INVTYPE_HAND", itemLevel=63, requiredLevel=58,
                            tooltip=["Hands", "321 Armor", "+12 Stamina"]))
        out.append(item("Tower Shield %s" % tag, quality=q, bound=bound, type="Armor", subType="Shields",
                        equipSlot="INVTYPE_SHIELD", tooltip=["2153 Armor"]))
        for w in WEAPONS:
            out.append(item("%s %s" % (w, tag), quality=q, bound=bound, type="Weapon", subType=w,
                            equipSlot="INVTYPE_2HWEAPON", itemLevel=60, requiredLevel=60,
                            tooltip=["(123.45 damage per second)"]))
        for p in PROFESSIONS:
            out.append(item("Recipe %s %s" % (p, tag), quality=q, bound=bound, type="Recipe", subType=p,
                            tooltip=["Requires %s (300)" % p]))
        out.append(item("Mana Drink %s" % tag, quality=q, bound=bound, type="Consumable", subType="Food & Drink",
                        tooltip=["Use: Restores 4410 mana over 30 sec."]))
        out.append(item("Class Scroll %s" % tag, quality=q, bound=bound, type="Consumable", subType="Scrolls",
                        tooltip=["Classes: Warrior, Paladin, Hunter, Rogue"]))
        for sub in ("Leather", "Herb", "Cloth", "Metal & Stone", "Enchanting", "Parts", "Cooking"):
            out.append(item("%s Goods %s" % (sub, tag), quality=q, bound=bound, type="Trade Goods", subType=sub,
                            tooltip=["Crafting Reagent"]))
        out.append(item("Arrows %s" % tag, quality=q, type="Projectile", subType="Arrow"))
        out.append(item("Bullets %s" % tag, quality=q, type="Projectile", subType="Bullet"))
    for stat in ("Attack Power", "Agility", "Strength", "Stamina", "Intellect", "Spirit"):
        out.append(item("Food %s" % stat, count=200, type="Consumable", subType="Food & Drink",
                        tooltip=["Use: Restores 2148 health over 30 sec. If you spend at least 10 seconds eating "
                                 "you will become well fed and gain 25 %s for 15 min." % stat]))
    out.append(item("Big Bag", type="Container", subType="Bag", equipSlot="INVTYPE_BAG", tooltip=["18 Slot Bag"]))
    out.append(item("Small Bag", type="Container", subType="Bag", equipSlot="INVTYPE_BAG", tooltip=["4 Slot Bag"]))
    out.append(item("Fishing Pole", type="Weapon", subType="Fishing Pole", equipSlot="INVTYPE_2HWEAPON"))
    return out


def db_for(cls, profs, level, worn=True):
    skills = [{"name": a, "skillLineCategoryID": 8} for a in ("Cloth", "Leather")]
    skills += [{"name": "Staves", "skillLineCategoryID": 6}, {"name": "Bows", "skillLineCategoryID": 6}]
    equipment = []
    if worn:
        equipment = [
            {"equipSlot": "INVTYPE_HEAD", "itemLevel": 5, "quality": 1, "tooltip": ["1 Armor"]},
            {"equipSlot": "INVTYPE_HAND", "itemLevel": 5, "quality": 1, "tooltip": ["1 Armor", "+1 Stamina"]},
            {"equipSlot": "INVTYPE_WEAPON", "tooltip": ["(1.5 damage per second)"]},
        ]
    bags = [{"bag": 0, "slots": 16, "free": 2, "items": sweep_items()},
            {"bag": 1, "slots": 6, "free": 0, "items": []}]
    me = LONGEST_NAME + "@Realm"
    alt = "Bcdefghijklm@Realm"
    return {"characters": {
        me: {"snapshot": {"takenAt": 1, "character": {"name": LONGEST_NAME, "classFile": cls, "level": level},
                          "skills": {"professions": [{"name": p, "rank": 1, "max": 75} for p in profs]},
                          "skillsModern": {"allSkills": skills}, "equipment": equipment, "bags": bags}},
        alt: {"snapshot": {"character": {"name": "Bcdefghijklm"},
                           "skills": {"professions": [{"name": "Leatherworking"}, {"name": "Blacksmithing"}]}}},
    }}, me


class RuleText(unittest.TestCase):
    def test_every_note_fits_the_tooltip(self):
        """Advice text is at most 48 characters, for every class, profession set and item kind."""
        lua = rules()
        lua.globals().DATA = None
        too_long, seen = {}, 0
        for cls in CLASSES:
            for profs in ([], ["Leatherworking", "Skinning"], ["Tailoring", "Enchanting", "First Aid", "Cooking", "Fishing"]):
                for level, worn in ((1, True), (60, True), (30, False)):
                    db, key = db_for(cls, profs, level, worn)
                    out = to_py(lua.globals().AICompanionRules.adviseAll(lua.table_from(db, recursive=True), key)[0])
                    for name, a in (out or {}).items():
                        a = a if isinstance(a, list) else [a.get(1), a.get(2), a.get(3)]
                        seen += 1
                        if len(a[1] or "") > 48:
                            too_long[a[1]] = (cls, name)
        self.assertGreater(seen, 1000)
        self.assertEqual(too_long, {}, "%d advice texts over 48 characters" % len(too_long))

    def test_silent_without_a_snapshot(self):
        lua = rules()
        R = lua.globals().AICompanionRules
        self.assertEqual(to_py(R.adviseAll(lua.table_from({"characters": {}}), "Nobody@Realm")[0]), {})


class RuleDecisions(unittest.TestCase):
    def advise(self, cls, it, profs=("Leatherworking",), level=20):
        lua = rules()
        db, key = db_for(cls, list(profs), level)
        db["characters"][key]["snapshot"]["bags"][0]["items"] = [it]
        out = to_py(lua.globals().AICompanionRules.adviseAll(lua.table_from(db, recursive=True), key)[0])
        a = (out or {}).get(it["name"])
        if a is None:
            return None
        return tuple(a) if isinstance(a, list) else (a[1], a[2], a[3])

    def test_mana_drink_for_a_warrior_is_disposed(self):
        a = self.advise("WARRIOR", item("Water", type="Consumable", subType="Food & Drink",
                                        tooltip=["Use: Restores 436 mana over 18 sec."]))
        self.assertEqual(a[0], "sell")

    def test_mana_drink_for_a_mage_is_kept(self):
        a = self.advise("MAGE", item("Water", type="Consumable", subType="Food & Drink",
                                     tooltip=["Use: Restores 436 mana over 18 sec."]))
        self.assertEqual(a[0], "carry")

    def test_recipe_above_skill_goes_to_bank(self):
        a = self.advise("HUNTER", item("Pattern X", type="Recipe", tooltip=["Requires Leatherworking (80)"]))
        self.assertEqual(a[:2], ("bank", "Learn at Leatherworking 80; you are at 1."))

    def test_recipe_for_an_alt_is_mailed(self):
        a = self.advise("HUNTER", item("Plans X", type="Recipe", tooltip=["Requires Blacksmithing (80)"]))
        self.assertEqual(a[:2], ("mail", "To Bcdefghijklm, for Blacksmithing."))

    def test_unknown_item_gets_no_advice(self):
        self.assertIsNone(self.advise("HUNTER", item("Odd Thing", type="Miscellaneous", subType="Other")))

    def test_lighter_armor_is_not_judged(self):
        self.assertIsNone(self.advise("HUNTER", item("Cloth Cap", type="Armor", subType="Cloth", equipSlot="INVTYPE_HEAD",
                                                     tooltip=["10 Armor"])))


if __name__ == "__main__":
    unittest.main()
