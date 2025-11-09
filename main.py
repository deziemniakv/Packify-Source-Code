import asyncio
import json
import os
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

INTENTS = discord.Intents.default()  
BOT_PREFIX = "!"  

DB_PATH = "collection.db"
TEST_GUILD_ID = None  
COLOR_DEFAULT = 0x2F3136

STARTING_COINS = 1000
STARTING_PACK = "basic"
INVENTORY_BASE_CAPACITY = 200


RARITY_META = {
    "Common": {
        "emoji": "⬜",
        "color": 0x98A2A9,
        "sell_multiplier": 0.75,
        "weight": 60,
    },
    "Uncommon": {
        "emoji": "🟩",
        "color": 0x43B581,
        "sell_multiplier": 0.85,
        "weight": 25,
    },
    "Rare": {
        "emoji": "🔷",
        "color": 0x3498DB,
        "sell_multiplier": 1.0,
        "weight": 10,
    },
    "Epic": {
        "emoji": "🟣",
        "color": 0x9B59B6,
        "sell_multiplier": 1.3,
        "weight": 4,
    },
    "Legendary": {
        "emoji": "🟡",
        "color": 0xF1C40F,
        "sell_multiplier": 1.8,
        "weight": 1,
    },
}


PACK_DEFS = {
    "basic": {
        "name": "Basic Pack",
        "price": 100,
        "min_cards": 3,
        "max_cards": 5,
        "drops": {"Common": 60, "Uncommon": 25, "Rare": 10, "Epic": 4, "Legendary": 1},
    },
    "rare": {
        "name": "Rare Pack",
        "price": 400,
        "min_cards": 5,
        "max_cards": 6,
        "drops": {"Common": 35, "Uncommon": 30, "Rare": 20, "Epic": 12, "Legendary": 3},
    },
    "epic": {
        "name": "Epic Pack",
        "price": 1000,
        "min_cards": 5,
        "max_cards": 7,
        "drops": {"Common": 20, "Uncommon": 25, "Rare": 30, "Epic": 20, "Legendary": 5},
    },

    "halloween": {
        "name": "Halloween Pack 🎃",
        "price": 500,
        "min_cards": 4,
        "max_cards": 6,
        "drops": {"Common": 30, "Uncommon": 30, "Rare": 25, "Epic": 12, "Legendary": 3},
        "event_only": True,
    },
}


