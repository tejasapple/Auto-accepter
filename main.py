import os
import asyncio
from datetime import datetime
from pyrogram import Client, filters, enums
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
# 🎨 COLOR BUTTONS HELPER FUNCTION
# ==========================================
def get_color_btn(text, url=None, callback_data=None, style="primary"):
    """
    Simulates Color Buttons feature for Pyrogram.
    Uses Emoji indicators to maintain premium UI.
    """
    style = style.lower()
    if style in ["success", "green", "paid"]:
        text = f"🟢 {text}"
    elif style in ["danger", "red", "delete", "disable"]:
        text = f"🔴 {text}"
    elif style in ["default", "gray", "grey", "cancel"]:
        text = f"⚪ {text}"
    else: # primary
        text = f"🔵 {text}"

    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=callback_data)


# ==========================================
# 🚀 START COMMAND
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    bot_info = await client.get_me()
    bot_username = bot_info.username
    
    admin_rights = "invite_users+manage_chat+restrict_members+promote_members+change_info+post_messages+edit_messages+delete_messages"
    
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("➕ Add to your Group", url=f"https://t.me/{bot_username}?startgroup=true&admin={admin_rights}", style="success")],
        [get_color_btn("📢 Add to your Channel", url=f"https://t.me/{bot_username}?startchannel=true&admin={admin_rights}", style="primary")]
    ])
    
    text = (
        f"<blockquote>👋 <b>WELCOME TO AUTO ACCEPT BOT</b></blockquote>\n\n"
        f"Hello <b>{message.from_user.first_name}</b>!\n\n"
        f"I am a lightning-fast Auto-Accept Bot. Add me to your Channel or Group as an Admin to automatically accept join requests securely.\n\n"
        f"<i>⚠️ Note: Please make sure 'Remain Anonymous' permission is turned OFF.</i>"
    )
    
    today = datetime.now().strftime("%Y-%m-%d")
    await users_col.update_one(
        {"user_id": message.from_user.id}, 
        {"$set": {"name": message.from_user.first_name}, "$setOnInsert": {"date": today}}, 
        upsert=True
    )
    
    await message.reply_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

# ==========================================
# 🛡️ AUTO ACCEPT & VERIFICATION DM
# ==========================================
@app.on_chat_join_request()
async def auto_accept_requests(client, request: ChatJoinRequest):
    chat = request.chat
    user = request.from_user
    
    text = (
        f"<blockquote>⚠️ <b>Security Verification Required</b></blockquote>\n\n"
        f"Hello <b>{user.first_name}</b>,\n\n"
        f"This is to prevent our group from bans and spam bots. "
        f"Please confirm your identity by clicking the button below to be accepted into <b>{chat.title}</b>."
    )
    
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("🤖 I am not a robot (Verify)", callback_data=f"verify_{chat.id}", style="success")]
    ])
    
    try:
        await client.send_message(chat_id=user.id, text=text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await client.send_message(chat_id=user.id, text=text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
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
    
    # Show Pop-up Alert
    await query.answer("✅ Identity Confirmed! Thanks for verification.", show_alert=True)
    
    try:
        # Approve Request
        await client.approve_chat_join_request(chat_id=chat_id, user_id=user.id)
        
        # Save User and Group to Database
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

        # Edit DM to Premium Welcome Message
        welcome_text = (
            f"<blockquote>🎉 <b>ACCESS GRANTED</b></blockquote>\n\n"
            f"Welcome to <b>{chat_title}</b>, <b>{user.first_name}</b>!\n\n"
            f"Your request has been successfully approved by our Auto-Verification System. You can now access the content."
        )
        await query.message.edit_text(welcome_text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        print(f"Error approving {user.id}: {e}")

# ==========================================
# ⚙️ ADVANCED ADMIN PANEL DASHBOARD
# ==========================================
@app.on_message(filters.command("admin") & filters.user(ADMIN_ID) & filters.private)
async def admin_dashboard(client, message):
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("📊 View Bot Live Stats", callback_data="admin_stats", style="primary")],
        [get_color_btn("👤 Broadcast to Users (DM)", callback_data="bcast_users", style="success")],
        [get_color_btn("👥 Broadcast to Groups/Channels", callback_data="bcast_chats", style="danger")]
    ])
    
    text = (
        f"<blockquote>⚙️ <b>ADVANCED ADMIN PANEL</b></blockquote>\n\n"
        f"Welcome to the Enterprise Admin Dashboard. Manage your bot's statistics and broadcast systems directly from here."
    )
    await message.reply_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

