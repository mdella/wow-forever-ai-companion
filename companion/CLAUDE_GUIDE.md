# AI Companion for WoW: Forever — Claude

The rules, the working loop and every file format are in [`SKILL.md`](SKILL.md), in this folder. Read it in full and follow it. This file holds only what is specific to Claude.

## Setup

1. **Claude with skills (Claude Code, the Claude desktop app):** install this folder as the skill `wow-forever-companion` (README, "Give your assistant the skill"). Claude then loads `SKILL.md` on its own when the player mentions the game.
2. **Claude without skills:** the player attaches `SKILL.md` to the chat. If only this file was attached, ask for `SKILL.md` before giving any advice.
3. **Folder access:** ask for access to the player's `_forever_` folder through Claude's own folder permission. Without it, follow "Without file access" in `SKILL.md`.

## Changelog

- Guide — The rules and formats moved to `SKILL.md`. This file keeps only Claude's setup.
