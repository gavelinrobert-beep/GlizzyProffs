# 🐉 WoW TBC Guild Recipe Bot

A Discord bot for tracking guild member recipes and professions in **World of Warcraft: Burning Crusade Anniversary**.

---

## Setup

### 1. Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **New Application** → give it a name (e.g. "Guild Recipe Tracker")
3. Go to **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable **Message Content Intent**
5. Copy your **Bot Token** (keep this secret!)
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`
7. Copy the generated URL and invite the bot to your server

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Your Token

Either set an environment variable:
```bash
export DISCORD_TOKEN="your-token-here"    # Linux/Mac
set DISCORD_TOKEN=your-token-here         # Windows
```

Or edit `bot.py` and replace `"YOUR_BOT_TOKEN_HERE"` with your token directly (not recommended for shared code).

### 4. Run the Bot

```bash
python bot.py
```

The bot will sync slash commands automatically on startup. It may take up to an hour for commands to appear globally, but they show instantly in your server if you specify a guild ID.

---

## Commands

| Command | Description |
|---|---|
| `/register <char_name> [realm]` | Register your WoW character |
| `/add_profession <profession> [skill_level]` | Add/update a profession |
| `/add_recipe <profession> <recipe_name> [notes]` | Add a recipe you know |
| `/remove_recipe <recipe_name>` | Remove a recipe |
| `/who_can_craft <recipe_name>` | Find who can craft something |
| `/list_recipes <profession>` | List all guild recipes for a profession |
| `/my_recipes` | View all your recipes (private) |
| `/guild_roster` | Show all members and their professions |
| `/help` | Show all commands |

---

## Example Usage

```
/register Thundermaw Whitemane
/add_profession Alchemy 375
/add_recipe Alchemy "Flask of Supreme Power" "2hr CD"
/add_recipe Tailoring "Primal Mooncloth Bag"
/who_can_craft Flask
/list_recipes Alchemy
```

---

## Data Storage

All data is stored locally in `guild_recipes.db` (SQLite). Back this file up regularly to avoid losing guild data.

---

## Tips

- Members **must use `/register` first** before adding professions or recipes
- Use the **notes field** to track cooldowns, mat requirements, etc.
- `/who_can_craft` supports partial name matching — searching "bag" finds all bag recipes
- `/my_recipes` is ephemeral (only visible to you)
