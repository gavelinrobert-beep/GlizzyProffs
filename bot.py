import discord
from discord.ext import commands
from discord import app_commands
import asyncpg
import os
import re
import urllib.parse
from datetime import datetime, timezone, timedelta

# ── Configuration ──────────────────────────────────────────────
TOKEN        = os.environ["DISCORD_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]

# TBC Professions
PROFESSIONS = [
    "Alchemy", "Blacksmithing", "Enchanting", "Engineering",
    "Herbalism", "Jewelcrafting", "Leatherworking", "Mining",
    "Skinning", "Tailoring", "Cooking", "First Aid", "Fishing"
]

PROFESSION_COLORS = {
    "Alchemy":        0x9B59B6,
    "Blacksmithing":  0x7F8C8D,
    "Enchanting":     0xE91E63,
    "Engineering":    0xF39C12,
    "Herbalism":      0x2ECC71,
    "Jewelcrafting":  0x3498DB,
    "Leatherworking": 0xA0522D,
    "Mining":         0x95A5A6,
    "Skinning":       0xD35400,
    "Tailoring":      0x1ABC9C,
    "Cooking":        0xE74C3C,
    "First Aid":      0xECF0F1,
    "Fishing":        0x2980B9,
}

# ── DB URL Parser ──────────────────────────────────────────────
def parse_db_url(url: str) -> dict:
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

            CREATE TABLE IF NOT EXISTS live_embeds (
                profession    TEXT PRIMARY KEY,
                channel_id    TEXT NOT NULL,
                message_id    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cooldowns (
                id            SERIAL PRIMARY KEY,
                discord_id    TEXT NOT NULL REFERENCES members(discord_id) ON DELETE CASCADE,
                recipe_name   TEXT NOT NULL,
                profession    TEXT NOT NULL,
                ready_at      TIMESTAMPTZ NOT NULL,
                notified      BOOLEAN DEFAULT FALSE,
                UNIQUE(discord_id, recipe_name)
            );
        """)

# ── Live Embed Builder ─────────────────────────────────────────
async def build_profession_embed(pool: asyncpg.Pool, profession: str) -> discord.Embed:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.char_name, r.recipe_name, r.notes
            FROM recipes r
            JOIN members m ON r.discord_id = m.discord_id
            WHERE r.profession = $1
            ORDER BY r.recipe_name, m.char_name
        """, profession)

    color = PROFESSION_COLORS.get(profession, 0xF4A92A)
    embed = discord.Embed(
        title=f"📚 {profession} — Guild Recipes",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    if not rows:
        embed.description = "*No recipes registered yet. Use `/add_recipe` to add some!*"
    else:
        recipe_map = {}
        for row in rows:
            entry = row['char_name'] + (f" *({row['notes']})*" if row['notes'] else "")
            recipe_map.setdefault(row['recipe_name'], []).append(entry)

        lines = [f"**{r}** — {', '.join(c)}" for r, c in sorted(recipe_map.items())]
        # Discord embed description limit is 4096 chars; truncate gracefully
        description = "\n".join(lines)
        if len(description) > 4000:
            description = description[:4000] + "\n*...use /list_recipes to see all*"
        embed.description = description
        embed.set_footer(text=f"{len(recipe_map)} recipe(s) • Last updated")

    return embed

async def refresh_live_embed(pool: asyncpg.Pool, bot: commands.Bot, profession: str):
    """Fetch the stored message for this profession and edit it with fresh data."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT channel_id, message_id FROM live_embeds WHERE profession = $1", profession
        )
    if not row:
        return
    try:
        channel = bot.get_channel(int(row['channel_id']))
        if not channel:
            return
        message = await channel.fetch_message(int(row['message_id']))
        embed = await build_profession_embed(pool, profession)
        await message.edit(embed=embed)
    except (discord.NotFound, discord.Forbidden):
        # Message was deleted or bot lost permissions — clean up the DB entry
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM live_embeds WHERE profession = $1", profession)

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
        # Start background cooldown checker
        self.loop.create_task(cooldown_checker(self))
        print("✅ Database connected and slash commands synced.")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="WoW TBC | /help"))

    async def close(self):
        if self.pool:
            await self.pool.close()
        await super().close()

bot = GuildBot()

# ── Background: Cooldown Checker ──────────────────────────────
import asyncio

async def cooldown_checker(bot: GuildBot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            async with bot.pool.acquire() as conn:
                due = await conn.fetch("""
                    SELECT c.id, c.discord_id, c.recipe_name, c.profession, m.char_name
                    FROM cooldowns c
                    JOIN members m ON c.discord_id = m.discord_id
                    WHERE c.ready_at <= NOW() AND c.notified = FALSE
                """)
                for row in due:
                    user = bot.get_user(int(row['discord_id']))
                    if user:
                        try:
                            embed = discord.Embed(
                                title="⏰ Cooldown Ready!",
                                description=f"**{row['char_name']}** — your **{row['recipe_name']}** ({row['profession']}) cooldown is ready to use!",
                                color=0x2ECC71
                            )
                            await user.send(embed=embed)
                        except discord.Forbidden:
                            pass  # User has DMs disabled
                    await conn.execute(
                        "UPDATE cooldowns SET notified = TRUE WHERE id = $1", row['id']
                    )
        except Exception as e:
            print(f"Cooldown checker error: {e}")
        await asyncio.sleep(60)  # Check every minute

# ── Autocomplete Helpers ───────────────────────────────────────
async def profession_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=p, value=p)
        for p in PROFESSIONS if current.lower() in p.lower()
    ]

# ── /register ─────────────────────────────────────────────────
@bot.tree.command(name="register", description="Register your WoW character with the guild bot")
@app_commands.describe(char_name="Your WoW character name", realm="Your realm name")
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
@app_commands.describe(profession="Your profession", skill_level="Your current skill level (1-375)")
@app_commands.autocomplete(profession=profession_autocomplete)
async def add_profession(interaction: discord.Interaction, profession: str, skill_level: int = 0):
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return
        if profession not in PROFESSIONS:
            await interaction.response.send_message(f"❌ Unknown profession.", ephemeral=True)
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
    await refresh_live_embed(bot.pool, bot, profession)

# ── /remove_recipe ─────────────────────────────────────────────
@bot.tree.command(name="remove_recipe", description="Remove a recipe from your list")
@app_commands.describe(recipe_name="Name of the recipe to remove")
async def remove_recipe(interaction: discord.Interaction, recipe_name: str):
    async with bot.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT profession FROM recipes
            WHERE discord_id = $1 AND LOWER(recipe_name) = LOWER($2)
        """, str(interaction.user.id), recipe_name)
        result = await conn.execute("""
            DELETE FROM recipes
            WHERE discord_id = $1 AND LOWER(recipe_name) = LOWER($2)
        """, str(interaction.user.id), recipe_name)

    deleted = int(result.split(" ")[-1])
    if deleted == 0:
        await interaction.response.send_message(f"❌ No recipe named **{recipe_name}** found.", ephemeral=True)
    else:
        await interaction.response.send_message(f"🗑️ Removed **{recipe_name}** from your recipes.")
        if row:
            await refresh_live_embed(bot.pool, bot, row['profession'])

# ── /update_recipe ─────────────────────────────────────────────
@bot.tree.command(name="update_recipe", description="Update the notes on one of your recipes")
@app_commands.describe(recipe_name="Name of the recipe to update", notes="New notes")
async def update_recipe(interaction: discord.Interaction, recipe_name: str, notes: str):
    async with bot.pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE recipes SET notes = $3
            WHERE discord_id = $1 AND LOWER(recipe_name) = LOWER($2)
            RETURNING profession, recipe_name
        """, str(interaction.user.id), recipe_name, notes)

    if not row:
        await interaction.response.send_message(f"❌ No recipe named **{recipe_name}** found.", ephemeral=True)
    else:
        await interaction.response.send_message(f"✏️ Updated **{row['recipe_name']}** notes to: *{notes}*")
        await refresh_live_embed(bot.pool, bot, row['profession'])

# ── /setup_live ────────────────────────────────────────────────
@bot.tree.command(name="setup_live", description="Post a live-updating recipe embed for a profession in this channel")
@app_commands.describe(profession="The profession to create a live embed for")
@app_commands.autocomplete(profession=profession_autocomplete)
@app_commands.checks.has_permissions(manage_channels=True)
async def setup_live(interaction: discord.Interaction, profession: str):
    if profession not in PROFESSIONS:
        await interaction.response.send_message("❌ Unknown profession.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    embed = await build_profession_embed(bot.pool, profession)
    message = await interaction.channel.send(embed=embed)

    async with bot.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO live_embeds (profession, channel_id, message_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (profession) DO UPDATE
              SET channel_id = EXCLUDED.channel_id,
                  message_id = EXCLUDED.message_id
        """, profession, str(interaction.channel.id), str(message.id))

    await interaction.followup.send(
        f"✅ Live **{profession}** embed posted! It will auto-update whenever recipes are added or removed.",
        ephemeral=True
    )