# ==========================================
# 📊 ADMIN CALLBACK: LIVE STATS
# ==========================================
@app.on_callback_query(filters.regex(r"^admin_stats$") & filters.user(ADMIN_ID))
async def show_live_stats(client, query):
    today = datetime.now().strftime("%Y-%m-%d")
    
    total_users = await users_col.count_documents({})
    today_users = await users_col.count_documents({"date": today})
    
    total_chats = await chats_col.count_documents({})
    today_chats = await chats_col.count_documents({"date": today})
    
    text = (
        f"<blockquote>📊 <b>DATABASE LIVE STATISTICS</b></blockquote>\n\n"
        f"👤 <b>Total Verified Users:</b> <code>{total_users}</code>\n"
        f"🆕 <b>Today's New Users:</b> <code>{today_users}</code>\n\n"
        f"👥 <b>Total Active Groups/Channels:</b> <code>{total_chats}</code>\n"
        f"🆕 <b>Today's New Groups/Channels:</b> <code>{today_chats}</code>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("🔙 Back to Admin Panel", callback_data="back_to_admin", style="default")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex(r"^back_to_admin$") & filters.user(ADMIN_ID))
async def back_to_admin_panel(client, query):
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("📊 View Bot Live Stats", callback_data="admin_stats", style="primary")],
        [get_color_btn("👤 Broadcast to Users (DM)", callback_data="bcast_users", style="success")],
        [get_color_btn("👥 Broadcast to Groups/Channels", callback_data="bcast_chats", style="danger")]
    ])
    text = (
        f"<blockquote>⚙️ <b>ADVANCED ADMIN PANEL</b></blockquote>\n\n"
        f"Welcome to the Enterprise Admin Dashboard. Manage your bot's statistics and broadcast systems directly from here."
    )
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

# ==========================================
# 📢 ADMIN PANEL: BROADCAST STATE MACHINE
# ==========================================
@app.on_callback_query(filters.regex(r"^bcast_(users|chats)$") & filters.user(ADMIN_ID))
async def start_bcast_flow(client, query):
    btype = query.matches[0].group(1)
    bcast_state[query.from_user.id] = {
        "type": btype,
        "step": "media",
        "media_type": None,
        "media_id": None,
        "text": None,
        "target_button_count": 0,
        "current_button_index": 0,
        "buttons": [],
        "temp_name": "",
        "temp_url": ""
    }
    
    target_name = "Verified Users (DM)" if btype == "users" else "Groups & Channels"
    
    text = (
        f"<blockquote>📢 <b>BROADCAST WIZARD</b></blockquote>\n\n"
        f"<b>Target:</b> {target_name}\n\n"
        f"<b>Step 1:</b> Send a <b>Photo</b> or <b>Video</b> for the broadcast.\n\n"
        f"<i>(Type /skip if you only want to send a text message)</i>"
    )
    await query.message.edit_text(text, parse_mode=enums.ParseMode.HTML)

