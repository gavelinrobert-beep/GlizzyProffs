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


# ── Notable TBC Recipes by Profession ─────────────────────────
TBC_RECIPES = {
    "Alchemy": [
        "Flask of Blinding Light", "Flask of Chromatic Wonder", "Flask of Fortification",
        "Flask of Mighty Restoration", "Flask of Pure Death", "Flask of Relentless Assault",
        "Flask of Supreme Power", "Flask of the Titans",
        "Elixir of Major Agility", "Elixir of Major Firepower", "Elixir of Major Fortitude",
        "Elixir of Major Frost Power", "Elixir of Major Mageblood", "Elixir of Major Shadow Power",
        "Elixir of Major Strength", "Elixir of Mastery", "Elixir of the Draenei",
        "Elixir of Empowerment", "Elixir of Healing Power",
        "Super Mana Potion", "Super Healing Potion", "Haste Potion", "Destruction Potion",
        "Ironshield Potion", "Fel Mana Potion",
        "Transmute: Primal Air to Fire", "Transmute: Primal Earth to Life",
        "Transmute: Primal Earth to Water", "Transmute: Primal Fire to Earth",
        "Transmute: Primal Shadow to Water", "Transmute: Primal Water to Air",
        "Transmute: Primal Life to Earth", "Transmute: Skyfire Diamond",
        "Transmute: Earthstorm Diamond",
    ],
    "Blacksmithing": [
        "Boots of the Resilient", "Bracers of the Green Fortress", "Bulwark of the Ancient Kings",
        "Cobra-Lash Boots", "Crossbow of Relentless Strikes", "Eternium Runed Blade",
        "Felsteel Longblade", "Flamebane Bracers", "Gauntlets of the Iron Tower",
        "Greater Rune of Warding", "Hand of Eternity", "Iceguard Breastplate",
        "Iceguard Gauntlets", "Iceguard Helm", "Khorium Champion",
        "Khorium Destroyer", "Lesser Ward of Shielding", "Lighter Eternium Rod",
        "Lunar Crescent", "Mooncleaver", "Oathkeeper", "Ragesteel Breastplate",
        "Ragesteel Gloves", "Ragesteel Helm", "Ragesteel Shoulders",
        "Shadesteel Bracers", "Shadesteel Greaves", "Shadesteel Sabots", "Shadesteel Shoulders",
        "Shuriken of Negation", "Storm Helm", "Stormherald",
        "Twisting Nether Chain Shirt", "Wicked Edge of the Planes",
    ],
    "Enchanting": [
        "Enchant Boots - Dexterity", "Enchant Boots - Fortitude", "Enchant Boots - Surefooted",
        "Enchant Bracer - Spellpower", "Enchant Bracer - Stats", "Enchant Bracer - Fortitude",
        "Enchant Chest - Exceptional Health", "Enchant Chest - Exceptional Mana",
        "Enchant Chest - Exceptional Stats",
        "Enchant Cloak - Greater Agility", "Enchant Cloak - Spell Penetration",
        "Enchant Gloves - Major Healing", "Enchant Gloves - Major Spellpower",
        "Enchant Gloves - Superior Agility", "Enchant Gloves - Threat",
        "Enchant Ring - Healing Power", "Enchant Ring - Spellpower", "Enchant Ring - Stats",
        "Enchant Shield - Major Stamina", "Enchant Shield - Resilience",
        "Enchant Weapon - Major Healing", "Enchant Weapon - Major Spellpower",
        "Enchant Weapon - Mongoose", "Enchant Weapon - Soulfrost",
        "Enchant Weapon - Spellsurge", "Enchant Weapon - Sunfire",
        "Enchant 2H Weapon - Major Agility", "Enchant Weapon - Greater Agility",
        "Enchant Weapon - Executioner",
    ],
    "Engineering": [
        "Adamantite Scope", "Deathblow X11 Goggles", "Destroyer Protoshield",
        "Ebon Netherscale Breastplate", "Gnomish Poultryizer", "Gnomish Power Goggles",
        "Goblin Rocket Launcher", "Hyper-Vision Goggles", "Justicar X1 Multi-Target Mortar",
        "Khorium Scope", "Quad Deathblow X44 Goggles", "Rocket Boots Xtreme",
        "Rocket Boots Xtreme Lite", "Stabilized Eternium Scope", "Steam-Powered Goggles",
        "Surestrike Goggles v2.0", "Surestrike Goggles v3.0",
        "Tankatronic Goggles", "Wonderheal XT68 Shades",
    ],
    "Jewelcrafting": [
        "Bold Living Ruby", "Brilliant Dawnstone", "Delicate Living Ruby",
        "Durable Talasite", "Enduring Talasite", "Flashing Living Ruby",
        "Forceful Talasite", "Gleaming Dawnstone", "Glinting Noble Topaz",
        "Glowing Nightseye", "Inscribed Noble Topaz", "Jagged Talasite",
        "Lustrous Star of Elune", "Mystic Dawnstone", "Potent Noble Topaz",
        "Quick Dawnstone", "Radiant Talasite", "Reckless Noble Topaz",
        "Rigid Star of Elune", "Royal Nightseye", "Runed Living Ruby",
        "Smooth Dawnstone", "Solid Star of Elune", "Sovereign Nightseye",
        "Sparkling Star of Elune", "Stormy Star of Elune", "Subtle Dawnstone",
        "Swift Windfire Diamond", "Tenacious Earthstorm Diamond",
        "Thundering Skyfire Diamond", "Veiled Noble Topaz",
    ],
    "Leatherworking": [
        "Bindings of the Wildheart", "Blue Dragonscale Breastplate",
        "Boots of Natural Grace", "Boots of Utter Darkness", "Boots of the Crimson Hawk",
        "Bracers of Renewed Life", "Cobrascale Gloves", "Cobrascale Hood",
        "Drums of Battle", "Drums of Panic", "Drums of Restoration", "Drums of Speed",
        "Ebon Netherscale Belt", "Ebon Netherscale Bracers",
        "Fel Leather Gloves", "Fel Leather Leggings", "Fel Leather Boots",
        "Felstalker Belt", "Felstalker Breastplate", "Felstalker Bracers",
        "Living Earth Bindings", "Living Earth Shoulders",
        "Netherdrake Gloves", "Netherdrake Helm",
        "Primalstrike Belt", "Primalstrike Bracers", "Primalstrike Vest",
        "Stylin Crimson Hat", "Stylin Jungle Hat", "Stylin Purple Hat",
        "Thick Draenic Vest", "Windhawk Armor", "Windhawk Belt", "Windhawk Bracers",
        "Windscale Hood",
    ],
    "Tailoring": [
        "Battlecast Hood", "Battlecast Pants", "Blackout Bindings",
        "Blackstrike Bracers", "Cloak of Arcane Evasion", "Cloak of Darkness",
        "Cloak of the Black Void", "Cloak of Eternity",
        "Frozen Shadoweave Boots", "Frozen Shadoweave Robe", "Frozen Shadoweave Shoulders",
        "Girdle of Ruination", "Primal Mooncloth", "Primal Mooncloth Bag",
        "Primal Mooncloth Belt", "Primal Mooncloth Gloves", "Primal Mooncloth Robe",
        "Primal Mooncloth Shoulders", "Runic Spellthread", "Silver Spellthread",
        "Shadowcloth", "Spellstrike Hood", "Spellstrike Pants",
        "Soulcloth Gloves", "Soulcloth Shoulders", "Soulcloth Vest",
        "Unyielding Girdle", "Unyielding Pants", "Whitemend Hood",
        "Whitemend Pants", "Windchannel Gloves",
    ],
    "Cooking": [
        "Blackened Basilisk", "Blackened Sporefish", "Buzzard Bites",
        "Crunchy Serpent", "Feltail Delight", "Fisherman Feast",
        "Golden Fish Sticks", "Grilled Mudfish", "Horrible Oily Sausage",
        "Lynx Steak", "Mok Nathal Shortribs", "Ravager Dog",
        "Roasted Clefthoof", "Skulfish Surprise", "Spicy Crawdad",
        "Sporefish Surprise", "Stewed Trout", "Talbuk Steak",
        "Warp Burger",
    ],
    "First Aid": [
        "Heavy Netherweave Bandage", "Netherweave Bandage",
    ],
    "Fishing": [
        "Furious Crawdad", "Mote of Water", "Enormous Barbed Gill Trout",
    ],
    "Herbalism": [],
    "Mining": [],
    "Skinning": [],
    "Engineering": [
        "Adamantite Scope", "Deathblow X11 Goggles", "Destroyer Protoshield",
        "Gnomish Poultryizer", "Goblin Rocket Launcher", "Hyper-Vision Goggles",
        "Khorium Scope", "Quad Deathblow X44 Goggles", "Rocket Boots Xtreme",
        "Rocket Boots Xtreme Lite", "Stabilized Eternium Scope",
        "Surestrike Goggles v2.0", "Surestrike Goggles v3.0",
        "Tankatronic Goggles", "Wonderheal XT68 Shades",
    ],
}

