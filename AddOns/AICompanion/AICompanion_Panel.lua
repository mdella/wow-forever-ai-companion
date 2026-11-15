-- AI Companion panel: the companion's plan for the character you are playing, inside the game.
-- Opened from the minimap button, the add-on menu next to the minimap (where the client has
-- one), or /aic panel. Content comes from AICompanionPlans (written by gen_data.py into the
-- AICompanion_Data add-on) and from the latest snapshot, so steps tick themselves as you play.

local _, ns = ...
ns = type(ns) == "table" and ns or {}
local Panel = {}
ns.panel = Panel

local function core() return ns.core or {} end
local function list(t) return type(t) == "table" and t or {} end
local function say(msg) local s = core().say if s then s(msg) end end

-------------------------------------------------------------------------------
-- Content: pure functions over the plan and the saved snapshot
-------------------------------------------------------------------------------

Panel.SECTIONS = {
    { key = "next", label = "Do next" },
    { key = "questing", label = "Questing" },
    { key = "professions", label = "Professions" },
    { key = "gear", label = "Gear" },
    { key = "talents", label = "Talents" },
    { key = "items", label = "Items" },
}

-- Where a recommendation comes from. The list shows no tags; an expanded step says it in
-- plain words, and only when the player should be careful.
Panel.CAUTION = {
    classic = "From the original game. Not confirmed for Forever.",
    unverified = "Not verified yet.",
}

-- The headline shown in the panel: the plan's short headline, or the first sentence of the full one.
function Panel.headline(plan)
    if type(plan) ~= "table" then return nil end
    if type(plan.headlineShort) == "string" and plan.headlineShort ~= "" then return plan.headlineShort end
    local h = plan.headline
    if type(h) ~= "string" then return nil end
    local first = h:match("^(.-[%.!%?])%s") or h
    return first
end

local ITEM_ORDER = { "sell", "auction", "mail", "bank", "use", "craft", "quest", "equip", "carry", "keep", "check" }

-- Facts the done rules need, read once from the snapshot and the character's store.
function Panel.facts(store)
    local s = type(store) == "table" and store.snapshot or nil
    if type(s) ~= "table" then return nil end
    local f = { equipped = {}, slots = {}, bagItems = {}, active = {}, completed = nil, skills = {}, freeSlots = 0,
                durability = nil, talentsSpent = 0, store = store }
    for _, e in ipairs(list(s.equipment)) do
        if type(e) == "table" then
            if e.name then f.equipped[e.name] = true end
            if e.slotName then f.slots[e.slotName] = true end
            local cur, max = tonumber(e.durability), tonumber(e.durabilityMax)
            if cur and max and max > 0 then
                local pct = cur / max * 100
                if not f.durability or pct < f.durability then f.durability = pct end
            end
        end
    end
    for _, b in ipairs(list(s.bags)) do
        if type(b) == "table" then
            f.freeSlots = f.freeSlots + (tonumber(b.free) or 0)
            for _, it in ipairs(list(b.items)) do
                if type(it) == "table" and it.name then f.bagItems[it.name] = (f.bagItems[it.name] or 0) + (tonumber(it.count) or 1) end
            end
        end
    end
    for _, q in ipairs(list(s.quests)) do
        if type(q) == "table" and q.title then f.active[q.title] = true end
    end
    if type(s.completedQuests) == "table" then
        f.completed = {}
        for _, q in ipairs(list(s.completedQuests.quests)) do
            if type(q) == "table" and q.title then f.completed[q.title] = true end
        end
    end
    for _, p in ipairs(list(type(s.skills) == "table" and s.skills.professions)) do
        if type(p) == "table" and p.name then f.skills[p.name] = { rank = tonumber(p.rank) or 0, max = tonumber(p.max) or 0 } end
    end
    for _, k in ipairs(list(type(s.skillsModern) == "table" and s.skillsModern.allSkills)) do
        if type(k) == "table" and k.name and not k.isHeader and not f.skills[k.name] then
            f.skills[k.name] = { rank = tonumber(k.rank or k.skillRank) or 0, max = tonumber(k.maxRank or k.skillMaxRank) or 0 }
        end
    end
    local tree = type(s.talents) == "table" and list(s.talents.trees)[1] or nil
    local cur = type(tree) == "table" and list(tree.currencies)[1] or nil
    if type(cur) == "table" then f.talentsSpent = tonumber(cur.spent) or 0 end
    return f
end

