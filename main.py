# pip install motor python-telegram-bot
import os
import asyncio
from datetime import datetime
from typing import Optional

import telegram
from motor.motor_asyncio import AsyncIOMotorClient
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatJoinRequest
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatJoinRequestHandler,
    ContextTypes,
    filters,
)

# ==========================================
# ⚙️ CONFIGURATION (अपनी डिटेल्स यहाँ डालें)
# ==========================================
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

# Broadcast State Manager (Memory)
bcast_state = {}

# ==========================================
# 🎨 COLOR BUTTONS HELPER (PTB api_kwargs)
# ==========================================
def normalize_style(value: str) -> str:
    """Normalizes color string for Telegram inline buttons."""
    value = (value or "").strip().lower()
    if value in {"success", "green", "paid"}:
        return "success"
    if value in {"danger", "red", "delete", "disable"}:
        return "danger"
    if value in {"default", "gray", "grey", "cancel"}:
        return "default"
    return "primary"

def get_color_btn(text: str, callback_data: Optional[str] = None, url: Optional[str] = None, style: str = "primary") -> InlineKeyboardButton:
    """Helper method to generate an InlineKeyboardButton with dynamic color support."""
    kwargs = {"api_kwargs": {"style": normalize_style(style)}}
    if url:
        return InlineKeyboardButton(text=text, url=url, **kwargs)
    return InlineKeyboardButton(text=text, callback_data=callback_data, **kwargs)

# ==========================================
# 🚀 START COMMAND
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = message.from_user
    bot = context.bot
    
    admin_rights = "invite_users+manage_chat+restrict_members+promote_members+change_info+post_messages+edit_messages+delete_messages"
    
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("➕ Add to your Group", url=f"https://t.me/{bot.username}?startgroup=true&admin={admin_rights}", style="success")],
        [get_color_btn("📢 Add to your Channel", url=f"https://t.me/{bot.username}?startchannel=true&admin={admin_rights}", style="primary")]
    ])
    
    text = (
        f"<blockquote>👋 <b>WELCOME TO AUTO ACCEPT BOT</b></blockquote>\n\n"
        f"Hello <b>{user.first_name}</b>!\n\n"
        f"I am a lightning-fast Auto-Accept Bot. Add me to your Channel or Group as an Admin to automatically accept join requests securely.\n\n"
        f"<i>⚠️ Note: Please make sure 'Remain Anonymous' permission is turned OFF.</i>"
    )
    
    today = datetime.now().strftime("%Y-%m-%d")
    await users_col.update_one(
        {"user_id": user.id}, 
        {"$set": {"name": user.first_name}, "$setOnInsert": {"date": today}}, 
        upsert=True
    )
    
    await message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# ==========================================
# 🛡️ AUTO ACCEPT & VERIFICATION DM
# ==========================================
async def auto_accept_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    chat = request.chat
    user = request.from_user
    
    text = (
        f"<blockquote>⚠️ <b>Security Verification Required</b></blockquote>\n\n"
        f"Hello <b>{user.first_name}</b>,\n\n"
        f"This is to prevent our group from bans and spam bots. "
        f"Please confirm your identity by clicking the button below to be accepted into <b>{chat.title}</b>."
    )
    
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("I am not a robot (Verify)", callback_data=f"verify_{chat.id}", style="success")]
    ])
    
    try:
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except telegram.error.RetryAfter as e:
        await asyncio.sleep(e.retry_after)
        await context.bot.send_message(chat_id=user.id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"Could not send DM to {user.first_name} ({user.id}): {e}")

