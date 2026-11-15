# AI Companion for WoW: Forever — Claude setup

Read and follow [COMPANION_GUIDE.md](COMPANION_GUIDE.md) for all gameplay rules, snapshot fields, plan formats, commands and troubleshooting. It is the shared source of truth for every assistant. When using attachments, attach both guides; if the shared guide is missing and you cannot read it from the repository, ask for it before advising.

## Rules

1. Use a Claude session with local file and command tools on the same computer as the game for in-game advice. Obtain access to the player's `_forever_` folder and a private persistent folder for `plans.json`.
2. Read snapshots without modifying SavedVariables. Use the repository's `gen_data.py` and optional `build.py` as described in the shared guide. Do the file work for the player.
3. If local access or command execution is unavailable, explain that you can give advice in chat from pasted `/aic copy` output or an attached snapshot. Do not claim to have read or written local files.
4. Before switching from another assistant, locate and read the existing private `plans.json`. Preserve all characters and step IDs.

## Starting prompt

> Be my WoW Forever companion. Follow CLAUDE_GUIDE.md and COMPANION_GUIDE.md. My game folder is `<path to your _forever_ folder>`. Read my latest snapshots, reuse my existing private plans.json if present, and write updated advice for the game.