-- true or false when the snapshot settles a done rule; nil when it cannot (unknown rule).
function Panel.check(rule, f)
    if type(rule) ~= "table" or type(f) ~= "table" then return nil end
    local kind, arg = next(rule)
    if kind == nil or next(rule, kind) ~= nil then return nil end
    if kind == "all" then
        for _, r in ipairs(list(arg)) do
            local ok = Panel.check(r, f)
            if ok ~= true then return ok end
        end
        return true
    end
    if kind == "equipped" then return f.equipped[arg] == true end
    if kind == "notEquipped" then return f.equipped[arg] ~= true end
    if kind == "slotFilled" then return f.slots[arg] == true end
    if kind == "notInBags" then
        for _, n in ipairs(list(arg)) do if f.bagItems[n] then return false end end
        return true
    end
    if kind == "questDone" then return not f.active[arg] and (f.completed == nil or f.completed[arg] == true) end
    if kind == "skill" or kind == "skillCapAbove" then
        local sk = type(arg) == "table" and f.skills[arg[1]] or nil
        local n = type(arg) == "table" and tonumber(arg[2]) or nil
        if not n then return nil end
        if kind == "skill" then return sk ~= nil and sk.rank >= n end
        return sk ~= nil and sk.max > n
    end
    if kind == "talentsSpent" then return f.talentsSpent >= (tonumber(arg) or math.huge) end
    if kind == "freeSlots" then return f.freeSlots >= (tonumber(arg) or math.huge) end
    if kind == "repaired" then return f.durability ~= nil and f.durability >= (tonumber(arg) or 101) end
    if kind == "captured" then
        local st = f.store
        if arg == "completed" then return f.completed ~= nil end
        if type(arg) == "string" and arg:find("^recipes:") then return type(st.recipes) == "table" and st.recipes[arg:sub(9)] ~= nil end
        if arg == "trainers" then return st.trainers ~= nil or st.trainerRaw ~= nil end
        return type(arg) == "string" and st[arg] ~= nil
    end
    return nil
end

-- One step as a panel line: its tick state and where it comes from.
local function stepLine(step, f, ticks, sources)
    local line = { kind = "step", id = step.id, title = step.title or "", detail = step.detail,
                   caution = Panel.CAUTION[step.tag] }
    local src = step.source and type(sources) == "table" and sources[step.source] or nil
    if type(src) == "table" and src.label then
        line.source = "Source: " .. src.label
        if src.scope == "classic" and not line.caution then line.caution = Panel.CAUTION.classic end
    end
    local auto = nil
    if step.done ~= nil then auto = Panel.check(step.done, f) end   -- true, false, or nil for a rule it cannot judge
    if auto ~= nil then
        line.auto, line.done = true, auto
    else
        line.auto, line.done = false, (step.id ~= nil and ticks[step.id] == true)
    end
    return line
end