# ==========================================
# ⚙️ ADVANCED ADMIN PANEL DASHBOARD
# ==========================================
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
        
    keyboard = InlineKeyboardMarkup([
        [get_color_btn("View Bot Live Stats", callback_data="admin_stats", style="primary")],
        [get_color_btn("Broadcast to Users (DM)", callback_data="bcast_users", style="success")],
        [get_color_btn("Broadcast to Groups/Channels", callback_data="bcast_chats", style="danger")]
    ])
    
    text = (
        f"<blockquote>⚙️ <b>ADVANCED ADMIN PANEL</b></blockquote>\n\n"
        f"Welcome to the Enterprise Admin Dashboard. Manage your bot's statistics and broadcast systems directly from here."
    )
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# ==========================================
# 🎛️ CALLBACK QUERY ROUTER (ALL BUTTONS)
# ==========================================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    uid = user.id
    
    try:
        await query.answer()
    except:
        pass

    # 1. Verification Callback
    if data.startswith("verify_"):
        chat_id = int(data.split("_")[1])
        today = datetime.now().strftime("%Y-%m-%d")
        
        try:
            await query.answer("✅ Identity Confirmed! Thanks for verification.", show_alert=True)
        except:
            pass
            
        try:
            await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=uid)
            
            await users_col.update_one(
                {"user_id": uid}, 
                {"$set": {"name": user.first_name}, "$setOnInsert": {"date": today}}, 
                upsert=True
            )
            
            try:
                chat = await context.bot.get_chat(chat_id)
                chat_title = chat.title
                await chats_col.update_one(
                    {"chat_id": chat_id}, 
                    {"$set": {"title": chat.title}, "$setOnInsert": {"date": today}}, 
                    upsert=True
                )
            except Exception:
                chat_title = "the group"

            welcome_text = (
                f"<blockquote>🎉 <b>ACCESS GRANTED</b></blockquote>\n\n"
                f"Welcome to <b>{chat_title}</b>, <b>{user.first_name}</b>!\n\n"
                f"Your request has been successfully approved by our Auto-Verification System. You can now access the content."
            )
            await query.message.edit_text(welcome_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Error approving {uid}: {e}")
        return

    # 2. Admin Live Stats
    if data == "admin_stats" and uid == ADMIN_ID:
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
        keyboard = InlineKeyboardMarkup([[get_color_btn("Back to Admin Panel", callback_data="back_to_admin", style="default")]])
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    # 3. Back to Admin Panel
    if data == "back_to_admin" and uid == ADMIN_ID:
        keyboard = InlineKeyboardMarkup([
            [get_color_btn("View Bot Live Stats", callback_data="admin_stats", style="primary")],
            [get_color_btn("Broadcast to Users (DM)", callback_data="bcast_users", style="success")],
            [get_color_btn("Broadcast to Groups/Channels", callback_data="bcast_chats", style="danger")]
        ])
        text = (
            f"<blockquote>⚙️ <b>ADVANCED ADMIN PANEL</b></blockquote>\n\n"
            f"Welcome to the Enterprise Admin Dashboard. Manage your bot's statistics and broadcast systems directly from here."
        )
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    # 4. Initiate Broadcast Flow
    if data in ["bcast_users", "bcast_chats"] and uid == ADMIN_ID:
        btype = "users" if data == "bcast_users" else "chats"
        bcast_state[uid] = {
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
        await query.message.edit_text(text, parse_mode=ParseMode.HTML)
        return

    # 5. Broadcast Color Button Selection
    if data.startswith("setcol_") and uid == ADMIN_ID:
        if uid not in bcast_state or bcast_state[uid]["step"] != "btn_color":
            try: await query.answer("Session expired or invalid step.", show_alert=True)
            except: pass
            return
            
        color_choice = data.split("_")[1]
        state = bcast_state[uid]
        
        state["buttons"].append({
            "name": state["temp_name"],
            "url": state["temp_url"],
            "style": color_choice
        })
        state["current_button_index"] += 1
        
        try: await query.message.delete()
        except: pass
        
        if state["current_button_index"] < state["target_button_count"]:
            state["step"] = "btn_name"
            next_num = state["current_button_index"] + 1
            await context.bot.send_message(uid, f"✅ <b>Button {next_num-1} Configured!</b>\n\n📝 <b>Configuring Button {next_num}:</b>\nPlease send the <b>Name (Text)</b> for this button.", parse_mode=ParseMode.HTML)
        else:
            state["step"] = "confirm"
            await context.bot.send_message(uid, "✅ <b>All Buttons Configured Successfully!</b>\n\nAll set! Type <b>/confirm</b> to start the broadcast or <b>/cancel</b> to abort.", parse_mode=ParseMode.HTML)
        return

# ==========================================
# 📢 BROADCAST WIZARD HANDLERS
# ==========================================
async def cancel_bcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        if uid in bcast_state:
            del bcast_state[uid]
            await update.message.reply_text("❌ <b>Broadcast Process Cancelled Successfully.</b>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("You don't have any active broadcast setup running.")

async def process_broadcast_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID or uid not in bcast_state:
        return
        
    state = bcast_state[uid]
    step = state["step"]
    message = update.message
    text = (message.text or message.caption or "").strip()
    
    if step == "media":
        if text == "/skip":
            state["step"] = "text"
            await message.reply_text("⏭ <b>Media Skipped.</b>\n\n<b>Step 2:</b> Now send the <b>Text Message</b>.\n<i>(Type /skip to skip text)</i>", parse_mode=ParseMode.HTML)
        elif message.photo:
            state["media_type"] = "photo"
            state["media_id"] = message.photo[-1].file_id
            state["step"] = "text"
            await message.reply_text("✅ <b>Photo Saved.</b>\n\n<b>Step 2:</b> Now send the <b>Text Message</b>.\n<i>(Type /skip to skip text)</i>", parse_mode=ParseMode.HTML)
        elif message.video:
            state["media_type"] = "video"
            state["media_id"] = message.video.file_id
            state["step"] = "text"
            await message.reply_text("✅ <b>Video Saved.</b>\n\n<b>Step 2:</b> Now send the <b>Text Message</b>.\n<i>(Type /skip to skip text)</i>", parse_mode=ParseMode.HTML)
        else:
            await message.reply_text("⚠️ Please send a Photo, Video or type /skip.")
            
    elif step == "text":
        if text == "/skip":
            if not state["media_id"]:
                await message.reply_text("⚠️ You cannot skip both Media and Text! Please send text.")
                return
            state["step"] = "btn_count"
            await message.reply_text("⏭ <b>Text Skipped.</b>\n\n<b>Step 3:</b> How many Inline Buttons do you want? (Send a number like 0, 1, 2, etc.)", parse_mode=ParseMode.HTML)
        else:
            state["text"] = text
            state["step"] = "btn_count"
            await message.reply_text("✅ <b>Text Saved.</b>\n\n<b>Step 3:</b> How many Inline Buttons do you want? (Send a number like 0, 1, 2, etc.)", parse_mode=ParseMode.HTML)
            
    elif step == "btn_count":
        try: count = int(text)
        except ValueError:
            await message.reply_text("⚠️ Please send a valid number.")
            return
            
        if count == 0:
            state["step"] = "confirm"
            await message.reply_text("✅ <b>No buttons selected.</b>\n\nAll set! Type <b>/confirm</b> to start the broadcast or <b>/cancel</b> to abort.", parse_mode=ParseMode.HTML)
        else:
            state["target_button_count"] = count
            state["current_button_index"] = 0
            state["step"] = "btn_name"
            await message.reply_text("📝 <b>Configuring Button 1:</b>\n\nPlease send the <b>Name (Text)</b> for this button.", parse_mode=ParseMode.HTML)
            
    elif step == "btn_name":
        state["temp_name"] = text
        state["step"] = "btn_url"
        await message.reply_text("✅ <b>Name Saved.</b>\n\nNow send the <b>URL (Link)</b> for this button (must start with http/https).", parse_mode=ParseMode.HTML)
        
    elif step == "btn_url":
        if not text.startswith("http"):
            await message.reply_text("⚠️ Invalid Link! Please send a valid link starting with http:// or https://")
            return
            
        state["temp_url"] = text
        state["step"] = "btn_color"
        
        # Color Selection Keyboard (Uses native colors)
        kb = InlineKeyboardMarkup([
            [get_color_btn("Success (Green)", callback_data="setcol_success", style="success"), get_color_btn("Danger (Red)", callback_data="setcol_danger", style="danger")],
            [get_color_btn("Primary (Blue)", callback_data="setcol_primary", style="primary"), get_color_btn("Default (Gray)", callback_data="setcol_default", style="default")]
        ])
        await message.reply_text("🎨 <b>Select Button Color:</b>\n\nChoose a color for this button from the menu below:", reply_markup=kb, parse_mode=ParseMode.HTML)

async def confirm_bcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        if uid not in bcast_state or bcast_state[uid]["step"] != "confirm":
            await update.message.reply_text("⚠️ No broadcast is waiting for confirmation.")
            return
            
        state = bcast_state[uid]
        await update.message.reply_text("🚀 <b>Broadcast Starting... Please wait.</b>", parse_mode=ParseMode.HTML)
        
        asyncio.create_task(execute_broadcast(context, uid, state))
        del bcast_state[uid]

async def execute_broadcast(context: ContextTypes.DEFAULT_TYPE, admin_id: int, state: dict):
    btype = state["type"]
    
    if btype == "users":
        targets = await users_col.find({}).to_list(length=None)
        id_key = "user_id"
    else:
        targets = await chats_col.find({}).to_list(length=None)
        id_key = "chat_id"
        
    success, failed = 0, 0
    
    inline_buttons = []
    for btn in state["buttons"]:
        inline_buttons.append([get_color_btn(btn["name"], url=btn["url"], style=btn["style"])])
        
    kb = InlineKeyboardMarkup(inline_buttons) if inline_buttons else None
        
    for target in targets:
        tid = target[id_key]
        try:
            if state["media_type"] == "photo":
                await context.bot.send_photo(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb, parse_mode=ParseMode.HTML)
            elif state["media_type"] == "video":
                await context.bot.send_video(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb, parse_mode=ParseMode.HTML)
            else:
                await context.bot.send_message(tid, state["text"], reply_markup=kb, parse_mode=ParseMode.HTML)
            
            success += 1
            await asyncio.sleep(0.05) # Safe delay
        except telegram.error.RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                if state["media_type"] == "photo":
                    await context.bot.send_photo(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb, parse_mode=ParseMode.HTML)
                elif state["media_type"] == "video":
                    await context.bot.send_video(tid, state["media_id"], caption=state["text"] or "", reply_markup=kb, parse_mode=ParseMode.HTML)
                else:
                    await context.bot.send_message(tid, state["text"], reply_markup=kb, parse_mode=ParseMode.HTML)
                success += 1
            except:
                failed += 1
        except Exception:
            failed += 1
            # Clean dead users/groups from Database automatically
            if btype == "users":
                await users_col.delete_one({"user_id": tid})
            else:
                await chats_col.delete_one({"chat_id": tid})
                
    await context.bot.send_message(
        admin_id, 
        f"<blockquote>✅ <b>BROADCAST COMPLETED</b></blockquote>\n\n"
        f"🎯 <b>Successfully Sent:</b> <code>{success}</code>\n"
        f"🚫 <b>Failed (Blocked/Removed):</b> <code>{failed}</code>",
        parse_mode=ParseMode.HTML
    )

# ==========================================
# 🏃 RUN THE BOT
# ==========================================
def main():
    print("Bot is Starting... ✅")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("admin", admin_dashboard, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("cancel", cancel_bcast, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("confirm", confirm_bcast, filters=filters.ChatType.PRIVATE))
    
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(ChatJoinRequestHandler(auto_accept_requests))
    
    # Message handler for processing broadcast media & text
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.PHOTO | filters.VIDEO | filters.TEXT) & ~filters.COMMAND, process_broadcast_steps))
    
    app.run_polling(allowed_updates=["message", "callback_query", "chat_join_request"], drop_pending_updates=True)

if __name__ == "__main__":
    main()
