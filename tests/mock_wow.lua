-- A stand-in for the World of Warcraft: Forever client, for testing the add-on outside the game.
--
-- It models only what the add-on relies on, and models it the way the add-on expects the
-- Forever client to behave (modern C_* interfaces, client interface 16001). Passing tests here
-- means the add-on is consistent with that model; it does not prove the real client agrees.
--
-- The harness sets the global WORLD (the character, bags, items, auction listings) before
-- running this file. Everything the add-on can observe is read from WORLD on each call, so a
-- test can change WORLD between events.

local W = WORLD
assert(type(W) == "table", "set WORLD before loading mock_wow.lua")

-- Capture what we need from the host Lua before the game sandbox removes it.
local osdate, floor, traceback = os.date, math.floor, debug.traceback

Mock = {
    now = W.startTime or 1794700800,   -- virtual clock, in seconds
    timers = {}, timerSeq = 0,
    frames = {},
    chat = {},                         -- everything the add-on printed
    errors = {},                       -- Lua errors the game would have shown
    violations = {},                   -- things the real game would refuse or misbehave on
    context = "load",                  -- what is running: load, event, timer, slash, tooltip
    reloadRequested = false,
    tooltipPostCalls = {},
    newGlobals = {},
    auction = { sent = {}, pending = nil, readyAt = 0 },
}
local M = Mock

