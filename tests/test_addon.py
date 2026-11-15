"""Scenario tests: the add-on running in the stand-in Forever client.

Run from the repository root:  python3 -m unittest discover -s tests -v
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import ROOT, Game, to_py  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tools"))
import set_interface  # noqa: E402

INTERFACE = set_interface.read_source()          # the supported Forever interface, e.g. "16001"
NEXT_INTERFACE = str(int(INTERFACE) + 1)          # a later release, for the follow-the-release tests
import world as W  # noqa: E402


def snapshot(source):
    return next(iter(source["characters"].values()))["snapshot"]


def bag_items(snap):
    return {i["name"]: i.get("count") for b in snap["bags"] for i in b.get("items", [])}


class GameTest(unittest.TestCase):
    """Every scenario ends by checking the client saw no Lua errors, refused calls or stray globals."""

    def setUp(self):
        self.games = []

    def game(self, world=None, **kw):
        g = Game(world or W.world(), **kw)
        self.games.append(g)
        return g.start()

    def tearDown(self):
        for g in self.games:
            if g.lua is not None:
                g.check_clean()


class Login(GameTest):
    def test_loads_and_greets(self):
        g = self.game()
        self.assertTrue(any("ready" in line for line in g.chat()))
        db = g.db()
        self.assertEqual(db["tooltipHook"], "ok")
        self.assertEqual(db["addonVersion"], self._toc_version())

    def test_version_matches_in_both_places(self):
        with open(os.path.join(ROOT, "AddOns/AICompanion/AICompanion.lua"), encoding="utf-8") as f:
            lua_version = next(l.split('"')[1] for l in f if l.startswith("local VERSION"))
        self.assertEqual(lua_version, self._toc_version())

    def _toc_version(self):
        with open(os.path.join(ROOT, "AddOns/AICompanion/AICompanion.toc"), encoding="utf-8") as f:
            return next(l.split(":", 1)[1].strip() for l in f if l.startswith("## Version:"))

    def test_login_snapshot_contents(self):
        g = self.game()
        s = g.char()["snapshot"]
        self.assertEqual(s["reason"], "login")
        c = s["character"]
        self.assertEqual((c["name"], c["classFile"], c["level"], c["money"]), ("Testchar", "HUNTER", 20, 123456))
        self.assertEqual(c["moneyText"], "12g 34s 56c")
        self.assertEqual(s["location"]["zone"], "Testvale")
        items = bag_items(s)
        self.assertEqual(items["Light Leather"], 14)
        self.assertEqual(items["Rough Arrow"], 200)
        self.assertEqual({b["bag"]: b["free"] for b in s["bags"]}, {0: 8, 1: 5})
        self.assertEqual({e["slotName"] for e in s["equipment"]}, {"Ranged", "Chest"})
        self.assertEqual([q["title"] for q in s["quests"]], ["Boar Trouble"])
        self.assertEqual(s["quests"][0]["category"], "Testvale")
        self.assertEqual(s["completedQuests"]["count"], 3)
        self.assertEqual(s["completedQuests"]["untitled"], 1)
        self.assertEqual({p["name"] for p in s["skills"]["professions"]}, {"Leatherworking", "Skinning"})
        self.assertEqual(s["client"]["interface"], int(INTERFACE))

    def test_item_records_carry_tooltip_and_price(self):
        g = self.game()
        bow = next(i for b in g.char()["snapshot"]["bags"] for i in b["items"] if i["name"] == "Hunting Bow")
        self.assertEqual((bow["itemID"], bow["quality"], bow["qualityName"]), (W.NEW_BOW, 2, "Uncommon"))
        self.assertEqual((bow["equipSlot"], bow["sellPriceEachText"]), ("INVTYPE_RANGED", "4s 20c"))
        self.assertIn("(5.7 damage per second)", bow["tooltip"])
        self.assertIn("Ranged  |  Bow", bow["tooltip"])

    def test_missing_interfaces_degrade_to_errors_not_crashes(self):
        g = Game(W.world())
        self.games.append(g)
        g.start()
        g.lua.execute("C_QuestLog = nil; C_SkillInfo = nil; C_TooltipInfo = nil; GetProfessions = nil")
        g.slash("/aic")
        s = g.char()["snapshot"]
        self.assertIn("quests", s["errors"])
        self.assertIn("quests", s["stale"])  # kept from the login snapshot
        self.assertEqual([q["title"] for q in s["quests"]], ["Boar Trouble"])
        self.assertEqual(bag_items(s)["Light Leather"], 14)

    def test_no_container_interface_at_all(self):
        g = Game(W.world())
        self.games.append(g)
        g.start()
        g.lua.execute("C_Container = nil")
        g.slash("/aic")
        s = g.char()["snapshot"]
        self.assertIn("bags", s["errors"])
        self.assertIn("bags", s["stale"])

    def test_hidden_values_are_marked_not_saved(self):
        w = W.world()
        w["items"][W.LEATHER]["tooltip"] = ["Crafting Reagent", "Secret line"]
        w["secrets"] = {"Secret line": True}
        g = self.game(w)
        leather = next(i for b in g.char()["snapshot"]["bags"] for i in b["items"] if i["name"] == "Light Leather")
        self.assertIn("<hidden>", leather["tooltip"])
        self.assertNotIn("Secret line", leather["tooltip"])


class Snapshots(GameTest):
    def test_event_triggers_snapshot_after_a_pause(self):
        g = self.game()
        g.world["character"]["money"] = 200000
        g.set("character", g.world["character"])
        g.fire("PLAYER_MONEY")
        g.advance(2)
        self.assertEqual(g.char()["snapshot"]["character"]["money"], 123456)  # waits 5 seconds
        g.advance(4)
        s = g.char()["snapshot"]
        self.assertEqual((s["reason"], s["character"]["money"]), ("auto", 200000))

    def test_many_events_make_one_snapshot(self):
        g = self.game()
        before = g.char()["snapshot"]["takenAt"]
        for _ in range(30):
            g.fire("BAG_UPDATE_DELAYED")
            g.advance(0.1)
        g.advance(6)
        after = g.char()["snapshot"]
        self.assertEqual(after["reason"], "auto")
        self.assertGreater(after["takenAt"], before)

    def test_no_snapshot_in_combat_then_one_after(self):
        g = self.game()
        g.set("inCombat", True)
        g.fire("PLAYER_MONEY")
        g.advance(10)
        self.assertEqual(g.char()["snapshot"]["reason"], "login")
        g.set("inCombat", False)
        g.fire("PLAYER_REGEN_ENABLED")
        g.advance(6)
        self.assertEqual(g.char()["snapshot"]["reason"], "auto")

    def test_periodic_snapshot_every_two_minutes(self):
        g = self.game()
        g.advance(125)
        self.assertEqual(g.char()["snapshot"]["reason"], "periodic")

    def test_manual_snapshot(self):
        g = self.game()
        g.slash("/aic")
        self.assertEqual(g.char()["snapshot"]["reason"], "manual")
        self.assertTrue(any("snapshot taken: 9 bag items, 1 active quests, 3 completed quests" in l for l in g.chat()))


class SaveAndReload(GameTest):
    def test_save_writes_snapshot_to_disk(self):
        g = self.game()
        self.assertIsNone(g.disk())  # nothing on disk before the first reload
        g.slash("/aic save")
        self.assertEqual(g.reloads, 1)
        disk = g.disk()
        self.assertEqual(snapshot(disk)["character"]["name"], "Testchar")
        self.assertEqual(bag_items(snapshot(disk))["Light Leather"], 14)
        self.assertEqual(disk["lastCharacter"], "Testchar@Testrealm")

    def test_question_survives_reload(self):
        g = self.game()
        g.slash("/aic ask where do I train skinning?")
        g.slash("/aic save")
        qs = g.disk()["questions"]
        self.assertEqual(qs[0]["text"], "where do I train skinning?")
        self.assertEqual(qs[0]["character"], "Testchar@Testrealm")

    def test_reload_is_never_requested_outside_a_typed_command(self):
        g = self.game()
        g.advance(600)
        self.assertFalse(g.M.reloadRequested)

    def test_copy_window(self):
        g = self.game()
        g.slash("/aic copy")
        text = g.lua.eval("AICompanionCopyFrame.editBox.text")
        self.assertIn("Testchar: level 20 Dwarf Hunter (Alliance)", text)
        self.assertIn("Light Leather x14", text)

    def test_help(self):
        g = self.game()
        g.slash("/aic help")
        self.assertTrue(any("/aic save" in l for l in g.chat()))


class Logout(GameTest):
    def test_logout_keeps_the_last_good_snapshot(self):
        g = self.game()
        g.logout()
        disk = g.disk()
        s = snapshot(disk)
        self.assertEqual(s["reason"], "logout started")
        self.assertEqual(s["character"]["money"], 123456)
        self.assertEqual(bag_items(s)["Light Leather"], 14)
        self.assertEqual(disk["lastSkipped"]["why"], "character data not loaded")
        # Only the leaving-world attempt is made while data is unloading; PLAYER_LOGOUT never tries.
        self.assertEqual(disk["lastSkipped"]["reason"], "leaving world")
        self.assertIn("lastLogoutText", disk)

    def test_instant_logout_in_an_inn(self):
        g = self.game()
        g.logout(countdown=0)
        s = snapshot(g.disk())
        self.assertEqual(bag_items(s)["Light Leather"], 14)

    def test_logout_in_combat_keeps_older_snapshot(self):
        g = self.game()
        g.set("inCombat", True)
        g.logout()
        s = snapshot(g.disk())
        self.assertEqual(s["reason"], "login")
        self.assertEqual(bag_items(s)["Light Leather"], 14)

    def test_next_login_starts_from_disk(self):
        g = self.game()
        g.slash("/aic ask hello")
        g.logout()
        g.login()
        self.assertEqual(g.db()["questions"][0]["text"], "hello")
        self.assertEqual(g.char()["snapshot"]["reason"], "login")


class Windows(GameTest):
    def test_bank_capture(self):
        w = W.world()
        w["bank"] = {-1: {"slots": 24, "name": "Bank", "items": {1: {"id": W.LINEN, "count": 20}}},
                     5: {"slots": 8, "name": "Linen Bag", "items": {2: {"id": W.JUNK, "count": 1}}}}
        g = self.game(w)
        g.set("bankOpen", True)
        g.fire("BANKFRAME_OPENED")
        g.advance(1)
        bank = g.char()["bank"]
        names = {i["name"] for b in bank["bags"] for i in b["items"]}
        self.assertEqual(names, {"Linen Cloth", "Broken Fang"})

    def test_recipe_capture(self):
        g = self.game()
        g.set("tradeSkill", {"profession": "Leatherworking", "recipes": [
            {"id": 2149, "name": "Handstitched Leather Boots", "difficulty": 1},
            {"id": 2152, "name": "Light Armor Kit", "difficulty": 0, "available": 3}]})
        g.fire("TRADE_SKILL_LIST_UPDATE")
        rec = g.char()["recipes"]["Leatherworking"]["recipes"]
        self.assertEqual([r["name"] for r in rec], ["Handstitched Leather Boots", "Light Armor Kit"])
        self.assertEqual(rec[1]["numAvailable"], 3)


class Auction(GameTest):
    def run_check(self, g, seconds=60):
        g.M.openAuction()
        self.assertTrue(any("auction house open" in l for l in g.chat()))
        g.lua.globals().AICompanionAuctionButton.Click(g.lua.globals().AICompanionAuctionButton)
        g.advance(seconds)

    def test_full_price_check(self):
        g = self.game()
        self.run_check(g)
        a = g.char()["auction"]
        queried = [q["search"] for q in g.auction_queries()]
        self.assertNotIn("Hearthstone", queried)  # soulbound
        self.assertEqual(sorted(queried), sorted(set(queried)))  # each name once
        self.assertEqual(len(queried), 8)
        self.assertTrue(all(q["qualityFilters"] for q in g.auction_queries()))
        self.assertEqual(a["lastRun"]["ended"], "finished")
        self.assertEqual((a["lastRun"]["checked"], a["lastRun"]["found"]), (8, 2))
        r = a["results"]["Light Leather"]
        self.assertEqual((r["found"], r["minPrice"], r["quantity"], r["carried"]), (True, 40, 120, 14))
        self.assertFalse(a["results"]["Broken Fang"]["found"])

    def test_queries_respect_the_throttle(self):
        g = self.game()
        self.run_check(g)
        times = [q["at"] for q in g.auction_queries()]
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(gap >= 1.0 for gap in gaps), gaps)

    def test_slow_server_with_a_strict_throttle(self):
        w = W.world()
        w["auctionThrottle"], w["auctionAnswerDelay"] = 3.0, 2.5
        g = self.game(w)
        self.run_check(g, seconds=120)
        self.assertEqual(g.char()["auction"]["lastRun"]["checked"], 8)

    def test_unanswered_search_moves_on(self):
        w = W.world()
        w["auctionSilent"] = {"Light Leather": True}
        g = self.game(w)
        self.run_check(g)
        a = g.char()["auction"]
        self.assertEqual(a["results"]["Light Leather"]["error"], "no answer from the auction house")
        self.assertEqual(a["lastRun"]["checked"], 8)
        self.assertTrue(a["results"]["Battleworn Plate Helm"]["found"])

    def test_closing_the_window_stops_the_check(self):
        g = self.game()
        g.M.openAuction()
        g.slash("/aic ah")
        g.advance(2.5)
        g.M.closeAuction()
        sent = len(g.auction_queries())
        g.advance(30)
        self.assertEqual(len(g.auction_queries()), sent)
        self.assertIn("stopped early", g.char()["auction"]["lastRun"]["ended"])

    def test_button_sits_under_the_window_without_touching_it(self):
        g = self.game()
        g.M.openAuction()
        b = g.lua.globals().AICompanionAuctionButton
        self.assertTrue(g.lua.eval("AICompanionAuctionButton.parent == UIParent"))
        p = to_py(b.point)
        self.assertEqual((p[0], p[2], p[3], p[4]), ("TOPRIGHT", "BOTTOMLEFT", 1096, 196))   # under the bottom right corner
        g.M.closeAuction()
        self.assertFalse(b.shown)
        g.M.openAuction()
        self.assertTrue(b.shown)

    def test_second_start_while_running_is_refused(self):
        g = self.game()
        g.M.openAuction()
        g.slash("/aic ah")
        g.slash("/aic ah")
        self.assertTrue(any("already running" in l for l in g.chat()))
        g.advance(60)

    def test_results_reach_disk_on_save(self):
        g = self.game()
        self.run_check(g)
        g.slash("/aic save")
        r = g.char(g.disk())["auction"]["results"]["Light Leather"]
        self.assertEqual(r["minPrice"], 40)

    def test_shopping_list_is_checked_first(self):
        data = 'AICompanionShopping = { ["Testchar"] = { "Coarse Thread" } }\nAICompanionAdvice = { characters = {} }\n'
        g = self.game(data_source=data)
        self.run_check(g)
        self.assertEqual(g.auction_queries()[0]["search"], "Coarse Thread")
        self.assertEqual(g.char()["auction"]["results"]["Coarse Thread"]["kind"], "shopping")


class Tooltips(GameTest):
    def assert_short(self, lines):
        content = [l for l in lines if (l[0] or "").strip()]
        self.assertLessEqual(len(content), 3, lines)
        for left, _ in content:
            if not left.startswith("AI Companion") and not left.startswith("Auction"):
                self.assertLessEqual(len(left), 48, left)

    def test_rule_advice(self):
        g = self.game()
        lines = g.hover(W.LEATHER)
        self.assertEqual(lines[1], ("AI Companion: Keep in bags", "rule"))
        self.assertEqual(lines[2][0], "Leatherworking material.")
        self.assert_short(lines)

    def test_junk(self):
        g = self.game()
        lines = g.hover(W.JUNK)
        self.assertEqual(lines[1][0], "AI Companion: Sell to vendor")
        self.assert_short(lines)

    def test_better_bow(self):
        g = self.game()
        lines = g.hover(W.NEW_BOW)
        self.assertEqual(lines[1][0], "AI Companion: Equip now")
        self.assertEqual(lines[2][0], "5.7 DPS vs 1.5 equipped.")

    def test_every_carried_item_stays_short(self):
        g = self.game()
        for item_id in W.ITEMS:
            self.assert_short(g.hover(item_id))

    def test_price_line_after_auction_check(self):
        g = self.game()
        Auction.run_check(self, g)
        lines = g.hover(W.LEATHER)
        self.assertEqual(lines[-1], ("Auction 40c (120 listed, just now)", "vendor 15c"))
        self.assert_short(lines)
        g.advance(7200)
        self.assertIn("2h ago", g.hover(W.LEATHER)[-1][0])

    def test_nothing_known_means_nothing_added(self):
        g = self.game()
        self.assertEqual(g.hover(99999), [])

    def test_silent_in_combat(self):
        g = self.game()
        g.set("inCombat", True)
        self.assertEqual(g.hover(W.LEATHER), [])

    def test_companion_advice_from_generated_data(self):
        out = os.path.join(tempfile.mkdtemp(), "AICompanion_Data.lua")
        subprocess.run([sys.executable, os.path.join(ROOT, "companion/gen_data.py"),
                        os.path.join(ROOT, "companion/plans.example.json"), out], check=True, capture_output=True)
        with open(out, encoding="utf-8") as f:
            data = f.read()
        w = W.world()
        w["character"]["name"] = "Firstname"
        g = self.game(w, data_source=data)
        lines = g.hover(W.HEARTHSTONE)
        self.assertEqual(lines[1][0], "AI Companion: Keep in bags")
        self.assertNotEqual(lines[1][1], "rule")      # the date the advice was written
        self.assertEqual(lines[2][0], "Set to Goldshire.")
        lines = g.hover(W.LEATHER)                    # companion advice wins over the rule
        self.assertEqual(lines[1][0], "AI Companion: Put in bank")
        self.assertEqual(lines[2][0], "For Leatherworking 55+.")


QUIVER = 1090
SORTED_ORDER = ["Broken Fang", "Linen Cloth", "Battleworn Plate Helm", "Pattern: Fine Leather Belt",
                "Hearthstone", "Light Leather", "Roasted Boar Meat", "Rough Arrow", "Hunting Bow"]


def sort_world():
    """The test character with a quiver (a special bag) and a split stack of leather."""
    w = W.world()
    w["items"][W.ARROWS]["family"] = 1
    w["bags"][2] = {"slots": 4, "name": "Light Quiver", "family": 1, "items": {2: {"id": W.ARROWS, "count": 200}}}
    w["bags"][1]["items"][3] = {"id": W.LEATHER, "count": 5}
    return w


class BagSort(GameTest):
    def layout(self, g, bag=None):
        """(bag, slot, name, count) for every item, in bag order."""
        out = []
        bags = g.lua.globals().WORLD.bags
        for b in sorted(bags.keys()):
            if bag is not None and b != bag:
                continue
            slots = bags[b]["items"]
            for s in sorted(slots.keys()) if slots is not None else []:
                it = slots[s]
                out.append((b, s, W.ITEMS[it["id"]]["name"], it["count"] or 1))
        return out

    def contents(self, g):
        totals = {}
        for _, _, name, count in self.layout(g):
            totals[name] = totals.get(name, 0) + count
        return totals

    def names_in_order(self, g):
        seen = []
        for b, _, name, _ in self.layout(g):
            if b != 2 and (not seen or seen[-1] != name):
                seen.append(name)
        return seen

    def test_groups_items_by_action(self):
        g = self.game(sort_world())
        before = self.contents(g)
        g.slash("/aic sort")
        g.advance(30)
        self.assertEqual(self.names_in_order(g), SORTED_ORDER)
        self.assertEqual(self.contents(g), before)                     # nothing lost or merged away
        self.assertTrue(any("bags sorted by advice" in l for l in g.chat()))
        bags = [b for b, *_ in self.layout(g) if b != 2]
        self.assertEqual([s for _, s, *_ in self.layout(g, 0)], list(range(1, 11)))
        self.assertEqual(bags, [0] * 10)                               # 10 stacks, packed into the backpack first

    def test_special_bags_are_left_alone(self):
        g = self.game(sort_world())
        g.slash("/aic sort")
        g.advance(30)
        self.assertEqual(self.layout(g, 2), [(2, 2, "Rough Arrow", 200)])

    def test_two_stacks_of_one_item_are_kept_apart(self):
        g = self.game(sort_world())
        g.slash("/aic sort")
        g.advance(30)
        leather = sorted(c for _, _, n, c in self.layout(g) if n == "Light Leather")
        self.assertEqual(leather, [5, 14])

    def test_sorting_twice_changes_nothing(self):
        g = self.game(sort_world())
        g.slash("/aic sort")
        g.advance(30)
        first, moves = self.layout(g), g.M.moves
        g.slash("/aic sort")
        g.advance(30)
        self.assertEqual(self.layout(g), first)
        self.assertEqual(g.M.moves, moves)

    def test_companion_advice_decides_the_group(self):
        data = 'AICompanionShopping = {}\nAICompanionAdvice = { asOf = "Nov 15", characters = { ["Testchar"] = { ["Hunting Bow"] = { "sell", "Vendor it." } } } }\n'
        g = self.game(sort_world(), data_source=data)
        g.slash("/aic sort")
        g.advance(30)
        self.assertEqual(self.names_in_order(g)[:3], ["Broken Fang", "Hunting Bow", "Linen Cloth"])

    def test_refused_in_combat(self):
        g = self.game(sort_world())
        g.set("inCombat", True)
        g.slash("/aic sort")
        g.advance(10)
        self.assertEqual(g.M.moves, 0)
        self.assertTrue(any("can't sort bags in combat" in l for l in g.chat()))

    def test_stops_when_combat_starts(self):
        g = self.game(sort_world())
        before = self.contents(g)
        g.slash("/aic sort")
        g.advance(0.25)
        g.set("inCombat", True)
        g.fire("PLAYER_REGEN_DISABLED")
        moves = g.M.moves
        g.advance(30)
        self.assertEqual(g.M.moves, moves)
        self.assertEqual(self.contents(g), before)
        self.assertTrue(any("you entered combat" in l for l in g.chat()))

    def test_stops_when_combat_starts_before_the_game_says_so(self):
        g = self.game(sort_world())
        g.slash("/aic sort")
        g.advance(0.25)
        g.set("inCombat", True)          # combat has begun; PLAYER_REGEN_DISABLED not yet delivered
        moves = g.M.moves
        g.advance(30)
        self.assertEqual(g.M.moves, moves)
        self.assertTrue(any("you entered combat" in l for l in g.chat()))

    def test_refused_move_leaves_nothing_on_the_cursor(self):
        w = sort_world()
        w["refusePlace"] = True
        g = self.game(w)
        before = self.layout(g)
        g.slash("/aic sort")
        g.advance(10)
        self.assertEqual(self.layout(g), before)
        self.assertTrue(any("the game refused a move" in l for l in g.chat()))
        # tearDown fails the test if an item is still on the cursor

    def test_stops_when_loot_arrives_mid_sort(self):
        g = self.game(sort_world())
        g.slash("/aic sort")
        g.advance(0.25)
        g.lua.execute("WORLD.bags[0].items[16] = { id = %d, count = 1 }" % W.JUNK)   # looted mid-sort
        moves = g.M.moves
        g.advance(30)
        self.assertEqual(g.M.moves, moves)
        self.assertEqual(self.contents(g)["Broken Fang"], 4)
        self.assertTrue(any("your bags changed while sorting" in l for l in g.chat()))

    def test_refused_while_holding_an_item(self):
        g = self.game(sort_world())
        g.lua.execute("C_Container.PickupContainerItem(0, 2)")
        g.slash("/aic sort")
        self.assertTrue(any("put down the item on your cursor" in l for l in g.chat()))
        self.assertEqual(g.M.moves, 0)
        g.lua.execute("ClearCursor()")

    def test_stops_if_the_game_forbids_moves(self):
        w = sort_world()
        w["forbidMoves"] = True
        g = self.game(w)
        before = self.layout(g)
        g.slash("/aic sort")
        g.advance(10)
        self.assertEqual(self.layout(g), before)
        self.assertTrue(any("does not let add-ons move items" in l for l in g.chat()))

    def test_slow_server(self):
        w = sort_world()
        w["moveLock"] = 1.5
        g = self.game(w)
        g.slash("/aic sort")
        g.advance(120)
        self.assertEqual(self.names_in_order(g), SORTED_ORDER)

    def sort_button(self, g):
        return g.lua.globals().AICompanionSortButton

    def test_button_follows_the_open_bag_window(self):
        w = sort_world()
        w["bagFrames"] = "login"
        g = self.game(w)
        b = self.sort_button(g)
        self.assertTrue(g.lua.eval("AICompanionSortButton.parent == UIParent"))   # never a child of a bag window
        self.assertFalse(b.shown)                                                  # bags closed
        g.lua.execute("OpenAllBags()")
        g.advance(0.3)
        self.assertTrue(b.shown)
        p = to_py(b.point)
        self.assertEqual((p[0], p[2], p[3], p[4]), ("BOTTOMRIGHT", "BOTTOMLEFT", 1596, 602))   # just above the window's top right
        self.assertTrue(g.lua.eval("AICompanionSortButton.point[2] == UIParent"))
        g.lua.execute("ToggleAllBags()")
        g.advance(0.3)
        self.assertFalse(b.shown)

    def test_button_when_bag_windows_appear_late(self):
        w = sort_world()
        w["bagFrames"] = "late"
        g = self.game(w)
        self.assertFalse(self.sort_button(g).shown)
        g.lua.execute("OpenAllBags()")
        g.advance(0.3)
        self.assertTrue(self.sort_button(g).shown)

    def test_nothing_hooks_bag_opening(self):
        w = sort_world()
        w["bagFrames"] = "login"
        g = self.game(w)
        g.lua.execute("OpenAllBags() ToggleAllBags() ToggleAllBags()")
        g.advance(1)
        self.assertEqual(to_py(g.M.hooks) or [], [])

    def test_button_click_sorts(self):
        w = sort_world()
        w["bagFrames"] = "login"
        g = self.game(w)
        g.lua.execute("OpenAllBags()")
        g.advance(0.3)
        b = self.sort_button(g)
        b.scripts.OnClick(b)
        g.advance(30)
        self.assertEqual(self.names_in_order(g), SORTED_ORDER)

    def test_debug_report(self):
        w = sort_world()
        w["bagFrames"] = "login"
        g = self.game(w)
        g.lua.execute("OpenAllBags()")
        g.advance(0.3)
        g.slash("/aic sort debug")
        chat = " ".join(g.chat())
        self.assertIn("bag windows: ContainerFrameCombinedBags (open), ContainerFrame1 (closed)", chat)
        self.assertIn("sort button: shown above ContainerFrameCombinedBags", chat)
        g.slash("/aic sort")
        g.advance(30)
        g.slash("/aic save")
        debug = g.disk()["sortDebug"]
        self.assertGreater(debug["lastRun"]["moves"], 0)


class BlockedActions(GameTest):
    """Issue #15: a blocked or forbidden action is recorded so it can be traced."""

    def test_blocked_action_is_recorded(self):
        g = self.game(sort_world())
        g.slash("/aic")
        g.fire("ADDON_ACTION_BLOCKED", "AICompanion", "UseContainerItem()")
        rec = g.db()["blockedActions"][0]
        self.assertEqual((rec["event"], rec["func"], rec["inCombat"]), ("ADDON_ACTION_BLOCKED", "UseContainerItem()", False))
        self.assertTrue(rec["lastAction"].startswith("snapshot (manual)"))
        self.assertEqual(rec["addonVersion"], g.db()["addonVersion"])
        self.assertTrue(any("the game blocked UseContainerItem()" in l for l in g.chat()))
        g.slash("/aic save")
        self.assertEqual(g.disk()["blockedActions"][0]["func"], "UseContainerItem()")

    def test_says_so_once_and_keeps_the_last_twenty(self):
        g = self.game(sort_world())
        for i in range(25):
            g.fire("ADDON_ACTION_BLOCKED", "AICompanion", "F%d()" % i)
        recs = g.db()["blockedActions"]
        self.assertEqual((len(recs), recs[0]["func"], recs[-1]["func"]), (20, "F5()", "F24()"))
        self.assertEqual(len([l for l in g.chat() if "the game blocked" in l]), 1)

    def test_other_addons_are_not_recorded(self):
        g = self.game(sort_world())
        g.fire("ADDON_ACTION_BLOCKED", "SomeOtherAddon", "UseContainerItem()")
        self.assertNotIn("blockedActions", g.db())

    def test_forbidden_move_is_recorded_with_what_the_sort_was_doing(self):
        w = sort_world()
        w["forbidMoves"] = True
        g = self.game(w)
        g.slash("/aic sort")
        g.advance(5)
        rec = g.db()["blockedActions"][0]
        self.assertEqual(rec["event"], "ADDON_ACTION_FORBIDDEN")
        self.assertTrue(rec["lastAction"].startswith("sort: moving"), rec["lastAction"])

    def test_blocked_shown_in_debug_report(self):
        g = self.game(sort_world())
        g.fire("ADDON_ACTION_BLOCKED", "AICompanion", "UseContainerItem()")
        g.slash("/aic sort debug")
        self.assertTrue(any("last blocked action" in l and "UseContainerItem()" in l for l in g.chat()))


