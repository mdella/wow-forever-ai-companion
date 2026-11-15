# AI Companion for World of Warcraft: Forever

An add-on that saves a snapshot of your character (gear, bags, quests, professions, location, auction prices) to a file on your PC, so an AI assistant can act as your playing companion: what to do next, what to do with each item, what to buy. The advice then shows up in the game, in item tooltips.

It is built for **WoW: Forever** only (client interface 16001). It is not tested on Classic or retail.

> Early version, shared between friends. Expect rough edges.

## What you get

| | Add-on alone | Add-on + your own Claude |
|---|---|---|
| Character snapshots saved to disk | Yes | Yes |
| Auction price check, with prices in item tooltips | Yes | Yes |
| Rule-based item advice in tooltips (sell, keep, bank, mail to another character, equip) | Yes | Yes |
| Advice specific to you: quests, recipes, vendors, upgrades, "craft this now" | No | Yes |
| A dashboard page for all your characters | No | Yes |
| In-game panel with your plan, steps that tick themselves as you play | Items tab only | Yes |

Nothing is sent anywhere by the add-on. The game does not let add-ons use the network. Your data stays on your PC, and in your own Claude conversation if you use one.

## Install

1. Close the game.
2. Download this repository (Code, then Download ZIP) and unzip it.
3. Find the `_forever_` folder inside your game folder. On Windows it is usually `C:\Program Files (x86)\World of Warcraft\_forever_`.
4. Copy the two folders inside `AddOns` (`AICompanion` and `AICompanion_Data`) into `_forever_\Interface\AddOns`.
5. Start the game. On the character screen, open AddOns and check that "AI Companion" and "AI Companion Data" are both ticked.
6. Log in and type `/aic save`. The screen reloads for a second. That writes your first snapshot.

When you update later, replace only the `AICompanion` folder. `AICompanion_Data` holds your own advice and shopping lists.

## Use it with Claude

You need a Claude subscription and the Claude desktop app on the same computer as the game.

1. Start a new chat in the Claude desktop app.
2. Attach `companion/CLAUDE_GUIDE.md` from this repository and say:
   *"Be my WoW Forever companion. Follow the attached guide. My game folder is `<path to your _forever_ folder>`."*
3. Approve the folder access Claude asks for.

Claude reads your snapshot, researches Forever sources, and writes its advice into `AICompanion_Data`. Type `/reload` in the game to see it.

## Commands

| Command | What it does |
|---|---|
| `/aic save` | Take a snapshot and reload so it is written to disk. Do this before asking for advice. |
| `/aic ask <question>` | Leave a question for your companion with the next snapshot. |
| `/aic ah` | At an auctioneer: check prices for your bags, bank and shopping list. |
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

- WoW: Forever is new. Much of what is written online is about older versions of the game. The guide tells Claude to say so whenever its source is not about Forever. When the game and the advice disagree, the game is right.
- The built-in rules know item categories, not recipes. They will not tell you what to craft.
- The add-on writes its file only on `/reload` or logout. Advice is only as fresh as your last save.

## Repository layout

| Path | What |
|---|---|
| `AddOns/AICompanion/` | The add-on: `AICompanion.lua` (snapshots, auction check, tooltips) and `AICompanion_Rules.lua` (built-in advice rules). |
| `AddOns/AICompanion_Data/` | Your shopping lists and item advice. Ships empty. |
| `companion/CLAUDE_GUIDE.md` | Instructions for the assistant. |
| `companion/` | Tools the assistant uses: `gen_data.py` (writes the data add-on from a plan file), `build.py` and `template.html` (dashboard), `plans.example.json` (plan file format). |
| `tests/` | Automated checks: the add-on run inside a stand-in game client. Run on every change. |

## License

MIT. See `LICENSE`.

World of Warcraft is a trademark of Blizzard Entertainment. This project is not affiliated with or endorsed by Blizzard.
