import discord
from discord.ext import commands
from discord import app_commands
import asyncpg
import os
import urllib.parse

# ── Configuration ──────────────────────────────────────────────
TOKEN        = os.environ["DISCORD_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Parse DATABASE_URL manually to work around Python 3.13 + asyncpg hostname parsing bug
# (urlparse in 3.13 incorrectly rejects valid hostnames like *.pooler.supabase.com)
def parse_db_url(url: str) -> dict:
    import re
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)", url)
    if not m:
        raise ValueError("Could not parse DATABASE_URL")
    user, password, host, port, database = m.groups()
    return {
        "host":     host,
        "port":     int(port) if port else 5432,
        "user":     user,
        "password": urllib.parse.unquote(password),
        "database": database,
        "ssl":      "require",
    }

# TBC Professions
PROFESSIONS = [
    "Alchemy", "Blacksmithing", "Enchanting", "Engineering",
    "Herbalism", "Jewelcrafting", "Leatherworking", "Mining",
    "Skinning", "Tailoring", "Cooking", "First Aid", "Fishing"
]

# ── Database Setup ─────────────────────────────────────────────
async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                discord_id    TEXT PRIMARY KEY,
                discord_name  TEXT NOT NULL,
                char_name     TEXT NOT NULL,
                realm         TEXT DEFAULT 'Unknown'
            );

            CREATE TABLE IF NOT EXISTS professions (
                id            SERIAL PRIMARY KEY,
                discord_id    TEXT NOT NULL REFERENCES members(discord_id) ON DELETE CASCADE,
                profession    TEXT NOT NULL,
                skill_level   INTEGER DEFAULT 0,
                UNIQUE(discord_id, profession)
            );

            CREATE TABLE IF NOT EXISTS recipes (
                id            SERIAL PRIMARY KEY,
                discord_id    TEXT NOT NULL REFERENCES members(discord_id) ON DELETE CASCADE,
                profession    TEXT NOT NULL,
                recipe_name   TEXT NOT NULL,
                notes         TEXT DEFAULT ''
            );
        """)

# ── Bot Setup ──────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

class GuildBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.pool: asyncpg.Pool = None

    async def setup_hook(self):
        self.pool = await asyncpg.create_pool(**parse_db_url(DATABASE_URL))
        await init_db(self.pool)
        await self.tree.sync()
        print("✅ Database connected and slash commands synced.")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="WoW TBC | /help"))

    async def close(self):
        if self.pool:
            await self.pool.close()
        await super().close()

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
    async with bot.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO members (discord_id, discord_name, char_name, realm)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (discord_id) DO UPDATE
              SET discord_name = EXCLUDED.discord_name,
                  char_name    = EXCLUDED.char_name,
                  realm        = EXCLUDED.realm
        """, str(interaction.user.id), interaction.user.display_name, char_name, realm)

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
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return
        if profession not in PROFESSIONS:
            await interaction.response.send_message(f"❌ Unknown profession. Valid: {', '.join(PROFESSIONS)}", ephemeral=True)
            return
        await conn.execute("""
            INSERT INTO professions (discord_id, profession, skill_level)
            VALUES ($1, $2, $3)
            ON CONFLICT (discord_id, profession) DO UPDATE SET skill_level = EXCLUDED.skill_level
        """, str(interaction.user.id), profession, skill_level)

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
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return
        existing = await conn.fetchrow("""
            SELECT id FROM recipes
            WHERE discord_id = $1 AND profession = $2 AND LOWER(recipe_name) = LOWER($3)
        """, str(interaction.user.id), profession, recipe_name)
        if existing:
            await interaction.response.send_message(f"⚠️ You already have **{recipe_name}** listed!", ephemeral=True)
            return
        await conn.execute("""
            INSERT INTO recipes (discord_id, profession, recipe_name, notes)
            VALUES ($1, $2, $3, $4)
        """, str(interaction.user.id), profession, recipe_name, notes)

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
@app_commands.describe(recipe_name="Name of the recipe to remove")
async def remove_recipe(interaction: discord.Interaction, recipe_name: str):
    async with bot.pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM recipes
            WHERE discord_id = $1 AND LOWER(recipe_name) = LOWER($2)
        """, str(interaction.user.id), recipe_name)

    deleted = int(result.split(" ")[-1])
    if deleted == 0:
        await interaction.response.send_message(f"❌ No recipe named **{recipe_name}** found on your character.", ephemeral=True)
    else:
        await interaction.response.send_message(f"🗑️ Removed **{recipe_name}** from your recipes.")

# ── /who_can_craft ─────────────────────────────────────────────
@bot.tree.command(name="who_can_craft", description="Find guild members who know a specific recipe")
@app_commands.describe(recipe_name="Part of the recipe name to search for")
async def who_can_craft(interaction: discord.Interaction, recipe_name: str):
    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.char_name, m.discord_name, r.recipe_name, r.profession, r.notes
            FROM recipes r
            JOIN members m ON r.discord_id = m.discord_id
            WHERE LOWER(r.recipe_name) LIKE LOWER($1)
            ORDER BY r.profession, m.char_name
        """, f"%{recipe_name}%")

    if not rows:
        await interaction.response.send_message(f"❌ No guild members found with a recipe matching **{recipe_name}**.", ephemeral=True)
        return

    embed = discord.Embed(title=f"🔍 Who can craft: \"{recipe_name}\"", color=0xF4A92A)
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
    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.char_name, r.recipe_name, r.notes
            FROM recipes r
            JOIN members m ON r.discord_id = m.discord_id
            WHERE r.profession = $1
            ORDER BY r.recipe_name, m.char_name
        """, profession)

    if not rows:
        await interaction.response.send_message(f"❌ No recipes found for **{profession}** in the guild.", ephemeral=True)
        return

    recipe_map = {}
    for row in rows:
        key = row['recipe_name']
        entry = row['char_name'] + (f" *({row['notes']})*" if row['notes'] else "")
        recipe_map.setdefault(key, []).append(entry)

    lines = [f"**{r}** — {', '.join(c)}" for r, c in sorted(recipe_map.items())]
    embed = discord.Embed(title=f"📚 Guild {profession} Recipes", color=0x9B59B6)
    embed.description = "\n".join(lines[:20])
    footer = f"{len(lines)} recipe(s) total"
    if len(lines) > 20:
        footer = f"Showing 20 of {len(lines)} recipes. Use /who_can_craft to search for more."
    embed.set_footer(text=footer)
    await interaction.response.send_message(embed=embed)

# ── /my_recipes ────────────────────────────────────────────────
@bot.tree.command(name="my_recipes", description="View all your registered recipes")
async def my_recipes(interaction: discord.Interaction):
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return
        rows = await conn.fetch("""
            SELECT profession, recipe_name, notes FROM recipes
            WHERE discord_id = $1
            ORDER BY profession, recipe_name
        """, str(interaction.user.id))

    embed = discord.Embed(title=f"📜 {member['char_name']}'s Recipes", color=0x1ABC9C)
    if not rows:
        embed.description = "No recipes added yet. Use `/add_recipe` to add some!"
    else:
        prof_map = {}
        for row in rows:
            entry = row['recipe_name'] + (f" *({row['notes']})*" if row['notes'] else "")
            prof_map.setdefault(row['profession'], []).append(entry)
        for prof, rlist in sorted(prof_map.items()):
            embed.add_field(name=f"⚒️ {prof}", value="\n".join(rlist), inline=False)
        embed.set_footer(text=f"{len(rows)} recipe(s) total")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /guild_roster ──────────────────────────────────────────────
@bot.tree.command(name="guild_roster", description="Show all registered guild members and their professions")
async def guild_roster(interaction: discord.Interaction):
    async with bot.pool.acquire() as conn:
        members = await conn.fetch("SELECT * FROM members ORDER BY char_name")
        if not members:
            await interaction.response.send_message("❌ No members registered yet!", ephemeral=True)
            return

        embed = discord.Embed(title="⚔️ Guild Roster", color=0xF4A92A)
        for m in members:
            profs = await conn.fetch(
                "SELECT profession, skill_level FROM professions WHERE discord_id = $1 ORDER BY profession",
                m['discord_id']
            )
            recipe_count = await conn.fetchval(
                "SELECT COUNT(*) FROM recipes WHERE discord_id = $1", m['discord_id']
            )
            prof_str = ", ".join(f"{p['profession']} ({p['skill_level']})" for p in profs) or "*No professions added*"
            embed.add_field(
                name=f"🧙 {m['char_name']} ({m['realm']})",
                value=f"{prof_str}\n📜 {recipe_count} recipe(s) registered",
                inline=False
            )
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
    for cmd, desc in [
        ("/register", "Register your character with the bot"),
        ("/add_profession", "Add/update a profession and skill level"),
        ("/add_recipe", "Add a recipe you know to the guild database"),
        ("/remove_recipe", "Remove a recipe from your list"),
        ("/who_can_craft", "Find who can craft a specific item"),
        ("/list_recipes", "List all guild recipes for a profession"),
        ("/my_recipes", "View all your registered recipes (private)"),
        ("/guild_roster", "Show all members and their professions"),
    ]:
        embed.add_field(name=cmd, value=desc, inline=False)
    embed.set_footer(text="For Azeroth! 🏰")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── Run ────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
