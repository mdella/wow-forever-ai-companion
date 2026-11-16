"""Checks the add-on and the stand-in client against the real Forever client's API.

tests/forever/api_names.json lists every function, event and key enum that an in-game dump
of the Forever client found (from the ForeverAPI project, MIT licence; see tests/forever/LICENSE).
Refresh it after a game patch.
"""

import json
import os
import re
import sys
import unittest

from lupa import lua51

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import ADDONS, MOCK, ROOT, toc_files, to_py  # noqa: E402

with open(os.path.join(ROOT, "tests", "forever", "api_names.json"), encoding="utf-8") as f:
    FOREVER = json.load(f)
PRESENT = {"verified", "undocumented"}

# Calls that are absent on Forever on purpose: Classic-era fallbacks, each guarded so the
# add-on degrades to no output. They never run on Forever.
CLASSIC_FALLBACKS = {
    "QueryAuctionItems", "GetNumAuctionItems", "CanSendAuctionQuery", "GetAuctionItemInfo", "GetItemInfo",
    "GetFactionInfo", "GetNumFactions", "GetNumSkillLines", "GetSkillLineInfo", "GetMerchantItemInfo",
    "GetPetHappiness", "UnitCharacterPoints",
}
CLASSIC_EVENTS = {"AUCTION_ITEM_LIST_UPDATE"}
# Blizzard functions written in Lua, which the dump of C functions does not list.
LUA_UI_FUNCTIONS = {"TooltipDataProcessor.AddTooltipPostCall"}
LUA_BUILTINS = {
    "assert", "error", "ipairs", "next", "pairs", "pcall", "print", "rawget", "rawset", "select", "setmetatable",
    "getmetatable", "tonumber", "tostring", "type", "unpack", "xpcall", "loadstring", "date", "time",
}


def addon_sources():
    out = {}
    for addon in ("AICompanion_Data", "AICompanion"):
        for fname in toc_files(addon)[0]:
            with open(os.path.join(ADDONS, addon, fname), encoding="utf-8") as f:
                out[fname] = f.read()
    return out


def strip_strings_and_comments(src):
    src = re.sub(r"--\[\[.*?\]\]", "", src, flags=re.S)
    src = re.sub(r"--[^\n]*", "", src)
    return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', src)


def game_calls(src):
    """Game functions the source calls: C_X.Y anywhere, and capitalised globals called or passed to try()."""
    code = strip_strings_and_comments(src)
    defined = set(re.findall(r"\blocal\s+function\s+([A-Za-z_]\w*)", code))
    defined |= set(re.findall(r"\bfunction\s+([A-Za-z_]\w*)\s*\(", code))   # the add-on's own global functions
    defined |= set(re.findall(r"\blocal\s+([A-Za-z_][\w,\s]*?)\s*=", code) and
                   [n.strip() for m in re.findall(r"\blocal\s+([A-Za-z_][\w,\s]*?)\s*=", code) for n in m.split(",")])
    names = set(re.findall(r"\b(C_\w+\.\w+)\b", code))
    names |= set(re.findall(r"\b(TooltipDataProcessor\.\w+)\b", code))
    names |= {n for n in re.findall(r"(?<![.:\w])([A-Z]\w*)\s*\(", code) if n not in defined}
    names |= {n for n in re.findall(r"\btry\(\s*([A-Z]\w*)\s*[,)]", code) if n not in defined}
    return names


def registered_events(src):
    code = strip_strings_and_comments(src)
    events = set(re.findall(r"handlers\.([A-Z][A-Z_]+)\b", code))
    block = re.search(r"REFRESH_EVENTS\s*=\s*\{(.*?)\}", src, flags=re.S)
    events |= set(re.findall(r'"([A-Z_]+)"', block.group(1))) if block else set()
    return events


class AddonUsesOnlyForeverAPI(unittest.TestCase):
    def test_every_game_function_exists_in_forever(self):
        missing = {}
        for fname, src in addon_sources().items():
            for name in game_calls(src):
                if name in LUA_BUILTINS or name in LUA_UI_FUNCTIONS or name in CLASSIC_FALLBACKS:
                    continue
                if FOREVER["functions"].get(name) not in PRESENT:
                    missing.setdefault(fname, []).append(name)
        self.assertEqual(missing, {}, "game functions the Forever client does not have")

    def test_classic_fallbacks_really_are_absent(self):
        """If Forever gains one of these, the fallback list is stale: review it."""
        present = sorted(n for n in CLASSIC_FALLBACKS if FOREVER["functions"].get(n) in PRESENT)
        self.assertEqual(present, [])

    def test_every_event_exists_in_forever(self):
        src = addon_sources()["AICompanion.lua"]
        events = registered_events(src)
        self.assertIn("PLAYER_CAMPING", events)
        missing = sorted(e for e in events - CLASSIC_EVENTS if FOREVER["events"].get(e) not in PRESENT)
        self.assertEqual(missing, [])


class StandInClientMatchesForever(unittest.TestCase):
    """The stand-in client must not offer anything the real client lacks, or tests would lie."""

    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().WORLD = self.lua.table()
        before = set(self.lua.globals().keys())
        with open(MOCK, encoding="utf-8") as f:
            self.lua.execute(f.read())
        g = self.lua.globals()
        self.defined = {}
        for k in set(g.keys()) - before:
            v = g[k]
            if lua51.lua_type(v) == "function":
                self.defined[k] = "function"
            elif lua51.lua_type(v) == "table" and str(k).startswith("C_"):
                for fk in v.keys():
                    if lua51.lua_type(v[fk]) == "function":
                        self.defined["%s.%s" % (k, fk)] = "function"

    def test_mock_functions_exist_in_forever(self):
        harness_only = {"time", "date", "print", "GetTime", "issecretvalue"}
        fake = sorted(n for n in self.defined if n not in harness_only and FOREVER["functions"].get(n) not in PRESENT
                      and n not in LUA_UI_FUNCTIONS)
        self.assertEqual(fake, [])

    def test_mock_enums_match_forever(self):
        enum = to_py(self.lua.globals().Enum)
        for name, real in FOREVER["enums"].items():
            if name in enum:
                mine = enum[name]
                wrong = {k: (v, real.get(k)) for k, v in mine.items() if real.get(k) != v}
                self.assertEqual(wrong, {}, "Enum.%s differs from Forever" % name)


if __name__ == "__main__":
    unittest.main()