CARD_POOL = [

    ("Vampire Count", "Rare", "Classic Monsters", 240),
    ("Swamp Creature", "Uncommon", "Classic Monsters", 120),
    ("Haunted Ghost", "Common", "Classic Monsters", 60),
    ("Mad Scientist", "Uncommon", "Classic Monsters", 110),
    ("Cursed Mummy", "Rare", "Classic Monsters", 250),
    ("Wolfman", "Epic", "Classic Monsters", 450),
    ("Franken Titan", "Legendary", "Classic Monsters", 950),
    ("Headless Rider", "Epic", "Classic Monsters", 500),
    ("Wicked Witch", "Rare", "Classic Monsters", 260),
    ("Gravekeeper", "Common", "Classic Monsters", 65),


    ("Rookie Astronaut", "Common", "Space Explorers", 55),
    ("Veteran Pilot", "Uncommon", "Space Explorers", 130),
    ("Mission Commander", "Rare", "Space Explorers", 270),
    ("Alien Diplomat", "Epic", "Space Explorers", 520),
    ("Star Cartographer", "Uncommon", "Space Explorers", 125),
    ("Quantum Engineer", "Rare", "Space Explorers", 280),
    ("Warp Navigator", "Epic", "Space Explorers", 540),
    ("Galactic Empress", "Legendary", "Space Explorers", 1000),
    ("Probe Operator", "Common", "Space Explorers", 60),
    ("Exobiologist", "Rare", "Space Explorers", 300),


    ("Sun Tablet", "Common", "Ancient Artifacts", 70),
    ("Moon Chalice", "Uncommon", "Ancient Artifacts", 140),
    ("Dragon Relic", "Epic", "Ancient Artifacts", 600),
    ("Phoenix Feather", "Legendary", "Ancient Artifacts", 1100),
    ("King's Signet", "Rare", "Ancient Artifacts", 310),
    ("Oracle Stone", "Epic", "Ancient Artifacts", 620),
    ("Crystal Lens", "Uncommon", "Ancient Artifacts", 135),
    ("Time Dial", "Rare", "Ancient Artifacts", 330),
    ("Ancient Map", "Common", "Ancient Artifacts", 80),
    ("Golem Core", "Epic", "Ancient Artifacts", 650),


    ("Pumpkin Baron", "Rare", "Halloween", 350),
    ("Shadow Banshee", "Epic", "Halloween", 700),
    ("Candy Goober", "Common", "Halloween", 75),
    ("Lantern Keeper", "Uncommon", "Halloween", 160),
    ("Nightmare King", "Legendary", "Halloween", 1200),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def is_october() -> bool:
    dt = datetime.now(timezone.utc)
    return dt.month == 10

def readable_ts(ts: Optional[str]) -> str:
    if not ts:
        return "N/A"
    try:
        d = datetime.fromisoformat(ts)
        return f"{discord.utils.format_dt(d, 'R')} ({discord.utils.format_dt(d, 'f')})"
    except Exception:
        return ts

def random_id(n: int = 10) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def rarity_emoji(r: str) -> str:
    return RARITY_META.get(r, {}).get("emoji", "❔")

def rarity_color(r: str) -> int:
    return RARITY_META.get(r, {}).get("color", COLOR_DEFAULT)

def calc_sell_price(base_value: int, rarity: str) -> int:
    mult = RARITY_META.get(rarity, {}).get("sell_multiplier", 1.0)
    return int(base_value * mult)

def clamp(n, lo, hi):
    return max(lo, min(n, hi))

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        wallet INTEGER NOT NULL DEFAULT 0,
        shop_level INTEGER NOT NULL DEFAULT 1,
        shelves INTEGER NOT NULL DEFAULT 0,
        inventory_capacity INTEGER NOT NULL DEFAULT 200,
        lifetime_profit INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        last_daily TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS cards (
        card_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        rarity TEXT,
        collection TEXT,
        base_value INTEGER
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory (
        inventory_id TEXT PRIMARY KEY,
        user_id INTEGER,
        card_id INTEGER,
        created_at TEXT,
        locked INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (card_id) REFERENCES cards(card_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS packs (
        type TEXT PRIMARY KEY,
        name TEXT,
        price INTEGER,
        min_cards INTEGER,
        max_cards INTEGER,
        drops TEXT,
        event_only INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS owned_packs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        pack_type TEXT,
        created_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS store_stock (
        user_id INTEGER,
        pack_type TEXT,
        quantity INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, pack_type)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS marketplace (
        listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER,
        item_type TEXT,           -- 'card' or 'pack'
        inventory_id TEXT,        -- if card
        pack_type TEXT,           -- if pack
        quantity INTEGER,
        price INTEGER,
        status TEXT DEFAULT 'active',
        created_at TEXT
    );
    """
]

async def setup_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for sql in CREATE_TABLES_SQL:
            await db.execute(sql)
        await db.commit()


        for name, rarity, collection, base_value in CARD_POOL:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO cards (name, rarity, collection, base_value) VALUES (?, ?, ?, ?)",
                    (name, rarity, collection, base_value),
                )
            except Exception:
                pass

        for ptype, meta in PACK_DEFS.items():
            drops_json = json.dumps(meta["drops"])
            await db.execute(
                """INSERT OR REPLACE INTO packs (type, name, price, min_cards, max_cards, drops, event_only)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ptype,
                    meta["name"],
                    meta["price"],
                    meta["min_cards"],
                    meta["max_cards"],
                    drops_json,
                    1 if meta.get("event_only") else 0,
                ),
            )
        await db.commit()

async def get_user(db, user_id: int) -> Optional[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as c:
        return await c.fetchone()

async def create_user(db, user_id: int) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, wallet, shop_level, shelves, inventory_capacity, lifetime_profit, created_at) VALUES (?, ?, 1, 0, ?, 0, ?)",
        (user_id, STARTING_COINS, INVENTORY_BASE_CAPACITY, now_iso()),
    )
    await db.execute(
        "INSERT INTO owned_packs (user_id, pack_type, created_at) VALUES (?, ?, ?)",
        (user_id, STARTING_PACK, now_iso()),
    )
    await db.commit()

async def get_pack_def(db, pack_type: str) -> Optional[Dict]:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM packs WHERE type = ?", (pack_type,)) as c:
        row = await c.fetchone()
        if not row:
            return None
        return {
            "type": row["type"],
            "name": row["name"],
            "price": row["price"],
            "min_cards": row["min_cards"],
            "max_cards": row["max_cards"],
            "drops": json.loads(row["drops"]),
            "event_only": bool(row["event_only"]),
        }

async def list_pack_types(db, include_event: bool = False) -> List[Dict]:
    db.row_factory = aiosqlite.Row
    if include_event:
        async with db.execute("SELECT * FROM packs") as c:
            rows = await c.fetchall()
    else:
        async with db.execute("SELECT * FROM packs WHERE event_only = 0") as c:
            rows = await c.fetchall()
    out = []
    for row in rows:
        out.append({
            "type": row["type"],
            "name": row["name"],
            "price": row["price"],
            "min_cards": row["min_cards"],
            "max_cards": row["max_cards"],
            "drops": json.loads(row["drops"]),
            "event_only": bool(row["event_only"]),
        })
    return out

async def inventory_count(db, user_id: int) -> int:
    async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ?", (user_id,)) as c:
        row = await c.fetchone()
        return row[0] if row else 0

async def inventory_items(db, user_id: int, limit: int = 100, offset: int = 0) -> List[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    q = """
    SELECT inv.inventory_id, inv.created_at, inv.locked,
           cards.card_id, cards.name, cards.rarity, cards.collection, cards.base_value
    FROM inventory AS inv
    JOIN cards ON cards.card_id = inv.card_id
    WHERE inv.user_id = ?
    ORDER BY inv.created_at DESC
    LIMIT ? OFFSET ?
    """
    async with db.execute(q, (user_id, limit, offset)) as c:
        return await c.fetchall()

async def get_inventory_item(db, user_id: int, inventory_id: str) -> Optional[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    q = """
    SELECT inv.inventory_id, inv.user_id, inv.locked,
           cards.card_id, cards.name, cards.rarity, cards.collection, cards.base_value
    FROM inventory AS inv
    JOIN cards ON cards.card_id = inv.card_id
    WHERE inv.user_id = ? AND inv.inventory_id = ?
    """
    async with db.execute(q, (user_id, inventory_id)) as c:
        return await c.fetchone()

async def add_card_to_inventory(db, user_id: int, card_id: int) -> str:
    inv_id = random_id()
    await db.execute(
        "INSERT INTO inventory (inventory_id, user_id, card_id, created_at, locked) VALUES (?, ?, ?, ?, 0)",
        (inv_id, user_id, card_id, now_iso()),
    )
    return inv_id

async def remove_inventory_item(db, user_id: int, inventory_id: str) -> None:
    await db.execute("DELETE FROM inventory WHERE user_id = ? AND inventory_id = ?", (user_id, inventory_id))

async def owned_packs_count(db, user_id: int) -> int:
    async with db.execute("SELECT COUNT(*) FROM owned_packs WHERE user_id = ?", (user_id,)) as c:
        row = await c.fetchone()
        return row[0] if row else 0

async def pop_oldest_owned_pack(db, user_id: int) -> Optional[str]:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT id, pack_type FROM owned_packs WHERE user_id = ? ORDER BY id ASC LIMIT 1", (user_id,)) as c:
        row = await c.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM owned_packs WHERE id = ?", (row["id"],))
        return row["pack_type"]

async def give_owned_pack(db, user_id: int, pack_type: str):
    await db.execute("INSERT INTO owned_packs (user_id, pack_type, created_at) VALUES (?, ?, ?)", (user_id, pack_type, now_iso()))

async def adjust_wallet(db, user_id: int, delta: int):
    await db.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (delta, user_id))

async def set_last_daily(db, user_id: int):
    await db.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (now_iso(), user_id))

async def add_profit(db, user_id: int, delta: int):
    await db.execute("UPDATE users SET lifetime_profit = lifetime_profit + ? WHERE user_id = ?", (delta, user_id))

async def get_wallet(db, user_id: int) -> int:
    async with db.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,)) as c:
        row = await c.fetchone()
        return int(row[0]) if row else 0

async def get_card_ids_by_rarity(db, rarity: str, include_halloween: bool = True) -> List[int]:
    db.row_factory = aiosqlite.Row
    if include_halloween:
        q = "SELECT card_id FROM cards WHERE rarity = ?"
        args = (rarity,)
    else:
        q = "SELECT card_id FROM cards WHERE rarity = ? AND collection != 'Halloween'"
        args = (rarity,)
    async with db.execute(q, args) as c:
        rows = await c.fetchall()
        return [r["card_id"] for r in rows]

async def count_rare_or_better(db, user_id: int) -> int:
    db.row_factory = aiosqlite.Row
    q = """
    SELECT COUNT(*)
    FROM inventory inv
    JOIN cards c ON c.card_id = inv.card_id
    WHERE inv.user_id = ? AND (c.rarity IN ('Rare', 'Epic', 'Legendary'))
    """
    async with db.execute(q, (user_id,)) as c:
        row = await c.fetchone()
        return row[0] if row else 0

async def compute_shop_value(db, user_id: int) -> int:
    wallet = await get_wallet(db, user_id)
    db.row_factory = aiosqlite.Row
    q = """
    SELECT SUM(c.base_value) FROM inventory inv
    JOIN cards c ON c.card_id = inv.card_id
    WHERE inv.user_id = ?
    """
    async with db.execute(q, (user_id,)) as c:
        inv_val_row = await c.fetchone()
        inv_val = int(inv_val_row[0]) if inv_val_row and inv_val_row[0] else 0

    async with db.execute("SELECT shop_level, shelves FROM users WHERE user_id = ?", (user_id,)) as c:
        row = await c.fetchone()
        level = row[0] if row else 1
        shelves = row[1] if row else 0

    upgrade_value = level * 200 + shelves * 150
    return wallet + inv_val + upgrade_value

async def get_store_stock(db, user_id: int) -> Dict[str, int]:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT pack_type, quantity FROM store_stock WHERE user_id = ?", (user_id,)) as c:
        rows = await c.fetchall()
        return {r["pack_type"]: r["quantity"] for r in rows}

