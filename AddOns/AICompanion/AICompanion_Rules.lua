-- AI Companion rules: item advice worked out from the character snapshot alone, with no AI involved.
-- Pure functions over the saved snapshot, so the same code can be checked outside the game.
-- A rule returns nothing when it cannot be sure; no advice is better than wrong advice.

AICompanionRules = { version = 1 }
local R = AICompanionRules

-- Which professions consume each kind of trade good (the game's own item sub-category).
local CONSUMERS = {
    ["Cooking"] = { "Cooking" },
    ["Leather"] = { "Leatherworking" },
    ["Herb"] = { "Alchemy" },
    ["Cloth"] = { "Tailoring", "First Aid" },
    ["Metal & Stone"] = { "Blacksmithing", "Engineering" },
    ["Enchanting"] = { "Enchanting" },
    ["Parts"] = { "Engineering" },
    ["Devices"] = { "Engineering" },
    ["Explosives"] = { "Engineering" },
}

-- Which Well Fed stats matter to each class. Anything else is treated as a spare food.
local FOOD_STATS = {
    HUNTER = { ["Attack Power"] = true, ["Agility"] = true },
    ROGUE = { ["Attack Power"] = true, ["Agility"] = true, ["Strength"] = true },
    WARRIOR = { ["Attack Power"] = true, ["Strength"] = true, ["Stamina"] = true },
    PALADIN = { ["Attack Power"] = true, ["Strength"] = true, ["Stamina"] = true, ["Intellect"] = true },
    SHAMAN = { ["Attack Power"] = true, ["Strength"] = true, ["Intellect"] = true, ["Agility"] = true },
    DRUID = { ["Attack Power"] = true, ["Strength"] = true, ["Intellect"] = true, ["Agility"] = true },
    MAGE = { ["Intellect"] = true, ["Spirit"] = true },
    PRIEST = { ["Intellect"] = true, ["Spirit"] = true },
    WARLOCK = { ["Intellect"] = true, ["Spirit"] = true, ["Stamina"] = true },
}
local NO_MANA = { WARRIOR = true, ROGUE = true }
local CLOTH_ONLY = { MAGE = true, PRIEST = true, WARLOCK = true }
local WEAPON_DPS_CLASSES = { WARRIOR = true, ROGUE = true, HUNTER = true, PALADIN = true }
local ARMOR_KINDS = { Cloth = 1, Leather = 2, Mail = 3, Plate = 4 }
local KEEP_FOOD = 20
local TIGHT_BAGS = 6

local function list(t) return type(t) == "table" and t or {} end

local function money(c)
    c = math.floor(tonumber(c) or 0)
    local g, s, cp = math.floor(c / 10000), math.floor((c % 10000) / 100), c % 100
    local parts = {}
    if g > 0 then parts[#parts + 1] = g .. " gold" end
    if s > 0 then parts[#parts + 1] = s .. " silver" end
    if cp > 0 or #parts == 0 then parts[#parts + 1] = cp .. " copper" end
    return table.concat(parts, " ")
end
R.money = money

local function tipFind(item, pattern)
    for _, line in ipairs(list(item.tooltip)) do
        if type(line) == "string" then
            local a, b = line:match(pattern)
            if a then return a, b end
        end
    end
end

local function tipHas(item, text)
    for _, line in ipairs(list(item.tooltip)) do
        if type(line) == "string" and line:find(text, 1, true) then return true end
    end
    return false
end

local function slotGroup(equipSlot)
    if equipSlot == "INVTYPE_ROBE" then return "INVTYPE_CHEST" end
    if equipSlot == "INVTYPE_RANGEDRIGHT" or equipSlot == "INVTYPE_THROWN" then return "INVTYPE_RANGED" end
    if equipSlot == "INVTYPE_2HWEAPON" or equipSlot == "INVTYPE_WEAPONMAINHAND" then return "INVTYPE_WEAPON" end
    return equipSlot
end

local function firstName(key) return (tostring(key):match("^([^@]+)")) or tostring(key) end
local function realmOf(key) return tostring(key):match("@(.+)$") end

-- Everything the rules need to know about one character, read from the saved data.
function R.context(db, charKey)
    local store = type(db) == "table" and type(db.characters) == "table" and db.characters[charKey] or nil
    local s = type(store) == "table" and store.snapshot or nil
    if type(s) ~= "table" or type(s.character) ~= "table" then return nil end
    local c = s.character
    local ctx = {
        name = c.name or firstName(charKey), class = c.classFile, level = tonumber(c.level) or 1, faction = c.faction,
        takenAt = s.takenAt, profs = {}, armor = nil, weapons = nil, equipped = {}, others = {},
        prices = {}, foods = {}, freeSlots = 0, bagCount = 0, smallestBag = nil, counts = {},
    }
    for _, p in ipairs(list(type(s.skills) == "table" and s.skills.professions)) do
        if type(p) == "table" and p.name then ctx.profs[p.name] = { rank = tonumber(p.rank) or 0, max = tonumber(p.max) or 0 } end
    end
    local all = type(s.skillsModern) == "table" and s.skillsModern.allSkills or nil
    if type(all) == "table" and #all > 0 then
        ctx.armor, ctx.weapons = {}, {}
        for _, k in ipairs(all) do
            if type(k) == "table" and not k.isHeader and k.name then
                if k.skillLineCategoryID == 8 then ctx.armor[k.name] = true end
                if k.skillLineCategoryID == 6 then ctx.weapons[k.name] = true end
            end
        end
    end
    for _, e in pairs(list(s.equipment)) do
        if type(e) == "table" and e.equipSlot then
            local g = slotGroup(e.equipSlot)
            ctx.equipped[g] = ctx.equipped[g] or {}
            table.insert(ctx.equipped[g], e)
        end
    end
    for _, b in ipairs(list(s.bags)) do
        if type(b) == "table" then
            local special = b.bag == 5 or (type(b.name) == "string" and (b.name:find("Quiver") or b.name:find("Ammo") or b.name:find("Reagent")))
            if not special then ctx.freeSlots = ctx.freeSlots + (tonumber(b.free) or 0) end
            if b.bag and b.bag >= 1 and b.bag <= 4 then
                ctx.bagCount = ctx.bagCount + 1
                local n = tonumber(b.slots)
                if not special and n and (not ctx.smallestBag or n < ctx.smallestBag) then ctx.smallestBag = n end
            end
            for _, it in ipairs(list(b.items)) do
                if type(it) == "table" and it.name then ctx.counts[it.name] = (ctx.counts[it.name] or 0) + (tonumber(it.count) or 1) end
            end
        end
    end
    -- the player's other characters on the same realm and faction (for mailing)
    for key, st in pairs(db.characters) do
        local os = type(st) == "table" and st.snapshot or nil
        if key ~= charKey and type(os) == "table" and type(os.character) == "table" and realmOf(key) == realmOf(charKey)
            and (os.character.faction == nil or ctx.faction == nil or os.character.faction == ctx.faction) then
            local o = { name = os.character.name or firstName(key), profs = {} }
            for _, p in ipairs(list(type(os.skills) == "table" and os.skills.professions)) do
                if type(p) == "table" and p.name then o.profs[p.name] = true end
            end
            table.insert(ctx.others, o)
        end
        local a = type(st) == "table" and st.auction or nil
        if type(a) == "table" and type(a.results) == "table" then
            for name, r in pairs(a.results) do
                if type(r) == "table" and type(r.checkedAt) == "number" and not r.error then
                    local cur = ctx.prices[name]
                    if not cur or r.checkedAt > cur.checkedAt then ctx.prices[name] = r end
                end
            end
        end
    end
    table.sort(ctx.others, function(a, b) return a.name < b.name end)
    -- Well Fed foods carried, to decide which one is worth keeping
    local wanted = FOOD_STATS[ctx.class or ""] or {}
    for _, b in ipairs(list(s.bags)) do
        for _, it in ipairs(list(type(b) == "table" and b.items)) do
            if type(it) == "table" and it.subType == "Food & Drink" and tipHas(it, "well fed") then
                local amount, stat = tipFind(it, "gain (%d+) ([%a ]-) for")
                local f = ctx.foods[it.name] or { count = 0 }
                f.count = f.count + (tonumber(it.count) or 1)
                f.stat, f.amount, f.wanted = stat, tonumber(amount) or 0, stat ~= nil and wanted[stat] == true
                ctx.foods[it.name] = f
            end
        end
    end
    ctx.bestFood, ctx.wantedFoodCount = nil, 0
    for name, f in pairs(ctx.foods) do
        if f.wanted then
            ctx.wantedFoodCount = ctx.wantedFoodCount + f.count
            local best = ctx.bestFood and ctx.foods[ctx.bestFood]
            if not best or f.amount > best.amount or (f.amount == best.amount and name < ctx.bestFood) then ctx.bestFood = name end
        end
    end
    return ctx
end

-- Tooltip advice text is at most this long.
local MAX_NOTE = 48
R.MAX_NOTE = MAX_NOTE

-- Add the first hint that still fits in the tooltip, or none.
local function fitHint(text, ...)
    for i = 1, select("#", ...) do
        local hint = select(i, ...)
        if #text + #hint <= MAX_NOTE then return text .. hint end
    end
    return text
end

-- Last resort for text that is still too long: cut at a word boundary.
local function fitNote(text)
    if type(text) ~= "string" or #text <= MAX_NOTE then return text end
    local cut = text:sub(1, MAX_NOTE - 3):match("^(.*%S)%s") or text:sub(1, MAX_NOTE - 3)
    return (cut:gsub("[%s%p]+$", "")) .. "..."
end

-- Sell to a vendor or list on the auction house, for something the character has no use for.
local function dispose(ctx, item, why)
    local vendor = tonumber(item.sellPriceEach) or 0
    if item.bound then
        if vendor <= 0 then return nil end
        return "sell", why
    end
    local p = ctx.prices[item.name]
    if type(p) == "table" and p.found and type(p.minPrice) == "number" then
        if p.minPrice * 0.95 >= vendor * 2 and p.minPrice > 0 then
            return "auction", why
        end
        if vendor <= 0 then return nil end
        return "sell", why
    end
    if vendor <= 0 then return nil end
    if (tonumber(item.quality) or 0) >= 2 then
        return "auction", fitHint(why, " Check the price first.", " Check price.")
    end
    return "sell", why
end

local function hasConsumer(profs, kinds)
    for _, p in ipairs(kinds) do if profs[p] then return p end end
end

local function gearRule(ctx, item)
    local slot = item.equipSlot
    if type(slot) ~= "string" or slot == "" or slot:find("NON_EQUIP") then return nil end
    local sub = item.subType or ""
    -- gathering tools
    if sub == "Fishing Pole" then
        if ctx.profs["Fishing"] then return "carry", "Needed for Fishing.", "tool" end
        return dispose(ctx, item, "You have no Fishing.")
    end
    if item.type == "Weapon" and sub == "Miscellaneous" then return "carry", "Profession tool.", "tool" end
    if slot == "INVTYPE_BAG" then
        local n = tonumber((tipFind(item, "(%d+) Slot")))
        if not n then return nil end
        if ctx.bagCount < 4 then return "equip", n .. " slots, and a bag slot is empty.", "bag" end
        if ctx.smallestBag and n > ctx.smallestBag then return "equip", n .. " slots. Replaces your " .. ctx.smallestBag .. "-slot bag.", "bag" end
        if ctx.smallestBag then return dispose(ctx, item, "No bigger than your bags.") end
        return nil
    end
    if slot == "INVTYPE_AMMO" or slot == "INVTYPE_QUIVER" then return nil end
    if item.type ~= "Armor" and item.type ~= "Weapon" then return nil end
    -- can this character use it?
    if item.type == "Armor" and ARMOR_KINDS[sub] and slot ~= "INVTYPE_CLOAK" then
        if ctx.armor then
            if not ctx.armor[sub] then return dispose(ctx, item, sub .. " armor; you can't wear it.") end
        elseif CLOTH_ONLY[ctx.class or ""] then
            if sub ~= "Cloth" then return dispose(ctx, item, sub .. " armor; you can't wear it.") end
        else
            return nil
        end
        local best = 0
        for kind in pairs(ctx.armor or {}) do if (ARMOR_KINDS[kind] or 0) > best then best = ARMOR_KINDS[kind] end end
        if best > 0 and ARMOR_KINDS[sub] < best then return nil end   -- lighter armor than the class wears: do not judge
    elseif item.type == "Armor" and sub == "Shields" then
        if not ctx.armor then return nil end
        if not ctx.armor["Shield"] and not ctx.armor["Shields"] then return dispose(ctx, item, "You can't use shields.") end
    elseif item.type == "Weapon" then
        if not ctx.weapons then return nil end
        if not ctx.weapons[sub] then return dispose(ctx, item, "You have no " .. sub .. " skill.") end
        if not WEAPON_DPS_CLASSES[ctx.class or ""] then return nil end   -- casters choose weapons for stats, not damage
    end
    local need = tonumber(item.requiredLevel) or 0
    local worn = ctx.equipped[slotGroup(slot)]
    if item.type == "Weapon" then
        local dps = tonumber((tipFind(item, "%(([%d%.]+) damage per second%)")))
        if not dps then return nil end
        if not worn or #worn == 0 then
            if need > ctx.level then return "carry", "Equip at level " .. need .. "; that slot is empty.", "gear" end
            return "equip", "That weapon slot is empty.", "gear"
        end
        local wdps = tonumber((tipFind(worn[1], "%(([%d%.]+) damage per second%)")))
        if not wdps then return nil end
        if dps > wdps then
            if need > ctx.level then return "carry", "Equip at level " .. need .. ": " .. dps .. " DPS vs " .. wdps .. ".", "gear" end
            return "equip", dps .. " DPS vs " .. wdps .. " equipped.", "gear"
        end
        return dispose(ctx, item, dps .. " DPS vs " .. wdps .. " equipped.")
    end
    -- armor: compare with the weakest piece worn in that slot
    if slot == "INVTYPE_FINGER" or slot == "INVTYPE_TRINKET" or slot == "INVTYPE_NECK" or sub == "Miscellaneous" then return nil end
    if not worn or #worn == 0 then
        if need > ctx.level then return "carry", "Equip at level " .. need .. "; that slot is empty.", "gear" end
        return "equip", "Nothing worn in that slot.", "gear"
    end
    local w = worn[1]
    local a, wa = tonumber((tipFind(item, "^(%d+) Armor"))), tonumber((tipFind(w, "^(%d+) Armor")))
    local il, wil = tonumber(item.itemLevel) or 0, tonumber(w.itemLevel) or 0
    local hasStats = tipHas(item, "+") or tipHas(w, "+")
    if hasStats then
        if il > wil + 2 and (tonumber(item.quality) or 0) >= (tonumber(w.quality) or 0) then
            if need > ctx.level then return "carry", "Equip at level " .. need .. ": item level " .. il .. " vs " .. wil .. ".", "gear" end
            return "equip", "Item level " .. il .. " vs " .. wil .. " worn. Compare stats.", "gear"
        end
        if il + 2 < wil then return dispose(ctx, item, "Item level " .. il .. " vs " .. wil .. " worn.") end
        return nil
    end
    if a and wa then
        if a > wa then
            if need > ctx.level then return "carry", "Equip at level " .. need .. ": " .. a .. " armor vs " .. wa .. ".", "gear" end
            return "equip", a .. " armor vs " .. wa .. " worn. Then sell the old one.", "gear"
        end
        return dispose(ctx, item, a .. " armor vs " .. wa .. " worn.")
    end
    return nil
end

local function foodRule(ctx, item)
    if tipHas(item, "mana") and not tipHas(item, "health") then
        if NO_MANA[ctx.class or ""] then return dispose(ctx, item, "Mana drink; your class has no mana.") end
        return "carry", "Restores mana between fights.", "drink"
    end
    local f = ctx.foods[item.name]
    if f then
        if not ctx.bestFood then return "carry", "Well Fed: +5% XP from kills for 15 min.", "food" end
        if item.name == ctx.bestFood then
            local extra = f.count - KEEP_FOOD
            return "carry", "Best food: " .. f.amount .. " " .. tostring(f.stat) .. "."
                .. (extra > 0 and (" Keep " .. KEEP_FOOD .. "; vendor " .. extra .. ".") or ""), "food"
        end
        local best = ctx.foods[ctx.bestFood]
        if f.wanted and ctx.foods[ctx.bestFood].count < KEEP_FOOD then
            return "carry", f.amount .. " " .. tostring(f.stat) .. ". Reserve food.", "food"
        end
        if not tipHas(item, "experience") or (best and ctx.wantedFoodCount >= 5) then
            return dispose(ctx, item, tostring(f.stat or "Its stat") .. " is no use to you; you carry better.")
        end
        return "carry", "Well Fed: +5% XP from kills for 15 min.", "food"
    end
    if tipHas(item, "health") then
        if ctx.bestFood and ctx.wantedFoodCount >= 5 then return dispose(ctx, item, "No buff; you carry better food.") end
        return "carry", "Plain food. Eat between fights.", "food"
    end
    return nil
end

local function recipeRule(ctx, item)
    if tipHas(item, "Already known") then return dispose(ctx, item, "Already known.") end
    local prof, rank = tipFind(item, "Requires ([%a ]-) %((%d+)%)")
    if not prof then return nil end
    local mine = ctx.profs[prof]
    if mine then
        if mine.rank >= (tonumber(rank) or 0) then return "use", "Learn it now (needs " .. prof .. " " .. rank .. ").", "recipe" end
        return "bank", "Learn at " .. prof .. " " .. rank .. "; you are at " .. mine.rank .. ".", "recipe"
    end
    if not item.bound then
        for _, o in ipairs(ctx.others) do
            if o.profs[prof] then return "mail", "To " .. o.name .. ", for " .. prof .. ".", "recipe" end
        end
    end
    return dispose(ctx, item, "None of your characters has " .. prof .. ".")
end

local function tradeRule(ctx, item)
    if not tipHas(item, "Crafting Reagent") then return nil end
    local kinds = CONSUMERS[item.subType or ""]
    if not kinds then return nil end
    local mine = hasConsumer(ctx.profs, kinds)
    if mine then
        if ctx.freeSlots < TIGHT_BAGS then
            return "bank", mine .. " material; bags are nearly full.", "trade"
        end
        return "carry", mine .. " material.", "trade"
    end
    if not item.bound then
        for _, o in ipairs(ctx.others) do
            local theirs = hasConsumer(o.profs, kinds)
            if theirs then return "mail", "To " .. o.name .. ", for " .. theirs .. ".", "trade" end
        end
    end
    return dispose(ctx, item, "None of your characters uses it.")
end

-- Advice for one item record from the snapshot. Returns action, note, rule name; or nothing.
function R.advise(ctx, item)
    if type(ctx) ~= "table" or type(item) ~= "table" or not item.name then return nil end
    local t, sub, q = item.type or "", item.subType or "", tonumber(item.quality) or 1
    if item.itemID == 6948 or item.name == "Hearthstone" then return "carry", "Your way home.", "hearthstone" end
    if t == "Quest" or tipHas(item, "Quest Item") then return "quest", "Quest item.", "quest" end
    local a, n, rule = gearRule(ctx, item)
    if a then return a, n, rule or "gear" end
    if t == "Armor" or t == "Weapon" or t == "Container" then
        return nil
    end
    if t == "Projectile" then
        local w = ctx.weapons
        if not w then return nil end
        if (sub == "Arrow" and (w["Bows"] or w["Crossbows"])) or (sub == "Bullet" and w["Guns"]) then return "carry", "Ammunition for your weapon.", "ammo" end
        return dispose(ctx, item, "For a weapon you can't use.")
    end
    if t == "Recipe" then
        a, n, rule = recipeRule(ctx, item)
        if a then return a, n, rule or "recipe" end
        return nil
    end
    if q == 0 then
        if (tonumber(item.sellPriceEach) or 0) > 0 then return "sell", "Poor quality. Nothing uses it.", "junk" end
        return nil
    end
    if t == "Consumable" then
        local classes = tipFind(item, "^Classes: (.+)$")
        if classes and ctx.class then
            local mine = false
            for word in classes:gmatch("[^,]+") do
                if word:gsub("%s", ""):upper() == ctx.class then mine = true end
            end
            if not mine then
                a, n = dispose(ctx, item, "Only usable by " .. classes .. ".")
                if a then return a, n, "class" end
                return nil
            end
        end
        if sub == "Food & Drink" then
            a, n, rule = foodRule(ctx, item)
            if a then return a, n, rule or "food" end
            return nil
        end
        if sub == "Potions" then return "carry", "Emergency use; put it on a bar.", "potion" end
        if sub == "Bandages" then
            if ctx.profs["First Aid"] then return "carry", "Use between pulls.", "bandage" end
            return nil
        end
        if sub == "Elixirs" or sub == "Scrolls" then return "carry", "Use it when it helps; don't hoard it.", "buff" end
        return nil
    end
    if t == "Trade Goods" or t == "Reagent" then
        a, n, rule = tradeRule(ctx, item)
        if a then return a, n, rule or "trade" end
        return nil
    end
    return nil
end

-- Advice for everything the character carries or has banked, by item name.
function R.adviseAll(db, charKey)
    local ctx = R.context(db, charKey)
    if not ctx then return {}, nil end
    local out = {}
    local store = db.characters[charKey]
    local function run(bags)
        for _, b in ipairs(list(bags)) do
            for _, it in ipairs(list(type(b) == "table" and b.items)) do
                if type(it) == "table" and it.name and not out[it.name] then
                    local ok, a, n, rule = pcall(R.advise, ctx, it)
                    if ok and a then out[it.name] = { a, fitNote(n), rule } end
                end
            end
        end
    end
    run(store.snapshot.bags)
    run(type(store.bank) == "table" and store.bank.bags or nil)
    return out, ctx
end
