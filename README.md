# Packify: Collection & Tycoon Bot for Discord

Open. Collect. Trade. Tycoon your shop.

Packify is a Discord collection simulator with animated pack openings, trading, a marketplace, shop upgrades, daily bonuses, and leaderboards. Built with discord.py 2.x and SQLite.

![Packify animation](assets/pack_rare.gif)

## Features

- Animated pack openings (GIFs for Basic, Rare, Epic, Halloween)
- Card rarities and themed collections
- Inventory management, selling, trading, marketplace
- Shop upgrades, shelves, store stock, daily NPC sales
- Seasonal events (e.g., Halloween pack in October)
- Leaderboard and profiles
- EN/PL language toggle via /setlang
- SQLite persistence (async via aiosqlite)

## Commands (slash)

- Basic
  - /start — Create your account and shop
  - /profile — Shop level, wallet, packs, rare+
  - /inventory — View your cards (paginated)
  - /openpack — Open a pack (plays GIF, then shows results)
  - /buy pack <type> — Buy basic/rare/epic (halloween during October)
  - /sell <card> — Sell a card by inventory ID (autocomplete)
  - /shop upgrade — Upgrade your shop (adds capacity)
  - /leaderboard — Top players by shop value
  - /packinfo <type> — Drop odds and sample cards
- Tycoon / Economy
  - /buy shelf — Buy shelves (capacity + NPC sales cap)
  - /buy stock — Buy packs for your store’s stock
  - /daily — Claim coins + NPC sales based on shelves/stock
  - /trade @user — Secure card trading with locks/confirm
  - /event — Shows current events
- Interactive / Other
  - /gift @user <item> — Gift card:<ID> or pack:<type>[:qty]
  - /collection — Collection progress by theme
  - /market — Marketplace (list, buy, remove via UI)
  - /help — Overview of commands
  - /support — Invite links + support server
  - /setlang — English/Polish selector (user or server scope)

## Quickstart

Prerequisites
- Python 3.10+
- A Discord Application + Bot Token (see “Create a Discord Application” below)

Install
- Clone the repo, then:
  - Windows:
    - py -m venv .venv
    - .venv\Scripts\activate
    - py -m pip install -U -r requirements.txt
  - macOS/Linux:
    - python3 -m venv .venv
    - source .venv/bin/activate
    - python3 -m pip install -U -r requirements.txt

requirements.txt
- discord.py>=2.3
- aiosqlite
- python-dotenv
- uvloop; sys_platform != 'win32'  # optional perf on Linux/macOS

Configure
- Create a .env in the project root:
  - DISCORD_TOKEN=YOUR_BOT_TOKEN
  - SUPPORT_SERVER_URL=https://discord.gg/your-support (optional)
  - TEST_GUILD_ID=123456789012345678 (optional; speeds up slash sync in that server)

Animations (GIFs)
- Put your GIFs in ./assets/:
  - assets/pack_basic.gif
  - assets/pack_rare.gif
  - assets/pack_epic.gif
  - assets/pack_halloween.gif
- The bot is already wired to show these when /openpack runs. You can also use hosted URLs—see ANIM_GIFS in code.

Run
- python bot.py
- First global sync can take up to 1 hour. For instant testing, set TEST_GUILD_ID in .env and restart.

## Create a Discord Application

1) Go to https://discord.com/developers/applications → New Application  
2) Bot tab → Add Bot → Copy the Token → put it in .env as DISCORD_TOKEN  
3) Privileged intents: Not required for this bot’s default features  
4) Invite URL (two variants):
   - Minimal:
     https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=0&scope=bot%20applications.commands
   - Administrator:
     https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=8&scope=bot%20applications.commands
   Replace CLIENT_ID with your application’s ID. The /support command also generates invite links automatically.

## Configuration notes

- Pack GIFs: Edit ANIM_GIFS and DEFAULT_ANIM_DELAY in bot.py to point to local paths or hosted URLs, and to match your GIF length.
- Events: The Halloween pack is available in October only (is_october() gate).
- Language: /setlang lets users (or server admins) switch EN/PL. You can add more strings in the STRINGS dict.
- Support links: Set SUPPORT_SERVER_URL in .env so /support shows your server button.
- Fast slash sync: Set TEST_GUILD_ID to your test server ID during development.

## Data and storage

- SQLite database: collection.db (auto-created on first run)
- Tables: users, cards, inventory, packs, owned_packs, store_stock, marketplace, guild_settings
- Seeding: Cards and packs are seeded automatically from CARD_POOL and PACK_DEFS on startup
- Reset: Stop the bot and delete collection.db to wipe all data (dev only)

## Typical flow

1) /start  
2) /buy pack rare  
3) /openpack (shows Rare GIF, then results)  
4) /inventory, /sell, /trade, /market  
5) /daily + /buy stock and /buy shelf to grow NPC sales  
6) /leaderboard to compare

## Troubleshooting

- Slash commands not showing up:
  - The bot must be invited with the “applications.commands” scope
  - Use TEST_GUILD_ID for instant dev sync; global sync takes time
  - Restart the bot after adding new commands

- “NameError: send_pack_animation_gif is not defined”  
  - Ensure the helper function is present at module level and ANIM_GIFS is defined; restart the bot

- GIF didn’t send / too large:
  - Keep attachments under your server’s upload limit (8 MB on most servers)
  - Prefer hosted GIF URLs in ANIM_GIFS for larger files

- “403 Forbidden” when sending messages:
  - Check the bot’s role permissions in the channel (Send Messages, Embed Links)

- Database “locked” errors:
  - Don’t open the DB in another program while the bot runs; stop the bot before editing

## Project structure (suggested)

- bot.py — main bot
- collection.db — SQLite DB (auto)
- assets/
  - pack_basic.gif
  - pack_rare.gif
  - pack_epic.gif
  - pack_halloween.gif
- .env — secrets and config
- requirements.txt — dependencies
- README.md — this file

## Security, Terms, Privacy

- Packify does not require message content intent by default. Keep your token private.
- Add your Terms of Service and Privacy Policy links to the website and/or repo.
- Not affiliated with Discord.

## Contributing

Issues and PRs are welcome. Please:
- Keep features async and non-blocking
- Match code style and naming (PEP 8)
- Include migration notes if you change the DB schema