async def change_store_stock(db, user_id: int, pack_type: str, delta_qty: int):
    current = 0
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT quantity FROM store_stock WHERE user_id = ? AND pack_type = ?", (user_id, pack_type)) as c:
        row = await c.fetchone()
        if row:
            current = int(row[0])
    new_q = current + delta_qty
    if new_q < 0:
        new_q = 0
    await db.execute(
        "INSERT INTO store_stock (user_id, pack_type, quantity) VALUES (?, ?, ?) ON CONFLICT(user_id, pack_type) DO UPDATE SET quantity = excluded.quantity",
        (user_id, pack_type, new_q),
    )

def choose_rarity(drops: Dict[str, int]) -> str:
    rarities = list(drops.keys())
    weights = [drops[r] for r in rarities]
    return random.choices(rarities, weights=weights, k=1)[0]

async def roll_pack_cards(db, pack_type: str) -> List[aiosqlite.Row]:
    pack = await get_pack_def(db, pack_type)
    if not pack:
        return []
    n = random.randint(pack["min_cards"], pack["max_cards"])

    results = []
    include_halloween = is_october()
    for _ in range(n):
        rarity = choose_rarity(pack["drops"])
        ids = await get_card_ids_by_rarity(db, rarity, include_halloween=include_halloween)
        if not ids:
            ids = await get_card_ids_by_rarity(db, "Common", include_halloween=True)
        card_id = random.choice(ids)
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)) as c:
            row = await c.fetchone()
            results.append(row)
    return results

class TycoonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=BOT_PREFIX, intents=INTENTS)
        self.db: Optional[aiosqlite.Connection] = None

    async def setup_hook(self) -> None:
        await setup_db()
        self.db = await aiosqlite.connect(DB_PATH)
        self.db.row_factory = aiosqlite.Row

        if TEST_GUILD_ID:
            guild = discord.Object(id=TEST_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def close(self) -> None:
        if self.db:
            await self.db.close()
        await super().close()

bot = TycoonBot()

class InventoryView(discord.ui.View):
    def __init__(self, user_id: int, items: List[aiosqlite.Row], page_size: int = 10, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.items = items
        self.page_size = page_size
        self.page = 0

    def format_page(self) -> discord.Embed:
        start = self.page * self.page_size
        chunk = self.items[start:start+self.page_size]
        embed = discord.Embed(title="🎒 Inventory", color=COLOR_DEFAULT)
        if not chunk:
            embed.description = "No cards found."
            return embed
        for row in chunk:
            inv_id = row["inventory_id"]
            nm = row["name"]
            rarity = row["rarity"]
            coll = row["collection"]
            val = row["base_value"]
            lock = "🔒" if row["locked"] else ""
            embed.add_field(
                name=f"{rarity_emoji(rarity)} {nm} [{rarity}] {lock}",
                value=f"ID: `{inv_id}` • Collection: {coll} • Base value: {val}",
                inline=False
            )
        total_pages = max(1, (len(self.items) + self.page_size - 1) // self.page_size)
        embed.set_footer(text=f"Page {self.page+1}/{total_pages} • Use buttons to navigate")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.format_page(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        max_page = max(0, (len(self.items) - 1) // self.page_size)
        if self.page < max_page:
            self.page += 1
        await interaction.response.edit_message(embed=self.format_page(), view=self)

class TradeState:
    def __init__(self, a_id: int, b_id: int):
        self.a_id = a_id
        self.b_id = b_id
        self.a_offers: List[str] = []
        self.b_offers: List[str] = []
        self.a_confirmed = False
        self.b_confirmed = False
        self.created_at = datetime.now(timezone.utc)

class TradeView(discord.ui.View):
    def __init__(self, bot: TycoonBot, state: TradeState, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.state = state
        self.msg: Optional[discord.Message] = None

    def _summary(self) -> discord.Embed:
        embed = discord.Embed(title="🤝 Trade Session", color=0x5865F2)
        a_user = f"<@{self.state.a_id}>"
        b_user = f"<@{self.state.b_id}>"
        a_list = "\n".join(f"`{x}`" for x in self.state.a_offers) or "*None*"
        b_list = "\n".join(f"`{x}`" for x in self.state.b_offers) or "*None*"
        embed.add_field(name=f"{a_user} offers", value=a_list, inline=True)
        embed.add_field(name=f"{b_user} offers", value=b_list, inline=True)
        embed.set_footer(text="Use 'Add/Confirm/Cancel'. IDs are inventory IDs. Locked items cannot be traded.")
        return embed

    async def _add_items_modal(self, interaction: discord.Interaction, who: str):
        class OfferModal(discord.ui.Modal, title="Add cards to offer"):
            ids = discord.ui.TextInput(
                label="Inventory IDs (comma separated)", placeholder="ABC123, DEF456, ...", required=True
            )
            async def on_submit(self, modal_interaction: discord.Interaction):
                offers = [x.strip() for x in str(self.ids.value).split(",") if x.strip()]
                await modal_interaction.response.defer(thinking=False)
                await self._apply_offers(modal_interaction, offers, who)

        modal = OfferModal()
        modal._apply_offers = self._apply_offers 
        await interaction.response.send_modal(modal)

    async def _apply_offers(self, interaction: discord.Interaction, offers: List[str], who: str):
        uid = interaction.user.id
        if (who == "A" and uid != self.state.a_id) or (who == "B" and uid != self.state.b_id):
            await interaction.followup.send("This button isn't for you.", ephemeral=True)
            return

        valid_ids = []
        async with self.bot.db.execute("SELECT inventory_id, locked FROM inventory WHERE user_id = ? AND inventory_id IN (%s)" %
                                       ",".join("?"*len(offers)), (uid, *offers)) as c:
            rows = await c.fetchall()
            found = {r[0]: r[1] for r in rows}
        for oid in offers:
            if oid in found and found[oid] == 0:
                valid_ids.append(oid)

        if not valid_ids:
            await interaction.followup.send("No valid/unlocked items found for those IDs.", ephemeral=True)
            return

        await self.bot.db.execute(
            "UPDATE inventory SET locked = 1 WHERE user_id = ? AND inventory_id IN (%s)" % ",".join("?"*len(valid_ids)),
            (uid, *valid_ids)
        )

        if who == "A":
            self.state.a_offers.extend(valid_ids)
            self.state.a_confirmed = False
        else:
            self.state.b_offers.extend(valid_ids)
            self.state.b_confirmed = False

        await self.bot.db.commit()

        await interaction.followup.send(f"Added {len(valid_ids)} items to your offer and locked them.", ephemeral=True)
        if self.msg:
            await self.msg.edit(embed=self._summary(), view=self)

    async def _unlock_all(self):
        ids = self.state.a_offers + self.state.b_offers
        if not ids:
            return
        await self.bot.db.execute(
            "UPDATE inventory SET locked = 0 WHERE inventory_id IN (%s)" % ",".join("?"*len(ids)),
            (*ids,)
        )
        await self.bot.db.commit()

    async def _finalize_trade(self, interaction: discord.Interaction):
        ids_a = self.state.a_offers
        ids_b = self.state.b_offers
        if ids_a:
            await self.bot.db.execute(
                "UPDATE inventory SET user_id = ?, locked = 0 WHERE inventory_id IN (%s)" % ",".join("?"*len(ids_a)),
                (self.state.b_id, *ids_a)
            )
        if ids_b:
            await self.bot.db.execute(
                "UPDATE inventory SET user_id = ?, locked = 0 WHERE inventory_id IN (%s)" % ",".join("?"*len(ids_b)),
                (self.state.a_id, *ids_b)
            )
        await self.bot.db.commit()
        await interaction.followup.send("Trade complete ✅", ephemeral=True)
        if self.msg:
            await self.msg.edit(content="Trade complete ✅", embed=self._summary(), view=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in {self.state.a_id, self.state.b_id}

    @discord.ui.button(label="Add (A)", style=discord.ButtonStyle.primary)
    async def add_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._add_items_modal(interaction, "A")

    @discord.ui.button(label="Add (B)", style=discord.ButtonStyle.primary)
    async def add_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._add_items_modal(interaction, "B")

    @discord.ui.button(label="Confirm (A)", style=discord.ButtonStyle.success)
    async def confirm_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.state.a_id:
            await interaction.response.send_message("This is for the other trader.", ephemeral=True)
            return
        self.state.a_confirmed = True
        await interaction.response.defer()
        if self.msg:
            await self.msg.edit(embed=self._summary(), view=self)
        if self.state.a_confirmed and self.state.b_confirmed:
            await self._finalize_trade(interaction)

    @discord.ui.button(label="Confirm (B)", style=discord.ButtonStyle.success)
    async def confirm_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.state.b_id:
            await interaction.response.send_message("This is for the other trader.", ephemeral=True)
            return
        self.state.b_confirmed = True
        await interaction.response.defer()
        if self.msg:
            await self.msg.edit(embed=self._summary(), view=self)
        if self.state.a_confirmed and self.state.b_confirmed:
            await self._finalize_trade(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._unlock_all()
        await interaction.response.send_message("Trade canceled.", ephemeral=True)
        if self.msg:
            await self.msg.edit(content="Trade canceled.", embed=self._summary(), view=None)
        self.stop()

    async def on_timeout(self):
        await self._unlock_all()
        try:
            if self.msg:
                await self.msg.edit(content="Trade timed out.", view=None)
        except Exception:
            pass

class MarketView(discord.ui.View):
    def __init__(self, bot: TycoonBot, viewer_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.viewer_id = viewer_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    def _render_embed(self, listings: List[aiosqlite.Row]) -> discord.Embed:
        embed = discord.Embed(title="🌐 Marketplace", color=0xFFB347)
        if not listings:
            embed.description = "No active listings. Use the buttons to list or buy."
            return embed
        for row in listings[:10]:
            lid = row["listing_id"]
            seller = f"<@{row['seller_id']}>"
            if row["item_type"] == "card":
                embed.add_field(
                    name=f"#{lid} • Card • Price: {row['price']}",
                    value=f"Seller: {seller} • Card ID: `{row['inventory_id']}`",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"#{lid} • Pack • Price: {row['price']} • Qty: {row['quantity']}",
                    value=f"Seller: {seller} • Type: `{row['pack_type']}`",
                    inline=False
                )
        embed.set_footer(text="Use List Card/List Pack/Buy/Remove to interact.")
        return embed

    async def refresh(self):
        self.bot.db.row_factory = aiosqlite.Row
        async with self.bot.db.execute("SELECT * FROM marketplace WHERE status = 'active' ORDER BY listing_id DESC LIMIT 20") as c:
            rows = await c.fetchall()
        if self.message:
            await self.message.edit(embed=self._render_embed(rows), view=self)

    @discord.ui.button(label="List Card", style=discord.ButtonStyle.primary)
    async def list_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ListCardModal(discord.ui.Modal, title="List Card on Marketplace"):
            inv_id = discord.ui.TextInput(label="Inventory ID", placeholder="ABC123...", required=True, max_length=32)
            price = discord.ui.TextInput(label="Price", placeholder="e.g., 300", required=True)
            async def on_submit(self, mi: discord.Interaction):
                await mi.response.defer()
                inv = await get_inventory_item(self_view.bot.db, mi.user.id, str(self.inv_id.value).strip())
                if not inv:
                    await mi.followup.send("You don't own that card, or it doesn't exist.", ephemeral=True)
                    return
                if inv["locked"]:
                    await mi.followup.send("That card is locked (maybe in a trade).", ephemeral=True)
                    return
                try:
                    p = int(str(self.price.value))
                    p = max(1, p)
                except:
                    await mi.followup.send("Invalid price.", ephemeral=True)
                    return
                await self_view.bot.db.execute("UPDATE inventory SET locked = 1 WHERE inventory_id = ?", (inv["inventory_id"],))
                await self_view.bot.db.execute(
                    "INSERT INTO marketplace (seller_id, item_type, inventory_id, price, created_at) VALUES (?, 'card', ?, ?, ?)",
                    (mi.user.id, inv["inventory_id"], p, now_iso())
                )
                await self_view.bot.db.commit()
                await mi.followup.send(f"Listed card `{inv['inventory_id']}` for {p}.", ephemeral=True)
                await self_view.refresh()

        self_view = self
        await interaction.response.send_modal(ListCardModal())

    @discord.ui.button(label="List Pack", style=discord.ButtonStyle.primary)
    async def list_pack(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ListPackModal(discord.ui.Modal, title="List Pack(s) on Marketplace"):
            ptype = discord.ui.TextInput(label="Pack Type", placeholder="basic / rare / epic", required=True)
            qty = discord.ui.TextInput(label="Quantity", placeholder="e.g., 1", required=True)
            price = discord.ui.TextInput(label="Price per pack", placeholder="e.g., 150", required=True)
            async def on_submit(self, mi: discord.Interaction):
                await mi.response.defer()
                ptype_s = str(self.ptype.value).strip().lower()
                pack = await get_pack_def(self_view.bot.db, ptype_s)
                if not pack:
                    await mi.followup.send("Unknown pack type.", ephemeral=True)
                    return
                try:
                    q = max(1, int(str(self.qty.value)))
                    p = max(1, int(str(self.price.value)))
                except:
                    await mi.followup.send("Invalid quantity/price.", ephemeral=True)
                    return
                stock = await get_store_stock(self_view.bot.db, mi.user.id)
                available = stock.get(ptype_s, 0)
                if available < q:
                    await mi.followup.send(f"Not enough in store stock. You have {available} of {ptype_s}.", ephemeral=True)
                    return
                await change_store_stock(self_view.bot.db, mi.user.id, ptype_s, -q)
                await self_view.bot.db.execute(
                    "INSERT INTO marketplace (seller_id, item_type, pack_type, quantity, price, created_at) VALUES (?, 'pack', ?, ?, ?, ?)",
                    (mi.user.id, ptype_s, q, p, now_iso())
                )
                await self_view.bot.db.commit()
                await mi.followup.send(f"Listed {q}x {ptype_s} pack(s) at {p} each.", ephemeral=True)
                await self_view.refresh()

        self_view = self
        await interaction.response.send_modal(ListPackModal())

    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        class BuyModal(discord.ui.Modal, title="Buy from Marketplace"):
            listing_id = discord.ui.TextInput(label="Listing ID", placeholder="Number", required=True)
            quantity = discord.ui.TextInput(label="Quantity (packs only)", placeholder="1 (ignored for cards)", required=False, default="1")
            async def on_submit(self, mi: discord.Interaction):
                await mi.response.defer()
                try:
                    lid = int(str(self.listing_id.value).strip())
                except:
                    await mi.followup.send("Invalid listing ID.", ephemeral=True)
                    return
                qty_req = 1
                try:
                    qty_req = max(1, int(str(self.quantity.value)))
                except:
                    qty_req = 1
                self_view.bot.db.row_factory = aiosqlite.Row
                async with self_view.bot.db.execute("SELECT * FROM marketplace WHERE listing_id = ? AND status = 'active'", (lid,)) as c:
                    listing = await c.fetchone()
                if not listing:
                    await mi.followup.send("Listing not found.", ephemeral=True)
                    return
                if listing["seller_id"] == mi.user.id:
                    await mi.followup.send("You can't buy your own listing.", ephemeral=True)
                    return
                if listing["item_type"] == "card":
                    price = listing["price"]
                    wallet = await get_wallet(self_view.bot.db, mi.user.id)
                    if wallet < price:
                        await mi.followup.send("Not enough coins.", ephemeral=True)
                        return
                    await adjust_wallet(self_view.bot.db, mi.user.id, -price)
                    await adjust_wallet(self_view.bot.db, listing["seller_id"], price)
                    await self_view.bot.db.execute(
                        "UPDATE inventory SET user_id = ?, locked = 0 WHERE inventory_id = ?",
                        (mi.user.id, listing["inventory_id"])
                    )
                    await self_view.bot.db.execute("UPDATE marketplace SET status = 'sold' WHERE listing_id = ?", (lid,))
                    await self_view.bot.db.commit()
                    await mi.followup.send("Purchased card successfully.", ephemeral=True)
                else:
                    q_avail = listing["quantity"]
                    q_buy = clamp(qty_req, 1, q_avail)
                    price_total = q_buy * listing["price"]
                    wallet = await get_wallet(self_view.bot.db, mi.user.id)
                    if wallet < price_total:
                        await mi.followup.send(f"Not enough coins for {q_buy} pack(s).", ephemeral=True)
                        return
                    await adjust_wallet(self_view.bot.db, mi.user.id, -price_total)
                    await adjust_wallet(self_view.bot.db, listing["seller_id"], price_total)
                    for _ in range(q_buy):
                        await give_owned_pack(self_view.bot.db, mi.user.id, listing["pack_type"])
                    if q_buy == q_avail:
                        await self_view.bot.db.execute("UPDATE marketplace SET status = 'sold' WHERE listing_id = ?", (lid,))
                    else:
                        await self_view.bot.db.execute("UPDATE marketplace SET quantity = quantity - ? WHERE listing_id = ?", (q_buy, lid))
                    await self_view.bot.db.commit()
                    await mi.followup.send(f"Purchased {q_buy} pack(s).", ephemeral=True)
                await self_view.refresh()

        self_view = self
        await interaction.response.send_modal(BuyModal())

    @discord.ui.button(label="Remove Listing", style=discord.ButtonStyle.secondary)
    async def remove_listing(self, interaction: discord.Interaction, button: discord.ui.Button):
        class RemoveModal(discord.ui.Modal, title="Remove My Listing"):
            listing_id = discord.ui.TextInput(label="Listing ID", required=True)
            async def on_submit(self, mi: discord.Interaction):
                await mi.response.defer()
                try:
                    lid = int(str(self.listing_id.value).strip())
                except:
                    await mi.followup.send("Invalid listing ID.", ephemeral=True)
                    return
                self_view.bot.db.row_factory = aiosqlite.Row
                async with self_view.bot.db.execute("SELECT * FROM marketplace WHERE listing_id = ? AND status = 'active'", (lid,)) as c:
                    listing = await c.fetchone()
                if not listing:
                    await mi.followup.send("Listing not found or not active.", ephemeral=True)
                    return
                if listing["seller_id"] != mi.user.id:
                    await mi.followup.send("That's not your listing.", ephemeral=True)
                    return
                # Return item
                if listing["item_type"] == "card":
                    await self_view.bot.db.execute("UPDATE inventory SET locked = 0 WHERE inventory_id = ?", (listing["inventory_id"],))
                else:
                    await change_store_stock(self_view.bot.db, mi.user.id, listing["pack_type"], listing["quantity"])
                await self_view.bot.db.execute("UPDATE marketplace SET status = 'removed' WHERE listing_id = ?", (lid,))
                await self_view.bot.db.commit()
                await mi.followup.send("Listing removed.", ephemeral=True)
                await self_view.refresh()

        self_view = self
        await interaction.response.send_modal(RemoveModal())

    async def on_timeout(self):
        try:
            if self.message:
                await self.message.edit(view=None)
        except Exception:
            pass

@bot.tree.command(description="Create your account and shop")
async def start(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    async with bot.db.execute("SELECT 1 FROM users WHERE user_id = ?", (interaction.user.id,)) as c:
        row = await c.fetchone()
    if row:
        await interaction.followup.send("You already have an account.", ephemeral=True)
        return
    await create_user(bot.db, interaction.user.id)
    await bot.db.commit()
    await interaction.followup.send(f"Account created! You received {STARTING_COINS} coins and a {STARTING_PACK} pack. Use /openpack to open it!", ephemeral=True)

@bot.tree.command(description="Show your shop profile")
async def profile(interaction: discord.Interaction):
    await interaction.response.defer(thinking=False, ephemeral=False)
    user = await get_user(bot.db, interaction.user.id)
    if not user:
        await interaction.followup.send("Use /start first.", ephemeral=True)
        return
    packs = await owned_packs_count(bot.db, interaction.user.id)
    rare_count = await count_rare_or_better(bot.db, interaction.user.id)
    shop_val = await compute_shop_value(bot.db, interaction.user.id)
    stock = await get_store_stock(bot.db, interaction.user.id)
    stock_summary = ", ".join(f"{k}:{v}" for k, v in stock.items()) or "None"

    embed = discord.Embed(title=f"🏪 {interaction.user.display_name}'s Shop", color=0x00BFFF)
    embed.add_field(name="Level", value=str(user["shop_level"]))
    embed.add_field(name="Wallet", value=str(user["wallet"]))
    embed.add_field(name="Packs owned", value=str(packs))
    embed.add_field(name="Rare+ cards", value=str(rare_count))
    embed.add_field(name="Shelves", value=str(user["shelves"]))
    embed.add_field(name="Inventory Cap", value=str(user["inventory_capacity"]))
    embed.add_field(name="Lifetime Profit", value=str(user["lifetime_profit"]), inline=False)
    embed.add_field(name="Store Stock", value=stock_summary, inline=False)
    embed.add_field(name="Shop Value", value=str(shop_val), inline=False)
    embed.set_footer(text=f"Created {readable_ts(user['created_at'])} • Last daily {readable_ts(user['last_daily'])}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(description="Show all cards you own")
async def inventory(interaction: discord.Interaction):
    await interaction.response.defer()
    user = await get_user(bot.db, interaction.user.id)
    if not user:
        await interaction.followup.send("Use /start first.", ephemeral=True)
        return
    items = await inventory_items(bot.db, interaction.user.id, limit=400, offset=0)
    view = InventoryView(interaction.user.id, items)
    embed = view.format_page()
    msg = await interaction.followup.send(embed=embed, view=view)
    view.message = msg

@bot.tree.command(name="openpack", description="Open one of your packs")
async def openpack_cmd(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    user = await get_user(bot.db, interaction.user.id)
    if not user:
        await interaction.followup.send("Use /start first.", ephemeral=True)
        return
    pack_type = await pop_oldest_owned_pack(bot.db, interaction.user.id)
    if not pack_type:
        await interaction.followup.send("You have no packs to open. Use /buy pack <type>.", ephemeral=True)
        return

    pack_def = await get_pack_def(bot.db, pack_type)
    inv_count = await inventory_count(bot.db, interaction.user.id)
    to_open_preview = pack_def["max_cards"]
    if inv_count + pack_def["min_cards"] > user["inventory_capacity"]:
        await interaction.followup.send(f"Not enough inventory space. You need at least {pack_def['min_cards']} empty slots. Use /shop upgrade.", ephemeral=True)
        await give_owned_pack(bot.db, interaction.user.id, pack_type)
        await bot.db.commit()
        return

    embed = discord.Embed(title=f"🎁 Opening {pack_def['name']}...", color=0xE67E22)
    embed.description = "Rolling cards..."
    msg = await interaction.followup.send(embed=embed)

    cards = await roll_pack_cards(bot.db, pack_type)
    obtained = []
    for idx, c in enumerate(cards, start=1):
        inv_id = await add_card_to_inventory(bot.db, interaction.user.id, c["card_id"])
        obtained.append((c, inv_id))

        reveal = f"{rarity_emoji(c['rarity'])} {c['name']} [{c['rarity']}] • {c['collection']} (ID: `{inv_id}`)"
        embed.description = (embed.description or "") + f"\n{reveal}"
        embed.color = rarity_color(c["rarity"])
        await msg.edit(embed=embed)
        await asyncio.sleep(0.7)

    await bot.db.commit()

    summary = discord.Embed(
        title="✨ Pack Results",
        description="\n".join(
            f"{rarity_emoji(c['rarity'])} {c['name']} [{c['rarity']}] • {c['collection']} • Base {c['base_value']} (ID: `{inv}`)"
            for c, inv in obtained
        ),
        color=0x2ECC71
    )
    await msg.edit(embed=summary)


class BuyGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="buy", description="Buy items")

    @app_commands.describe(type="Pack type to buy (basic/rare/epic[/halloween])")
    @app_commands.command(name="pack", description="Buy a pack")
    async def buy_pack(self, interaction: discord.Interaction, type: str):
        await interaction.response.defer()
        user = await get_user(bot.db, interaction.user.id)
        if not user:
            await interaction.followup.send("Use /start first.", ephemeral=True)
            return
        ptype = type.lower()
        pack = await get_pack_def(bot.db, ptype)
        if not pack:
            await interaction.followup.send("Unknown pack type.", ephemeral=True)
            return
        if pack.get("event_only") and not is_october():
            await interaction.followup.send("That pack is event-only and not currently available.", ephemeral=True)
            return
        wallet = await get_wallet(bot.db, interaction.user.id)
        price = pack["price"]
        if wallet < price:
            await interaction.followup.send("Not enough coins.", ephemeral=True)
            return
        await adjust_wallet(bot.db, interaction.user.id, -price)
        await give_owned_pack(bot.db, interaction.user.id, ptype)
        await bot.db.commit()
        await interaction.followup.send(f"Purchased 1x {pack['name']} for {price} coins.")

    @app_commands.describe(amount="Number of shelves to buy (default 1)")
    @app_commands.command(name="shelf", description="Buy a shelf (increases capacity, boosts store)")
    async def buy_shelf(self, interaction: discord.Interaction, amount: Optional[int] = 1):
        await interaction.response.defer()
        user = await get_user(bot.db, interaction.user.id)
        if not user:
            await interaction.followup.send("Use /start first.", ephemeral=True)
            return
        amount = max(1, int(amount or 1))
        total_cost = 0
        shelves = user["shelves"]
        for i in range(amount):
            cost = 500 * (shelves + 1 + i)
            total_cost += cost
        wallet = await get_wallet(bot.db, interaction.user.id)
        if wallet < total_cost:
            await interaction.followup.send(f"Not enough coins. Need {total_cost}.", ephemeral=True)
            return
        await adjust_wallet(bot.db, interaction.user.id, -total_cost)
        await bot.db.execute("UPDATE users SET shelves = shelves + ?, inventory_capacity = inventory_capacity + ? WHERE user_id = ?",
                             (amount, amount * 20, interaction.user.id))
        await bot.db.commit()
        await interaction.followup.send(f"Bought {amount} shelf/shelves for {total_cost}. Capacity +{amount*20}.")

    @app_commands.describe(type="Pack type for store stock", quantity="Quantity to buy for store stock")
    @app_commands.command(name="stock", description="Buy stock for your store (NPC sales via /daily)")
    async def buy_stock(self, interaction: discord.Interaction, type: str, quantity: int):
        await interaction.response.defer()
        user = await get_user(bot.db, interaction.user.id)
        if not user:
            await interaction.followup.send("Use /start first.", ephemeral=True)
            return
        ptype = type.lower()
        pack = await get_pack_def(bot.db, ptype)
        if not pack:
            await interaction.followup.send("Unknown pack type.", ephemeral=True)
            return
        quantity = max(1, int(quantity))
        cost = pack["price"] * quantity
        wallet = await get_wallet(bot.db, interaction.user.id)
        if wallet < cost:
            await interaction.followup.send(f"Not enough coins. Need {cost}.", ephemeral=True)
            return
        await adjust_wallet(bot.db, interaction.user.id, -cost)
        await change_store_stock(bot.db, interaction.user.id, ptype, quantity)
        await bot.db.commit()
        await interaction.followup.send(f"Bought {quantity}x {pack['name']} for store stock.")

bot.tree.add_command(BuyGroup())

async def sell_card_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    bot.db.row_factory = aiosqlite.Row
    query = f"%{current}%"
    q = """
    SELECT inv.inventory_id, c.name, c.rarity
    FROM inventory inv
    JOIN cards c ON c.card_id = inv.card_id
    WHERE inv.user_id = ? AND (c.name LIKE ? OR inv.inventory_id LIKE ?)
    LIMIT 20
    """
    choices = []
    async with bot.db.execute(q, (interaction.user.id, query, query)) as c:
        rows = await c.fetchall()
    for r in rows:
        label = f"{r['name']} [{r['rarity']}] • {r['inventory_id']}"
        choices.append(app_commands.Choice(name=label[:100], value=r["inventory_id"]))
    return choices

@bot.tree.command(description="Sell a card from your inventory")
@app_commands.describe(card="Inventory ID of the card to sell")
@app_commands.autocomplete(card=sell_card_autocomplete)
async def sell(interaction: discord.Interaction, card: str):
    await interaction.response.defer()
    user = await get_user(bot.db, interaction.user.id)
    if not user:
        await interaction.followup.send("Use /start first.", ephemeral=True)
        return
    inv = await get_inventory_item(bot.db, interaction.user.id, card.strip())
    if not inv:
        await interaction.followup.send("Card not found.", ephemeral=True)
        return
    if inv["locked"]:
        await interaction.followup.send("This card is locked (maybe in a trade/market).", ephemeral=True)
        return
    value = calc_sell_price(inv["base_value"], inv["rarity"])
    await remove_inventory_item(bot.db, interaction.user.id, inv["inventory_id"])
    await adjust_wallet(bot.db, interaction.user.id, value)
    await add_profit(bot.db, interaction.user.id, value)
    await bot.db.commit()
    await interaction.followup.send(f"Sold {inv['name']} [{inv['rarity']}] for {value} coins.")

class ShopGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Shop management")

    @app_commands.command(name="upgrade", description="Upgrade your shop (more space, better prestige)")
    async def upgrade(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = await get_user(bot.db, interaction.user.id)
        if not user:
            await interaction.followup.send("Use /start first.", ephemeral=True)
            return
        level = user["shop_level"]
        cost = 800 * level
        wallet = await get_wallet(bot.db, interaction.user.id)
        if wallet < cost:
            await interaction.followup.send(f"Not enough coins. Upgrade to level {level+1} costs {cost}.", ephemeral=True)
            return
        cap_increase = 50 + 10 * level
        await adjust_wallet(bot.db, interaction.user.id, -cost)
        await bot.db.execute("UPDATE users SET shop_level = shop_level + 1, inventory_capacity = inventory_capacity + ? WHERE user_id = ?",
                             (cap_increase, interaction.user.id))
        await bot.db.commit()
        await interaction.followup.send(f"Upgraded shop to level {level+1}! Capacity +{cap_increase}.")

bot.tree.add_command(ShopGroup())


@bot.tree.command(description="Show top shops by value")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    bot.db.row_factory = aiosqlite.Row
    async with bot.db.execute("SELECT user_id FROM users") as c:
        rows = await c.fetchall()
    scores = []
    for r in rows:
        uid = r["user_id"]
        val = await compute_shop_value(bot.db, uid)
        scores.append((uid, val))
    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:10]
    embed = discord.Embed(title="🏆 Leaderboard: Shop Value", color=0xFEE75C)
    if not top:
        embed.description = "No players yet. Use /start!"
    else:
        for idx, (uid, val) in enumerate(top, start=1):
            embed.add_field(name=f"#{idx} • {val}", value=f"<@{uid}>", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(description="Claim your daily bonus and store sales")
async def daily(interaction: discord.Interaction):
    await interaction.response.defer()
    user = await get_user(bot.db, interaction.user.id)
    if not user:
        await interaction.followup.send("Use /start first.", ephemeral=True)
        return
    ok = True
    msg = ""
    if user["last_daily"]:
        last = datetime.fromisoformat(user["last_daily"])
        if datetime.now(timezone.utc) - last < timedelta(hours=22):
            ok = False
            rem = timedelta(hours=22) - (datetime.now(timezone.utc) - last)
            hrs = int(rem.total_seconds() // 3600)
            mins = int((rem.total_seconds() % 3600) // 60)
            msg = f"Daily not ready. Try again in {hrs}h {mins}m."
    if not ok:
        await interaction.followup.send(msg, ephemeral=True)
        return

    base = random.randint(100, 200)

    shelves = user["shelves"]
    stock = await get_store_stock(bot.db, interaction.user.id)
    sales_capacity = shelves * 5
    total_sales_profit = 0
    total_sold = {}
    if sales_capacity > 0 and stock:
        for ptype, qty in sorted(stock.items(), key=lambda kv: PACK_DEFS[kv[0]]["price"] if kv[0] in PACK_DEFS else 0, reverse=True):
            if sales_capacity <= 0:
                break
            if qty <= 0:
                continue
            sell_units = min(qty, sales_capacity)
            pack = await get_pack_def(bot.db, ptype)
            if not pack:
                continue
            margin = 0.2
            profit_per = int(pack["price"] * margin)
            total_sales_profit += profit_per * sell_units
            await change_store_stock(bot.db, interaction.user.id, ptype, -sell_units)
            total_sold[ptype] = sell_units
            sales_capacity -= sell_units

    total_gain = base + total_sales_profit
    await adjust_wallet(bot.db, interaction.user.id, total_gain)
    await add_profit(bot.db, interaction.user.id, total_gain)
    await set_last_daily(bot.db, interaction.user.id)
    await bot.db.commit()

    sold_str = ", ".join(f"{k}x{v}" for k, v in total_sold.items()) if total_sold else "No sales"
    await interaction.followup.send(f"Daily claimed! +{base} bonus. Store sales: {sold_str} → +{total_sales_profit}. Total +{total_gain}.")

@bot.tree.command(description="Trade cards with another player")
@app_commands.describe(user="The user to trade with")
async def trade(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer()
    if user.bot or user.id == interaction.user.id:
        await interaction.followup.send("Choose a valid trading partner.", ephemeral=True)
        return
    u1 = await get_user(bot.db, interaction.user.id)
    u2 = await get_user(bot.db, user.id)
    if not u1 or not u2:
        await interaction.followup.send("Both players need to /start first.", ephemeral=True)
        return
    state = TradeState(interaction.user.id, user.id)
    view = TradeView(bot, state)
    embed = view._summary()
    msg = await interaction.channel.send(content=f"Trade session started: <@{interaction.user.id}> ↔ <@{user.id}>", embed=embed, view=view)
    view.msg = msg

@bot.tree.command(description="Gift a card or pack to someone")
@app_commands.describe(user="Recipient", item="card:<InvID> or pack:<type>[:qty]")
async def gift(interaction: discord.Interaction, user: discord.User, item: str):
    await interaction.response.defer(ephemeral=True)
    if user.bot or user.id == interaction.user.id:
        await interaction.followup.send("Choose a valid recipient.", ephemeral=True)
        return
    giver = await get_user(bot.db, interaction.user.id)
    receiver = await get_user(bot.db, user.id)
    if not giver or not receiver:
        await interaction.followup.send("Both players need to /start first.", ephemeral=True)
        return
    item = item.strip().lower()
    if item.startswith("card:"):
        inv_id = item.split("card:", 1)[1].strip().upper()
        inv = await get_inventory_item(bot.db, interaction.user.id, inv_id)
        if not inv:
            await interaction.followup.send("Card not found or not yours.", ephemeral=True)
            return
        if inv["locked"]:
            await interaction.followup.send("That card is locked.", ephemeral=True)
            return
        await bot.db.execute("UPDATE inventory SET user_id = ? WHERE inventory_id = ?", (user.id, inv_id))
        await bot.db.commit()
        await interaction.followup.send(f"Gave card `{inv_id}` to {user.mention}.", ephemeral=True)
    elif item.startswith("pack:"):
        rest = item.split("pack:", 1)[1]
        parts = rest.split(":")
        ptype = parts[0].strip()
        qty = 1
        if len(parts) > 1:
            try:
                qty = max(1, int(parts[1]))
            except:
                qty = 1
        bot.db.row_factory = aiosqlite.Row
        async with bot.db.execute("SELECT id FROM owned_packs WHERE user_id = ? AND pack_type = ? LIMIT ?", (interaction.user.id, ptype, qty)) as c:
            pack_rows = await c.fetchall()
        if len(pack_rows) < qty:
            await interaction.followup.send("You don't have enough owned packs of that type.", ephemeral=True)
            return
        ids = [r["id"] for r in pack_rows]
        await bot.db.execute(
            "DELETE FROM owned_packs WHERE id IN (%s)" % ",".join("?"*len(ids)),
            (*ids,)
        )
        for _ in range(qty):
            await give_owned_pack(bot.db, user.id, ptype)
        await bot.db.commit()
        await interaction.followup.send(f"Gave {qty}x {ptype} pack(s) to {user.mention}.", ephemeral=True)
    else:
        await interaction.followup.send("Invalid item format. Use card:<InvID> or pack:<type>[:qty].", ephemeral=True)

@bot.tree.command(description="Show your thematic collection progress")
async def collection(interaction: discord.Interaction):
    await interaction.response.defer()
    user = await get_user(bot.db, interaction.user.id)
    if not user:
        await interaction.followup.send("Use /start first.", ephemeral=True)
        return
    bot.db.row_factory = aiosqlite.Row
    async with bot.db.execute("SELECT DISTINCT collection FROM cards") as c:
        collections = [r[0] for r in await c.fetchall()]
    desc_lines = []
    for coll in collections:
        async with bot.db.execute(
            """
            SELECT COUNT(DISTINCT c.card_id) FROM inventory inv
            JOIN cards c ON c.card_id = inv.card_id
            WHERE inv.user_id = ? AND c.collection = ?
            """,
            (interaction.user.id, coll)
        ) as c:
            have_row = await c.fetchone()
        async with bot.db.execute("SELECT COUNT(*) FROM cards WHERE collection = ?", (coll,)) as c:
            total_row = await c.fetchone()
        have = int(have_row[0] or 0)
        total = int(total_row[0] or 0)
        pct = 0 if total == 0 else int(have * 100 / total)
        bars = "█" * (pct // 10) + "░" * (10 - pct // 10)
        desc_lines.append(f"{coll}: [{bars}] {have}/{total} ({pct}%)")
    embed = discord.Embed(title="🗂️ Collection Progress", description="\n".join(desc_lines) or "No cards yet.", color=0x95A5A6)
    await interaction.followup.send(embed=embed)

@bot.tree.command(description="Open the global marketplace")
async def market(interaction: discord.Interaction):
    await interaction.response.defer()
    view = MarketView(bot, interaction.user.id)
    bot.db.row_factory = aiosqlite.Row
    async with bot.db.execute("SELECT * FROM marketplace WHERE status = 'active' ORDER BY listing_id DESC LIMIT 20") as c:
        rows = await c.fetchall()
    embed = view._render_embed(rows)
    msg = await interaction.followup.send(embed=embed, view=view)
    view.message = msg

@bot.tree.command(description="Show pack info (odds, contents)")
@app_commands.describe(type="Pack type to inspect")
async def packinfo(interaction: discord.Interaction, type: str):
    await interaction.response.defer()
    pack = await get_pack_def(bot.db, type.lower())
    if not pack:
        await interaction.followup.send("Unknown pack type.", ephemeral=True)
        return
    odds = pack["drops"]
    odds_str = "\n".join(f"{rarity_emoji(r)} {r}: {pct}%" for r, pct in odds.items())
    bot.db.row_factory = aiosqlite.Row
    sample_lines = []
    for r in ["Legendary", "Epic", "Rare", "Uncommon", "Common"]:
        async with bot.db.execute("SELECT name FROM cards WHERE rarity = ? AND (? OR collection != 'Halloween') LIMIT 5",
                                  (r, 1 if is_october() else 0)) as c:
            rows = await c.fetchall()
        names = ", ".join([rw[0] for rw in rows]) or "—"
        sample_lines.append(f"{rarity_emoji(r)} {r}: {names}")
    embed = discord.Embed(
        title=f"📦 {pack['name']}",
        description=f"Price: {pack['price']} • Cards: {pack['min_cards']}-{pack['max_cards']}\n\nOdds:\n{odds_str}\n\nExamples:\n" + "\n".join(sample_lines),
        color=0xF39C12
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(description="Show current events")
async def event(interaction: discord.Interaction):
    await interaction.response.defer()
    if is_october():
        embed = discord.Embed(
            title="🎃 Halloween Pack Event",
            description="Limited-time Halloween Pack available! Exclusive cards in the 'Halloween' collection are in rotation.\nUse /buy pack halloween and /packinfo halloween.",
            color=0xE67E22
        )
    else:
        embed = discord.Embed(
            title="📅 No active event",
            description="Check back later for seasonal events!",
            color=0x95A5A6
        )
    await interaction.followup.send(embed=embed)

SUPPORT_SERVER_URL = os.getenv("SUPPORT_SERVER_URL", "https://discord.gg/bwG2jS7Xhn")

INVITE_PERMISSIONS = discord.Permissions()
INVITE_PERMISSIONS.update(
    view_channel=True,
    send_messages=True,
    embed_links=True,
    read_message_history=True
)

class SupportView(discord.ui.View):
    def __init__(self, invite_url: str, support_url: Optional[str], timeout: float = 120):
        super().__init__(timeout=timeout)
        self.add_item(discord.ui.Button(
            label="Invite Bot",
            style=discord.ButtonStyle.link,
            url=invite_url,
            emoji="🤖"
        ))
        if support_url and support_url.startswith("http"):
            self.add_item(discord.ui.Button(
                label="Server Support",
                style=discord.ButtonStyle.link,
                url=support_url,
                emoji="🛠️"
            ))

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

@bot.tree.command(name="help", description="Show bot commands and tips")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    embed = discord.Embed(
        title="📖 Help — Collection Simulator",
        description="Quick overview of commands. Use /support for invite & support server.",
        color=0x5865F2
    )

    embed.add_field(
        name="🎒 Basic",
        value="\n".join([
            "/start — Create your account and shop",
            "/profile — Shop level, wallet, packs, rare+",
            "/inventory — View your cards (with IDs)",
            "/openpack — Open a pack with animation",
            "/buy pack <type> — Buy a pack",
            "/sell <card> — Sell a card by inventory ID",
            "/shop upgrade — Upgrade your shop",
            "/leaderboard — Top shops by value",
            "/packinfo <type> — Pack odds & sample cards",
        ]),
        inline=False
    )

    embed.add_field(
        name="🏪 Tycoon / Economy",
        value="\n".join([
            "/buy shelf — More shelves + capacity",
            "/buy stock — Buy packs for store stock",
            "/daily — Claim bonus + NPC store sales",
            "/trade @user — Trade with another player",
            "/event — Current events (e.g., Halloween 🎃)",
        ]),
        inline=False
    )

    embed.add_field(
        name="💎 Additional / Interactive",
        value="\n".join([
            "/gift @user <item> — Gift card:<ID> or pack:<type>[:qty]",
            "/collection — Collection progress",
            "/market — Global marketplace",
            "/support — Invite link + support server",
        ]),
        inline=False
    )

    embed.set_footer(text="Tip: Use autocomplete in /sell to find your card IDs quickly.")
    await interaction.followup.send(embed=embed, ephemeral=False)


@bot.tree.command(name="support", description="Invite the bot and get the support server link")
async def support_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    invite_url = discord.utils.oauth_url(
        bot.user.id,
        permissions=INVITE_PERMISSIONS,
        scopes=("bot", "applications.commands")
    )
    support_url = SUPPORT_SERVER_URL if SUPPORT_SERVER_URL and SUPPORT_SERVER_URL.startswith("http") else None

    embed = discord.Embed(
        title="🆘 Support",
        description="Need help or want to invite the bot to another server? Use the buttons below.",
        color=0x5865F2
    )
    if not support_url:
        embed.set_footer(text="Owner: set SUPPORT_SERVER_URL in your .env to enable the Support Server button.")

    view = SupportView(invite_url, support_url)
    msg = await interaction.followup.send(embed=embed, view=view, ephemeral=False)
    view.message = msg 

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    try:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)
    except:
        await interaction.followup.send(f"Error: {error}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Slash commands synced.")

if __name__ == "__main__":
    if not TOKEN:
        print("Missing DISCORD_TOKEN in .env")
        raise SystemExit(1)

    bot.run(TOKEN)