# ── /set_cooldown ──────────────────────────────────────────────
@bot.tree.command(name="set_cooldown", description="Start a cooldown timer — bot will DM you when it's ready")
@app_commands.describe(
    recipe_name="The recipe with a cooldown (e.g. Primal Mooncloth)",
    profession="The profession this belongs to",
    hours="Cooldown duration in hours (e.g. 96 for 4 days)"
)
@app_commands.autocomplete(profession=profession_autocomplete)
async def set_cooldown(interaction: discord.Interaction, recipe_name: str, profession: str, hours: int):
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return

        ready_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        await conn.execute("""
            INSERT INTO cooldowns (discord_id, recipe_name, profession, ready_at, notified)
            VALUES ($1, $2, $3, $4, FALSE)
            ON CONFLICT (discord_id, recipe_name) DO UPDATE
              SET ready_at = EXCLUDED.ready_at, notified = FALSE
        """, str(interaction.user.id), recipe_name, profession, ready_at)

    days = hours // 24
    remaining_hours = hours % 24
    duration_str = f"{days}d {remaining_hours}h" if days else f"{hours}h"
    ready_ts = int(ready_at.timestamp())

    embed = discord.Embed(
        title="⏱️ Cooldown Started",
        description=(
            f"**{member['char_name']}** — **{recipe_name}** ({profession})\n"
            f"Duration: **{duration_str}**\n"
            f"Ready: <t:{ready_ts}:F> (<t:{ready_ts}:R>)\n\n"
            f"I'll DM you when it's ready!"
        ),
        color=0xF4A92A
    )
    await interaction.response.send_message(embed=embed)

