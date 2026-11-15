"""The in-game companion panel (issue #2): plan content, self-ticking steps, minimap button."""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import ROOT, Game, to_py  # noqa: E402
from test_addon import GameTest  # noqa: E402
import world as W  # noqa: E402

PLAN = {
    "roster": ["Testchar Test"],
    "sources": {
        "fsrc": {"label": "Forever site: page", "url": "https://example.com/forever"},
        "old": {"label": "Old wiki: page", "url": "https://example.com/classic", "scope": "classic"},
    },
    "characters": {"Testchar": {
        "headline": "Level 20 hunter. Finish Boar Trouble, then train.",
        "next": [
            {"id": "t-bow", "title": "Equip the Hunting Bow", "detail": "5.7 DPS.", "tag": "game", "done": {"equipped": "Hunting Bow"}},
            {"id": "t-boar", "title": "Finish Boar Trouble", "tag": "lookup", "source": "fsrc", "done": {"questDone": "Boar Trouble"}},
            {"id": "t-first", "title": "First Steps", "tag": "game", "done": {"questDone": "First Steps"}},
            {"id": "t-eat", "title": "Eat before the fight", "tag": "judgment"},
            {"id": "t-lw", "title": "Leatherworking 50", "tag": "game", "done": {"skill": ["Leatherworking", 50]}},
            {"id": "t-lw60", "title": "Leatherworking 60", "tag": "classic", "source": "old", "done": {"skill": ["Leatherworking", 60]}},
            {"id": "t-junk", "title": "Sell the fangs", "tag": "game", "done": {"notInBags": ["Broken Fang"]}},
            {"id": "t-all", "title": "Old bow and space", "tag": "game", "done": {"all": [{"equipped": "Worn Shortbow"}, {"freeSlots": 10}]}},
            {"id": "t-rec", "title": "Open Leatherworking", "tag": "game", "done": {"captured": "recipes:Leatherworking"}},
            {"id": "t-odd", "title": "A rule from a newer plan", "tag": "unverified", "done": {"somethingNew": 1}},
        ],
        "questing": [{"title": "Testvale", "note": "In this order.", "steps": [
            {"id": "q1", "title": "Boar Trouble", "tag": "lookup", "source": "fsrc", "done": {"questDone": "Boar Trouble"}}]}],
        "professions": {"Leatherworking": {"status": "50 of 75.", "next": "Train Journeyman in Testtown.", "tag": "classic", "source": "old"}},
        "gear": [{"id": "g1", "title": "Ranged: Hunting Bow", "tag": "game", "done": {"equipped": "Hunting Bow"}}],
        "talents": {"note": "5 points in Marksmanship.", "suggestion": "Next: Improved Concussive Shot.", "tag": "judgment"},
        "bags": "Two free slots in the pouch.",
        "blindspots": [{"text": "Open your Leatherworking window once.", "done": {"captured": "recipes:Leatherworking"}}],
        "items": {"Light Leather": {"action": "bank", "tip": "For Leatherworking 55+."}},
    }},
}


def data_file(plan=PLAN):
    d = tempfile.mkdtemp()
    src, out = os.path.join(d, "plans.json"), os.path.join(d, "AICompanion_Data.lua")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    subprocess.run([sys.executable, os.path.join(ROOT, "companion/gen_data.py"), src, out], check=True, capture_output=True)
    with open(out, encoding="utf-8") as f:
        return f.read()


OLD_DATA_FILE = '''AICompanionShopping = {}
AICompanionAdvice = { asOf = "Nov 1", characters = {} }
'''


class PanelTest(GameTest):
    def panel(self, g):
        return g.ns["AICompanion"].panel

    def model(self, g):
        return to_py(self.panel(g).currentModel()[0])

    def steps(self, g, section="next"):
        return {l["id"]: l for l in self.model(g)["sections"][section] if l.get("id")}

    def open(self, g):
        g.slash("/aic panel")
        return g.lua.globals().AICompanionPanel