class BagSortRealTiming(GameTest):
    """Moves confirmed late and unevenly, as in the real client (issue #8)."""

    def run_sort(self, **timing):
        w = sort_world()
        w.update(timing)
        g = self.game(w)
        before = BagSort.contents(self, g)
        g.slash("/aic sort")
        g.advance(120)
        self.assertEqual(BagSort.contents(self, g), before)
        return g

    def layout(self, g, bag=None):
        return BagSort.layout(self, g, bag)

    def assert_sorted(self, g):
        self.assertEqual(BagSort.names_in_order(self, g), SORTED_ORDER)
        self.assertTrue(any("bags sorted by advice" in l for l in g.chat()), g.chat())

    def test_default_timing(self):
        self.assert_sorted(self.run_sort())

    def test_lock_clears_before_the_contents_change(self):
        self.assert_sorted(self.run_sort(moveUnlock=0.1, moveConfirm=0.4, moveSkew=0.0))

    def test_the_two_slots_of_a_swap_update_apart(self):
        self.assert_sorted(self.run_sort(moveUnlock=0.6, moveConfirm=0.2, moveSkew=0.5))

    def test_slow_server(self):
        self.assert_sorted(self.run_sort(moveUnlock=1.5, moveConfirm=1.2, moveSkew=0.6))

    def test_instant_server(self):
        self.assert_sorted(self.run_sort(moveUnlock=0.0, moveConfirm=0.0, moveSkew=0.0))

    def test_a_move_the_game_never_confirms(self):
        g = self.run_sort(moveUnlock=200, moveConfirm=200, moveSkew=0)
        line = next(l for l in g.chat() if "did not confirm a move" in l)
        self.assertIn("to bag 0 slot", line)
        g.advance(300)   # let the stand-in client finish, so nothing is left locked

    def test_real_change_is_reported_with_detail(self):
        g = self.game(sort_world())
        g.slash("/aic sort")
        g.advance(0.05)
        g.lua.execute("WORLD.bags[0].items[16] = { id = %d, count = 1 }" % W.JUNK)
        g.advance(30)
        line = next(l for l in g.chat() if "your bags changed" in l)
        self.assertIn("(bag 0 slot 16: expected empty, found Broken Fang)", line)

