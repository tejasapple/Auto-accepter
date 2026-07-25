import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from pyrogram.errors import UserIsBlocked, PeerIdInvalid, FloodWait
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# ⚙️ CONFIGURATION (अपनी डिटेल्स यहाँ डालें)
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

# Broadcast State Manager (Memory)
bcast_state = {}

# ==========================================
# 🚀 START COMMAND
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    bot_info = await client.get_me()
    bot_username = bot_info.username
    
    admin_rights = "invite_users+manage_chat+restrict_members+promote_members+change_info+post_messages+edit_messages+delete_messages"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to your Group", url=f"https://t.me/{bot_username}?startgroup=true&admin={admin_rights}")],
        [InlineKeyboardButton("📢 Add to your Channel", url=f"https://t.me/{bot_username}?startchannel=true&admin={admin_rights}")]
    ])
    
    text = (
        f"**Hello {message.from_user.first_name}! 👋**\n\n"
        f"I am a fast Auto-Accept Bot. Add me to your Channel or Group as an Admin to automatically accept join requests.\n\n"
        f"**Note:** Please make sure 'Remain Anonymous' permission is turned OFF."
    )
    
    today = datetime.now().strftime("%Y-%m-%d")
    await users_col.update_one(
        {"user_id": message.from_user.id}, 
        {"$set": {"name": message.from_user.first_name}, "$setOnInsert": {"date": today}}, 
        upsert=True
    )
    
    await message.reply_text(text, reply_markup=keyboard)

# ==========================================
# 🛡️ AUTO ACCEPT & VERIFICATION DM
# ==========================================
@app.on_chat_join_request()
async def auto_accept_requests(client, request: ChatJoinRequest):
    chat = request.chat
    user = request.from_user
    
    text = (
        f"⚠️ **Verification Required**\n\n"
        f"Hello {user.first_name},\n"
        f"This is to prevent our group from bans and spam. "
        f"Please confirm your identity to be accepted into **{chat.title}**."
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 I am not a robot", callback_data=f"verify_{chat.id}")]
    ])
    
    try:
        await client.send_message(chat_id=user.id, text=text, reply_markup=keyboard)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await client.send_message(chat_id=user.id, text=text, reply_markup=keyboard)
    except Exception as e:
        print(f"Could not send DM to {user.first_name} ({user.id}): {e}")

# ==========================================
# ✅ HANDLE VERIFICATION CALLBACK
# ==========================================
@app.on_callback_query(filters.regex(r"^verify_(\d+)$"))
async def verify_user(client, query):
    chat_id = int(query.matches[0].group(1))
    user = query.from_user
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Show Pop-up Alert
    await query.answer("You are confirmed your identity. Thanks for verification.", show_alert=True)
    
    try:
        # 2. Approve Request
        await client.approve_chat_join_request(chat_id=chat_id, user_id=user.id)
        
        # 3. Save User and Group to Database without duplicates (upsert=True)
        await users_col.update_one(
            {"user_id": user.id}, 
            {"$set": {"name": user.first_name}, "$setOnInsert": {"date": today}}, 
            upsert=True
        )
        
        try:
            chat = await client.get_chat(chat_id)
            chat_title = chat.title
            await chats_col.update_one(
                {"chat_id": chat_id}, 
                {"$set": {"title": chat.title}, "$setOnInsert": {"date": today}}, 
                upsert=True
            )
        except:
            chat_title = "the group"

        # 4. Edit DM to Welcome Message
        welcome_text = f"**Welcome to {chat_title}, {user.first_name}! 🎉**\n\nYour request has been approved and you can now access the content."
        await query.message.edit_text(welcome_text)
        
    except Exception as e:
        print(f"Error approving {user.id}: {e}")

# ==========================================
# 📊 ADMIN PANEL: GET STATS
# ==========================================
@app.on_message(filters.command("stats") & filters.user(ADMIN_ID) & filters.private)
async def get_stats(client, message):
    processing_msg = await message.reply_text("Fetching live stats from database... ⏳")
    
    today = datetime.now().strftime("%Y-%m-%d")
    total_users = await users_col.count_documents({})
    today_users = await users_col.count_documents({"date": today})
    
    total_chats = await chats_col.count_documents({})
    today_chats = await chats_col.count_documents({"date": today})
    
    text = (
        f"**📊 Bot Live Status**\n\n"
        f"👤 **Total Unique Users:** `{total_users}`\n"
        f"🆕 **Today's New Users:** `{today_users}`\n\n"
        f"👥 **Total Active Groups:** `{total_chats}`\n"
        f"🆕 **Today's New Groups:** `{today_chats}`"
    )
    await processing_msg.edit_text(text)