local function violation(text) M.violations[#M.violations + 1] = text end
local function lerror(where, err) M.errors[#M.errors + 1] = where .. ": " .. tostring(err) end

local function run(context, where, fn, ...)
    local prev = M.context
    M.context = context
    local args, n = { ... }, select("#", ...)
    local ok, err = xpcall(function() return fn(unpack(args, 1, n)) end, traceback)
    M.context = prev
    if not ok then lerror(where, err) end
    return ok
end

-------------------------------------------------------------------------------
-- Clock and timers
-------------------------------------------------------------------------------

function time() return floor(M.now) end
function date(fmt, t) return osdate(fmt or "%c", t or floor(M.now)) end
function GetTime() return M.now end

local function schedule(delay, fn, owner)
    M.timerSeq = M.timerSeq + 1
    local t = { at = M.now + math.max(delay or 0, 0), fn = fn, seq = M.timerSeq, owner = owner }
    M.timers[#M.timers + 1] = t
    return t
end

C_Timer = {}
function C_Timer.After(delay, fn)
    if type(fn) ~= "function" then error("C_Timer.After: callback is not a function") end
    schedule(delay, fn)
end
function C_Timer.NewTicker(interval, fn, iterations)
    if type(fn) ~= "function" then error("C_Timer.NewTicker: callback is not a function") end
    local ticker = { cancelled = false, left = iterations }
    function ticker:Cancel() self.cancelled = true end
    function ticker:IsCancelled() return self.cancelled end
    local function tick()
        if ticker.cancelled then return end
        fn(ticker)
        if ticker.left then
            ticker.left = ticker.left - 1
            if ticker.left <= 0 then return end
        end
        schedule(interval, tick, ticker)
    end
    schedule(interval, tick, ticker)
    return ticker
end
C_Timer.NewTimer = function(delay, fn) return C_Timer.NewTicker(delay, fn, 1) end

-- Move the clock forward, running every timer that falls due, in order.
function M.advance(seconds)
    local target = M.now + seconds
    while true do
        local best, bi
        for i, t in ipairs(M.timers) do
            if t.at <= target and (not best or t.at < best.at or (t.at == best.at and t.seq < best.seq)) then best, bi = t, i end
        end
        if not best then break end
        table.remove(M.timers, bi)
        M.now = best.at
        run("timer", "timer", best.fn)
    end
    M.now = target
end

-------------------------------------------------------------------------------
-- Frames, events, chat, slash commands
-------------------------------------------------------------------------------

local function noop() end
local Widget = {}
Widget.__index = function(_, k) return Widget[k] or noop end
function Widget:SetScript(name, fn) self.scripts[name] = fn end
function Widget:GetScript(name) return self.scripts[name] end
function Widget:HookScript(name, fn)
    local old = self.scripts[name]
    self.scripts[name] = function(...) if old then old(...) end fn(...) end
end
function Widget:RegisterEvent(e) self.events[e] = true end
function Widget:UnregisterEvent(e) self.events[e] = nil end
function Widget:IsEventRegistered(e) return self.events[e] == true end
function Widget:SetText(t) self.text = t end
function Widget:GetText() return self.text end
function Widget:Show() self.shown = true end
function Widget:Hide() self.shown = false end
function Widget:IsShown() return self.shown == true end
function Widget:CreateFontString() return M.widget("FontString") end
function Widget:CreateTexture() return M.widget("Texture") end
function Widget:Click() local f = self.scripts.OnClick if f then run("slash", "OnClick", f, self, "LeftButton") end end

function M.widget(kind, name)
    local w = setmetatable({ kind = kind, name = name, scripts = {}, events = {}, shown = true }, Widget)
    if name then rawset(_G, name, w) end
    return w
end

function CreateFrame(kind, name, parent, template)
    local f = M.widget(kind or "Frame", name)
    f.parent, f.template = parent, template
    M.frames[#M.frames + 1] = f
    return f
end

UIParent = M.widget("Frame", "UIParent")

function M.fire(event, ...)
    for _, f in ipairs(M.frames) do
        if f.events[event] and f.scripts.OnEvent then
            run("event", event, f.scripts.OnEvent, f, event, ...)
        end
    end
end

function print(...)
    local parts = {}
    for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
    M.chat[#M.chat + 1] = table.concat(parts, " ")
end

SlashCmdList = {}
function M.slash(text)
    local cmd, rest = text:match("^(/%S+)%s*(.-)$")
    for key, fn in pairs(SlashCmdList) do
        for i = 1, 9 do
            local alias = rawget(_G, "SLASH_" .. key .. i)
            if alias == nil then break end
            if alias:lower() == cmd:lower() then return run("slash", text, fn, rest) end
        end
    end
    error("no slash command " .. tostring(cmd))
end

function ReloadUI()
    -- The real client only reloads from a key press, click or typed command.
    if M.context ~= "slash" then violation("ReloadUI called from " .. M.context .. "; the game ignores it") return end
    M.reloadRequested = true
end

function InCombatLockdown() return W.inCombat == true end

-- Values the client hides from add-ons. Only defined when a test lists some, like a client
-- without the feature.
if W.secrets then
    function issecretvalue(v) return type(v) == "string" and W.secrets[v] == true end
end

-------------------------------------------------------------------------------
-- Items
-------------------------------------------------------------------------------

local ITEMS = setmetatable({}, { __index = function(_, k) return (W.items or {})[k] end })
local QUALITY_COLOR = { [0] = "9d9d9d", "ffffff", "1eff00", "0070dd", "a335ee", "ff8000" }

local function itemIDOf(x)
    if type(x) == "number" then return x end
    if type(x) == "string" then return tonumber(x:match("item:(%d+)")) or (function()
        for id, it in pairs(W.items or {}) do if it.name == x then return id end end
    end)() end
end

function M.link(id)
    local it = ITEMS[id]
    if not it then return nil end
    return ("|cff%s|Hitem:%d::::::::|h[%s]|h|r"):format(QUALITY_COLOR[it.quality or 1] or "ffffff", id, it.name)
end

local function getItemInfo(x)
    local id = itemIDOf(x)
    local it = id and ITEMS[id]
    if not it then return nil end
    return it.name, M.link(id), it.quality or 1, it.itemLevel or 1, it.requiredLevel or 0, it.type or "Miscellaneous",
           it.subType or "Junk", it.maxStack or 1, it.equipLoc or "", 134400, it.sellPrice or 0
end

C_Item = {
    GetItemInfo = getItemInfo,
    GetItemNameByID = function(id) local it = ITEMS[itemIDOf(id)] return it and it.name end,
}

local function tooltipData(id)
    local it = ITEMS[id]
    if not it then return nil end
    local lines = { { leftText = M.link(id) and it.name } }
    for _, l in ipairs(it.tooltip or {}) do
        if type(l) == "table" then lines[#lines + 1] = { leftText = l[1], rightText = l[2] }
        else lines[#lines + 1] = { leftText = l } end
    end
    return { id = id, type = 0, lines = lines }
end

-------------------------------------------------------------------------------
-- Character
-------------------------------------------------------------------------------

local C = setmetatable({}, { __index = function(_, k) return (W.character or {})[k] end })
local function unloaded() return W.characterDataUnloaded == true end

function UnitName(unit)
    if unit == "player" then return C.name end
    if unit == "npc" then return W.npc end
    if unit == "target" then return W.target end
end
function UnitFullName(unit) if unit == "player" then return C.name, C.realm end end
function GetRealmName() return C.realm end
function UnitClass(unit) if unit == "player" then return C.className, C.class end end
function UnitRace(unit) if unit == "player" then return C.race, C.race end end
function UnitFactionGroup(unit) if unit == "player" then return C.faction, C.faction end end
function UnitSex(unit) if unit == "player" then return C.sex end end
function UnitLevel(unit) if unit == "player" then return C.level end end
function UnitXP() return C.xp or 0 end
function UnitXPMax() return C.xpMax or 1000 end
function GetXPExhaustion() return C.rested end
function IsResting() return C.resting == true end
function GetMoney() if unloaded() then return 0 end return C.money or 0 end
function UnitExists(unit) return unit == "player" end
function UnitIsDeadOrGhost() return false end
function GetRealZoneText() return W.zone end
function GetZoneText() return W.zone end
function GetSubZoneText() return W.subZone end
function GetBindLocation() return W.hearth end
function GetBuildInfo() return "1.16.1", "99999", "Nov 1 2026", 16001 end
function GetLocale() return "enUS" end

function GetProfessions()
    local p = C.professions or {}
    local idx = {}
    for i = 1, #p do idx[i] = i end
    return unpack(idx)
end
function GetProfessionInfo(i)
    local p = (C.professions or {})[i]
    if not p then return nil end
    return p.name, 0, p.rank, p.max, 0, 0, p.skillLine or 0
end

-- Armor and weapon proficiencies, read by the rules (category 8 = armor, 6 = weapons).
C_SkillInfo = {
    GetNumSkillLines = function() return #(C.skills or {}) end,
    GetSkillLineInfo = function(i)
        local s = (C.skills or {})[i]
        if not s then return nil end
        return { name = s[1], skillLineCategoryID = s[2], isHeader = false }
    end,
}

-------------------------------------------------------------------------------
-- Bags, bank and equipment
-------------------------------------------------------------------------------

NUM_TOTAL_EQUIPPED_BAG_SLOTS = 4
local BAGS = setmetatable({}, { __index = function(_, k) return (W.bags or {})[k] end })

local function bag(b)
    if unloaded() then return nil end
    if b < 0 or b > NUM_TOTAL_EQUIPPED_BAG_SLOTS then
        if not W.bankOpen then return nil end
        return (W.bank or {})[b]
    end
    return BAGS[b]
end

C_Container = {}
function C_Container.GetContainerNumSlots(b) local x = bag(b) return x and x.slots or 0 end
function C_Container.GetBagName(b) local x = bag(b) return x and x.name end
function C_Container.GetContainerNumFreeSlots(b)
    local x = bag(b)
    if not x then return 0, 0 end
    local used = 0
    for s = 1, x.slots do if x.items and x.items[s] then used = used + 1 end end
    return x.slots - used, 0
end
function C_Container.GetContainerItemInfo(b, s)
    local x = bag(b)
    local slot = x and x.items and x.items[s]
    if not slot then return nil end
    local it = ITEMS[slot.id] or {}
    return {
        hyperlink = M.link(slot.id), stackCount = slot.count or 1, itemID = slot.id, itemName = it.name,
        isBound = slot.bound == true, hasNoValue = (it.sellPrice or 0) == 0, quality = it.quality,
    }
end

local EQUIP = setmetatable({}, { __index = function(_, k) return (W.equipment or {})[k] end })
function GetInventoryItemLink(unit, slot)
    if unit ~= "player" or unloaded() then return nil end
    return EQUIP[slot] and M.link(EQUIP[slot])
end
function GetInventoryItemCount() return 1 end
function GetInventoryItemDurability() return nil end

C_TooltipInfo = {
    GetBagItem = function(b, s)
        local x = bag(b)
        local slot = x and x.items and x.items[s]
        return slot and tooltipData(slot.id)
    end,
    GetInventoryItem = function(unit, slot) return EQUIP[slot] and tooltipData(EQUIP[slot]) end,
}

-------------------------------------------------------------------------------
-- Quests
-------------------------------------------------------------------------------

local function QUESTS() return W.quests or {} end
C_QuestLog = {
    GetNumQuestLogEntries = function() if unloaded() then return 0 end return #QUESTS() end,
    GetInfo = function(i)
        local q = QUESTS()[i]
        if not q then return nil end
        return { title = q.title, questID = q.id, level = q.level, isHeader = q.header == true }
    end,
    IsComplete = function(id) for _, q in ipairs(QUESTS()) do if q.id == id then return q.complete == true end end return false end,
    GetQuestObjectives = function(id)
        for _, q in ipairs(QUESTS()) do if q.id == id then return q.objectives end end
    end,
    GetAllCompletedQuestIDs = function() return W.completedQuests or {} end,
    GetTitleForQuestID = function(id) return (W.questTitles or {})[id] end,
    RequestLoadQuestByID = function() end,
}

-------------------------------------------------------------------------------
-- Trade skill window (only while open)
-------------------------------------------------------------------------------

C_TradeSkillUI = {
    GetAllRecipeIDs = function()
        if not W.tradeSkill then return nil end
        local ids = {}
        for _, r in ipairs(W.tradeSkill.recipes) do ids[#ids + 1] = r.id end
        return ids
    end,
    GetBaseProfessionInfo = function() return W.tradeSkill and { professionName = W.tradeSkill.profession } end,
    GetRecipeInfo = function(id)
        for _, r in ipairs((W.tradeSkill or {}).recipes or {}) do
            if r.id == id then return { name = r.name, learned = true, relativeDifficulty = r.difficulty or 0, craftable = true, numAvailable = r.available or 0 } end
        end
    end,
}

-------------------------------------------------------------------------------
-- Tooltips
-------------------------------------------------------------------------------

Enum = {
    TooltipDataType = { Item = 0, Spell = 1, Unit = 2 },
    SpellBookSpellBank = { Player = 0, Pet = 1 },
    AuctionHouseSortOrder = { Price = 0, Name = 1, Level = 2, Bid = 3, Buyout = 4 },
    -- Values as the Forever client has them (tests/forever/api_names.json).
    AuctionHouseFilter = {
        None = 0, UncollectedOnly = 1, UsableOnly = 2, CurrentExpansionOnly = 3, UpgradesOnly = 4, ExactMatch = 5,
        PoorQuality = 6, CommonQuality = 7, UncommonQuality = 8, RareQuality = 9, EpicQuality = 10,
        LegendaryQuality = 11, ArtifactQuality = 12, LegendaryCraftedItemOnly = 13,
    },
}

TooltipDataProcessor = {
    AddTooltipPostCall = function(kind, fn)
        M.tooltipPostCalls[kind] = M.tooltipPostCalls[kind] or {}
        table.insert(M.tooltipPostCalls[kind], fn)
    end,
}

-- Show an item tooltip and return the lines the add-on added to it.
function M.hover(id)
    local tip = { added = {} }
    function tip:AddLine(text, r, g, b, wrap) self.added[#self.added + 1] = { left = text, wrap = wrap } end
    function tip:AddDoubleLine(l, rt) self.added[#self.added + 1] = { left = l, right = rt } end
    for _, fn in ipairs(M.tooltipPostCalls[Enum.TooltipDataType.Item] or {}) do
        run("tooltip", "tooltip", fn, tip, tooltipData(id) or { id = id })
    end
    return tip.added
end

-------------------------------------------------------------------------------
-- Auction house
-- Modelled rules: a browse query with no quality filter matches nothing; a query sent while
-- the throttle is not ready is dropped; one query is answered at a time.
-------------------------------------------------------------------------------

local A = M.auction
local THROTTLE = W.auctionThrottle or 1.0
local ANSWER_DELAY = W.auctionAnswerDelay or 0.3

C_AuctionHouse = {}
function C_AuctionHouse.IsThrottledMessageSystemReady() return M.now >= A.readyAt end
function C_AuctionHouse.SendBrowseQuery(q)
    if not W.auctionOpen then violation("auction query sent with the auction window closed") return end
    if M.now < A.readyAt then violation("auction query sent while throttled: " .. tostring(q.searchString)) return end
    if A.pending then violation("auction query sent before the previous one was answered: " .. tostring(q.searchString)) end
    A.readyAt = M.now + THROTTLE
    local filters = {}
    for _, f in ipairs(q.filters or {}) do filters[f] = true end
    local F = Enum.AuctionHouseFilter
    local anyQuality = filters[F.PoorQuality] or filters[F.CommonQuality] or filters[F.UncommonQuality]
        or filters[F.RareQuality] or filters[F.EpicQuality]
    local results = {}
    if anyQuality then
        for name, listing in pairs(W.auctionListings or {}) do
            local match = (filters[F.ExactMatch] and name == q.searchString)
                or (not filters[F.ExactMatch] and name:lower():find(q.searchString:lower(), 1, true))
            if match then
                results[#results + 1] = { itemKey = { itemID = itemIDOf(name) or 0 }, minPrice = listing.price, totalQuantity = listing.quantity }
            end
        end
    end
    A.sent[#A.sent + 1] = { search = q.searchString, at = M.now, filters = #(q.filters or {}), qualityFilters = anyQuality == true }
    local silent = (W.auctionSilent or {})[q.searchString]
    if silent then return end
    local token = {}
    A.pending = token
    schedule(ANSWER_DELAY, function()
        if A.pending ~= token then return end
        A.pending = nil
        A.results = results
        M.fire("AUCTION_HOUSE_BROWSE_RESULTS_UPDATED")
    end)
    schedule(THROTTLE, function() M.fire("AUCTION_HOUSE_THROTTLED_SYSTEM_READY") end)
end
function C_AuctionHouse.GetBrowseResults() return A.results or {} end
function C_AuctionHouse.GetItemKeyInfo(key)
    local it = ITEMS[key.itemID]
    return it and { itemName = it.name }
end

function M.openAuction()
    W.auctionOpen = true
    AuctionHouseFrame = AuctionHouseFrame or M.widget("Frame", "AuctionHouseFrame")
    M.fire("AUCTION_HOUSE_SHOW")
end
function M.closeAuction()
    W.auctionOpen = false
    M.fire("AUCTION_HOUSE_CLOSED")
end

-------------------------------------------------------------------------------
-- Game sandbox: the client has no os, io or module loading, and add-ons should not
-- create globals beyond the ones they declare.
-------------------------------------------------------------------------------

os, io, require, dofile, loadfile, package, module, debug = nil, nil, nil, nil, nil, nil, nil, nil
python = nil

function M.trackGlobals(allowed)
    setmetatable(_G, {
        __newindex = function(t, k, v)
            if not allowed[k] then M.newGlobals[#M.newGlobals + 1] = tostring(k) end
            rawset(t, k, v)
        end,
    })
end

-- Run one add-on file as the game does: with the add-on name and a private table as "...".
function M.loadFile(addon, path, source, ns)
    local chunk, err = loadstring(source, "@" .. path)
    if not chunk then lerror(path, err) return false end
    return run("load", path, chunk, addon, ns)
end

-------------------------------------------------------------------------------
-- SavedVariables: what the game writes to disk on /reload or logout.
-- Only strings, numbers, booleans and tables survive; anything else is a fault.
-------------------------------------------------------------------------------

function M.serialize(name, value)
    local out, seen = {}, {}
    local function emit(v, indent, path)
        local t = type(v)
        if t == "string" then out[#out + 1] = ("%q"):format(v)
        elseif t == "number" then
            if v ~= v or v == math.huge or v == -math.huge then violation("saved value is not a finite number at " .. path) out[#out + 1] = "0"
            elseif v == floor(v) and math.abs(v) < 2^53 then out[#out + 1] = ("%d"):format(v)
            else out[#out + 1] = ("%.17g"):format(v) end
        elseif t == "boolean" then out[#out + 1] = tostring(v)
        elseif t == "table" then
            if seen[v] then violation("saved table refers to itself at " .. path) out[#out + 1] = "nil" return end
            seen[v] = true
            out[#out + 1] = "{\n"
            local keys = {}
            for k in pairs(v) do keys[#keys + 1] = k end
            table.sort(keys, function(a, b)
                if type(a) == type(b) and (type(a) == "number" or type(a) == "string") then return a < b end
                return type(a) < type(b)
            end)
            for _, k in ipairs(keys) do
                local kt = type(k)
                if kt ~= "string" and kt ~= "number" then
                    violation("saved key of type " .. kt .. " at " .. path)
                else
                    out[#out + 1] = indent .. "\t[" .. (kt == "string" and ("%q"):format(k) or tostring(k)) .. "] = "
                    emit(v[k], indent .. "\t", path .. "." .. tostring(k))
                    out[#out + 1] = ",\n"
                end
            end
            out[#out + 1] = indent .. "}"
            seen[v] = nil
        else
            violation("saved value of type " .. t .. " at " .. path)
            out[#out + 1] = "nil"
        end
    end
    out[#out + 1] = "\n" .. name .. " = "
    emit(value, "", name)
    out[#out + 1] = "\n"
    return table.concat(out)
end