# ── /my_cooldowns ──────────────────────────────────────────────
@bot.tree.command(name="my_cooldowns", description="Check your active cooldown timers")
async def my_cooldowns(interaction: discord.Interaction):
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return
        rows = await conn.fetch("""
            SELECT recipe_name, profession, ready_at, notified
            FROM cooldowns
            WHERE discord_id = $1
            ORDER BY ready_at ASC
        """, str(interaction.user.id))

    embed = discord.Embed(title=f"⏱️ {member['char_name']}'s Cooldowns", color=0xF4A92A)
    if not rows:
        embed.description = "No active cooldowns. Use `/set_cooldown` to track one!"
    else:
        for row in rows:
            ready_ts = int(row['ready_at'].timestamp())
            now = datetime.now(timezone.utc)
            if row['ready_at'] <= now:
                status = "✅ **Ready!**"
            else:
                status = f"<t:{ready_ts}:R> (ready <t:{ready_ts}:F>)"
            embed.add_field(
                name=f"{'✅' if row['notified'] else '⏳'} {row['recipe_name']} ({row['profession']})",
                value=status,
                inline=False
            )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /guild_cooldowns ───────────────────────────────────────────
@bot.tree.command(name="guild_cooldowns", description="See all active cooldowns across the guild")
async def guild_cooldowns(interaction: discord.Interaction):
    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.char_name, c.recipe_name, c.profession, c.ready_at, c.notified
            FROM cooldowns c
            JOIN members m ON c.discord_id = m.discord_id
            ORDER BY c.ready_at ASC
        """)

    embed = discord.Embed(title="⏱️ Guild Cooldowns", color=0xF4A92A)
    if not rows:
        embed.description = "No cooldowns tracked yet. Use `/set_cooldown` to add one!"
    else:
        now = datetime.now(timezone.utc)
        for row in rows:
            ready_ts = int(row['ready_at'].timestamp())
            if row['ready_at'] <= now:
                status = "✅ **Ready!**"
            else:
                status = f"<t:{ready_ts}:R>"
            embed.add_field(
                name=f"{row['char_name']} — {row['recipe_name']} ({row['profession']})",
                value=status,
                inline=False
            )
    await interaction.response.send_message(embed=embed)

# ── /clear_cooldown ────────────────────────────────────────────
@bot.tree.command(name="clear_cooldown", description="Remove a cooldown timer")
@app_commands.describe(recipe_name="The recipe cooldown to remove")
async def clear_cooldown(interaction: discord.Interaction, recipe_name: str):
    async with bot.pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM cooldowns
            WHERE discord_id = $1 AND LOWER(recipe_name) = LOWER($2)
        """, str(interaction.user.id), recipe_name)

    deleted = int(result.split(" ")[-1])
    if deleted == 0:
        await interaction.response.send_message(f"❌ No cooldown found for **{recipe_name}**.", ephemeral=True)
    else:
        await interaction.response.send_message(f"🗑️ Cleared cooldown for **{recipe_name}**.")

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
            WHERE discord_id = $1 ORDER BY profession, recipe_name
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
    sections = [
        ("📋 Registration", [
            ("/register", "Register your WoW character"),
            ("/add_profession", "Add/update a profession and skill level"),
            ("/guild_roster", "Show all members and their professions"),
        ]),
        ("📜 Recipes", [
            ("/add_recipe", "Add a recipe you know"),
            ("/remove_recipe", "Remove a recipe"),
            ("/update_recipe", "Update notes on a recipe"),
            ("/who_can_craft", "Find who can craft a specific item"),
            ("/my_recipes", "View your own recipes (private)"),
        ]),
        ("📺 Live Embeds", [
            ("/setup_live", "Post a live-updating recipe board in a channel (officers only)"),
        ]),
        ("⏱️ Cooldowns", [
            ("/set_cooldown", "Start a cooldown timer — get DM'd when ready"),
            ("/my_cooldowns", "View your active cooldowns (private)"),
            ("/guild_cooldowns", "See all guild cooldowns"),
            ("/clear_cooldown", "Remove a cooldown timer"),
        ]),
    ]
    for section, cmds in sections:
        embed.add_field(
            name=section,
            value="\n".join(f"`{cmd}` — {desc}" for cmd, desc in cmds),
            inline=False
        )
    embed.set_footer(text="For Azeroth! 🏰")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── Run ────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
