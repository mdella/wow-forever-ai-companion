"""Automatic companion updates: the logic shared by every operating system.

The scheduler (a macOS launch agent or a Windows scheduled task) only starts this code. Nothing
here costs AI tokens until a run is both worth it (a change that should change the advice) and
allowed (the daily budget). See README.md in this folder.
"""
import datetime, glob, json, os, shutil, subprocess, sys, time

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the companion/ folder
IS_WIN, IS_MAC = os.name == "nt", sys.platform == "darwin"

DEFAULTS = {
    "enabled": True,
    "dry_run": False,
    # TESTING DEFAULTS while players try this out. Set back to 3 runs a day, 2 hours apart, before
    # this is released (the README table says the same).
    "max_runs_per_day": 50,
    "min_gap_hours": 5 / 60,          # 5 minutes
    "model": "sonnet",
    "max_budget_usd_per_run": 0.75,
    "debounce_seconds": 30,
    "durability_warn_percent": 25,
    "bags_nearly_full_free_slots": 4,
    "web_research_on": ["level_bracket", "new_zone"],
    "level_bracket_size": 5,
    "game_dir": None,        # found automatically when empty
    "account": None,         # the account whose AICompanion.lua was written last, when empty
    "companion_dir": None,   # where plans.json lives; Documents/AI Companion when empty
    "python": None,          # the Python running this, when empty
    "claude_cmd": None,      # ["claude"] from the PATH or its usual install place, when empty
}


# ------------------------------------------------------------------ where things are

def home_dir():
    """Per-user folder for settings, state and logs (never inside the game or the repository)."""
    if os.environ.get("AIC_AUTO_HOME"):
        return os.environ["AIC_AUTO_HOME"]
    if IS_WIN:
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "AICompanion", "auto")
    if IS_MAC:
        return os.path.expanduser("~/Library/Application Support/AICompanion/auto")
    return os.path.expanduser("~/.local/share/AICompanion/auto")


def game_dir_candidates():
    out = []
    if IS_WIN:
        try:
            import winreg
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for sub in (r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft",
                            r"SOFTWARE\Blizzard Entertainment\World of Warcraft"):
                    try:
                        with winreg.OpenKey(root, sub) as k:
                            path = winreg.QueryValueEx(k, "InstallPath")[0]
                            base = os.path.dirname(os.path.normpath(path)) if os.path.basename(
                                os.path.normpath(path)).startswith("_") else path
                            out.append(os.path.join(base, "_forever_"))
                    except OSError:
                        pass
        except ImportError:
            pass
        for pf in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), r"C:\Program Files (x86)"):
            if pf:
                out.append(os.path.join(pf, "World of Warcraft", "_forever_"))
    elif IS_MAC:
        out += ["/Applications/World of Warcraft/_forever_", os.path.expanduser("~/Applications/World of Warcraft/_forever_")]
    return out


