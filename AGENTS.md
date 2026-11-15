# Instructions for Codex and other coding agents

## Choose the task

- **Working on this repository:** read and follow [CLAUDE.md](CLAUDE.md) before editing. It contains the shared development rules, architecture, Forever API constraints and required checks, regardless of which assistant you use.
- **Acting as a player's companion:** read [companion/CODEX_GUIDE.md](companion/CODEX_GUIDE.md) and [companion/COMPANION_GUIDE.md](companion/COMPANION_GUIDE.md) before reading snapshots or writing advice. Do not change add-on source while helping a player.
- If the task is unclear, establish whether the user wants development or gameplay help before writing files.

## Rules

- Keep character/account data, snapshots, generated dashboards and private plans outside this repository. The checked-in data add-on stays an empty test template.
- Keep gameplay rules and file schemas in `companion/COMPANION_GUIDE.md`; assistant setup guides link to it. Keep development rules in `CLAUDE.md`, shared through this file.
- Run `python3 -m unittest discover -s tests -v` (requires `lupa`) before every commit, including documentation changes. Report stand-in-client checks separately from real-game validation.