class Content(PanelTest):
    def test_steps_tick_themselves_from_the_snapshot(self):
        g = self.game(data_source=data_file())
        st = self.steps(g)
        done = {k: (v["auto"], v["done"]) for k, v in st.items()}
        self.assertEqual(done, {
            "t-bow": (True, False), "t-boar": (True, False), "t-first": (True, True), "t-eat": (False, False),
            "t-lw": (True, True), "t-lw60": (True, False), "t-junk": (True, False), "t-all": (True, True),
            "t-rec": (True, False), "t-odd": (False, False),
        })
        self.assertEqual([l["number"] for l in self.model(g)["sections"]["next"]], list(range(1, 11)))  # doing order kept

    def test_source_labels(self):
        g = self.game(data_source=data_file())
        st = self.steps(g)
        self.assertEqual((st["t-boar"]["tag"], st["t-boar"]["source"]), ("Forever source", "Source: Forever site: page"))
        self.assertEqual((st["t-lw60"]["tag"], st["t-lw60"]["source"]), ("Original-game source", "Original-game source: Old wiki: page"))
        self.assertEqual(st["t-eat"]["tag"], "My judgment")
        self.assertEqual(st["t-odd"]["tag"], "Not verified")

    def test_steps_update_as_you_play(self):
        g = self.game(data_source=data_file())
        self.assertFalse(self.steps(g)["t-bow"]["done"])
        w = g.world
        w["equipment"][18] = W.NEW_BOW
        g.set("equipment", w["equipment"])
        g.fire("PLAYER_EQUIPMENT_CHANGED")
        g.advance(6)
        self.assertTrue(self.steps(g)["t-bow"]["done"])
        self.assertFalse(self.steps(g)["t-all"]["done"])   # no longer wearing the old bow

    def test_captured_window_ticks_the_step_and_clears_the_blindspot(self):
        g = self.game(data_source=data_file())
        self.assertEqual(self.model(g)["blindspots"], ["Open your Leatherworking window once."])
        g.set("tradeSkill", {"profession": "Leatherworking", "recipes": [{"id": 1, "name": "Light Armor Kit"}]})
        g.fire("TRADE_SKILL_LIST_UPDATE")
        self.assertTrue(self.steps(g)["t-rec"]["done"])
        self.assertEqual(self.model(g).get("blindspots") or [], [])

    def test_other_sections(self):
        g = self.game(data_source=data_file())
        m = self.model(g)
        q = m["sections"]["questing"]
        self.assertEqual((q[0]["kind"], q[0]["title"], q[0]["detail"]), ("heading", "Testvale", "In this order."))
        self.assertEqual(q[1]["title"], "Boar Trouble")
        prof = m["sections"]["professions"]
        self.assertEqual(prof[0]["title"], "Leatherworking 50/75")
        self.assertEqual(prof[1]["title"], "Next: Train Journeyman in Testtown.")
        self.assertEqual(prof[1]["source"], "Original-game source: Old wiki: page")
        self.assertFalse(m["sections"]["gear"][0]["done"])
        self.assertEqual(m["sections"]["talents"][0]["title"], "5 points in Marksmanship.")
        self.assertEqual(m["bagsNote"], "Two free slots in the pouch.")

    def test_items_grouped_by_action(self):
        g = self.game(data_source=data_file())
        groups = [(grp["action"], [i["name"] for i in grp["items"]]) for grp in self.model(g)["sections"]["items"]]
        self.assertEqual(groups, [
            ("sell", ["Broken Fang", "Linen Cloth"]),
            ("auction", ["Battleworn Plate Helm"]),
            ("bank", ["Light Leather", "Pattern: Fine Leather Belt"]),
            ("equip", ["Hunting Bow"]),
            ("carry", ["Hearthstone", "Roasted Boar Meat", "Rough Arrow"]),
        ])
        leather = next(i for grp in self.model(g)["sections"]["items"] for i in grp["items"] if i["name"] == "Light Leather")
        self.assertEqual((leather["note"], leather["rule"]), ("For Leatherworking 55+.", False))

    def test_no_plan_shows_rule_advice_only(self):
        g = self.game(data_source=OLD_DATA_FILE)       # a data file from before plans existed
        m = self.model(g)
        self.assertFalse(m["hasPlan"])
        self.assertIn("No plan for Testchar yet", m["headline"])
        self.assertEqual(m["sections"]["items"][0]["action"], "sell")
        self.assertTrue(m["sections"]["items"][0]["items"][0]["rule"])
        self.open(g)
        rows = to_py(g.lua.globals().AICompanionPanel.lastRows)
        self.assertEqual(rows[0]["text"], "No plan for this character yet.")

    def test_plan_for_another_character_is_not_shown(self):
        plan = json.loads(json.dumps(PLAN))
        plan["characters"] = {"Someoneelse": plan["characters"]["Testchar"]}
        g = self.game(data_source=data_file(plan))
        self.assertFalse(self.model(g)["hasPlan"])


