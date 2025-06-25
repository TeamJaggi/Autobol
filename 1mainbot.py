import json
import logging
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatAdminRequired, PeerIdInvalid

# User account credentials (get from my.telegram.org)
API_ID = 28093492  # Your API ID
API_HASH = "2d18ff97ebdfc2f1f3a2596c48e3b4e4" # Your API Hash
SESSION_STRING = "BQGsrDQAU_-Qo51cnaQIYNyYgnuKCmUTcr-TZ_NclAv_7mv85esTZzlziNBqzeSSPBc_5cvTzWEkILE3MsVOJrouxIC5nnexy1MP7adAnmLlN6LHJu_-chDT289Y5xuedc1EG8jAODLKDCkglVIi1tTwBp8-QfgBCFqW-n5JwCt-_YyjXDC8AERccJbl5ZDYyXCyToGLq9Fn0fYd4U2pF1vPrCqZNcYydd3keRjoPmXBiYMuLtsZIWuPUyBn8lqH7oJ89CbOFVtjw97zfxbYkRxkvGQgmdCum-yWOWV1ZPyje_NqiYQlHNjInDSjxwto4q9exdmCB3u6inStGg0-ryyxwDCgQwAAAAHV1YXKAA" # Your session string
CONFIG_FILE = "config.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate credentials
if not API_ID or not API_HASH:
    raise ValueError("API_ID and API_HASH environment variables must be set")

if not SESSION_STRING:
    raise ValueError("SESSION_STRING environment variable must be set")