-- Bag and bank items grouped by recommended action: companion advice first, then the rules.
function Panel.items(store, adviceFor, ruleFor)
    local s = type(store) == "table" and store.snapshot or nil
    local groups, seen = {}, {}
    local function add(it, where)
        if type(it) ~= "table" or not it.name then return end
        local key = it.name
        if seen[key] then seen[key].count = seen[key].count + (tonumber(it.count) or 1) return end
        local action, note = nil, nil
        if adviceFor then action, note = adviceFor(it.name) end
        local fromRule = false
        if not action and ruleFor then action, note = ruleFor(it.name) fromRule = action ~= nil end
        if action == "keep" then action = "carry" end   -- both read "Keep in bags"
        action = action or "none"
        local e = { name = it.name, count = tonumber(it.count) or 1, note = note, rule = fromRule, where = where }
        seen[key] = e
        groups[action] = groups[action] or {}
        table.insert(groups[action], e)
    end
    for _, b in ipairs(list(type(s) == "table" and s.bags)) do
        for _, it in ipairs(list(type(b) == "table" and b.items)) do add(it, "bags") end
    end
    local bank = type(store) == "table" and store.bank or nil
    for _, b in ipairs(list(type(bank) == "table" and bank.bags)) do
        for _, it in ipairs(list(type(b) == "table" and b.items)) do add(it, "bank") end
    end
    local out = {}
    for _, action in ipairs(ITEM_ORDER) do
        if groups[action] then
            table.sort(groups[action], function(a, b) return a.name < b.name end)
            out[#out + 1] = { action = action, items = groups[action] }
        end
    end
    if groups.none then
        table.sort(groups.none, function(a, b) return a.name < b.name end)
        out[#out + 1] = { action = "none", items = groups.none }
    end
    return out
end

-- Everything the panel shows for one character, section by section.
-- plans: AICompanionPlans; store: DB.characters[charKey]; ticks: manual ticks for this character.
function Panel.model(plans, firstName, store, ticks, adviceFor, ruleFor)
    plans = type(plans) == "table" and plans or {}
    ticks = type(ticks) == "table" and ticks or {}
    local plan = type(plans.characters) == "table" and plans.characters[firstName] or nil
    local sources = plans.sources
    local f = Panel.facts(store) or Panel.facts({ snapshot = {} })
    local m = { name = firstName, asOf = plans.asOf, hasPlan = type(plan) == "table", sections = {} }
    m.headline = (m.hasPlan and Panel.headline(plan)) or ("No plan for " .. tostring(firstName) .. " yet. The Items tab shows the built-in advice.")
    m.takenAt = type(store) == "table" and type(store.snapshot) == "table" and store.snapshot.takenAtText or nil
    local function section(key) local t = {} m.sections[key] = t return t end
    if m.hasPlan then
        local t = section("next")
        for i, step in ipairs(list(plan.next)) do
            if type(step) == "table" then
                local line = stepLine(step, f, ticks, sources)
                line.number = i
                t[#t + 1] = line
            end
        end
        t = section("questing")
        for _, group in ipairs(list(plan.questing)) do
            if type(group) == "table" then
                t[#t + 1] = { kind = "heading", title = group.title or "", detail = group.note }
                for _, step in ipairs(list(group.steps)) do
                    if type(step) == "table" then t[#t + 1] = stepLine(step, f, ticks, sources) end
                end
            end
        end
        t = section("professions")
        local names = {}
        for name in pairs(list(plan.professions)) do names[#names + 1] = name end
        table.sort(names)
        for _, name in ipairs(names) do
            local p = plan.professions[name]
            if type(p) == "table" then
                local sk = f.skills[name]
                local line = { kind = "heading", title = name .. (sk and (" " .. sk.rank .. "/" .. sk.max) or ""), detail = p.status }
                t[#t + 1] = line
                if p.next then
                    local nl = stepLine({ title = "Next: " .. p.next, tag = p.tag, source = p.source }, f, ticks, sources)
                    nl.kind = "note"
                    t[#t + 1] = nl
                end
            end
        end
        t = section("gear")
        for _, step in ipairs(list(plan.gear)) do
            if type(step) == "table" then t[#t + 1] = stepLine(step, f, ticks, sources) end
        end
        t = section("talents")
        local tp = plan.talents
        if type(tp) == "table" then
            if tp.note then t[#t + 1] = { kind = "text", title = tp.note } end
            if tp.suggestion then
                local nl = stepLine({ title = tp.suggestion, tag = tp.tag, source = tp.source }, f, ticks, sources)
                nl.kind = "note"
                t[#t + 1] = nl
            end
        end
        if type(plan.bags) == "string" then m.bagsNote = plan.bags end
        m.blindspots = {}
        for _, b in ipairs(list(plan.blindspots)) do
            if type(b) == "table" and b.text then
                local done = nil
                if b.done ~= nil then done = Panel.check(b.done, f) end
                if done ~= true then m.blindspots[#m.blindspots + 1] = b.text end
            end
        end
    end
    if m.hasPlan then
        -- the bags note and what the companion cannot see yet close the Do next tab
        local t = m.sections.next
        if m.bagsNote then
            t[#t + 1] = { kind = "heading", title = "Bags" }
            t[#t + 1] = { kind = "text", title = m.bagsNote }
        end
        if #m.blindspots > 0 then
            t[#t + 1] = { kind = "heading", title = "I can't see yet" }
            for _, b in ipairs(m.blindspots) do t[#t + 1] = { kind = "text", title = b } end
        end
    end
    m.sections.items = Panel.items(store, adviceFor, ruleFor)
    return m
end

-------------------------------------------------------------------------------
-- Display
-------------------------------------------------------------------------------

local FRAME_NAME = "AICompanionPanel"
local DEFAULT_W, DEFAULT_H, MIN_W, MIN_H = 900, 700, 640, 480
-- Fonts: titles in the large font, headings larger still, nothing smaller than 12.
local FONT_TITLE, FONT_HEADING, FONT_TEXT = "GameFontHighlightLarge", "GameFontNormalHuge", "GameFontHighlight"
local DETAIL_GREY = 0.85

local frame, scroll, content, bar, tabs, pool = nil, nil, nil, nil, {}, {}
local current, expanded = "next", nil
local refreshTicker

local function panelDB()
    local DB = core().db and core().db()
    if type(DB) ~= "table" then return nil end
    DB.panel = type(DB.panel) == "table" and DB.panel or {}
    DB.panel.ticks = type(DB.panel.ticks) == "table" and DB.panel.ticks or {}
    return DB.panel
end

local function firstName()
    local key = core().charKey and core().charKey()
    return key and (tostring(key):match("^([^@]+)")) or nil, key
end

local function currentModel()
    local DB = core().db and core().db()
    local name, key = firstName()
    if type(DB) ~= "table" or not key then return nil end
    local pdb = panelDB()
    pdb.ticks[key] = type(pdb.ticks[key]) == "table" and pdb.ticks[key] or {}
    local store = type(DB.characters) == "table" and DB.characters[key] or nil
    local plans = type(AICompanionPlans) == "table" and AICompanionPlans or nil
    return Panel.model(plans, name, store, pdb.ticks[key], core().adviceFor, core().ruleFor), pdb.ticks[key]
end
Panel.currentModel = currentModel

local function actionLabel(action)
    if action == "none" then return "No advice yet" end
    local L = core().ADVICE_LABEL and core().ADVICE_LABEL[action]
    return L and L[1] or action
end

-- A section of the model as display rows. Steps show one line (tick box, title, tag);
-- the expanded step also shows its detail and source.
-- Row: { key, text, sub, check = {id, done, auto}, heading, expandable }
function Panel.rows(m, key, open)
    local rows = {}
    local function add(r) rows[#rows + 1] = r end
    if key == "items" then
        for gi, g in ipairs(m.sections.items or {}) do
            add({ key = "g" .. gi, text = actionLabel(g.action), heading = true })
            for _, it in ipairs(g.items) do
                local rkey = "item:" .. it.name
                local sub
                if open == rkey then
                    sub = it.note
                    if it.rule and sub then sub = sub .. " (built-in rule)" end
                    if it.where == "bank" then sub = (sub and sub .. " " or "") .. "In the bank." end
                end
                add({ key = rkey, text = it.name .. (it.count > 1 and (" x" .. it.count) or ""), sub = sub,
                      expandable = it.note ~= nil or it.where == "bank" })
            end
        end
        if #rows == 0 then add({ key = "empty", text = "No snapshot of your bags yet. Type /aic to take one." }) end
        return rows
    end
    if not m.hasPlan then
        add({ key = "noplan", text = "No plan for this character yet." })
        return rows
    end
    for i, l in ipairs(m.sections[key] or {}) do
        local rkey = l.id or (key .. ":" .. i)
        if l.kind == "heading" then
            add({ key = rkey, text = l.title, heading = true, sub = l.detail })
        elseif l.kind == "text" then
            add({ key = rkey, text = l.title })
        else
            local more = {}
            if l.detail and l.detail ~= "" then more[#more + 1] = l.detail end
            if l.caution then more[#more + 1] = l.caution end
            if l.source then more[#more + 1] = l.source end
            local title = (l.number and (l.number .. ". ") or "") .. l.title
            add({ key = rkey, text = title,
                  sub = (open == rkey and #more > 0) and table.concat(more, "\n") or nil,
                  expandable = #more > 0,
                  check = l.kind == "step" and { id = l.id, done = l.done, auto = l.auto } or nil,
                  done = l.done })
        end
    end
    if #rows == 0 then add({ key = "nothing", text = "Nothing planned here yet." }) end
    return rows
end

local function textHeight(fs, default)
    local h = fs.GetStringHeight and fs:GetStringHeight()
    return (type(h) == "number" and h > 0) and h or default
end

local function rowFrame(i)
    local r = pool[i]
    if r then return r end
    r = CreateFrame("Button", nil, content)
    r.check = CreateFrame("CheckButton", nil, r, "UICheckButtonTemplate")
    r.check:SetSize(24, 24)
    r.title = r:CreateFontString(nil, "OVERLAY", FONT_TITLE)
    r.title:SetJustifyH("LEFT")
    r.title:SetWordWrap(false)
    r.sub = r:CreateFontString(nil, "OVERLAY", FONT_TEXT)
    r.sub:SetJustifyH("LEFT")
    r.sub:SetWordWrap(true)
    r.sub:SetTextColor(DETAIL_GREY, DETAIL_GREY, DETAIL_GREY)
    r.hl = r:CreateTexture(nil, "HIGHLIGHT")
    r.hl:SetAllPoints(r)
    r.hl:SetColorTexture(1, 1, 1, 0.06)
    pool[i] = r
    return r
end

local function updateBar()
    if not (scroll and bar) then return end
    local visible = scroll:GetHeight() or ((frame:GetHeight() or DEFAULT_H) - 150)
    local range = math.max(0, (content.fullHeight or 0) - visible)
    bar:SetMinMaxValues(0, range)
    if range <= 0 then bar:Hide() scroll:SetVerticalScroll(0) bar:SetValue(0) else bar:Show() end
    if (bar:GetValue() or 0) > range then bar:SetValue(range) end
end

local render
render = function()
    if not frame or not frame:IsShown() then return end
    local m, ticks = currentModel()
    if not m then return end
    frame.title:SetText("AI Companion: " .. tostring(m.name))
    frame.headline:SetText(m.headline or "")
    frame.footer:SetText(m.takenAt and ("Snapshot " .. m.takenAt .. (m.asOf and ("   Plan " .. m.asOf) or "")) or "No snapshot yet")
    for key, tab in pairs(tabs) do
        if key == current then tab:LockHighlight() else tab:UnlockHighlight() end
    end
    local rows = Panel.rows(m, current, expanded)
    frame.lastRows = rows
    local width = (frame:GetWidth() or DEFAULT_W) - 64
    content:SetWidth(width)
    local y = 0
    for i, r in ipairs(rows) do
        local f = rowFrame(i)
        local x = 6
        f:ClearAllPoints()
        f:SetPoint("TOPLEFT", content, "TOPLEFT", 0, -y)
        f:SetWidth(width)
        if r.check then
            f.check:ClearAllPoints()
            f.check:SetPoint("TOPLEFT", f, "TOPLEFT", x, 0)
            f.check:SetChecked(r.check.done == true)
            f.check:SetEnabled(not r.check.auto and r.check.id ~= nil)
            f.check:SetScript("OnClick", function(btn)
                if r.check.auto or not r.check.id then return end
                ticks[r.check.id] = btn:GetChecked() and true or nil
                render()
            end)
            f.check:Show()
            x = x + 30
        else
            f.check:Hide()
        end
        f.title:SetFontObject(r.heading and FONT_HEADING or FONT_TITLE)
        f.title:ClearAllPoints()
        f.title:SetPoint("TOPLEFT", f, "TOPLEFT", x, -3)
        f.title:SetWidth(width - x - 12)
        f.title:SetText(r.text or "")
        if r.heading then f.title:SetTextColor(1, 0.82, 0)
        elseif r.done then f.title:SetTextColor(0.55, 0.85, 0.55)
        else f.title:SetTextColor(1, 1, 1) end
        local h = math.max(textHeight(f.title, r.heading and 22 or 18), 24) + 4
        if r.sub then
            f.sub:ClearAllPoints()
            f.sub:SetPoint("TOPLEFT", f, "TOPLEFT", x, -h)
            f.sub:SetWidth(width - x - 12)
            f.sub:SetText(r.sub)
            f.sub:Show()
            h = h + textHeight(f.sub, 14) + 6
        else
            f.sub:Hide()
        end
        f:SetHeight(h)
        f:SetScript("OnClick", function()
            if not r.expandable then return end
            expanded = (expanded ~= r.key) and r.key or nil   -- one step open at a time
            render()
        end)
        f:Show()
        y = y + h + 2
    end
    for i = #rows + 1, #pool do pool[i]:Hide() end
    content.fullHeight = y
    content:SetHeight(math.max(y, 10))
    updateBar()
end
Panel.render = render

local function savePosition()
    local pdb = panelDB()
    if not pdb or not frame then return end
    local point, _, relPoint, x, y = frame:GetPoint(1)
    if point then pdb.point = { point, relPoint, x, y } end
    local w, h = frame:GetWidth(), frame:GetHeight()
    if w and h then pdb.width, pdb.height = math.max(w, MIN_W), math.max(h, MIN_H) end
end

local function build()
    if frame then return frame end
    local pdb = panelDB() or {}
    local f = CreateFrame("Frame", FRAME_NAME, UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    f:SetSize(math.max(pdb.width or DEFAULT_W, MIN_W), math.max(pdb.height or DEFAULT_H, MIN_H))
    if type(pdb.point) == "table" then f:SetPoint(pdb.point[1], UIParent, pdb.point[2], pdb.point[3], pdb.point[4])
    else f:SetPoint("CENTER") end
    f:SetFrameStrata("DIALOG")
    f:SetClampedToScreen(true)
    if f.SetBackdrop then
        f:SetBackdrop({ bgFile = "Interface\\ChatFrame\\ChatFrameBackground", edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
                        edgeSize = 16, insets = { left = 4, right = 4, top = 4, bottom = 4 } })
        f:SetBackdropColor(0.05, 0.05, 0.07, 0.95)
    end
    f:EnableMouse(true)
    f:SetMovable(true)
    f:SetResizable(true)
    if f.SetResizeBounds then f:SetResizeBounds(MIN_W, MIN_H, 1600, 1200) end
    f:RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", function(self) self:StartMoving() end)
    f:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() savePosition() end)
    f.title = f:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    f.title:SetPoint("TOPLEFT", 16, -14)
    local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", -2, -2)
    close:SetScript("OnClick", function() f:Hide() end)
    -- headline: two lines at most, with its own space above the tabs
    f.headline = f:CreateFontString(nil, "OVERLAY", FONT_TITLE)
    f.headline:SetPoint("TOPLEFT", 16, -40)
    f.headline:SetPoint("RIGHT", f, "RIGHT", -16, 0)
    f.headline:SetHeight(44)
    f.headline:SetJustifyH("LEFT")
    f.headline:SetJustifyV("TOP")
    f.headline:SetWordWrap(true)
    if f.headline.SetMaxLines then f.headline:SetMaxLines(2) end
    local prev
    for _, s in ipairs(Panel.SECTIONS) do
        local b = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
        b:SetSize(104, 26)
        if prev then b:SetPoint("LEFT", prev, "RIGHT", 4, 0) else b:SetPoint("TOPLEFT", 14, -90) end
        b:SetText(s.label)
        b:SetScript("OnClick", function() current, expanded = s.key, nil render() end)
        tabs[s.key] = b
        prev = b
    end
    -- the list, with its own scroll bar (a visible track and thumb) and mouse-wheel scrolling
    scroll = CreateFrame("ScrollFrame", nil, f)
    scroll:SetPoint("TOPLEFT", 16, -126)
    scroll:SetPoint("BOTTOMRIGHT", -34, 40)
    content = CreateFrame("Frame", nil, scroll)
    content:SetSize(DEFAULT_W - 64, 10)
    scroll:SetScrollChild(content)
    bar = CreateFrame("Slider", nil, f)
    bar:SetOrientation("VERTICAL")
    bar:SetWidth(12)
    bar:SetPoint("TOPRIGHT", f, "TOPRIGHT", -14, -126)
    bar:SetPoint("BOTTOMRIGHT", f, "BOTTOMRIGHT", -14, 40)
    local track = bar:CreateTexture(nil, "BACKGROUND")
    track:SetAllPoints(bar)
    track:SetColorTexture(0.2, 0.2, 0.22, 0.9)
    local thumb = bar:CreateTexture(nil, "OVERLAY")
    thumb:SetColorTexture(0.75, 0.75, 0.78, 1)
    thumb:SetSize(12, 48)
    bar:SetThumbTexture(thumb)
    bar:SetValueStep(1)
    bar:SetMinMaxValues(0, 0)
    bar:SetValue(0)
    bar:SetScript("OnValueChanged", function(_, value) scroll:SetVerticalScroll(value or 0) end)
    scroll:EnableMouseWheel(true)
    scroll:SetScript("OnMouseWheel", function(_, delta)
        local lo, hi = bar:GetMinMaxValues()
        local v = math.min(math.max((bar:GetValue() or 0) - (delta or 0) * 48, lo or 0), hi or 0)
        bar:SetValue(v)
        scroll:SetVerticalScroll(v)
    end)
    -- footer strip: one line, below the list, never under it
    f.footer = f:CreateFontString(nil, "OVERLAY", FONT_TEXT)
    f.footer:SetPoint("BOTTOMLEFT", 16, 14)
    f.footer:SetPoint("RIGHT", f, "RIGHT", -40, 0)
    f.footer:SetJustifyH("LEFT")
    f.footer:SetWordWrap(false)
    f.footer:SetTextColor(0.7, 0.7, 0.7)
    local grip = CreateFrame("Button", nil, f)
    grip:SetSize(16, 16)
    grip:SetPoint("BOTTOMRIGHT", -4, 4)
    grip:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
    grip:SetHighlightTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Highlight")
    grip:SetPushedTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Down")
    grip:SetScript("OnMouseDown", function() f:StartSizing("BOTTOMRIGHT") end)
    grip:SetScript("OnMouseUp", function() f:StopMovingOrSizing() savePosition() render() end)
    f:SetScript("OnShow", function()
        render()
        if C_Timer and C_Timer.NewTicker and not refreshTicker then
            refreshTicker = C_Timer.NewTicker(5, function() pcall(render) end)
        end
    end)
    f:SetScript("OnHide", function()
        if refreshTicker then refreshTicker:Cancel() refreshTicker = nil end
    end)
    -- Escape closes it, like the game's own windows.
    if type(UISpecialFrames) == "table" then table.insert(UISpecialFrames, FRAME_NAME) end
    f:Hide()
    frame = f
    return f
end

function Panel.toggle()
    if frame and frame:IsShown() then frame:Hide() return end
    if InCombatLockdown and InCombatLockdown() then say("the panel opens after combat.") return end
    if core().takeSnapshot then core().takeSnapshot("panel") end   -- so the ticks are current
    local ok, err = pcall(build)
    if not ok then say("could not open the panel: " .. tostring(err)) return end
    frame:Show()   -- OnShow draws it
end
Panel.isShown = function() return frame ~= nil and frame:IsShown() end

-- Key binding (Bindings.xml): Key Bindings > AddOns > AI Companion > "Open or close the panel".
-- The labels are globals the Key Bindings screen reads; the binding calls the function below.
BINDING_HEADER_AICOMPANION = "AI Companion"
BINDING_NAME_AICOMPANION_TOGGLE_PANEL = "Open or close the panel"
function AICompanion_TogglePanel()
    local ok, err = pcall(Panel.toggle)
    if not ok then say("could not open the panel: " .. tostring(err)) end
end

-- The key the player bound, as the game names it ("F8", "Shift-P"), or nil.
function Panel.boundKey()
    if type(GetBindingKey) ~= "function" then return nil end
    local key = GetBindingKey("AICOMPANION_TOGGLE_PANEL")
    if type(key) ~= "string" or key == "" then return nil end
    local text = type(GetBindingText) == "function" and GetBindingText(key) or nil
    return (type(text) == "string" and text ~= "") and text or key
end
Panel.select = function(key) current, expanded = key, nil render() end
Panel.expand = function(key) expanded = key render() end

-------------------------------------------------------------------------------
-- Minimap button: round, in the standard gold ring, like the game's own and other add-ons'.
-- Draggable around the minimap edge; position kept.
-------------------------------------------------------------------------------

-- First art file the client really has, so a missing file never shows as a blank square.
local function firstFile(list)
    for _, path in ipairs(list) do
        local id = type(GetFileIDFromPath) == "function" and GetFileIDFromPath(path) or nil
        if type(id) == "number" and id > 0 then return path end
    end
    return nil
end

Panel.ICONS = { "Interface\\Icons\\INV_Misc_Book_09", "Interface\\Icons\\INV_Misc_Book_11",
                "Interface\\Icons\\INV_Scroll_03", "Interface\\Icons\\INV_Misc_Note_01" }
local RING = "Interface\\Minimap\\MiniMap-TrackingBorder"
local RING_ATLAS = "ui-hud-minimap-button"
local BACKGROUND = "Interface\\Minimap\\UI-Minimap-Background"
local HIGHLIGHT = "Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight"
local ROUND_MASK = "Interface\\CharacterFrame\\TempPortraitAlphaMask"

local button
local function placeButton(angle)
    if not button or not Minimap then return end
    local r = ((Minimap:GetWidth() or 140) / 2) + 5
    local a = math.rad(angle or 225)
    button:ClearAllPoints()
    button:SetPoint("CENTER", Minimap, "CENTER", math.cos(a) * r, math.sin(a) * r)
end
Panel.placeButton = placeButton

local function dragUpdate()
    local mx, my = Minimap:GetCenter()
    local cx, cy = GetCursorPosition()
    local scale = (Minimap.GetEffectiveScale and Minimap:GetEffectiveScale()) or 1
    if not (mx and my and cx and cy) then return end
    local angle = math.deg(math.atan2(cy / scale - my, cx / scale - mx))
    local pdb = panelDB()
    if pdb then pdb.minimapAngle = angle end
    placeButton(angle)
end

local function buildButton()
    if button or type(Minimap) ~= "table" then return end
    local b = CreateFrame("Button", "AICompanionMinimapButton", Minimap)
    b:SetSize(31, 31)
    b:SetFrameStrata("MEDIUM")
    b:SetFrameLevel(8)
    b:RegisterForClicks("AnyUp")
    b:RegisterForDrag("LeftButton")
    b.art = {}
    local bg = b:CreateTexture(nil, "BACKGROUND")
    bg:SetSize(24, 24)
    bg:SetPoint("CENTER")
    bg:SetTexture(BACKGROUND)
    local icon = b:CreateTexture(nil, "ARTWORK")
    icon:SetSize(20, 20)
    icon:SetPoint("CENTER")
    local iconFile = firstFile(Panel.ICONS)
    icon:SetTexture(iconFile or Panel.ICONS[1])
    icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
    if b.CreateMaskTexture and icon.AddMaskTexture then      -- clip the square icon to a circle
        local mask = b:CreateMaskTexture()
        mask:SetTexture(ROUND_MASK, "CLAMPTOBLACKADDITIVE", "CLAMPTOBLACKADDITIVE")
        mask:SetAllPoints(icon)
        icon:AddMaskTexture(mask)
        b.art.mask = ROUND_MASK
    end
    local ring = b:CreateTexture(nil, "OVERLAY")
    if firstFile({ RING }) then
        ring:SetSize(50, 50)
        ring:SetPoint("TOPLEFT")
        ring:SetTexture(RING)
        b.art.ring = RING
    elseif C_Texture and C_Texture.GetAtlasInfo and C_Texture.GetAtlasInfo(RING_ATLAS) then
        ring:SetSize(36, 36)
        ring:SetPoint("CENTER")
        ring:SetAtlas(RING_ATLAS)
        b.art.ring = RING_ATLAS
    end
    b:SetHighlightTexture(HIGHLIGHT, "ADD")
    b.art.icon, b.icon = iconFile or Panel.ICONS[1], icon
    -- pressed: the icon shifts slightly, as game buttons do
    b:SetScript("OnMouseDown", function() icon:ClearAllPoints() icon:SetPoint("CENTER", 1, -1) end)
    b:SetScript("OnMouseUp", function() icon:ClearAllPoints() icon:SetPoint("CENTER") end)
    b:SetScript("OnClick", function() Panel.toggle() end)
    b:SetScript("OnDragStart", function(self) self:SetScript("OnUpdate", function() pcall(dragUpdate) end) end)
    b:SetScript("OnDragStop", function(self)
        self:SetScript("OnUpdate", nil)
        icon:ClearAllPoints() icon:SetPoint("CENTER")
    end)
    b:SetScript("OnEnter", function(self)
        if GameTooltip and GameTooltip.SetOwner then
            GameTooltip:SetOwner(self, "ANCHOR_LEFT")
            GameTooltip:SetText("AI Companion")
            local key = Panel.boundKey()
            GameTooltip:AddLine(key and ("Click or press " .. key .. ": open the plan") or "Click: open the plan", 1, 1, 1)
            GameTooltip:AddLine("Drag: move this button", 1, 1, 1)
            GameTooltip:Show()
        end
    end)
    b:SetScript("OnLeave", function() if GameTooltip and GameTooltip.Hide then GameTooltip:Hide() end end)
    button = b
    local pdb = panelDB()
    placeButton(pdb and pdb.minimapAngle)
end

-- The add-on menu next to the minimap. Its registration call is reported by other Forever
-- add-ons, not confirmed by an in-game dump, so it is tried quietly.
local function registerCompartment()
    local c = AddonCompartmentFrame
    if type(c) ~= "table" or type(c.RegisterAddon) ~= "function" then return false end
    return pcall(c.RegisterAddon, c, {
        text = "AI Companion",
        icon = firstFile(Panel.ICONS) or Panel.ICONS[1],
        notCheckable = true,
        func = function() Panel.toggle() end,
    })
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:SetScript("OnEvent", function()
    pcall(buildButton)
    local ok = registerCompartment()
    local DB = core().db and core().db()
    if type(DB) == "table" then DB.panelCompartment = ok and "registered" or "not available" end
end)
