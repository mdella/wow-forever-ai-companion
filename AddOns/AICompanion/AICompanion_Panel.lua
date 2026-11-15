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

-- Where a recommendation comes from, as the web dashboard labels it.
Panel.TAGS = {
    game = "From your game data",
    lookup = "Forever source",
    classic = "Original-game source",
    judgment = "My judgment",
    unverified = "Not verified",
}

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
    local line = { kind = "step", id = step.id, title = step.title or "", detail = step.detail, tag = Panel.TAGS[step.tag] }
    local src = step.source and type(sources) == "table" and sources[step.source] or nil
    if type(src) == "table" and src.label then
        line.source = (src.scope == "classic" and "Original-game source: " or "Source: ") .. src.label
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
    m.headline = m.hasPlan and plan.headline or ("No plan for " .. tostring(firstName) .. " yet. Ask your companion for one; until then the Items tab shows the built-in advice.")
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
    m.sections.items = Panel.items(store, adviceFor, ruleFor)
    return m
end

-------------------------------------------------------------------------------
-- Display
-------------------------------------------------------------------------------

local FRAME_NAME = "AICompanionPanel"
local frame, content, tabs, pool = nil, nil, {}, {}
local current = "next"
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

local function line(i)
    local l = pool[i]
    if l then return l end
    l = {}
    l.check = CreateFrame("CheckButton", nil, content, "UICheckButtonTemplate")
    l.check:SetSize(20, 20)
    l.text = content:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    l.text:SetJustifyH("LEFT")
    l.text:SetWordWrap(true)
    l.sub = content:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    l.sub:SetJustifyH("LEFT")
    l.sub:SetWordWrap(true)
    pool[i] = l
    return l
end

local ACTION_LABEL = function(action)
    if action == "none" then return "No advice yet" end
    local L = core().ADVICE_LABEL and core().ADVICE_LABEL[action]
    return L and L[1] or action
end