# Initialize client with session string
app = Client(
    name="auto_forwarder",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info("Config file not found, creating new one")
        default_config = {
            "source_channels": [],  # Channels to monitor
            "target_channels": [],  # Channels to forward to
            "replacements": {},     # Text replacements
            "forwarded_messages": set(),  # Track forwarded messages (prevent duplicates)
            "admin_chat": None      # Your personal chat for bot commands
        }
        save_config(default_config)
        return default_config
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config file")
        return {
            "source_channels": [],
            "target_channels": [],
            "replacements": {},
            "forwarded_messages": set(),
            "admin_chat": None
        }


def save_config(data):
    try:
        # Convert set to list for JSON serialization
        if "forwarded_messages" in data and isinstance(data["forwarded_messages"], set):
            data["forwarded_messages"] = list(data["forwarded_messages"])
        
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Config saved successfully")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


async def get_entity_info(client, identifier):
    """Get chat information from username or ID"""
    try:
        if isinstance(identifier, str) and identifier.startswith('-100'):
            # Channel ID format
            chat_id = int(identifier)
        elif isinstance(identifier, str) and identifier.startswith('@'):
            # Username format
            chat_id = identifier
        else:
            # Try as integer
            chat_id = int(identifier) if str(identifier).lstrip('-').isdigit() else identifier
        
        chat = await client.get_chat(chat_id)
        return chat
    except Exception as e:
        logger.error(f"Failed to get entity info for {identifier}: {e}")
        return None


@app.on_message(filters.command("add") & filters.private)
async def add_channel(client, message: Message):
    """Add source or target channel"""
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply_text(
            "Usage: /add source|target @channel_username OR channel_id\n"
            "Example: /add source @TechNews\n"
            "Example: /add target -1001234567890"
        )
        return

    mode, channel = parts[1], parts[2]
    
    if mode not in ["source", "target"]:
        await message.reply_text("Invalid mode. Use 'source' or 'target'.")
        return

    # Get chat info
    chat = await get_entity_info(client, channel)
    if not chat:
        await message.reply_text(f"❌ Cannot access channel: {channel}")
        return

    data = load_config()
    key = f"{mode}_channels"
    
    channel_id = str(chat.id)
    
    if mode == "target":
        # Check if we can send messages to target
        try:
            await client.send_message(chat.id, "✅ Test message - bot access confirmed")
            await asyncio.sleep(1)
        except ChatAdminRequired:
            await message.reply_text(f"❌ No permission to send messages in {chat.title}")
            return
        except Exception as e:
            await message.reply_text(f"❌ Cannot send to {chat.title}: {str(e)}")
            return
    
    if channel_id not in data[key]:
        data[key].append(channel_id)
        save_config(data)
        await message.reply_text(
            f"✅ Added {chat.title} to {mode} channels\n"
            f"ID: {channel_id}\n"
            f"Type: {chat.type}"
        )
        logger.info(f"Added {chat.title} ({channel_id}) to {mode} channels")
    else:
        await message.reply_text("❌ Channel already added.")


@app.on_message(filters.command("remove") & filters.private)
async def remove_channel(client, message: Message):
    """Remove source or target channel"""
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply_text("Usage: /remove source|target @channel_username OR channel_id")
        return

    mode, channel = parts[1], parts[2]
    
    if mode not in ["source", "target"]:
        await message.reply_text("Invalid mode. Use 'source' or 'target'.")
        return

    # Get chat info to find the correct ID
    chat = await get_entity_info(client, channel)
    if chat:
        channel_id = str(chat.id)
    else:
        channel_id = channel  # Use as-is if we can't resolve

    data = load_config()
    key = f"{mode}_channels"

    if channel_id in data[key]:
        data[key].remove(channel_id)
        save_config(data)
        await message.reply_text(f"✅ Removed channel from {mode} channels.")
        logger.info(f"Removed {channel_id} from {mode} channels")
    else:
        await message.reply_text("❌ Channel not found.")


@app.on_message(filters.command("list") & filters.private)
async def list_channels(client, message: Message):
    """List all configured channels"""
    data = load_config()
    
    text = "📋 **Current Configuration:**\n\n"
    
    # Source channels
    text += f"**Source Channels ({len(data['source_channels'])}):**\n"
    for channel_id in data['source_channels']:
        chat = await get_entity_info(client, channel_id)
        if chat:
            text += f"• {chat.title} (`{channel_id}`)\n"
        else:
            text += f"• Unknown (`{channel_id}`) ❌\n"
    
    # Target channels
    text += f"\n**Target Channels ({len(data['target_channels'])}):**\n"
    for channel_id in data['target_channels']:
        chat = await get_entity_info(client, channel_id)
        if chat:
            text += f"• {chat.title} (`{channel_id}`)\n"
        else:
            text += f"• Unknown (`{channel_id}`) ❌\n"
    
    # Replacements
    text += f"\n**Replacement Rules ({len(data['replacements'])}):**\n"
    for old, new in data['replacements'].items():
        text += f"• `{old}` → `{new}`\n"
    
    if not data['source_channels'] and not data['target_channels']:
        text += "\n❌ No channels configured yet."
    
    await message.reply_text(text)


@app.on_message(filters.command("addreplace") & filters.private)
async def add_replacement(client, message: Message):
    """Add text replacement rule"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text("Usage: /addreplace old_text new_text")
        return

    old, new = parts[1], parts[2]
    
    data = load_config()
    data["replacements"][old] = new
    save_config(data)
    
    await message.reply_text(f"✅ Replacement rule added:\n`{old}` → `{new}`")
    logger.info(f"Added replacement rule: {old} → {new}")


@app.on_message(filters.command("removereplace") & filters.private)
async def remove_replacement(client, message: Message):
    """Remove text replacement rule"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply_text("Usage: /removereplace old_text")
        return

    old = parts[1]
    data = load_config()
    
    if old in data["replacements"]:
        del data["replacements"][old]
        save_config(data)
        await message.reply_text(f"✅ Removed replacement rule: `{old}`")
        logger.info(f"Removed replacement rule: {old}")
    else:
        await message.reply_text("❌ Rule not found.")


@app.on_message(filters.command("status") & filters.private)
async def status(client, message: Message):
    """Show bot status"""
    data = load_config()
    
    text = "🤖 **Forwarder Status:**\n\n"
    
    # Check source channels
    text += "**Source Channels:**\n"
    for channel_id in data['source_channels']:
        try:
            chat = await client.get_chat(int(channel_id))
            text += f"✅ {chat.title}\n"
        except Exception as e:
            text += f"❌ {channel_id} - Error: {str(e)[:30]}...\n"
    
    # Check target channels
    text += "\n**Target Channels:**\n"
    for channel_id in data['target_channels']:
        try:
            chat = await client.get_chat(int(channel_id))
            text += f"✅ {chat.title}\n"
        except Exception as e:
            text += f"❌ {channel_id} - Error: {str(e)[:30]}...\n"
    
    text += f"\n**Statistics:**\n"
    text += f"• Messages forwarded: {len(data.get('forwarded_messages', []))}\n"
    text += f"• Active replacements: {len(data['replacements'])}\n"
    
    await message.reply_text(text)


@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message: Message):
    """Show help"""
    help_text = """
🤖 **Telegram User Auto-Forwarder**

**Commands:**
• `/add source @channel` - Add source channel to monitor
• `/add target @channel` - Add target channel for forwarding
• `/remove source @channel` - Remove source channel
• `/remove target @channel` - Remove target channel
• `/list` - Show all configured channels
• `/addreplace old new` - Add text replacement rule
• `/removereplace old` - Remove replacement rule
• `/status` - Show forwarder status
• `/help` - Show this help

**Features:**
✅ Monitor ANY public channel (no need to join)
✅ Forward to any channel you have access to
✅ Text replacement/editing
✅ Duplicate message prevention
✅ Support for all message types

**Example Setup:**
```
/add source @TechNews
/add target @MyChannel
/addreplace "BREAKING" "🚨 BREAKING"
```

**Note:** This uses your user account, so it can monitor any public channel without joining!
"""
    
    await message.reply_text(help_text)