class WithoutDataFolder(GameTest):
    """Installing is one folder: AICompanion_Data appears only once the companion writes advice."""

    def test_runs_without_the_data_addon(self):
        g = self.game(with_data=False)
        self.assertTrue(any("ready" in line for line in g.chat()))
        self.assertIs(g.char()["snapshot"]["client"]["dataAddon"], False)
        lines = g.hover(W.LEATHER)                       # built-in rule advice still shows
        self.assertEqual(lines[1][1], "rule")
        m = to_py(g.ns["AICompanion"].panel.currentModel()[0])
        self.assertFalse(m["hasPlan"])
        self.assertIn("No plan for Testchar yet", m["headline"])
        g.slash("/aic save")                             # save and reload work too
        self.assertIs(g.char()["snapshot"]["client"]["dataAddon"], False)

    def test_snapshot_says_the_data_addon_is_loaded(self):
        g = self.game()
        self.assertIs(g.char()["snapshot"]["client"]["dataAddon"], True)


class GenDataCreatesFolder(unittest.TestCase):
    """gen_data.py creates the data add-on; its interface follows the installed AICompanion release."""

    def addons(self, installed_interface=None):
        """A temporary AddOns folder, with AICompanion's .toc if an interface is given."""
        addons = tempfile.mkdtemp()
        if installed_interface:
            os.makedirs(os.path.join(addons, "AICompanion"))
            with open(os.path.join(addons, "AICompanion", "AICompanion.toc"), "w", encoding="utf-8") as f:
                f.write("## Interface: %s\n## Title: AI Companion\n" % installed_interface)
        return addons

    def run_gen(self, addons):
        target = os.path.join(addons, "AICompanion_Data", "AICompanion_Data.lua")
        return subprocess.run([sys.executable, os.path.join(ROOT, "companion/gen_data.py"),
                               os.path.join(ROOT, "companion/plans.example.json"), target],
                              check=True, capture_output=True, text=True).stdout

    def data_toc(self, addons):
        with open(os.path.join(addons, "AICompanion_Data", "AICompanion_Data.toc"), encoding="utf-8") as f:
            return f.read()

    def test_creates_missing_folder_and_toc(self):
        addons = self.addons(INTERFACE)
        out = self.run_gen(addons)
        self.assertIn("restart the game", out)
        with open(os.path.join(ROOT, "AddOns/AICompanion_Data/AICompanion_Data.toc"), encoding="utf-8") as f:
            self.assertEqual(self.data_toc(addons), f.read())   # same as the repository's template
        self.assertTrue(os.path.exists(os.path.join(addons, "AICompanion_Data", "AICompanion_Data.lua")))
        self.assertNotIn("restart the game", self.run_gen(addons))  # second run: /reload is enough

    def test_interface_follows_the_installed_release_not_the_repository(self):
        addons = self.addons(NEXT_INTERFACE)               # an installed release the repo isn't at
        self.run_gen(addons)
        self.assertIn("## Interface: %s\n" % NEXT_INTERFACE, self.data_toc(addons))

    def test_new_release_updates_only_the_interface_line(self):
        addons = self.addons(INTERFACE)
        self.run_gen(addons)
        toc = os.path.join(addons, "AICompanion_Data", "AICompanion_Data.toc")
        with open(toc, "a", encoding="utf-8") as f:
            f.write("## X-Player-Note: keep me\n")
        with open(os.path.join(addons, "AICompanion", "AICompanion.toc"), "w", encoding="utf-8") as f:
            f.write("## Interface: %s\n" % NEXT_INTERFACE)  # the owner released a newer version
        out = self.run_gen(addons)
        self.assertIn("interface " + NEXT_INTERFACE, out)
        self.assertIn("restart the game", out)
        text = self.data_toc(addons)
        self.assertTrue(text.startswith("## Interface: %s\n" % NEXT_INTERFACE))
        self.assertNotIn(INTERFACE, text)
        self.assertIn("## X-Player-Note: keep me", text)

    def test_matching_interface_leaves_the_toc_alone(self):
        addons = self.addons(INTERFACE)
        self.run_gen(addons)
        toc = os.path.join(addons, "AICompanion_Data", "AICompanion_Data.toc")
        before = os.path.getmtime(toc)
        os.utime(toc, (before - 100, before - 100))
        self.assertNotIn("restart the game", self.run_gen(addons))
        self.assertEqual(os.path.getmtime(toc), before - 100)

    def test_without_an_installed_addon_uses_this_release(self):
        addons = self.addons()                             # AICompanion not next to the data folder
        self.run_gen(addons)
        with open(os.path.join(ROOT, "AddOns/AICompanion_Data/AICompanion_Data.toc"), encoding="utf-8") as f:
            self.assertEqual(self.data_toc(addons), f.read())

    def test_every_file_states_the_supported_interface(self):
        """FOREVER_INTERFACE is the one place it is set; tools/set_interface.py copies it everywhere."""
        self.assertEqual(set_interface.mismatches(INTERFACE), [],
                         "run: python3 tools/set_interface.py")


if __name__ == "__main__":
    unittest.main()
