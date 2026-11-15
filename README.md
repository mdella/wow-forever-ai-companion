# AI Companion for World of Warcraft: Forever

An add-on that saves a snapshot of your character (gear, bags, quests, professions, location, auction prices) to a file on your PC, so an AI assistant can act as your playing companion: what to do next, what to do with each item, what to buy. The advice then shows up in the game, in item tooltips.

It is built for **WoW: Forever** only (client interface 16001). It is not tested on Classic or retail.

> Early version, shared between friends. Expect rough edges.

## What you get

| | Add-on alone | Add-on + your own AI companion |
|---|---|---|
| Character snapshots saved to disk | Yes | Yes |
| Auction price check, with prices in item tooltips | Yes | Yes |
| Rule-based item advice in tooltips (sell, keep, bank, mail to another character, equip) | Yes | Yes |
| Advice specific to you: quests, recipes, vendors, upgrades, "craft this now" | No | Yes |
| A dashboard page for all your characters | No | Yes |
| In-game panel with your plan, steps that tick themselves as you play | Items tab only | Yes |

Nothing is sent anywhere by the add-on. The game does not let add-ons use the network. If you use an AI companion, the data you share with it is processed by your chosen AI service. Keep snapshots and personal plans out of this public repository.

## Install

1. Close the game.
2. Download this repository (Code, then Download ZIP) and unzip it.
3. Find the `_forever_` folder inside your game folder. On Windows it is usually `C:\Program Files (x86)\World of Warcraft\_forever_`.
4. Copy the `AICompanion` folder from inside `AddOns` into `_forever_\Interface\AddOns`. That's the only folder you install.
5. Start the game. On the character screen, open AddOns and check that "AI Companion" is ticked.
6. Log in and type `/aic save`. The screen reloads for a second. That writes your first snapshot.

If you use an assistant with local file access, it creates a second folder, `AICompanion_Data`, the first time it writes advice for you. That folder holds your own advice, shopping lists and plan. Restart the game once when your companion asks, and tick "AI Companion Data" too.

When you update later, replace only the `AICompanion` folder. Never replace or delete `AICompanion_Data`.

## Choose your AI companion

Claude and local Codex use the same snapshots, plan format and data generator. Choose the assistant you already use; the add-on needs no API key or provider setting. ChatGPT chat can also give advice from a pasted summary.