# ==========================================
# 📢 ADMIN PANEL: ADVANCED BROADCAST SYSTEM
# ==========================================
@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.private)
async def start_broadcast(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Personal Broadcast (DM)", callback_data="bcast_users")],
        [InlineKeyboardButton("👥 Group Broadcast", callback_data="bcast_chats")]
    ])
    await message.reply_text("Select where you want to broadcast:", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^bcast_(users|chats)$") & filters.user(ADMIN_ID))
async def bcast_selection(client, query):
    btype = query.matches[0].group(1)
    bcast_state[query.from_user.id] = {
        "type": btype,
        "step": "media",
        "media_type": None,
        "media_id": None,
        "text": None,
        "btn_name": None,
        "btn_url": None
    }
    
    target_name = "Users (DM)" if btype == "users" else "Groups"
    await query.message.edit_text(f"**Target:** {target_name}\n\n**Step 1:** Send Photo or Video.\n\n_(Type /skip if you don't want to send media)_")

@app.on_message(filters.command("cancel") & filters.user(ADMIN_ID) & filters.private)
async def cancel_bcast(client, message):
    if message.from_user.id in bcast_state:
        del bcast_state[message.from_user.id]
        await message.reply_text("❌ Broadcast Cancelled.")
    else:
        await message.reply_text("No active broadcast to cancel.")

@app.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["start", "stats", "broadcast", "cancel"]))
async def process_broadcast_steps(client, message):
    uid = message.from_user.id
    if uid not in bcast_state:
        return
    
    state = bcast_state[uid]
    step = state["step"]
    
    if step == "media":
        if message.text == "/skip":
            state["step"] = "text"
            await message.reply_text("Media Skipped ⏭\n\n**Step 2:** Send Text Message.\n_(Type /skip to skip)_")
        elif message.photo:
            state["media_type"] = "photo"
            state["media_id"] = message.photo.file_id
            state["step"] = "text"
            await message.reply_text("✅ Photo Saved.\n\n**Step 2:** Send Text Message.\n_(Type /skip to skip)_")
        elif message.video:
            state["media_type"] = "video"
            state["media_id"] = message.video.file_id
            state["step"] = "text"
            await message.reply_text("✅ Video Saved.\n\n**Step 2:** Send Text Message.\n_(Type /skip to skip)_")
        else:
            await message.reply_text("⚠️ Please send a Photo, Video or type /skip.")
            
    elif step == "text":
        if message.text == "/skip":
            if not state["media_id"]:
                return await message.reply_text("⚠️ You cannot skip both Media and Text! Please send text.")
            state["step"] = "btn_name"
            await message.reply_text("Text Skipped ⏭\n\n**Step 3:** Send Button Name.\n_(Type /skip to skip buttons)_")
        else:
            state["text"] = message.text or message.caption
            state["step"] = "btn_name"
            await message.reply_text("✅ Text Saved.\n\n**Step 3:** Send Button Name.\n_(Type /skip to skip buttons)_")
            
    elif step == "btn_name":
        if message.text == "/skip":
            state["step"] = "confirm"
            await message.reply_text("Buttons Skipped ⏭\n\n**Type /confirm to start broadcast.**")
        else:
            state["btn_name"] = message.text
            state["step"] = "btn_url"
            await message.reply_text("✅ Button Name Saved.\n\n**Step 4:** Send the Link (URL) for this button.")
            
    elif step == "btn_url":
        if message.text.startswith("http"):
            state["btn_url"] = message.text
            state["step"] = "confirm"
            await message.reply_text("✅ Link Saved.\n\n**Type /confirm to start broadcast.**")
        else:
            await message.reply_text("⚠️ Please send a valid link starting with http:// or https://")
            
    elif step == "confirm":
        if message.text == "/confirm":
            await message.reply_text("🚀 Broadcast Starting...")
            await execute_broadcast(client, uid, state)
            del bcast_state[uid]
        else:
            await message.reply_text("⚠️ Type **/confirm** to start or **/cancel** to abort.")

async def execute_broadcast(client, admin_id, state):
    btype = state["type"]
    
    if btype == "users":
        targets = await users_col.find({}).to_list(length=None)
        id_key = "user_id"
    else:
        targets = await chats_col.find({}).to_list(length=None)
        id_key = "chat_id"
        
    success, failed = 0, 0
    
    kb = None
    if state["btn_name"] and state["btn_url"]:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(state["btn_name"], url=state["btn_url"])]])
        
    for target in targets:
        tid = target[id_key]
        try:
            if state["media_type"] == "photo":
                await client.send_photo(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb)
            elif state["media_type"] == "video":
                await client.send_video(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb)
            else:
                await client.send_message(tid, state["text"], reply_markup=kb)
            
            success += 1
            await asyncio.sleep(0.1) # Safe delay to avoid Telegram Limits
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            failed += 1
            # Clean dead users/groups from Database
            if btype == "users":
                await users_col.delete_one({"user_id": tid})
            else:
                await chats_col.delete_one({"chat_id": tid})
                
    await client.send_message(
        admin_id, 
        f"**✅ Broadcast Completed!**\n\n🎯 Successfully Sent: `{success}`\n🚫 Failed (Blocked/Removed): `{failed}`"
    )

# ==========================================
# 🏃 RUN THE BOT
# ==========================================
if __name__ == "__main__":
    print("Bot is Starting... ✅")
    app.run()
    print("Bot Stopped. ❌")
