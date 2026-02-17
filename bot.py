import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
from typing import Optional

# ── Configuration ──────────────────────────────────────────────
# Set your bot token in an environment variable: DISCORD_TOKEN
TOKEN = os.environ.get("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")

# TBC Professions
PROFESSIONS = [
    "Alchemy", "Blacksmithing", "Enchanting", "Engineering",
    "Herbalism", "Jewelcrafting", "Leatherworking", "Mining",
    "Skinning", "Tailoring", "Cooking", "First Aid", "Fishing"
]

# ── Database Setup ─────────────────────────────────────────────
def get_db():
    db = sqlite3.connect("guild_recipes.db")
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            discord_id    TEXT PRIMARY KEY,
            discord_name  TEXT NOT NULL,
            char_name     TEXT NOT NULL,
            realm         TEXT DEFAULT 'Unknown'
        );

        CREATE TABLE IF NOT EXISTS professions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id    TEXT NOT NULL,
            profession    TEXT NOT NULL,
            skill_level   INTEGER DEFAULT 0,
            FOREIGN KEY (discord_id) REFERENCES members(discord_id),
            UNIQUE(discord_id, profession)
        );

        CREATE TABLE IF NOT EXISTS recipes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id    TEXT NOT NULL,
            profession    TEXT NOT NULL,
            recipe_name   TEXT NOT NULL,
            notes         TEXT DEFAULT '',
            FOREIGN KEY (discord_id) REFERENCES members(discord_id)
        );
    """)
    db.commit()
    db.close()

# ── Bot Setup ──────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

class GuildBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Slash commands synced.")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="WoW TBC | /help"))

bot = GuildBot()

# ── Autocomplete Helpers ───────────────────────────────────────
async def profession_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=p, value=p)
        for p in PROFESSIONS if current.lower() in p.lower()
    ]

# ── /register ─────────────────────────────────────────────────
@bot.tree.command(name="register", description="Register your WoW character with the guild bot")
@app_commands.describe(
    char_name="Your WoW character name",
    realm="Your realm name (default: Unknown)"
)
async def register(interaction: discord.Interaction, char_name: str, realm: str = "Unknown"):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO members (discord_id, discord_name, char_name, realm) VALUES (?, ?, ?, ?)",
        (str(interaction.user.id), interaction.user.display_name, char_name, realm)
    )
    db.commit()
    db.close()
    embed = discord.Embed(
        title="✅ Character Registered",
        description=f"**{char_name}** on **{realm}** has been registered to {interaction.user.mention}!",
        color=0xF4A92A
    )
    embed.set_footer(text="Use /add_profession to add your professions.")
    await interaction.response.send_message(embed=embed)

# ── /add_profession ────────────────────────────────────────────
@bot.tree.command(name="add_profession", description="Add or update a profession for your character")
@app_commands.describe(
    profession="Your profession",
    skill_level="Your current skill level (1-375)"
)
@app_commands.autocomplete(profession=profession_autocomplete)
async def add_profession(interaction: discord.Interaction, profession: str, skill_level: int = 0):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE discord_id = ?", (str(interaction.user.id),)).fetchone()
    if not member:
        await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
        db.close()
        return
    if profession not in PROFESSIONS:
        await interaction.response.send_message(f"❌ Unknown profession. Valid: {', '.join(PROFESSIONS)}", ephemeral=True)
        db.close()
        return
    db.execute(
        "INSERT OR REPLACE INTO professions (discord_id, profession, skill_level) VALUES (?, ?, ?)",
        (str(interaction.user.id), profession, skill_level)
    )
    db.commit()
    db.close()
    embed = discord.Embed(
        title="⚒️ Profession Updated",
        description=f"**{member['char_name']}** — {profession} ({skill_level}/375)",
        color=0x3A9BD5
    )
    await interaction.response.send_message(embed=embed)

# ── /add_recipe ────────────────────────────────────────────────
@bot.tree.command(name="add_recipe", description="Add a recipe you know to the guild database")
@app_commands.describe(
    profession="The profession this recipe belongs to",
    recipe_name="Name of the recipe (e.g. Primal Mooncloth Bag)",
    notes="Optional notes (e.g. 'cooldown 4 days', 'need mats')"
)
@app_commands.autocomplete(profession=profession_autocomplete)
async def add_recipe(interaction: discord.Interaction, profession: str, recipe_name: str, notes: str = ""):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE discord_id = ?", (str(interaction.user.id),)).fetchone()
    if not member:
        await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
        db.close()
        return
    # Prevent duplicates for same person
    existing = db.execute(
        "SELECT id FROM recipes WHERE discord_id = ? AND profession = ? AND LOWER(recipe_name) = LOWER(?)",
        (str(interaction.user.id), profession, recipe_name)
    ).fetchone()
    if existing:
        await interaction.response.send_message(f"⚠️ You already have **{recipe_name}** listed!", ephemeral=True)
        db.close()
        return
    db.execute(
        "INSERT INTO recipes (discord_id, profession, recipe_name, notes) VALUES (?, ?, ?, ?)",
        (str(interaction.user.id), profession, recipe_name, notes)
    )
    db.commit()
    db.close()
    embed = discord.Embed(
        title="📜 Recipe Added",
        description=f"**{recipe_name}** ({profession})\nAdded for **{member['char_name']}**",
        color=0x2ECC71
    )
    if notes:
        embed.add_field(name="Notes", value=notes)
    await interaction.response.send_message(embed=embed)

# ── /remove_recipe ─────────────────────────────────────────────
@bot.tree.command(name="remove_recipe", description="Remove a recipe from your list")
@app_commands.describe(
    recipe_name="Name of the recipe to remove"
)
async def remove_recipe(interaction: discord.Interaction, recipe_name: str):
    db = get_db()
    result = db.execute(
        "DELETE FROM recipes WHERE discord_id = ? AND LOWER(recipe_name) = LOWER(?)",
        (str(interaction.user.id), recipe_name)
    )
    db.commit()
    db.close()
    if result.rowcount == 0:
        await interaction.response.send_message(f"❌ No recipe named **{recipe_name}** found on your character.", ephemeral=True)
    else:
        await interaction.response.send_message(f"🗑️ Removed **{recipe_name}** from your recipes.")

# ── /who_can_craft ─────────────────────────────────────────────
@bot.tree.command(name="who_can_craft", description="Find guild members who know a specific recipe")
@app_commands.describe(recipe_name="Part of the recipe name to search for")
async def who_can_craft(interaction: discord.Interaction, recipe_name: str):
    db = get_db()
    rows = db.execute("""
        SELECT m.char_name, m.discord_name, r.recipe_name, r.profession, r.notes
        FROM recipes r
        JOIN members m ON r.discord_id = m.discord_id
        WHERE LOWER(r.recipe_name) LIKE LOWER(?)
        ORDER BY r.profession, m.char_name
    """, (f"%{recipe_name}%",)).fetchall()
    db.close()

    if not rows:
        await interaction.response.send_message(f"❌ No guild members found with a recipe matching **{recipe_name}**.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🔍 Who can craft: \"{recipe_name}\"",
        color=0xF4A92A
    )
    for row in rows:
        val = f"**Profession:** {row['profession']}"
        if row['notes']:
            val += f"\n**Notes:** {row['notes']}"
        embed.add_field(name=f"🧙 {row['char_name']} ({row['discord_name']})", value=val, inline=False)
    embed.set_footer(text=f"Found {len(rows)} result(s)")
    await interaction.response.send_message(embed=embed)

# ── /list_recipes ──────────────────────────────────────────────
@bot.tree.command(name="list_recipes", description="List all guild recipes for a specific profession")
@app_commands.describe(profession="The profession to list recipes for")
@app_commands.autocomplete(profession=profession_autocomplete)
async def list_recipes(interaction: discord.Interaction, profession: str):
    db = get_db()
    rows = db.execute("""
        SELECT m.char_name, r.recipe_name, r.notes
        FROM recipes r
        JOIN members m ON r.discord_id = m.discord_id
        WHERE r.profession = ?
        ORDER BY r.recipe_name, m.char_name
    """, (profession,)).fetchall()
    db.close()

    if not rows:
        await interaction.response.send_message(f"❌ No recipes found for **{profession}** in the guild.", ephemeral=True)
        return

    # Group by recipe name
    recipe_map = {}
    for row in rows:
        key = row['recipe_name']
        if key not in recipe_map:
            recipe_map[key] = []
        entry = row['char_name']
        if row['notes']:
            entry += f" *({row['notes']})*"
        recipe_map[key].append(entry)

    embed = discord.Embed(
        title=f"📚 Guild {profession} Recipes",
        color=0x9B59B6
    )
    # Discord embeds have a 6000 char limit; paginate if needed
    lines = []
    for recipe, crafters in sorted(recipe_map.items()):
        lines.append(f"**{recipe}** — {', '.join(crafters)}")

    # Split into chunks of 20
    chunk = lines[:20]
    embed.description = "\n".join(chunk)
    if len(lines) > 20:
        embed.set_footer(text=f"Showing 20 of {len(lines)} recipes. Search with /who_can_craft for more.")
    else:
        embed.set_footer(text=f"{len(lines)} recipe(s) total")
    await interaction.response.send_message(embed=embed)

# ── /my_recipes ────────────────────────────────────────────────
@bot.tree.command(name="my_recipes", description="View all your registered recipes")
async def my_recipes(interaction: discord.Interaction):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE discord_id = ?", (str(interaction.user.id),)).fetchone()
    if not member:
        await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
        db.close()
        return
    rows = db.execute("""
        SELECT profession, recipe_name, notes FROM recipes
        WHERE discord_id = ?
        ORDER BY profession, recipe_name
    """, (str(interaction.user.id),)).fetchall()
    db.close()

    embed = discord.Embed(
        title=f"📜 {member['char_name']}'s Recipes",
        color=0x1ABC9C
    )
    if not rows:
        embed.description = "No recipes added yet. Use `/add_recipe` to add some!"
    else:
        prof_map = {}
        for row in rows:
            prof_map.setdefault(row['profession'], []).append(
                row['recipe_name'] + (f" *({row['notes']})*" if row['notes'] else "")
            )
        for prof, rlist in sorted(prof_map.items()):
            embed.add_field(name=f"⚒️ {prof}", value="\n".join(rlist), inline=False)
        embed.set_footer(text=f"{len(rows)} recipe(s) total")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /guild_roster ──────────────────────────────────────────────
@bot.tree.command(name="guild_roster", description="Show all registered guild members and their professions")
async def guild_roster(interaction: discord.Interaction):
    db = get_db()
    members = db.execute("SELECT * FROM members ORDER BY char_name").fetchall()
    if not members:
        await interaction.response.send_message("❌ No members registered yet!", ephemeral=True)
        db.close()
        return

    embed = discord.Embed(title="⚔️ Guild Roster", color=0xF4A92A)
    for m in members:
        profs = db.execute(
            "SELECT profession, skill_level FROM professions WHERE discord_id = ? ORDER BY profession",
            (m['discord_id'],)
        ).fetchall()
        recipe_count = db.execute(
            "SELECT COUNT(*) as cnt FROM recipes WHERE discord_id = ?", (m['discord_id'],)
        ).fetchone()['cnt']

        if profs:
            prof_str = ", ".join(f"{p['profession']} ({p['skill_level']})" for p in profs)
        else:
            prof_str = "*No professions added*"

        embed.add_field(
            name=f"🧙 {m['char_name']} ({m['realm']})",
            value=f"{prof_str}\n📜 {recipe_count} recipe(s) registered",
            inline=False
        )
    db.close()
    embed.set_footer(text=f"{len(members)} member(s) registered")
    await interaction.response.send_message(embed=embed)

# ── /help ──────────────────────────────────────────────────────
@bot.tree.command(name="help", description="Show all available bot commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🐉 WoW TBC Guild Recipe Bot",
        description="Track guild recipes and professions for Burning Crusade Anniversary!",
        color=0xF4A92A
    )
    commands_info = [
        ("/register", "Register your character with the bot"),
        ("/add_profession", "Add/update a profession and skill level"),
        ("/add_recipe", "Add a recipe you know to the guild database"),
        ("/remove_recipe", "Remove a recipe from your list"),
        ("/who_can_craft", "Find who can craft a specific item"),
        ("/list_recipes", "List all guild recipes for a profession"),
        ("/my_recipes", "View all your registered recipes (private)"),
        ("/guild_roster", "Show all members and their professions"),
    ]
    for cmd, desc in commands_info:
        embed.add_field(name=cmd, value=desc, inline=False)
    embed.set_footer(text="For Azeroth! 🏰")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── Run ────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("Starting WoW TBC Guild Recipe Bot...")
    bot.run(TOKEN)