| Option | What it can do | Guide |
|---|---|---|
| Claude with local file and command tools | Read snapshots, write in-game advice, build a dashboard | [Claude setup](companion/CLAUDE_GUIDE.md) |
| Local Codex app, CLI or IDE with file and command tools | Read snapshots, write in-game advice, build a dashboard | [Codex / ChatGPT setup](companion/CODEX_GUIDE.md) |
| ChatGPT chat / Project without local file tools | Give advice in chat from data you share | [Advice-only mode](companion/CODEX_GUIDE.md#3-advice-only-chatgpt) |

All assistants follow [the shared companion guide](companion/COMPANION_GUIDE.md), including Forever source checks and the rule that your in-game data wins. In-game advice needs an assistant running on the game computer with permission to read and write the relevant folders. A remote Codex checkout or an ordinary ChatGPT Project alone cannot update your local game files.

### Use it with Claude

Use a Claude session on the same computer as the game with local file and command tools enabled.

1. Start a new chat in the Claude desktop app.
2. Attach **both** `companion/CLAUDE_GUIDE.md` and `companion/COMPANION_GUIDE.md` from this repository and say:
   *"Be my WoW Forever companion. Follow both attached guides. My game folder is `<path to your _forever_ folder>`."*
3. Approve the folder access Claude asks for. Your companion handles Python and file work; you only perform the in-game actions it requests.

Your companion reads your snapshot, researches Forever sources, and writes its advice into `AICompanion_Data`. Type `/reload` in the game to see it, or fully restart if it created the data add-on or changed its `.toc`.

### Use it with Codex

Use a local Codex session with file and command tools on the game computer. See [OpenAI's Codex documentation](https://learn.chatgpt.com/docs/learn/best-practices) for setup and access options.

1. Open this repository folder as your Codex project or working directory. Codex reads the root `AGENTS.md`; the gameplay guides are in `companion/`.
2. Start a chat and say:
   *"Be my WoW Forever companion, rather than modifying this repository. Read AGENTS.md, companion/CODEX_GUIDE.md and companion/COMPANION_GUIDE.md. My game folder is `<path to your _forever_ folder>`. Use `<private folder outside this repository>` for my persistent plans.json. Read my latest snapshots, preserve any existing plans, and write updated advice for the game."*
3. Grant the folder permissions Codex requests. It handles Python setup, snapshot parsing and generation. If local tools are unavailable, use the ChatGPT advice-only workflow below.
4. Follow its request to `/reload`, or fully restart and enable "AI Companion Data" when the data add-on is first created.

### Use it with ChatGPT chat / Projects

1. Attach **both** `companion/CODEX_GUIDE.md` and `companion/COMPANION_GUIDE.md` to a chat, or add them as Project files and instruct ChatGPT to follow them.
2. In the game, type `/aic save`, then `/aic copy`. Copy the summary into chat.
3. Say: *"Be my WoW Forever companion. Follow both guides in advice-only mode. Here is my saved character summary. Tell me what to do next, label sources that are unconfirmed for Forever, and tell me what information is missing."*

This gives you advice in chat. To put advice into tooltips and the in-game panel, use the local Codex or Claude workflow above. Repeat the save-and-paste step when you want updated advice. [ChatGPT Projects share uploaded files and instructions across chats; they do not by themselves grant access to a folder on your PC.](https://learn.chatgpt.com/docs/projects)

### Switching assistants

Keep your private `plans.json` in one persistent folder outside this repository, and tell the new assistant where it is. Have it read that file and a fresh snapshot before updating advice, preserving all characters and step IDs. Use one assistant at a time. Keep your installed `AICompanion_Data` folder when switching.

## Commands

| Command | What it does |
|---|---|
| `/aic save` | Take a snapshot and reload so it is written to disk. Do this before asking for advice. |
| `/aic ask <question>` | Leave a question for your companion with the next snapshot. |
| `/aic ah` | At an auctioneer: check prices for your bags, bank and shopping list. If you use Auctionator, its prices are used instead and this checks only what Auctionator hasn't seen lately. |
| `/aic ah age <days>` | With Auctionator: how many days its prices count as fresh (default 5). Older than that, the "check prices" button comes back. |
| `/aic sort` | Group your bags by what to do with each item: sell, auction, mail, bank, use, craft, quest, keep. Also a "Sort by advice" button above your bags. |
| `/aic panel` | Open your companion panel: this character's plan, inside the game. Also the book button on the minimap (drag it to move it). |
| `/aic copy` | Show a text summary you can copy and paste. |
| `/aic help` | All commands. |

Logging out also saves a snapshot. Log in to each character once. Opening your bank, a trainer, a vendor, a flight master or a profession window lets the add-on record those too.

## Item tooltips

```
AI Companion: Put in bank                     Nov 14
For Leatherworking 55+.
Auction 7c (2653 listed, 34m ago)          vendor 1c
```

- A date on the right means the advice came from your companion.
- `rule` on the right means the add-on worked it out itself. Rules stay silent when they cannot be sure.
- The auction line appears once you have run a price check.

## Good to know

- WoW: Forever is new. Much of what is written online is about older versions of the game. The shared guide tells every assistant to say so whenever its source is not about Forever. When the game and the advice disagree, the game is right.
- The built-in rules know item categories, not recipes. They will not tell you what to craft.
- The add-on writes its file only on `/reload` or logout. Advice is only as fresh as your last save.
- If you use **Auctionator**, AI Companion reads its prices, so you don't need the "check prices" button. The button only appears when Auctionator's prices are older than 5 days, or Auctionator isn't installed.

## Repository layout

| Path | What |
|---|---|
| `AddOns/AICompanion/` | The add-on: `AICompanion.lua` (snapshots, auction check, tooltips) and `AICompanion_Rules.lua` (built-in advice rules). |
| `AddOns/AICompanion_Data/` | Empty template of the data add-on, used by the tests. Not installed; your companion creates your own copy. |
| `AGENTS.md`, `CLAUDE.md` | Shared repository development instructions; Codex starts with `AGENTS.md`. |
| `companion/COMPANION_GUIDE.md` | Shared gameplay rules, snapshot fields and plan format for every assistant. |
| `companion/CLAUDE_GUIDE.md`, `companion/CODEX_GUIDE.md` | Setup and starting prompts for Claude and Codex / ChatGPT. |
| `companion/` | Tools the assistant uses: `gen_data.py` (writes the data add-on from a plan file), `build.py` and `template.html` (dashboard), `plans.example.json` (plan file format). |
| `FOREVER_INTERFACE` | The game version the add-on supports, set in this one place. `tools/set_interface.py` copies it into the other files. |
| `tests/` | Automated checks: the add-on run inside a stand-in game client. Run on every change. |

## License

MIT. See `LICENSE`.

World of Warcraft is a trademark of Blizzard Entertainment. This project is not affiliated with or endorsed by Blizzard.
