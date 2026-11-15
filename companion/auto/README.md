# Automatic companion updates (optional, Claude)

Your companion's advice can update itself after you play, without you asking. When the game saves (`/aic save`, `/reload` or logging out), a small program on your computer checks what changed. Only when something should change your advice does it ask Claude, and never more often than your daily limit.

Watching and checking cost nothing. Only the Claude update itself uses your Claude plan.

## What you need

- **Claude Code**, installed and signed in once, on a paid Claude plan (Pro or Max). See Claude's own install instructions for your system.
- **Python 3.** On Windows, tick "Add python.exe to PATH" when installing it.
- **A first plan from your companion.** Automatic updates keep an existing plan current. They don't write the first one.

## Install

1. Open this folder, `companion/auto`.
2. Double-click **Install-Windows.cmd** (Windows) or **Install-Mac.command** (Mac).
   - **Windows:** if "Windows protected your PC" appears, click **More info → Run anyway**.
   - **Mac:** if macOS says it can't be opened, go to **System Settings → Privacy & Security → Open Anyway**.
3. It sets up its own copy of what it needs, starts watching, and shows a checklist. Every line should say `OK`. A `FIX` line says what to do.

To check it any time, double-click **Check-Windows.cmd** or **Check-Mac.command**. To stop it, double-click **Uninstall-Windows.cmd** or **Uninstall-Mac.command**.

## What starts an update

- a level-up, or a new level range
- quests picked up, finished or ready to turn in
- a new zone
- new talent points
- bags nearly full
- gear that needs repair, or new gear
- profession milestones
- opening your bank, a profession window, a trainer or a vendor
- a question left with `/aic ask`

A `/reload` with nothing new, or a zone you've been to before, starts nothing. The dashboard page is rebuilt on every save, for free.

When an update finishes, you get a notification: type `/reload` in the game to see the new advice.

## Limits

The defaults:
- at most **50 updates a day**, temporary while it's being tested (normally 3)
- at least **5 minutes apart**, temporary while it's being tested (normally 2 hours)
- Claude's **Sonnet** model
- web research only for a new zone or level range

When a limit is reached, the changes wait for the next allowed time. Nothing is lost.

The settings are in `config.json`. Its location is shown by the Check script:
- **Windows:** `%APPDATA%\AICompanion\auto`
- **Mac:** `~/Library/Application Support/AICompanion/auto`

| Setting | Default | What it does |
|---|---|---|
| `max_runs_per_day` | 50 while testing (normally 3) | Updates allowed per day |
| `min_gap_hours` | 0.083 (5 minutes) while testing (normally 2) | Hours between updates |
| `model` | `sonnet` | Claude model for updates |
| `max_budget_usd_per_run` | 0.75 | Spending cap for one update |
| `enabled` | true | false pauses it without uninstalling |
| `companion_dir` | Documents/AI Companion | Where your `plans.json` is |
| `game_dir`, `account` | found automatically | Your `_forever_` folder and WoW account folder |

## How much it uses

Run `python aic_auto.py report` with the Python the installer set up. It shows each day's updates, tokens and estimated cost, plus the average over the last 7 days.

On a subscription, the cost figure is an estimate that counts toward your plan's usage limits, not a charge. One test update cost an estimated $0.15. Use the report to set limits that fit your plan.

## How it works

- **Watching:**
  - **Mac:** a launch agent runs the check whenever the game's save folder changes, and every 30 minutes for changes that were waiting.
  - **Windows:** a scheduled task runs the check every 5 minutes while you're signed in. Task Scheduler can't watch a file, so the check compares the save file's timestamp, which takes milliseconds and starts nothing if it's unchanged.
- **Checking:** the same Python code on both systems (`core.py`) compares your characters with the last check and keeps a short list of what changed.
- **Updating:** Claude Code runs without a window, in your companion folder. It can edit files only there, gets only the list of changes, and writes the advice into the game with `gen_data.py`. While it works, a `.automation-running` file in the companion folder tells your companion conversation to wait.
- **Logs:** `logs/` next to `config.json`.
