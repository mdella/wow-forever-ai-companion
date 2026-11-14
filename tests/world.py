"""A made-up level 20 Hunter used by the tests. No real character or account data."""

HEARTHSTONE, JUNK, LEATHER, LINEN, NEW_BOW, OLD_BOW, PLATE_HELM, MEAT, ARROWS, PATTERN, VEST = (
    6948, 1001, 2318, 2589, 1003, 1004, 1005, 1006, 1007, 1008, 1009)

ITEMS = {
    HEARTHSTONE: dict(name="Hearthstone", quality=1, type="Miscellaneous", subType="Junk", sellPrice=0,
                      tooltip=["Soulbound", "Use: Returns you to Testtown."]),
    JUNK: dict(name="Broken Fang", quality=0, type="Miscellaneous", subType="Junk", sellPrice=15, maxStack=5),
    LEATHER: dict(name="Light Leather", quality=1, type="Trade Goods", subType="Leather", sellPrice=15, maxStack=20,
                  tooltip=["Crafting Reagent"]),
    LINEN: dict(name="Linen Cloth", quality=1, type="Trade Goods", subType="Cloth", sellPrice=13, maxStack=20,
                tooltip=["Crafting Reagent"]),
    NEW_BOW: dict(name="Hunting Bow", quality=2, type="Weapon", subType="Bows", equipLoc="INVTYPE_RANGED",
                  itemLevel=22, requiredLevel=17, sellPrice=420,
                  tooltip=[("Ranged", "Bow"), ("11 - 21 Damage", "Speed 2.80"), "(5.7 damage per second)", "Requires Level 17"]),
    OLD_BOW: dict(name="Worn Shortbow", quality=1, type="Weapon", subType="Bows", equipLoc="INVTYPE_RANGED",
                  itemLevel=5, sellPrice=10,
                  tooltip=[("Ranged", "Bow"), ("2 - 5 Damage", "Speed 2.30"), "(1.5 damage per second)"]),
    PLATE_HELM: dict(name="Battleworn Plate Helm", quality=2, type="Armor", subType="Plate", equipLoc="INVTYPE_HEAD",
                     itemLevel=24, requiredLevel=40, sellPrice=380, tooltip=[("Head", "Plate"), "210 Armor"]),
    MEAT: dict(name="Roasted Boar Meat", quality=1, type="Consumable", subType="Food & Drink", sellPrice=6, maxStack=20,
               tooltip=["Use: Restores 243 health over 21 sec. Must remain seated while eating."]),
    ARROWS: dict(name="Rough Arrow", quality=1, type="Projectile", subType="Arrow", equipLoc="INVTYPE_AMMO",
                 sellPrice=0, maxStack=200),
    PATTERN: dict(name="Pattern: Fine Leather Belt", quality=1, type="Recipe", subType="Leatherworking", sellPrice=250,
                  tooltip=["Requires Leatherworking (80)"]),
    VEST: dict(name="Rough Leather Vest", quality=1, type="Armor", subType="Leather", equipLoc="INVTYPE_CHEST",
               itemLevel=10, sellPrice=40, tooltip=[("Chest", "Leather"), "45 Armor"]),
}


def world():
    return {
        "character": {
            "name": "Testchar", "realm": "Testrealm", "className": "Hunter", "class": "HUNTER",
            "race": "Dwarf", "faction": "Alliance", "sex": 2, "level": 20, "xp": 4100, "xpMax": 12300,
            "money": 123456,
            "professions": [
                {"name": "Leatherworking", "rank": 50, "max": 75, "skillLine": 165},
                {"name": "Skinning", "rank": 60, "max": 75, "skillLine": 393},
            ],
            "skills": [["Cloth", 8], ["Leather", 8], ["Bows", 6], ["Daggers", 6]],
        },
        "zone": "Testvale", "subZone": "Testtown", "hearth": "Testtown",
        "items": ITEMS,
        "bags": {
            0: {"slots": 16, "name": "Backpack", "items": {
                1: {"id": HEARTHSTONE, "count": 1, "bound": True},
                2: {"id": JUNK, "count": 3},
                3: {"id": LEATHER, "count": 14},
                4: {"id": LINEN, "count": 8},
                5: {"id": NEW_BOW, "count": 1},
                6: {"id": PLATE_HELM, "count": 1},
                7: {"id": MEAT, "count": 12},
                8: {"id": PATTERN, "count": 1},
            }},
            1: {"slots": 6, "name": "Small Brown Pouch", "items": {
                1: {"id": ARROWS, "count": 200},
            }},
        },
        "equipment": {18: OLD_BOW, 5: VEST},
        "quests": [
            {"title": "Testvale", "header": True},
            {"id": 501, "title": "Boar Trouble", "level": 18,
             "objectives": [{"text": "Boar killed: 4/10", "finished": False, "numFulfilled": 4, "numRequired": 10}]},
        ],
        "completedQuests": [100, 101, 102],
        "questTitles": {100: "First Steps", 101: "Second Steps"},
        "auctionListings": {
            "Light Leather": {"price": 40, "quantity": 120},
            "Battleworn Plate Helm": {"price": 4500, "quantity": 2},
        },
    }