@app.on_message(filters.command("cancel") & filters.user(ADMIN_ID) & filters.private)
async def cancel_bcast(client, message):
    if message.from_user.id in bcast_state:
        del bcast_state[message.from_user.id]
        await message.reply_text("❌ <b>Broadcast Process Cancelled Successfully.</b>", parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text("You don't have any active broadcast setup running.")

# Main Broadcast Step Handler
@app.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["start", "admin", "stats", "cancel", "confirm"]))
async def process_broadcast_steps(client, message):
    uid = message.from_user.id
    if uid not in bcast_state:
        return
    
    state = bcast_state[uid]
    step = state["step"]
    
    if step == "media":
        if message.text == "/skip":
            state["step"] = "text"
            await message.reply_text("⏭ <b>Media Skipped.</b>\n\n<b>Step 2:</b> Now send the <b>Text Message</b>.\n<i>(Type /skip to skip text)</i>", parse_mode=enums.ParseMode.HTML)
        elif message.photo:
            state["media_type"] = "photo"
            state["media_id"] = message.photo.file_id
            state["step"] = "text"
            await message.reply_text("✅ <b>Photo Saved.</b>\n\n<b>Step 2:</b> Now send the <b>Text Message</b>.\n<i>(Type /skip to skip text)</i>", parse_mode=enums.ParseMode.HTML)
        elif message.video:
            state["media_type"] = "video"
            state["media_id"] = message.video.file_id
            state["step"] = "text"
            await message.reply_text("✅ <b>Video Saved.</b>\n\n<b>Step 2:</b> Now send the <b>Text Message</b>.\n<i>(Type /skip to skip text)</i>", parse_mode=enums.ParseMode.HTML)
        else:
            await message.reply_text("⚠️ Please send a Photo, Video or type /skip.")
            
    elif step == "text":
        if message.text == "/skip":
            if not state["media_id"]:
                return await message.reply_text("⚠️ You cannot skip both Media and Text! Please send text.")
            state["step"] = "btn_count"
            await message.reply_text("⏭ <b>Text Skipped.</b>\n\n<b>Step 3:</b> How many Inline Buttons do you want? (Send a number like 0, 1, 2, etc.)", parse_mode=enums.ParseMode.HTML)
        else:
            state["text"] = message.text or message.caption
            state["step"] = "btn_count"
            await message.reply_text("✅ <b>Text Saved.</b>\n\n<b>Step 3:</b> How many Inline Buttons do you want? (Send a number like 0, 1, 2, etc.)", parse_mode=enums.ParseMode.HTML)
            
    elif step == "btn_count":
        try:
            count = int(message.text.strip())
        except ValueError:
            return await message.reply_text("⚠️ Please send a valid number.")
            
        if count == 0:
            state["step"] = "confirm"
            await message.reply_text("✅ <b>No buttons selected.</b>\n\nAll set! Type <b>/confirm</b> to start the broadcast or <b>/cancel</b> to abort.", parse_mode=enums.ParseMode.HTML)
        else:
            state["target_button_count"] = count
            state["current_button_index"] = 0
            state["step"] = "btn_name"
            await message.reply_text(f"📝 <b>Configuring Button 1:</b>\n\nPlease send the <b>Name (Text)</b> for this button.", parse_mode=enums.ParseMode.HTML)
            
    elif step == "btn_name":
        state["temp_name"] = message.text
        state["step"] = "btn_url"
        await message.reply_text(f"✅ <b>Name Saved.</b>\n\nNow send the <b>URL (Link)</b> for this button (must start with http/https).", parse_mode=enums.ParseMode.HTML)
        
    elif step == "btn_url":
        if not message.text.startswith("http"):
            return await message.reply_text("⚠️ Invalid Link! Please send a valid link starting with http:// or https://")
            
        state["temp_url"] = message.text
        state["step"] = "btn_color"
        
        # Color Selection Keyboard
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 Success (Green)", callback_data="setcol_success"), InlineKeyboardButton("🔴 Danger (Red)", callback_data="setcol_danger")],
            [InlineKeyboardButton("🔵 Primary (Blue)", callback_data="setcol_primary"), InlineKeyboardButton("⚪ Default (Gray)", callback_data="setcol_default")]
        ])
        await message.reply_text("🎨 <b>Select Button Color:</b>\n\nChoose a color for this button from the menu below:", reply_markup=kb, parse_mode=enums.ParseMode.HTML)

