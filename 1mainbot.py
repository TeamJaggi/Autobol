import json
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatAdminRequired

# 🔐 Hardcoded credentials
API_ID = 28093492
API_HASH = "2d18ff97ebdfc2f1f3a2596c48e3b4e4"
SESSION_STRING = "BQGsrDQAYbbI2LrPFEd9tyl9cqi_hzNvqamdWVllmio4GIEfO-z1uHpJntmTllHNth65tyOPZgnOTY_v1jzc8bPrplfLcqml8L8nqOwwfCWA3hHTO1WUslvOl7T4cI4c11NfVajrkWj-WxKL21BzGXqG-oBCaIqHUfu4TYjnzgC0oClavaS2c0MyxRjC3dj7vKCGnZj6rnHEy5pXA1McJHxJx1x5v-UlZEss8TuE5T1zXuNp5l1WOKFzI6rR_Oo4sSYGIgL85h6Ic7iuYw69fdtBnpGmTqMtnoCDozSOxQklN7oiBeSU8lw7p5kxY1N_KdIiERfpIPh2qLj0YVQBHr0zulhfxAAAAAHV1YXKAA"

CONFIG_FILE = "config.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Start Pyrogram Client
app = Client(
    name="auto_forwarder",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# Load/save config helpers
def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        default = {
            "source_channels": [],
            "target_channels": [],
            "replacements": {},
            "forwarded_messages": [],
        }
        save_config(default)
        return default

def save_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")

# Get channel or chat entity
async def get_entity_info(client, identifier):
    try:
        return await client.get_chat(identifier)
    except Exception as e:
        logger.error(f"Error getting chat {identifier}: {e}")
        return None

# ✅ /help command (fixed)
@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    print(f"✅ /help command received from: {message.from_user.id}")
    await message.reply_text("""
🤖 *Telegram UserBot Forwarder*

🔧 Commands:
/add source @channel
/add target @channel
/remove source @channel
/remove target @channel
/list — Show all added channels
/addreplace old new — Text replacement
/removereplace old — Remove replacement
/status — Forwarder status

✅ Bot is working!""")

# ✅ /add command
@app.on_message(filters.command("add"))
async def add_channel(client, message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("Use: /add source|target @channel")
        return

    mode, target = parts[1], parts[2]
    if mode not in ["source", "target"]:
        return await message.reply("Use: /add source|target")

    chat = await get_entity_info(client, target)
    if not chat:
        return await message.reply("❌ Invalid channel.")

    config = load_config()
    key = f"{mode}_channels"
    if str(chat.id) not in config[key]:
        config[key].append(str(chat.id))
        save_config(config)
        await message.reply(f"✅ Added {chat.title} to {mode} list.")
    else:
        await message.reply("Already added.")

# ✅ /remove command
@app.on_message(filters.command("remove"))
async def remove_channel(client, message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("Use: /remove source|target @channel")

    mode, target = parts[1], parts[2]
    config = load_config()
    key = f"{mode}_channels"

    chat = await get_entity_info(client, target)
    if chat and str(chat.id) in config[key]:
        config[key].remove(str(chat.id))
        save_config(config)
        await message.reply("✅ Removed.")
    else:
        await message.reply("❌ Not found.")

# ✅ /list command
@app.on_message(filters.command("list"))
async def list_all(client, message: Message):
    config = load_config()
    reply = "**Source Channels:**\n" + "\n".join(config["source_channels"]) or "None"
    reply += "\n\n**Target Channels:**\n" + "\n".join(config["target_channels"]) or "None"
    reply += "\n\n**Replacements:**\n" + "\n".join([f"{k} → {v}" for k, v in config["replacements"].items()]) or "None"
    await message.reply_text(reply)

# ✅ /addreplace command
@app.on_message(filters.command("addreplace"))
async def add_replace(client, message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.reply("Usage: /addreplace old new")

    old, new = parts[1], parts[2]
    config = load_config()
    config["replacements"][old] = new
    save_config(config)
    await message.reply(f"Added replacement: `{old}` → `{new}`")

# ✅ /removereplace command
@app.on_message(filters.command("removereplace"))
async def remove_replace(client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("Usage: /removereplace old")

    old = parts[1]
    config = load_config()
    if old in config["replacements"]:
        del config["replacements"][old]
        save_config(config)
        await message.reply("Removed.")
    else:
        await message.reply("Not found.")

# ✅ /status command
@app.on_message(filters.command("status"))
async def status(client, message: Message):
    config = load_config()
    text = f"📡 Forwarding Active\n\nSources: {len(config['source_channels'])}\nTargets: {len(config['target_channels'])}\nReplacements: {len(config['replacements'])}\nForwarded Msgs: {len(config['forwarded_messages'])}"
    await message.reply(text)

# ✅ Message Forwarder
@app.on_message(filters.channel)
async def forward_handler(client, message: Message):
    config = load_config()
    sid = str(message.chat.id)
    if sid not in config["source_channels"]:
        return

    mid = f"{sid}_{message.id}"
    if mid in config["forwarded_messages"]:
        return

    text = message.text or message.caption or ""
    for old, new in config["replacements"].items():
        text = text.replace(old, new)

    for tid in config["target_channels"]:
        try:
            if message.text:
                await client.send_message(int(tid), text)
            elif message.photo:
                await client.send_photo(int(tid), message.photo.file_id, caption=text)
            elif message.video:
                await client.send_video(int(tid), message.video.file_id, caption=text)
        except Exception as e:
            logger.error(f"Forward failed: {e}")

    config["forwarded_messages"].append(mid)
    if len(config["forwarded_messages"]) > 1000:
        config["forwarded_messages"] = config["forwarded_messages"][-1000:]
    save_config(config)

# 🔁 Run the client
async def main():
    await app.start()
    print("✅ Bot started. Type /help to begin.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