class Window(PanelTest):
    def test_opens_and_closes(self):
        g = self.game(data_source=data_file())
        f = self.open(g)
        self.assertTrue(f.shown)
        rows = to_py(f.lastRows)
        self.assertEqual(rows[0]["text"], "1. Equip the Hunting Bow")
        self.assertEqual(rows[0]["sub"], "5.7 DPS.  [From your game data]")
        self.assertEqual(rows[2]["text"], "3. First Steps  (done)")
        self.assertIn("Level 20 hunter", f.headline.text)
        self.assertIn("Snapshot", f.footer.text)
        g.slash("/aic panel")
        self.assertFalse(f.shown)

    def test_tabs(self):
        g = self.game(data_source=data_file())
        f = self.open(g)
        for key, first in (("questing", "Testvale"), ("professions", "Leatherworking 50/75"), ("gear", "Ranged: Hunting Bow"),
                           ("talents", "5 points in Marksmanship."), ("items", "Sell to vendor")):
            self.panel(g).select(key)
            self.assertEqual(to_py(f.lastRows)[0]["text"], first, key)

    def test_escape_closes_it(self):
        g = self.game(data_source=data_file())
        self.open(g)
        self.assertIn("AICompanionPanel", to_py(g.lua.globals().UISpecialFrames))

    def test_does_not_open_in_combat(self):
        g = self.game(data_source=data_file())
        g.set("inCombat", True)
        g.slash("/aic panel")
        self.assertTrue(any("opens after combat" in l for l in g.chat()))
        self.assertFalse(self.panel(g).isShown())

    def test_manual_tick_is_remembered_per_character(self):
        g = self.game(data_source=data_file())
        self.open(g)
        g.lua.execute("Mock.lastTicks = nil")
        model, ticks = self.panel(g).currentModel()
        ticks["t-eat"] = True
        self.assertTrue(self.steps(g)["t-eat"]["done"])
        g.slash("/aic save")
        self.assertTrue(self.steps(g)["t-eat"]["done"])
        self.assertTrue(g.disk()["panel"]["ticks"]["Testchar@Testrealm"]["t-eat"])

    def test_tick_box_click(self):
        g = self.game(data_source=data_file())
        f = self.open(g)
        g.lua.execute('''
            for _, fr in ipairs(Mock.frames) do
                if fr.kind == "CheckButton" and fr.shown and fr.enabled ~= false then
                    fr:SetChecked(true); fr.scripts.OnClick(fr); break
                end
            end''')
        self.assertTrue(self.steps(g)["t-eat"]["done"])

    def test_self_ticking_steps_cannot_be_ticked_by_hand(self):
        g = self.game(data_source=data_file())
        self.open(g)
        enabled = g.lua.eval('''(function()
            local n = 0
            for _, fr in ipairs(Mock.frames) do
                if fr.kind == "CheckButton" and fr.shown and fr.enabled ~= false then n = n + 1 end
            end
            return n end)()''')
        self.assertEqual(enabled, 2)   # "Eat before the fight" and the step with an unknown rule

    def test_position_and_size_are_remembered(self):
        g = self.game(data_source=data_file())
        f = self.open(g)
        g.lua.execute('''
            local f = AICompanionPanel
            f:SetSize(600, 700); f:SetPoint("TOPLEFT", UIParent, "TOPLEFT", 40, -60)
            f.scripts.OnDragStop(f)''')
        g.slash("/aic save")
        f = self.open(g)
        self.assertEqual((f.width, f.height), (600, 700))
        self.assertEqual(to_py(f.point)[2:], ["TOPLEFT", 40, -60])

    def test_refreshes_while_open(self):
        g = self.game(data_source=data_file())
        f = self.open(g)
        g.set("tradeSkill", {"profession": "Leatherworking", "recipes": [{"id": 1, "name": "Light Armor Kit"}]})
        g.fire("TRADE_SKILL_LIST_UPDATE")
        g.advance(6)
        row = next(r for r in to_py(f.lastRows) if r["text"].startswith("9."))
        self.assertTrue(row["text"].endswith("(done)"))
        g.slash("/aic panel")
        g.advance(30)   # the refresh timer stops with the window


