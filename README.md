# 🐉 WoW TBC Guild Recipe Bot — Cloud Deployment Guide

This version uses **Supabase** (free hosted PostgreSQL) for persistent storage and **Railway** for 24/7 hosting. Your bot will stay online even when your computer is off.

---

## Overview

| Service | Purpose | Cost |
|---|---|---|
| Discord | Bot platform | Free |
| Supabase | Database (PostgreSQL) | Free tier (500MB) |
| Railway | Hosting (runs the bot 24/7) | Free tier (500hrs/month) |
| GitHub | Code storage for Railway to deploy from | Free |

---

## Step 1 — Create Your Discord Bot

1. Go to https://discord.com/developers/applications
2. Click **New Application** → give it a name
3. Go to **Bot** tab → click **Reset Token** and copy your token (save it somewhere safe!)
4. Under **Privileged Gateway Intents**, enable **Message Content Intent**
5. Go to **OAuth2 → URL Generator**:
   - Scopes: ✅ `bot`, ✅ `applications.commands`
   - Bot Permissions: ✅ `Send Messages`, ✅ `Embed Links`, ✅ `Read Message History`
6. Copy the URL at the bottom and open it in your browser to invite the bot to your server

---

## Step 2 — Set Up Supabase (Free Database)

1. Go to https://supabase.com and sign up (free)
2. Click **New Project** → fill in a name and password (save the password!)
3. Wait ~2 minutes for the project to be created
4. Go to **Project Settings → Database**
5. Scroll down to **Connection string → URI** and copy the string that looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres
   ```
6. Replace `[YOUR-PASSWORD]` with the password you set

That's your `DATABASE_URL`. The bot will automatically create all the tables on first run — you don't need to do anything else in Supabase.

---

## Step 3 — Put the Code on GitHub

1. Go to https://github.com and create a free account if you don't have one
2. Click **New Repository** → name it `wow-recipe-bot` → set to **Private** → click **Create**
3. Upload these 3 files to the repo: `bot.py`, `requirements.txt`, `Procfile`
   - Click **Add file → Upload files** and drag them in
   - Click **Commit changes**

---

## Step 4 — Deploy on Railway

1. Go to https://railway.app and sign up with your GitHub account
2. Click **New Project → Deploy from GitHub repo**
3. Select your `wow-recipe-bot` repository
4. Railway will detect it automatically. Before it deploys, click **Variables** and add:

   | Variable Name | Value |
   |---|---|
   | `DISCORD_TOKEN` | Your bot token from Step 1 |
   | `DATABASE_URL` | Your Supabase connection string from Step 2 |

5. Click **Deploy** — Railway will install dependencies and start your bot!

---

## Checking It's Working

- In Railway, click your deployment and open the **Logs** tab
- You should see:
  ```
  ✅ Database connected and slash commands synced.
  ✅ Logged in as YourBot#1234 (ID: ...)
  ```
- Go to your Discord server and type `/help` — the bot should respond!

> **Note:** Slash commands can take up to 1 hour to appear globally on Discord, but usually show within a few minutes.

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

## Troubleshooting

**Bot doesn't respond to commands:** Check the Railway logs for errors. Make sure both environment variables are set correctly.

**`DATABASE_URL` error:** Make sure you replaced `[YOUR-PASSWORD]` in the Supabase URL with your actual password.

**Commands don't show up in Discord:** Wait up to 1 hour. If still not showing, redeploy on Railway.

**Railway free tier:** Railway gives 500 execution hours/month free. A Discord bot uses ~720hrs/month, so you may need to upgrade to their $5/month Hobby plan for true 24/7 uptime. Alternatively, Fly.io's free tier has no hour limit for small apps.