-- Turn a section of the model into display rows: { text, sub, check = {id, done, auto}, indent, color }.
function Panel.rows(m, key)
    local rows = {}
    local function add(r) rows[#rows + 1] = r end
    if key == "items" then
        for _, g in ipairs(m.sections.items or {}) do
            add({ text = ACTION_LABEL(g.action), color = "heading" })
            for _, it in ipairs(g.items) do
                local sub = it.note
                if it.rule and sub then sub = sub .. " (rule)" end
                if it.where == "bank" then sub = (sub and sub .. " " or "") .. "In the bank." end
                add({ text = it.name .. (it.count > 1 and (" x" .. it.count) or ""), sub = sub, indent = 1 })
            end
        end
        if #rows == 0 then add({ text = "No snapshot of your bags yet. Type /aic to take one." }) end
        return rows
    end
    local section = m.sections[key]
    if not m.hasPlan then
        add({ text = "No plan for this character yet." })
        return rows
    end
    for _, l in ipairs(section or {}) do
        local meta = {}
        if l.tag then meta[#meta + 1] = l.tag end
        if l.source then meta[#meta + 1] = l.source end
        if l.kind == "heading" then
            add({ text = l.title, sub = l.detail, color = "heading" })
        elseif l.kind == "text" then
            add({ text = l.title })
        else
            local detail = l.detail
            if #meta > 0 then detail = (detail and detail .. "  " or "") .. "[" .. table.concat(meta, "; ") .. "]" end
            local title = (l.number and (l.number .. ". ") or "") .. l.title
            if l.kind == "step" and l.auto then title = title .. (l.done and "  (done)" or "") end
            add({ text = title, sub = detail, indent = l.kind == "note" and 1 or 0,
                  check = l.kind == "step" and { id = l.id, done = l.done, auto = l.auto } or nil,
                  color = l.done and "done" or nil })
        end
    end
    if #rows == 0 then add({ text = "Nothing planned here yet." }) end
    return rows
end

local function textHeight(fs, default)
    local h = fs.GetStringHeight and fs:GetStringHeight()
    return (type(h) == "number" and h > 0) and h or default
end

local function render()
    if not frame or not frame:IsShown() then return end
    local m, ticks = currentModel()
    if not m then return end
    frame.title:SetText("AI Companion: " .. tostring(m.name) .. (m.asOf and ("  (plan " .. m.asOf .. ")") or ""))
    frame.headline:SetText(m.headline or "")
    local extra = {}
    if m.bagsNote then extra[#extra + 1] = "Bags: " .. m.bagsNote end
    for _, b in ipairs(m.blindspots or {}) do extra[#extra + 1] = "I can't see yet: " .. b end
    if m.takenAt then extra[#extra + 1] = "Snapshot " .. m.takenAt end
    frame.footer:SetText(table.concat(extra, "   "))
    for key, tab in pairs(tabs) do
        if key == current then tab:LockHighlight() else tab:UnlockHighlight() end
    end
    local rows = Panel.rows(m, current)
    frame.lastRows = rows
    local width = (frame:GetWidth() or 460) - 60
    local y = -4
    for i, r in ipairs(rows) do
        local l = line(i)
        local x = 4 + (r.indent or 0) * 16
        if r.check then
            l.check:ClearAllPoints()
            l.check:SetPoint("TOPLEFT", content, "TOPLEFT", x, y + 2)
            l.check:SetChecked(r.check.done == true)
            l.check:SetEnabled(not r.check.auto and r.check.id ~= nil)
            l.check:SetScript("OnClick", function(btn)
                if r.check.auto or not r.check.id then return end
                ticks[r.check.id] = btn:GetChecked() and true or nil
                render()
            end)
            l.check:Show()
            x = x + 22
        else
            l.check:Hide()
        end
        l.text:ClearAllPoints()
        l.text:SetPoint("TOPLEFT", content, "TOPLEFT", x, y)
        l.text:SetWidth(width - x)
        l.text:SetText(r.text or "")
        if r.color == "heading" then l.text:SetTextColor(1, 0.82, 0)
        elseif r.color == "done" then l.text:SetTextColor(0.5, 0.8, 0.5)
        else l.text:SetTextColor(1, 1, 1) end
        l.text:Show()
        y = y - textHeight(l.text, 14) - 2
        if r.sub and r.sub ~= "" then
            l.sub:ClearAllPoints()
            l.sub:SetPoint("TOPLEFT", content, "TOPLEFT", x, y)
            l.sub:SetWidth(width - x)
            l.sub:SetText(r.sub)
            l.sub:Show()
            y = y - textHeight(l.sub, 12) - 2
        else
            l.sub:Hide()
        end
        y = y - 6
    end
    for i = #rows + 1, #pool do pool[i].check:Hide() pool[i].text:Hide() pool[i].sub:Hide() end
    content:SetSize(width, math.max(-y, 10))
end
Panel.render = render

local function savePosition()
    local pdb = panelDB()
    if not pdb or not frame then return end
    local point, _, relPoint, x, y = frame:GetPoint(1)
    if point then pdb.point = { point, relPoint, x, y } end
    local w, h = frame:GetWidth(), frame:GetHeight()
    if w and h then pdb.width, pdb.height = w, h end
end

local function build()
    if frame then return frame end
    local pdb = panelDB() or {}
    local f = CreateFrame("Frame", FRAME_NAME, UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    f:SetSize(pdb.width or 480, pdb.height or 520)
    if type(pdb.point) == "table" then f:SetPoint(pdb.point[1], UIParent, pdb.point[2], pdb.point[3], pdb.point[4])
    else f:SetPoint("CENTER") end
    f:SetFrameStrata("DIALOG")
    f:SetClampedToScreen(true)
    if f.SetBackdrop then
        f:SetBackdrop({ bgFile = "Interface\\ChatFrame\\ChatFrameBackground", edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
                        edgeSize = 14, insets = { left = 3, right = 3, top = 3, bottom = 3 } })
        f:SetBackdropColor(0, 0, 0, 0.92)
    end
    f:EnableMouse(true)
    f:SetMovable(true)
    f:SetResizable(true)
    if f.SetResizeBounds then f:SetResizeBounds(360, 300, 900, 1000) end
    f:RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", function(self) self:StartMoving() end)
    f:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() savePosition() end)
    f.title = f:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    f.title:SetPoint("TOPLEFT", 12, -10)
    local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", 0, 0)
    close:SetScript("OnClick", function() f:Hide() end)
    f.headline = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    f.headline:SetPoint("TOPLEFT", 12, -32)
    f.headline:SetPoint("RIGHT", f, "RIGHT", -12, 0)
    f.headline:SetJustifyH("LEFT")
    f.headline:SetWordWrap(true)
    local prev
    for i, s in ipairs(Panel.SECTIONS) do
        local b = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
        b:SetSize(74, 20)
        if prev then b:SetPoint("LEFT", prev, "RIGHT", 2, 0) else b:SetPoint("TOPLEFT", 10, -76) end
        b:SetText(s.label)
        b:SetScript("OnClick", function() current = s.key render() end)
        tabs[s.key] = b
        prev = b
    end
    local sf = CreateFrame("ScrollFrame", "AICompanionPanelScroll", f, "UIPanelScrollFrameTemplate")
    sf:SetPoint("TOPLEFT", 12, -102)
    sf:SetPoint("BOTTOMRIGHT", -32, 36)
    content = CreateFrame("Frame", nil, sf)
    content:SetSize(400, 10)
    sf:SetScrollChild(content)
    f.footer = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.footer:SetPoint("BOTTOMLEFT", 12, 12)
    f.footer:SetPoint("RIGHT", f, "RIGHT", -28, 0)
    f.footer:SetJustifyH("LEFT")
    local grip = CreateFrame("Button", nil, f)
    grip:SetSize(16, 16)
    grip:SetPoint("BOTTOMRIGHT", -4, 4)
    grip:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
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
Panel.select = function(key) current = key render() end

-------------------------------------------------------------------------------
-- Minimap button, draggable around the minimap edge, and the add-on menu entry
-------------------------------------------------------------------------------

local button
local function placeButton(angle)
    if not button or not Minimap then return end
    local r = ((Minimap:GetWidth() or 140) / 2) + 10
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
    b:SetNormalTexture("Interface\\Icons\\INV_Misc_Book_09")
    b:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
    b:RegisterForClicks("AnyUp")
    b:RegisterForDrag("LeftButton")
    b:SetScript("OnClick", function() Panel.toggle() end)
    b:SetScript("OnDragStart", function(self) self:SetScript("OnUpdate", function() pcall(dragUpdate) end) end)
    b:SetScript("OnDragStop", function(self) self:SetScript("OnUpdate", nil) end)
    b:SetScript("OnEnter", function(self)
        if GameTooltip and GameTooltip.SetOwner then
            GameTooltip:SetOwner(self, "ANCHOR_LEFT")
            GameTooltip:SetText("AI Companion")
            GameTooltip:AddLine("Click: your plan. Drag: move this button.", 1, 1, 1)
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
        icon = "Interface\\Icons\\INV_Misc_Book_09",
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