class MinimapButton(PanelTest):
    def button(self, g):
        return g.lua.globals().AICompanionMinimapButton

    def test_click_opens_the_panel(self):
        g = self.game(data_source=data_file())
        b = self.button(g)
        b.scripts.OnClick(b)
        self.assertTrue(self.panel(g).isShown())

    def test_drag_moves_it_around_the_minimap_and_is_remembered(self):
        g = self.game(data_source=data_file())
        b = self.button(g)
        g.lua.execute('''
            local b = AICompanionMinimapButton
            b.scripts.OnDragStart(b)
            Mock.cursorX, Mock.cursorY = 700, 600   -- straight above the minimap centre (700, 500)
            b.scripts.OnUpdate(b)
            b.scripts.OnDragStop(b)''')
        self.assertAlmostEqual(g.db()["panel"]["minimapAngle"], 90)
        self.assertIsNone(b.scripts.OnUpdate)
        g.slash("/aic save")
        p = to_py(self.button(g).point)
        self.assertEqual(p[0], "CENTER")
        self.assertAlmostEqual(p[3], 0, places=6)
        self.assertAlmostEqual(p[4], 80)

    def test_default_position(self):
        g = self.game(data_source=data_file())
        p = to_py(self.button(g).point)
        self.assertLess(p[3], 0)
        self.assertLess(p[4], 0)   # lower left of the minimap until moved


class AddonMenu(PanelTest):
    def test_registers_when_the_client_has_the_menu(self):
        g = Game(W.world(), data_source=data_file())
        self.games.append(g)
        g.lua_prelude = '''AddonCompartmentFrame = M.widget("Frame", "AddonCompartmentFrame")
            function AddonCompartmentFrame:RegisterAddon(info) Mock.compartment = info end'''
        g.start()
        self.assertEqual(g.db()["panelCompartment"], "registered")
        info = g.M.compartment
        self.assertEqual(info["text"], "AI Companion")
        info["func"]()
        self.assertTrue(self.panel(g).isShown())

    def test_quiet_without_it(self):
        g = self.game(data_source=data_file())
        self.assertEqual(g.db()["panelCompartment"], "not available")

    def test_quiet_if_registration_fails(self):
        g = Game(W.world(), data_source=data_file())
        self.games.append(g)
        g.lua_prelude = '''AddonCompartmentFrame = M.widget("Frame", "AddonCompartmentFrame")
            function AddonCompartmentFrame:RegisterAddon() error("not supported") end'''
        g.start()
        self.assertEqual(g.db()["panelCompartment"], "not available")


class DataFile(PanelTest):
    def test_generator_writes_plans_in_plain_ascii(self):
        plan = json.loads(json.dumps(PLAN))
        plan["characters"]["Testchar"]["headline"] = "Go to Testtown — then “train” | now"
        text = data_file(plan)
        self.assertTrue(all(ord(c) < 128 for c in text))
        g = self.game(data_source=text)
        self.assertEqual(self.model(g)["headline"], 'Go to Testtown ,  then "train" / now')

    def test_example_plan_still_generates(self):
        with open(os.path.join(ROOT, "companion/plans.example.json"), encoding="utf-8") as f:
            text = data_file(json.load(f))
        self.assertIn("AICompanionPlans", text)