def find_claude():
    found = shutil.which("claude")
    if found:
        return [found]
    for p in (os.path.expanduser("~/.local/bin/claude.exe" if IS_WIN else "~/.local/bin/claude"),
              "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if os.path.exists(p):
            return [p]
    return None


class Config(dict):
    """Settings from config.json in home_dir(), with defaults and paths found automatically."""

    def __init__(self):
        super().__init__(DEFAULTS)
        self.home = home_dir()
        self.path = os.path.join(self.home, "config.json")
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.update(json.load(f))
        self.state_dir, self.log_dir = os.path.join(self.home, "state"), os.path.join(self.home, "logs")
        if not self["game_dir"]:
            self["game_dir"] = next((d for d in game_dir_candidates() if os.path.isdir(d)), None)
        if not self["python"]:
            self["python"] = sys.executable
        if not self["claude_cmd"]:
            self["claude_cmd"] = find_claude()
        if not self["companion_dir"]:
            self["companion_dir"] = os.path.join(os.path.expanduser("~"), "Documents", "AI Companion")
        if not self["account"] and self["game_dir"]:
            files = glob.glob(os.path.join(self["game_dir"], "WTF", "Account", "*", "SavedVariables", "AICompanion.lua"))
            if files:
                newest = max(files, key=os.path.getmtime)
                self["account"] = os.path.basename(os.path.dirname(os.path.dirname(newest)))

    def save(self, keys):
        """Write the given settings to config.json, keeping what is there."""
        os.makedirs(self.home, exist_ok=True)
        cur = {}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                cur = json.load(f)
        cur.update({k: self[k] for k in keys})
        atomic_write(self.path, json.dumps(cur, indent=2, sort_keys=True) + "\n")

    @property
    def saved_variables(self):
        if not (self["game_dir"] and self["account"]):
            return None
        return os.path.join(self["game_dir"], "WTF", "Account", self["account"], "SavedVariables", "AICompanion.lua")

    @property
    def data_lua(self):
        return os.path.join(self["game_dir"] or "", "Interface", "AddOns", "AICompanion_Data", "AICompanion_Data.lua")

    @property
    def plans(self):
        return os.path.join(self["companion_dir"], "plans.json")

    @property
    def running_marker(self):
        """Present while an AI run works; the interactive companion waits for it to go."""
        return os.path.join(self["companion_dir"], ".automation-running")


def atomic_write(path, text):
    with open(path + ".new", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(path + ".new", path)


def now():
    return datetime.datetime.now()


def stamp(t=None):
    return (t or now()).strftime("%Y-%m-%d %H:%M:%S")


class Store:
    """state/ and logs/ under home_dir()."""

    def __init__(self, cfg):
        self.cfg = cfg
        os.makedirs(cfg.state_dir, exist_ok=True)
        os.makedirs(cfg.log_dir, exist_ok=True)

    def load(self, name, default):
        try:
            with open(os.path.join(self.cfg.state_dir, name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def save(self, name, value):
        atomic_write(os.path.join(self.cfg.state_dir, name), json.dumps(value, indent=1, sort_keys=True))

    def log(self, msg):
        with open(os.path.join(self.cfg.log_dir, "gatekeeper.log"), "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (stamp(), msg))

    def runs(self):
        p = os.path.join(self.cfg.log_dir, "runs.jsonl")
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def add_run(self, rec):
        with open(os.path.join(self.cfg.log_dir, "runs.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")


class Lock:
    """One gatekeeper at a time, on every operating system."""

    def __init__(self, path):
        self.f = open(path, "a+")

    def acquire(self):
        try:
            if IS_WIN:
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False


# ------------------------------------------------------------------ reading the snapshot

def load_db(path):
    import lupa.lua51 as lua51
    L = lua51.LuaRuntime(unpack_returned_tuples=True)
    with open(path, encoding="utf-8", errors="replace") as f:
        L.execute(f.read())

    def conv(v):
        if lua51.lua_type(v) == "table":
            return {k: conv(v[k]) for k in v.keys()}
        return v
    return conv(L.globals().AICompanionDB) or {}


def lst(x):
    return list(x.values()) if isinstance(x, dict) else (x or [])


def summarize(key, store, db, cfg):
    """The handful of facts that should change the advice, for one character."""
    s = store.get("snapshot") or {}
    c = s.get("character") or {}
    loc = s.get("location") or {}
    quests = {}
    for q in lst(s.get("quests")):
        if isinstance(q, dict) and q.get("questID"):
            quests[str(q["questID"])] = {"title": q.get("title"), "ready": bool(q.get("readyForTurnIn") or q.get("complete"))}
    bags = [b for b in lst(s.get("bags")) if isinstance(b, dict) and b.get("bag") != 5]
    low = []
    for e in lst(s.get("equipment")):
        if isinstance(e, dict) and e.get("durabilityMax"):
            if 100.0 * (e.get("durability") or 0) / e["durabilityMax"] <= cfg["durability_warn_percent"]:
                low.append(e.get("slotName"))
    profs = {}
    for p in lst((s.get("skills") or {}).get("professions")):
        if isinstance(p, dict) and p.get("name"):
            profs[p["name"]] = {"rank": p.get("rank"), "max": p.get("max")}
    recipes = {k: (v or {}).get("seenAtText") for k, v in (store.get("recipes") or {}).items() if isinstance(v, dict)}
    questions = [q.get("text") for q in lst(db.get("questions")) if isinstance(q, dict) and q.get("character") == key]
    return {
        "name": c.get("name") or key.split("@")[0], "level": c.get("level"), "zone": loc.get("zone"),
        "talentPoints": c.get("unspentTalentPoints") or 0, "quests": quests,
        "bagsFree": sum(b.get("free") or 0 for b in bags), "durabilityLow": sorted(x for x in low if x),
        "equipment": {e.get("slotName"): e.get("name") for e in lst(s.get("equipment")) if isinstance(e, dict)},
        "professions": profs, "bank": (store.get("bank") or {}).get("seenAtText"), "recipes": recipes,
        "trainers": sorted((store.get("trainers") or {}).keys()), "merchants": sorted((store.get("merchants") or {}).keys()),
        "questions": questions, "takenAtText": s.get("takenAtText"),
    }


# Kinds that never start an AI run on their own.
QUIET = {"zone", "first_seen"}


def changes(old, new, seen_zones, cfg):
    """What changed, as (kind, text)."""
    n = new["name"]
    if old is None:
        return [("first_seen", "%s: first automatic look at this character" % n)]
    out = []
    if (new["level"] or 0) > (old["level"] or 0):
        out.append(("level_up", "%s reached level %s (was %s)" % (n, new["level"], old["level"])))
        size = cfg["level_bracket_size"]
        if ((new["level"] or 1) - 1) // size != ((old["level"] or 1) - 1) // size:
            out.append(("level_bracket", "%s entered a new level range (%s+)" % (n, new["level"])))
    if new["zone"] and new["zone"] != old["zone"]:
        out.append(("zone" if new["zone"] in seen_zones else "new_zone", "%s moved to %s" % (n, new["zone"])))
    oq, nq = old["quests"], new["quests"]
    for qid in sorted(nq.keys() - oq.keys()):
        out.append(("quest_added", "%s picked up quest: %s" % (n, nq[qid]["title"])))
    for qid in sorted(oq.keys() - nq.keys()):
        out.append(("quest_gone", "%s finished or dropped quest: %s" % (n, oq[qid]["title"])))
    for qid in sorted(nq.keys() & oq.keys()):
        if nq[qid]["ready"] and not oq[qid]["ready"]:
            out.append(("quest_ready", "%s can turn in: %s" % (n, nq[qid]["title"])))
    if new["talentPoints"] > old["talentPoints"]:
        out.append(("talents", "%s has %s unspent talent points" % (n, new["talentPoints"])))
    if new["bagsFree"] <= cfg["bags_nearly_full_free_slots"] < old["bagsFree"]:
        out.append(("bags_full", "%s's bags are nearly full (%s free)" % (n, new["bagsFree"])))
    for slot in sorted(set(new["durabilityLow"]) - set(old["durabilityLow"])):
        out.append(("repair", "%s's %s needs repair" % (n, slot)))
    for slot, item in sorted(new["equipment"].items(), key=lambda kv: str(kv[0])):
        if old["equipment"].get(slot) != item:
            out.append(("gear", "%s equipped %s (%s)" % (n, item, slot)))
    for prof, p in sorted(new["professions"].items()):
        op = old["professions"].get(prof)
        if not op:
            out.append(("profession", "%s learned %s" % (n, prof)))
        elif p["max"] != op["max"]:
            out.append(("profession", "%s trained %s to the next tier (max %s)" % (n, prof, p["max"])))
        elif (p["rank"] or 0) // 25 != (op["rank"] or 0) // 25:
            out.append(("profession", "%s's %s reached %s" % (n, prof, p["rank"])))
    if new["bank"] != old["bank"]:
        out.append(("bank", "%s's bank was recorded (%s)" % (n, new["bank"])))
    for prof, at in sorted(new["recipes"].items()):
        if old["recipes"].get(prof) != at:
            out.append(("recipes", "%s's %s recipes were recorded" % (n, prof)))
    for kind in ("trainers", "merchants"):
        for who in sorted(set(new[kind]) - set(old[kind])):
            out.append((kind, "%s visited %s (%s)" % (n, who, kind[:-1])))
    for q in new["questions"][len(old["questions"]):]:
        out.append(("question", "%s asked: %s" % (n, q)))
    return out


# ------------------------------------------------------------------ budget

def gap_text(hours):
    """The minimum gap in plain words: 5 min, 2h."""
    return "%d min" % round(hours * 60) if hours < 1 else "%gh" % hours


def budget_block(cfg, store, at=None):
    """Why an AI run may not start now, or None."""
    at = at or now()
    today = at.strftime("%Y-%m-%d")
    done = [r for r in store.runs() if r.get("started", "").startswith(today)]
    if len(done) >= cfg["max_runs_per_day"]:
        return "daily limit reached (%d of %d)" % (len(done), cfg["max_runs_per_day"])
    if done:
        last = datetime.datetime.strptime(done[-1]["started"], "%Y-%m-%d %H:%M:%S")
        ready = last + datetime.timedelta(hours=cfg["min_gap_hours"])
        if ready > at:
            return "minimum gap: next run allowed after %s" % ready.strftime("%H:%M")
    return None


# ------------------------------------------------------------------ the AI run

def rule_path(path):
    """A path as Claude Code permission rules write it: //absolute, with Windows drives as //c/..."""
    p = os.path.abspath(path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = "/" + p[0].lower() + p[2:]
    return "/" + p


def shell_path(path):
    """A path the AI's shell can run: forward slashes work in Git Bash on Windows and everywhere else."""
    return os.path.abspath(path).replace("\\", "/")


def prompt_for(cfg, pending):
    kinds = {c["kind"] for c in pending}
    web = sorted(kinds & set(cfg["web_research_on"]))
    research = ("You may use web search, only for what these changes need: %s. Label every source as Forever "
                "or not, as the guide says." % ", ".join(web)) if web else \
        "Do not use web search. Work from plans.json and the snapshot."
    py = shell_path(cfg["python"])
    text = """You are the player's WoW Forever AI companion, running automatically after the game saved. Follow the guide at {guide} (read only the sections you need).

What changed since the last automatic update (found by a script):
{changes}

Do this:
1. Read {plans}. Read only the parts of the snapshot these changes need: parse "{sv}" with `{py}` and `lupa`, and print just those parts. Don't print the whole file.
2. Update only the affected parts of plans.json (next steps, quests, gear, professions, items, answers to questions). Leave the rest as it is.
3. Write it into the game: `"{py}" "{gendata}" "{plans}" "{data}"`. If it says the game must be restarted, say so.
4. Read the data file back and check it.

{research}

Finish with two to four plain sentences for the player: what changed in the advice, and what to do in game (usually /reload).""".format(
        guide=shell_path(os.path.join(TOOLS, "CLAUDE_GUIDE.md")), changes="\n".join("- " + c["text"] for c in pending),
        plans=shell_path(cfg.plans), sv=shell_path(cfg.saved_variables), py=py,
        gendata=shell_path(os.path.join(TOOLS, "gen_data.py")), data=shell_path(cfg.data_lua), research=research)
    return text, bool(web)


def claude_command(cfg, prompt, web):
    allowed = ["Read", "Glob", "Grep",
               "Edit(%s/**)" % rule_path(cfg["companion_dir"]), "Write(%s/**)" % rule_path(cfg["companion_dir"]),
               "Bash(%s:*)" % shell_path(cfg["python"]), 'Bash("%s":*)' % shell_path(cfg["python"])]
    if web:
        allowed += ["WebSearch", "WebFetch"]
    cmd = list(cfg["claude_cmd"]) + ["-p", prompt, "--output-format", "json", "--model", cfg["model"],
                                     "--no-session-persistence", "--add-dir", cfg["game_dir"], "--add-dir", TOOLS,
                                     "--allowedTools", *allowed]
    if cfg.get("max_budget_usd_per_run"):
        cmd += ["--max-budget-usd", str(cfg["max_budget_usd_per_run"])]
    return cmd


def run_ai(cfg, store, pending):
    prompt, web = prompt_for(cfg, pending)
    cmd = claude_command(cfg, prompt, web)
    started = now()
    atomic_write(cfg.running_marker, "%d %s\n" % (os.getpid(), stamp(started)))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        p = subprocess.run(cmd, cwd=cfg["companion_dir"], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=1200, creationflags=flags)
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        out, err, code = "", "timed out after 20 minutes", -1
    except OSError as e:
        out, err, code = "", "could not start the AI: %s" % e, -2
    finally:
        try:
            os.remove(cfg.running_marker)
        except OSError:
            pass
    try:
        res = json.loads(out)
    except ValueError:
        res = {}
    usage = res.get("usage") or {}
    rec = {"started": stamp(started), "seconds": round((now() - started).total_seconds()), "exit": code,
           "ok": code == 0 and bool(res) and not res.get("is_error"), "model": cfg["model"], "web": web,
           "cost_usd": res.get("total_cost_usd"), "turns": res.get("num_turns"),
           "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
           "cache_read_tokens": usage.get("cache_read_input_tokens"),
           "cache_write_tokens": usage.get("cache_creation_input_tokens"),
           "kinds": sorted({c["kind"] for c in pending}), "subtype": res.get("subtype")}
    store.add_run(rec)
    atomic_write(os.path.join(cfg.log_dir, "last_result.txt"),
                 (res.get("result") or out or "") + ("\n\n[stderr]\n" + err if err else ""))
    store.log("AI run %s in %ss, est. cost %s, changes %s" % (
        "ok" if rec["ok"] else "FAILED (exit %s)" % code, rec["seconds"], rec["cost_usd"], rec["kinds"]))
    return rec["ok"]


def build_dashboard(cfg, store):
    if not os.path.exists(cfg.plans):
        return
    out = os.path.join(cfg["companion_dir"], "out", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p = subprocess.run([cfg["python"], os.path.join(TOOLS, "build.py"), cfg.saved_variables, cfg.plans,
                        os.path.join(TOOLS, "template.html"), out], cwd=TOOLS, capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    store.log("dashboard %s" % ("rebuilt" if p.returncode == 0 else
                                "failed: " + ((p.stderr or "").strip().splitlines() or ["?"])[-1]))


# ------------------------------------------------------------------ deciding

def decide(cfg, mode, notify=None, out=print):
    """mode: watch (debounce first), poll and now (no debounce), force (ignore the budget), dry (change nothing)."""
    store = Store(cfg)
    dry = mode == "dry" or cfg.get("dry_run")
    sv = cfg.saved_variables
    if not cfg.get("enabled") and mode not in ("dry", "force"):
        return store.log("disabled in config.json")
    if not sv or not os.path.exists(sv):
        return store.log("no AICompanion.lua found yet (game folder %s, account %s)" % (cfg["game_dir"], cfg["account"]))
    if mode == "watch":
        time.sleep(cfg["debounce_seconds"])
    while time.time() - os.path.getmtime(sv) < 5:      # the game is still writing it
        time.sleep(2)
    state = store.load("state.json", {"mtime": 0, "chars": {}, "zones": {}})
    pending = store.load("pending.json", [])
    mtime = os.path.getmtime(sv)
    found = []
    if mtime != state["mtime"]:
        db = load_db(sv)
        for key, cstore in sorted((db.get("characters") or {}).items()):
            if not isinstance(cstore, dict) or not cstore.get("snapshot"):
                continue
            new = summarize(key, cstore, db, cfg)
            seen = set(state["zones"].get(key, []))
            for kind, text in changes(state["chars"].get(key), new, seen, cfg):
                if kind not in QUIET:
                    found.append({"kind": kind, "text": text, "at": stamp()})
            if new["zone"]:
                seen.add(new["zone"])
            state["chars"][key], state["zones"][key] = new, sorted(seen)
        state["mtime"] = mtime
        if not dry:
            store.save("state.json", state)
            store.save("pending.json", pending + found)
            build_dashboard(cfg, store)
            store.log("snapshot read: %d new change(s), %d pending" % (len(found), len(pending) + len(found)))
    pending = pending + found
    if dry:
        out("new changes: %d" % len(found))
        for c in found:
            out("  [%s] %s" % (c["kind"], c["text"]))
    if not pending:
        if dry:
            out("nothing pending: no AI run")
        return
    if not os.path.exists(cfg.plans):
        msg = "changes pending, but there is no plans.json in %s yet; the first plan comes from your companion" % cfg["companion_dir"]
        return out(msg) if dry else store.log(msg)
    block = None if mode == "force" else budget_block(cfg, store)
    if dry:
        out("pending %d; budget: %s" % (len(pending), block or "a run is allowed now"))
        out("\n--- prompt that would be sent ---\n" + prompt_for(cfg, pending)[0])
        return
    if block:
        return store.log("AI run deferred: %s" % block)
    if os.path.exists(cfg.running_marker):
        return store.log("AI run deferred: another run is in progress")
    if not cfg["claude_cmd"]:
        return store.log("AI run skipped: Claude Code (claude) not found")
    if run_ai(cfg, store, pending):
        store.save("pending.json", [])
        if notify:
            notify("AI Companion", "Advice updated. Type /reload in the game.")


# ------------------------------------------------------------------ reports

def report(cfg, out=print):
    rs = Store(cfg).runs()
    if not rs:
        return out("no AI runs yet")
    days = {}
    for r in rs:
        d = days.setdefault(r["started"][:10], {"runs": 0, "cost": 0.0, "in": 0, "out": 0, "failed": 0})
        d["runs"] += 1
        d["cost"] += r.get("cost_usd") or 0
        d["in"] += sum(r.get(k) or 0 for k in ("input_tokens", "cache_read_tokens", "cache_write_tokens"))
        d["out"] += r.get("output_tokens") or 0
        d["failed"] += 0 if r.get("ok") else 1
    out("day         runs  failed  input tok  output tok  est. cost")
    for day in sorted(days):
        d = days[day]
        out("%s  %4d  %6d  %9d  %10d  $%.3f" % (day, d["runs"], d["failed"], d["in"], d["out"], d["cost"]))
    last7 = [days[k] for k in sorted(days)[-7:]]
    n = sum(d["runs"] for d in last7) or 1
    out("\nlast %d active day(s): %.1f runs/day, $%.3f per run, %d input + %d output tokens per run" % (
        len(last7), sum(d["runs"] for d in last7) / len(last7), sum(d["cost"] for d in last7) / n,
        sum(d["in"] for d in last7) / n, sum(d["out"] for d in last7) / n))
    out("limits: %d runs/day, %s apart, model %s, cap $%s per run" % (
        cfg["max_runs_per_day"], gap_text(cfg["min_gap_hours"]), cfg["model"], cfg.get("max_budget_usd_per_run")))


def check(cfg, scheduler_installed, out=print):
    """Everything a tester needs to confirm, in plain words. Returns True when all is well."""
    ok = True

    def line(good, text, fix=None):
        nonlocal ok
        ok = ok and good
        out(("OK    " if good else "FIX   ") + text + ("" if good or not fix else "\n      -> " + fix))

    line(bool(cfg["game_dir"]) and os.path.isdir(cfg["game_dir"] or ""), "game folder: %s" % cfg["game_dir"],
         'set "game_dir" in %s to your _forever_ folder' % cfg.path)
    sv = cfg.saved_variables
    line(bool(sv) and os.path.exists(sv), "snapshot file: %s" % sv,
         "log in once with AI Companion enabled and type /aic save")
    try:
        import lupa  # noqa: F401
        line(True, "Python with lupa: %s" % cfg["python"])
    except ImportError:
        line(False, "Python with lupa: %s" % cfg["python"], '"%s" -m pip install lupa' % cfg["python"])
    claude_ok = False
    if cfg["claude_cmd"]:
        try:
            v = subprocess.run(list(cfg["claude_cmd"]) + ["--version"], capture_output=True, text=True, timeout=60,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            claude_ok = v.returncode == 0
            ver = (v.stdout or "").strip()
        except (OSError, subprocess.TimeoutExpired):
            ver = ""
    line(claude_ok, "Claude Code: %s" % (" ".join(cfg["claude_cmd"] or []) + (" (%s)" % ver if claude_ok else "")),
         "install Claude Code and sign in once (it needs a paid Claude plan)")
    line(os.path.isdir(cfg["companion_dir"]), "companion folder: %s" % cfg["companion_dir"],
         'create it, or set "companion_dir" in %s to where your plans.json is' % cfg.path)
    line(os.path.exists(cfg.plans), "plan file: %s" % cfg.plans,
         "ask your companion for a first plan; automatic updates start after that")
    line(scheduler_installed, "watcher installed", "run the installer for your system in this folder")
    store = Store(cfg)
    today = now().strftime("%Y-%m-%d")
    out("      runs today: %d of %d; pending changes: %d; settings: %s" % (
        len([r for r in store.runs() if r.get("started", "").startswith(today)]), cfg["max_runs_per_day"],
        len(store.load("pending.json", [])), cfg.path))
    return ok