# Handle Color Selection Callback
@app.on_callback_query(filters.regex(r"^setcol_(success|danger|primary|default)$") & filters.user(ADMIN_ID))
async def handle_button_color(client, query):
    uid = query.from_user.id
    if uid not in bcast_state or bcast_state[uid]["step"] != "btn_color":
        return await query.answer("Session expired or invalid step.", show_alert=True)
        
    color_choice = query.matches[0].group(1)
    state = bcast_state[uid]
    
    # Save the configured button
    state["buttons"].append({
        "name": state["temp_name"],
        "url": state["temp_url"],
        "style": color_choice
    })
    
    state["current_button_index"] += 1
    await query.message.delete()
    
    if state["current_button_index"] < state["target_button_count"]:
        state["step"] = "btn_name"
        next_num = state["current_button_index"] + 1
        await client.send_message(uid, f"✅ <b>Button {next_num-1} Configured!</b>\n\n📝 <b>Configuring Button {next_num}:</b>\nPlease send the <b>Name (Text)</b> for this button.", parse_mode=enums.ParseMode.HTML)
    else:
        state["step"] = "confirm"
        await client.send_message(uid, "✅ <b>All Buttons Configured Successfully!</b>\n\nAll set! Type <b>/confirm</b> to start the broadcast or <b>/cancel</b> to abort.", parse_mode=enums.ParseMode.HTML)

# Final Confirmation Execution
@app.on_message(filters.command("confirm") & filters.user(ADMIN_ID) & filters.private)
async def confirm_bcast(client, message):
    uid = message.from_user.id
    if uid not in bcast_state or bcast_state[uid]["step"] != "confirm":
        return await message.reply_text("⚠️ No broadcast is waiting for confirmation.")
        
    state = bcast_state[uid]
    await message.reply_text("🚀 <b>Broadcast Starting... Please wait.</b>", parse_mode=enums.ParseMode.HTML)
    
    # Offload execution so it doesn't block
    asyncio.create_task(execute_broadcast(client, uid, state))
    del bcast_state[uid]

async def execute_broadcast(client, admin_id, state):
    btype = state["type"]
    
    if btype == "users":
        targets = await users_col.find({}).to_list(length=None)
        id_key = "user_id"
    else:
        targets = await chats_col.find({}).to_list(length=None)
        id_key = "chat_id"
        
    success, failed = 0, 0
    
    # Build Keyboard dynamically using our Color helper
    inline_buttons = []
    for btn in state["buttons"]:
        # Creating one button per row for clean UI, you can adjust to multiple per row if needed
        inline_buttons.append([get_color_btn(btn["name"], url=btn["url"], style=btn["style"])])
        
    kb = InlineKeyboardMarkup(inline_buttons) if inline_buttons else None
        
    for target in targets:
        tid = target[id_key]
        try:
            if state["media_type"] == "photo":
                await client.send_photo(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            elif state["media_type"] == "video":
                await client.send_video(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            else:
                await client.send_message(tid, state["text"], reply_markup=kb, parse_mode=enums.ParseMode.HTML)
            
            success += 1
            await asyncio.sleep(0.1) # Safe delay to avoid Telegram Flood Limits
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            failed += 1
            # Clean dead users/groups from Database automatically
            if btype == "users":
                await users_col.delete_one({"user_id": tid})
            else:
                await chats_col.delete_one({"chat_id": tid})
                
    await client.send_message(
        admin_id, 
        f"<blockquote>✅ <b>BROADCAST COMPLETED</b></blockquote>\n\n"
        f"🎯 <b>Successfully Sent:</b> <code>{success}</code>\n"
        f"🚫 <b>Failed (Blocked/Removed):</b> <code>{failed}</code>",
        parse_mode=enums.ParseMode.HTML
    )

# ==========================================
# 🏃 RUN THE BOT
# ==========================================
if __name__ == "__main__":
    print("Bot is Starting... ✅")
    app.run()
    print("Bot Stopped. ❌")
