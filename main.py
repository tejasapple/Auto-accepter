import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, FloodWait
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# ⚙️ CONFIGURATION (आपकी डिटेल्स)
# ==========================================
API_ID = 31660355  
API_HASH = "78292fcf0b3c508b3257e9dda9728df4" 
BOT_TOKEN = "8972078260:AAENtp-9JaIo5ykLuEs9B1er8l6T7WvuEQo" 
MONGO_DB_URI = "mongodb+srv://Tejas7xx:mrxtejas7@cluster0.akhlgjf.mongodb.net/?appName=Cluster0" 
ADMIN_ID = 8884734704  

# ==========================================
# 🗄️ DATABASE SETUP (MongoDB)
# ==========================================
db_client = AsyncIOMotorClient(MONGO_DB_URI)
db = db_client["AutoAcceptBot"]
users_col = db["users"]
chats_col = db["chats"]

app = Client("auto_accept_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🚀 START COMMAND & BUTTONS
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    bot_info = await client.get_me()
    bot_username = bot_info.username
    
    # Permissions for Group (Without Anonymous)
    group_admin_rights = "manage_chat+change_info+delete_messages+restrict_members+invite_users+pin_messages+promote_members+manage_video_chats"
    
    # Permissions for Channel (Without Anonymous)
    channel_admin_rights = "manage_chat+change_info+post_messages+edit_messages+delete_messages+invite_users+promote_members+manage_video_chats"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to your Group", url=f"https://t.me/{bot_username}?startgroup=true&admin={group_admin_rights}")],
        [InlineKeyboardButton("📢 Add to your Channel", url=f"https://t.me/{bot_username}?startchannel=true&admin={channel_admin_rights}")]
    ])
    
    text = (
        f"**Hello {message.from_user.first_name}! 👋**\n\n"
        f"I am a fast Auto-Accept Bot. Add me to your Channel or Group as an Admin to automatically accept join requests.\n\n"
        f"**Note:** Please ensure 'Remain Anonymous' permission is turned OFF."
    )
    
    # Save User to DB (For Broadcast)
    await users_col.update_one(
        {"user_id": message.from_user.id}, 
        {"$set": {"user_id": message.from_user.id, "first_name": message.from_user.first_name}}, 
        upsert=True
    )
    
    await message.reply_text(text, reply_markup=keyboard)


# ==========================================
# ✅ AUTO ACCEPT & WELCOME DM LOGIC
# ==========================================
@app.on_chat_join_request()
async def auto_accept_requests(client, request: ChatJoinRequest):
    chat = request.chat
    user = request.from_user
    
    try:
        # 1. Approve Request
        await client.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
        
        # 2. Save User and Chat to DB for Broadcasting
        await users_col.update_one(
            {"user_id": user.id}, 
            {"$set": {"user_id": user.id, "first_name": user.first_name}}, 
            upsert=True
        )
        await chats_col.update_one(
            {"chat_id": chat.id}, 
            {"$set": {"chat_id": chat.id, "title": chat.title}}, 
            upsert=True
        )
        
        # 3. Send Welcome DM
        try:
            welcome_text = f"**Hello {user.first_name}! 👋**\n\nYour request to join **{chat.title}** has been successfully approved! 🎉"
            await client.send_message(chat_id=user.id, text=welcome_text)
        except UserIsBlocked:
            pass # Ignore if user has blocked the bot
        except PeerIdInvalid:
            pass
        except Exception as e:
            print(f"DM Sending Error for {user.id}: {e}")
            
    except FloodWait as e:
        print(f"FloodWait encountered, sleeping for {e.value} seconds...")
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        print(f"Error accepting request for {user.id} in {chat.id}: {e}")


# ==========================================
# 📊 ADMIN PANEL: GET STATS
# ==========================================
@app.on_message(filters.command("stats") & filters.user(ADMIN_ID) & filters.private)
async def get_stats(client, message):
    processing_msg = await message.reply_text("Fetching live stats from database... ⏳")
    
    total_users = await users_col.count_documents({})
    total_chats = await chats_col.count_documents({})
    
    text = (
        f"**📊 Bot Live Status**\n\n"
        f"👤 **Total Unique Users (DMs):** `{total_users}`\n"
        f"👥 **Total Connected Groups/Channels:** `{total_chats}`"
    )
    await processing_msg.edit_text(text)


# ==========================================
# 📢 ADMIN PANEL: BROADCAST TO USERS (DMs)
# ==========================================
@app.on_message(filters.command("bcast_users") & filters.user(ADMIN_ID) & filters.private)
async def broadcast_to_users(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message with `/bcast_users` to send it to all users in DM.")
    
    bcast_msg = await message.reply_text("Started broadcast to users... ⏳")
    users = await users_col.find({}).to_list(length=None)
    
    success = 0
    failed = 0
    total = len(users)
    
    for user in users:
        try:
            await message.reply_to_message.copy(chat_id=user['user_id'])
            success += 1
            await asyncio.sleep(0.1) # Safe delay to avoid Telegram limits
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            await message.reply_to_message.copy(chat_id=user['user_id'])
            success += 1
        except UserIsBlocked:
            # Remove blocked users to keep DB clean
            await users_col.delete_one({"user_id": user['user_id']})
            failed += 1
        except Exception:
            failed += 1
            
        # Update progress dynamically every 20 messages
        if (success + failed) % 20 == 0:
            await bcast_msg.edit_text(f"**⏳ Broadcasting to Users...**\n\nTotal: `{total}`\nSent: `{success}`\nFailed: `{failed}`")
            
    await bcast_msg.edit_text(f"**✅ User Broadcast Completed!**\n\n🎯 Success: `{success}`\n🚫 Failed (Blocked/Deleted): `{failed}`")


# ==========================================
# 📢 ADMIN PANEL: BROADCAST TO CHATS (Groups/Channels)
# ==========================================
@app.on_message(filters.command("bcast_chats") & filters.user(ADMIN_ID) & filters.private)
async def broadcast_to_chats(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message with `/bcast_chats` to send it to all connected groups & channels.")
    
    bcast_msg = await message.reply_text("Started broadcast to chats... ⏳")
    chats = await chats_col.find({}).to_list(length=None)
    
    success = 0
    failed = 0
    total = len(chats)
    
    for chat in chats:
        try:
            await message.reply_to_message.copy(chat_id=chat['chat_id'])
            success += 1
            await asyncio.sleep(0.1)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
            await message.reply_to_message.copy(chat_id=chat['chat_id'])
            success += 1
        except Exception:
            # Bot might have been removed from the group/channel
            await chats_col.delete_one({"chat_id": chat['chat_id']})
            failed += 1
            
        # Update progress dynamically
        if (success + failed) % 10 == 0:
            await bcast_msg.edit_text(f"**⏳ Broadcasting to Chats...**\n\nTotal: `{total}`\nSent: `{success}`\nFailed: `{failed}`")
            
    await bcast_msg.edit_text(f"**✅ Chat Broadcast Completed!**\n\n🎯 Success: `{success}`\n🚫 Failed (Removed from Chat): `{failed}`")


# ==========================================
# 🏃 RUN THE BOT
# ==========================================
if __name__ == "__main__":
    print("Bot is Starting... ✅")
    app.run()
    print("Bot Stopped. ❌")