async def recipe_name_autocomplete(interaction: discord.Interaction, current: str):
    # Get the profession from the interaction options if available
    profession = None
    if interaction.data and "options" in interaction.data:
        for opt in interaction.data["options"]:
            if opt["name"] == "profession":
                profession = opt.get("value")
                break
    
    if profession and profession in TBC_RECIPES:
        recipes = TBC_RECIPES[profession]
    else:
        # Show all recipes across all professions
        recipes = [r for rlist in TBC_RECIPES.values() for r in rlist]
    
    matches = [r for r in recipes if current.lower() in r.lower()][:25]
    return [app_commands.Choice(name=r, value=r) for r in sorted(matches)]

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

            CREATE TABLE IF NOT EXISTS bank_config (
                guild_id      TEXT PRIMARY KEY,
                channel_id    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bank_requests (
                id            SERIAL PRIMARY KEY,
                discord_id    TEXT NOT NULL REFERENCES members(discord_id) ON DELETE CASCADE,
                item_name     TEXT NOT NULL,
                quantity      INTEGER DEFAULT 1,
                reason        TEXT DEFAULT '',
                status        TEXT DEFAULT 'pending',
                officer_id    TEXT,
                officer_note  TEXT DEFAULT '',
                message_id    TEXT,
                created_at    TIMESTAMPTZ DEFAULT NOW()
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
        # Re-register persistent bank request views so buttons work after restarts
        self.loop.create_task(restore_bank_views(self))
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


async def restore_bank_views(bot: GuildBot):
    """Re-attach button views to pending bank request messages after a restart."""
    await bot.wait_until_ready()
    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, message_id, channel_id
            FROM bank_requests b
            JOIN bank_config c ON c.guild_id = c.guild_id
            WHERE b.status = 'pending' AND b.message_id IS NOT NULL
        """)
    # Simpler: just add the persistent view globally so Discord routes
    # any bank_approve/bank_deny custom_id to the right handler
    bot.add_view(BankRequestView(0))
    print(f"✅ Persistent bank views restored.")

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
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /register_member (officer) ─────────────────────────────────
@bot.tree.command(name="register_member", description="Register a guild member and link them to their Discord (officers only)")
@app_commands.describe(
    member="The Discord user to register",
    char_name="Their WoW character name",
    realm="Their realm (optional)"
)
@app_commands.checks.has_permissions(manage_roles=True)
async def register_member(interaction: discord.Interaction, member: discord.Member, char_name: str, realm: str = "Unknown"):
    async with bot.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO members (discord_id, discord_name, char_name, realm)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (discord_id) DO UPDATE
              SET discord_name = EXCLUDED.discord_name,
                  char_name    = EXCLUDED.char_name,
                  realm        = EXCLUDED.realm
        """, str(member.id), member.display_name, char_name, realm)

    embed = discord.Embed(
        title="✅ Member Registered",
        description=f"**{char_name}** has been linked to {member.mention}!",
        color=0xF4A92A
    )
    embed.set_footer(text=f"Registered by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

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
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ── /add_recipe ────────────────────────────────────────────────
@bot.tree.command(name="add_recipe", description="Add a recipe you know to the guild database")
@app_commands.describe(
    profession="The profession this recipe belongs to",
    recipe_name="Name of the recipe (e.g. Primal Mooncloth Bag)",
    notes="Optional notes (e.g. 'cooldown 4 days', 'need mats')"
)
@app_commands.autocomplete(profession=profession_autocomplete, recipe_name=recipe_name_autocomplete)
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
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await refresh_live_embed(bot.pool, bot, profession)


# ── /add_recipe_for (officer) ──────────────────────────────────
@bot.tree.command(name="add_recipe_for", description="Add a recipe for another guild member (officers only)")
@app_commands.describe(
    member="The Discord user to add the recipe for",
    profession="The profession this recipe belongs to",
    recipe_name="Name of the recipe",
    notes="Optional notes (e.g. 'cooldown 4 days')"
)
@app_commands.autocomplete(profession=profession_autocomplete, recipe_name=recipe_name_autocomplete)
@app_commands.checks.has_permissions(manage_roles=True)
async def add_recipe_for(interaction: discord.Interaction, member: discord.Member, profession: str, recipe_name: str, notes: str = ""):
    async with bot.pool.acquire() as conn:
        target = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(member.id))
        if not target:
            await interaction.response.send_message(f"❌ {member.mention} isn't registered yet! Use `/register_member` first.", ephemeral=True)
            return
        existing = await conn.fetchrow("""
            SELECT id FROM recipes
            WHERE discord_id = $1 AND profession = $2 AND LOWER(recipe_name) = LOWER($3)
        """, str(member.id), profession, recipe_name)
        if existing:
            await interaction.response.send_message(f"⚠️ **{target['char_name']}** already has **{recipe_name}** listed!", ephemeral=True)
            return
        await conn.execute("""
            INSERT INTO recipes (discord_id, profession, recipe_name, notes)
            VALUES ($1, $2, $3, $4)
        """, str(member.id), profession, recipe_name, notes)

    embed = discord.Embed(
        title="📜 Recipe Added",
        description=f"**{recipe_name}** ({profession}) — Added for **{target['char_name']}** ({member.mention})",
        color=0x2ECC71
    )
    if notes:
        embed.add_field(name="Notes", value=notes)
    embed.set_footer(text=f"Added by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)
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
            SELECT m.char_name, m.discord_name, m.discord_id, r.recipe_name, r.profession, r.notes
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
        val += f"\n**Discord:** <@{row['discord_id']}>"
        if row['notes']:
            val += f"\n**Notes:** {row['notes']}"
        embed.add_field(name=f"🧙 {row['char_name']}", value=val, inline=False)
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
                name=f"🧙 {m['char_name']}",
                value=f"<@{m['discord_id']}> {f"({m['realm']})" if m['realm'] != 'Unknown' else ''}\n{prof_str}\n📜 {recipe_count} recipe(s) registered",
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
            ("/register", "Register your own WoW character"),
            ("/register_member", "Link a member\'s character to their Discord (officers only)"),
            ("/add_profession", "Add/update a profession and skill level"),
            ("/guild_roster", "Show all members and their professions"),
        ]),
        ("📜 Recipes", [
            ("/add_recipe", "Add a recipe you know"),
            ("/add_recipe_for", "Add a recipe for another member (officers only)"),
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
        ("🏦 Guild Bank", [
            ("/setup_bank", "Set the bank request channel (officers only)"),
            ("/bank_request", "Request an item from the guild bank"),
            ("/my_requests", "View your own bank requests (private)"),
            ("/pending_requests", "View all pending bank requests"),
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


# ── Bank Request Views (Buttons) ───────────────────────────────
class BankRequestView(discord.ui.View):
    def __init__(self, request_id: int):
        super().__init__(timeout=None)
        self.request_id = request_id
        # Set unique custom_ids per request so the bot can recover them after restart
        self.children[0].custom_id = f"bank_approve:{request_id}"
        self.children[1].custom_id = f"bank_deny:{request_id}"

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="bank_approve:0")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        request_id = int(button.custom_id.split(":")[1])
        await handle_bank_decision(interaction, request_id, "approved")

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="bank_deny:0")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        request_id = int(button.custom_id.split(":")[1])
        await handle_bank_decision(interaction, request_id, "denied")


async def handle_bank_decision(interaction: discord.Interaction, request_id: int, decision: str):
    # Officers only
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ Only officers can approve/deny requests.", ephemeral=True)
        return

    # Ask for an optional note via a modal
    class NoteModal(discord.ui.Modal, title=f"{'Approve' if decision == 'approved' else 'Deny'} Request"):
        note = discord.ui.TextInput(
            label="Officer note (optional)",
            placeholder="e.g. Check tab 2, or 'We're out of stock'",
            required=False,
            max_length=200
        )

        async def on_submit(self, modal_interaction: discord.Interaction):
            officer_note = self.note.value or ""
            async with bot.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    UPDATE bank_requests
                    SET status = $1, officer_id = $2, officer_note = $3
                    WHERE id = $4
                    RETURNING discord_id, item_name, quantity, reason
                """, decision, str(modal_interaction.user.id), officer_note, request_id)

            if not row:
                await modal_interaction.response.send_message("❌ Request not found.", ephemeral=True)
                return

            # Update the officer channel embed
            color = 0x2ECC71 if decision == "approved" else 0xE74C3C
            status_icon = "✅" if decision == "approved" else "❌"
            embed = discord.Embed(
                title=f"{status_icon} Bank Request {decision.capitalize()}",
                color=color,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Item", value=f"{row['item_name']} x{row['quantity']}", inline=True)
            embed.add_field(name="Reason", value=row['reason'] or "*None given*", inline=True)
            embed.add_field(name="Decision by", value=modal_interaction.user.mention, inline=True)
            if officer_note:
                embed.add_field(name="Note", value=officer_note, inline=False)

            await modal_interaction.response.edit_message(embed=embed, view=None)

            # DM the requester
            requester = bot.get_user(int(row['discord_id']))
            if requester:
                try:
                    dm_embed = discord.Embed(
                        title=f"{status_icon} Guild Bank Request {decision.capitalize()}",
                        description=f"Your request for **{row['item_name']} x{row['quantity']}** has been **{decision}**.",
                        color=color
                    )
                    if officer_note:
                        dm_embed.add_field(name="Officer note", value=officer_note)
                    dm_embed.set_footer(text=f"Decided by {modal_interaction.user.display_name}")
                    await requester.send(embed=dm_embed)
                except discord.Forbidden:
                    pass  # DMs disabled

    await interaction.response.send_modal(NoteModal())


# ── /setup_bank ────────────────────────────────────────────────
@bot.tree.command(name="setup_bank", description="Set the channel where bank requests will be posted (officers only)")
@app_commands.describe(channel="The channel to post bank requests in")
@app_commands.checks.has_permissions(manage_roles=True)
async def setup_bank(interaction: discord.Interaction, channel: discord.TextChannel):
    async with bot.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bank_config (guild_id, channel_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET channel_id = EXCLUDED.channel_id
        """, str(interaction.guild.id), str(channel.id))

    await interaction.response.send_message(
        f"✅ Bank requests will now be posted in {channel.mention}. Members can use `/bank_request` to submit requests.",
        ephemeral=True
    )


# ── /bank_request ──────────────────────────────────────────────
@bot.tree.command(name="bank_request", description="Request an item from the guild bank")
@app_commands.describe(
    item_name="Name of the item you need",
    quantity="How many you need",
    reason="Why you need it (e.g. 'for flask crafting')"
)
async def bank_request(interaction: discord.Interaction, item_name: str, quantity: int = 1, reason: str = ""):
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return

        config = await conn.fetchrow("SELECT channel_id FROM bank_config WHERE guild_id = $1", str(interaction.guild.id))
        if not config:
            await interaction.response.send_message("❌ Bank requests aren't set up yet. Ask an officer to use `/setup_bank`.", ephemeral=True)
            return

        # Check for duplicate pending request
        existing = await conn.fetchrow("""
            SELECT id FROM bank_requests
            WHERE discord_id = $1 AND LOWER(item_name) = LOWER($2) AND status = 'pending'
        """, str(interaction.user.id), item_name)
        if existing:
            await interaction.response.send_message(f"⚠️ You already have a pending request for **{item_name}**.", ephemeral=True)
            return

        # Insert the request
        request_id = await conn.fetchval("""
            INSERT INTO bank_requests (discord_id, item_name, quantity, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, str(interaction.user.id), item_name, quantity, reason)

    # Post to officer channel
    channel = bot.get_channel(int(config['channel_id']))
    if not channel:
        await interaction.response.send_message("❌ Bank request channel not found. Ask an officer to re-run `/setup_bank`.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏦 New Bank Request",
        color=0xF4A92A,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Character", value=member['char_name'], inline=True)
    embed.add_field(name="Item", value=f"{item_name} x{quantity}", inline=True)
    embed.add_field(name="Reason", value=reason or "*None given*", inline=False)
    embed.set_footer(text=f"Request #{request_id}")

    view = BankRequestView(request_id)
    message = await channel.send(embed=embed, view=view)

    # Store the message ID so we can edit it later
    async with bot.pool.acquire() as conn:
        await conn.execute("UPDATE bank_requests SET message_id = $1 WHERE id = $2", str(message.id), request_id)

    await interaction.response.send_message(
        f"✅ Your request for **{item_name} x{quantity}** has been submitted! You'll get a DM when an officer responds.",
        ephemeral=True
    )


# ── /my_requests ───────────────────────────────────────────────
@bot.tree.command(name="my_requests", description="View your bank requests")
async def my_requests(interaction: discord.Interaction):
    async with bot.pool.acquire() as conn:
        member = await conn.fetchrow("SELECT * FROM members WHERE discord_id = $1", str(interaction.user.id))
        if not member:
            await interaction.response.send_message("❌ You're not registered! Use `/register` first.", ephemeral=True)
            return
        rows = await conn.fetch("""
            SELECT item_name, quantity, reason, status, officer_note, created_at
            FROM bank_requests WHERE discord_id = $1
            ORDER BY created_at DESC LIMIT 10
        """, str(interaction.user.id))

    embed = discord.Embed(title=f"🏦 {member['char_name']}'s Bank Requests", color=0xF4A92A)
    if not rows:
        embed.description = "No requests yet. Use `/bank_request` to submit one!"
    else:
        for row in rows:
            icon = {"pending": "⏳", "approved": "✅", "denied": "❌"}.get(row['status'], "❓")
            val = f"Qty: {row['quantity']}"
            if row['reason']:
                val += f" | Reason: {row['reason']}"
            if row['officer_note']:
                val += f"\nOfficer note: *{row['officer_note']}*"
            embed.add_field(name=f"{icon} {row['item_name']} ({row['status']})", value=val, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /pending_requests ──────────────────────────────────────────
@bot.tree.command(name="pending_requests", description="View all pending guild bank requests")
async def pending_requests(interaction: discord.Interaction):
    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT b.id, b.item_name, b.quantity, b.reason, b.created_at, m.char_name
            FROM bank_requests b
            JOIN members m ON b.discord_id = m.discord_id
            WHERE b.status = 'pending'
            ORDER BY b.created_at ASC
        """)

    embed = discord.Embed(title="🏦 Pending Bank Requests", color=0xF4A92A)
    if not rows:
        embed.description = "No pending requests!"
    else:
        for row in rows:
            val = f"**{row['item_name']} x{row['quantity']}**"
            if row['reason']:
                val += f"\n*{row['reason']}*"
            ts = int(row['created_at'].timestamp())
            val += f"\nRequested <t:{ts}:R>"
            embed.add_field(name=f"#{row['id']} — {row['char_name']}", value=val, inline=False)
        embed.set_footer(text=f"{len(rows)} pending request(s)")
    await interaction.response.send_message(embed=embed)


# ── Run ────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)