@app.on_message(filters.command("getsession") & filters.private)
async def get_session_string(client, message: Message):
    """Get current session string (for backup purposes)"""
    try:
        session_string = await client.export_session_string()
        await message.reply_text(
            f"🔐 **Your Session String:**\n\n`{session_string}`\n\n"
            "⚠️ **IMPORTANT:** Keep this session string secure! "
            "Anyone with this string can access your Telegram account."
        )
        logger.info("Session string exported successfully")
    except Exception as e:
        await message.reply_text(f"❌ Failed to export session string: {str(e)}")
        logger.error(f"Failed to export session string: {e}")


@app.on_message(filters.channel)
async def handle_channel_message(client, message: Message):
    """Handle messages from channels - main forwarding logic"""
    data = load_config()
    
    source_channel_id = str(message.chat.id)
    
    # Check if this channel is being monitored
    if source_channel_id not in data['source_channels']:
        return
    
    # Prevent duplicate forwards
    message_id = f"{source_channel_id}_{message.id}"
    forwarded_messages = set(data.get('forwarded_messages', []))
    
    if message_id in forwarded_messages:
        return
    
    logger.info(f"New message from monitored channel: {message.chat.title}")
    
    # Get message content
    text = message.text or message.caption or ""
    
    # Apply text replacements
    for old, new in data["replacements"].items():
        text = text.replace(old, new)
    
    # Forward to all target channels
    successful_forwards = 0
    failed_forwards = 0
    
    for target_id in data["target_channels"]:
        try:
            target_chat_id = int(target_id)
            
            # Handle different message types
            if message.text:
                await client.send_message(target_chat_id, text)
            elif message.photo:
                await client.send_photo(target_chat_id, message.photo.file_id, caption=text)
            elif message.video:
                await client.send_video(target_chat_id, message.video.file_id, caption=text)
            elif message.document:
                await client.send_document(target_chat_id, message.document.file_id, caption=text)
            elif message.sticker:
                await client.send_sticker(target_chat_id, message.sticker.file_id)
            elif message.audio:
                await client.send_audio(target_chat_id, message.audio.file_id, caption=text)
            elif message.voice:
                await client.send_voice(target_chat_id, message.voice.file_id, caption=text)
            elif message.video_note:
                await client.send_video_note(target_chat_id, message.video_note.file_id)
            elif message.animation:
                await client.send_animation(target_chat_id, message.animation.file_id, caption=text)
            else:
                logger.warning(f"Unsupported message type from {source_channel_id}")
                continue
            
            successful_forwards += 1
            logger.info(f"Successfully forwarded to {target_id}")
            
        except FloodWait as e:
            logger.warning(f"Rate limited, waiting {e.value} seconds")
            await asyncio.sleep(e.value)
            failed_forwards += 1
        except Exception as e:
            failed_forwards += 1
            logger.error(f"Failed to forward to {target_id}: {e}")
    
    # Mark message as forwarded
    if successful_forwards > 0:
        forwarded_messages.add(message_id)
        data['forwarded_messages'] = list(forwarded_messages)
        
        # Keep only last 1000 message IDs to prevent infinite growth
        if len(data['forwarded_messages']) > 1000:
            data['forwarded_messages'] = data['forwarded_messages'][-1000:]
        
        save_config(data)
    
    if successful_forwards > 0 or failed_forwards > 0:
        logger.info(f"Forward summary: {successful_forwards} successful, {failed_forwards} failed")


async def main():
    """Main function"""
    print("🚀 Starting Telegram User Auto-Forwarder...")
    print("📱 This will use your user account to monitor and forward messages")
    print("⚠️  Make sure you have API_ID, API_HASH, and SESSION_STRING set!")
    
    try:
        await app.start()
        print("✅ Successfully logged in with session string!")
        
        # Get user info
        me = await app.get_me()
        print(f"👤 Logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'no_username'})")
        print("💬 Send /help to yourself to see available commands")
        print("🔐 Send /getsession to get your current session string for backup")
        print("🔄 Auto-forwarding is now active!")
        
        # Keep the client running
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        print(f"❌ Error: {e}")
        print("\n💡 If you're getting authentication errors:")
        print("1. Make sure your SESSION_STRING is valid and not expired")
        print("2. If you don't have a session string, run the script once without it to generate one")
        print("3. Use /getsession command to backup your session string")
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
