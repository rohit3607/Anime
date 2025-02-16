
import binascii
import base64
import re
import asyncio
from pyrogram import filters, Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from shortzy import Shortzy
import requests
import time
from datetime import datetime
import random
import string
from pyrogram.enums import ParseMode, ChatAction

from asyncio import sleep as asleep, gather
from pyrogram import filters, Client
from pyrogram.filters import command, private, user
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram import filters, Client
from bot import bot, bot_loop, Var, ani_cache
from bot.core.database import db
from bot.core.func_utils import *
from bot.core.auto_animes import get_animes
from bot.core.reporter import rep
from bot.func import *
from bot.autoDelete import *
from bot.query import *

# Create a global dictionary to store chat data
chat_data_cache = {}

@bot.on_message(command('start') & private)
@new_task
async def start_msg(client, message):
  
    uid = message.from_user.id
    from_user = message.from_user
    bot_info = await client.get_me()  
    bot_username = bot_info.username  
    txtargs = message.text.split()
    temp = await sendMessage(message, "<i>Connecting..</i>")

    # ✅ Add user to DB if not already present
    if not await db.present_user(uid):
        await db.add_user(uid)

    # 🔍 Check if user is subscribed (including pending requests)
    is_subscribed = True
    REQFSUB = await db.get_request_forcesub()
    buttons = []
    count = 0

    try:
        for total, chat_id in enumerate(await db.get_all_channels(), start=1):
            await message.reply_chat_action(ChatAction.PLAYING)

            # Show the join button of non-subscribed Channels.....
            if not await is_userJoin(client, user_id, chat_id):
                try:
                    # Check if chat data is in cache
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]  # Get data from cache
                    else:
                        data = await client.get_chat(chat_id)  # Fetch from API
                        chat_data_cache[chat_id] = data  # Store in cache

                    cname = data.title

                    # Handle private channels and links
                    if REQFSUB and not data.username: 
                        link = await db.get_stored_reqLink(chat_id)
                        await db.add_reqChannel(chat_id)

                        if not link:
                            link = (await client.create_chat_invite_link(chat_id=chat_id, creates_join_request=True)).invite_link
                            await db.store_reqLink(chat_id, link)
                    else:
                        link = data.invite_link

                    # Add button for the chat
                    buttons.append([InlineKeyboardButton(text=cname, url=link)])
                    count += 1
                    await temp.edit(f"<b>{'! ' * count}</b>")

                except Exception as e:
                    print(f"Can't Export Channel Name and Link..., Please Check If the Bot is admin in the FORCE SUB CHANNELS:\nProvided Force sub Channel:- {chat_id}")
                    return await temp.edit(f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @rohit_1888</i></b>\n<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>")

        try:
            buttons.append([InlineKeyboardButton(text='♻️ Tʀʏ Aɢᴀɪɴ', url=f"https://t.me/{bot_username}?start={message.command[1]}")])
        except IndexError:
            pass

        await message.reply_photo(
            photo=FORCE_PIC,
            caption=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # ✅ If user is subscribed, continue with normal start message
    if len(txtargs) <= 1:
        await temp.delete()
        btns = []
        for elem in Var.START_BUTTONS.split():
            try:
                bt, link = elem.split('|', maxsplit=1)
            except:
                continue
            if len(btns) != 0 and len(btns[-1]) == 1:
                btns[-1].insert(1, InlineKeyboardButton(bt, url=link))
            else:
                btns.append([InlineKeyboardButton(bt, url=link)])

        smsg = Var.START_MSG.format(
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            mention=from_user.mention, 
            user_id=from_user.id
        )

        if Var.START_PHOTO:
            await message.reply_photo(
                photo=Var.START_PHOTO, 
                caption=smsg,
                reply_markup=InlineKeyboardMarkup(btns) if len(btns) != 0 else None
            )
        else:
            await sendMessage(message, smsg, InlineKeyboardMarkup(btns) if len(btns) != 0 else None)
        return

    # ✅ Handle Movie Fetching from Stored Database
    try:
        arg = (await decode(txtargs[1])).split('-')
    except Exception as e:
        await rep.report(f"User : {uid} | Error : {str(e)}", "error")
        await editMessage(temp, "<b>Input Link Code Decode Failed !</b>")
        return

    if len(arg) == 2 and arg[0] == 'get':
        try:
            fid = int(int(arg[1]) / abs(int(Var.FILE_STORE)))
        except Exception as e:
            await rep.report(f"User : {uid} | Error : {str(e)}", "error")
            await editMessage(temp, "<b>Input Link Code is Invalid !</b>")
            return

        try:
            msg = await client.get_messages(Var.FILE_STORE, message_ids=fid)
            if msg.empty:
                return await editMessage(temp, "<b>File Not Found !</b>")

            # ✅ Fetch Auto-Delete, Caption & Protection Settings
            AUTO_DEL, DEL_TIMER, HIDE_CAPTION, CHNL_BTN, PROTECT_MODE = await asyncio.gather(
                db.get_auto_delete(), db.get_del_timer(), db.get_hide_caption(), db.get_channel_button(), db.get_protect_content()
            )

            if CHNL_BTN:
                button_name, button_link = await db.get_channel_button_link()

            original_caption = msg.caption.html if msg.caption else ""
            if CUSTOM_CAPTION and msg.document:
                caption = CUSTOM_CAPTION.format(previouscaption=original_caption, filename=msg.document.file_name)
            elif HIDE_CAPTION and (msg.document or msg.audio):
                caption = f"{original_caption}\n\n{CUSTOM_CAPTION}"
            else:
                caption = original_caption

            reply_markup = (
                InlineKeyboardMarkup([[InlineKeyboardButton(text=button_name, url=button_link)]])
                if CHNL_BTN and (msg.document or msg.photo or msg.video or msg.audio)
                else msg.reply_markup
            )

            # ✅ Send the File to User
            try:
                copied_msg = await msg.copy(
                    message.chat.id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_MODE
                )
                await temp.delete()

                # ⏳ Auto-Delete after Timer
                if AUTO_DEL:
                    asyncio.create_task(delete_message(copied_msg, DEL_TIMER))
                    asyncio.create_task(auto_del_notification(client.username, copied_msg, DEL_TIMER, txtargs[1]))

            except FloodWait as e:
                await asyncio.sleep(e.x)
                copied_msg = await msg.copy(
                    message.chat.id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup, protect_content=PROTECT_MODE
                )

                if AUTO_DEL:
                    asyncio.create_task(delete_message(copied_msg, DEL_TIMER))
                    asyncio.create_task(auto_del_notification(client.username, copied_msg, DEL_TIMER, txtargs[1]))

        except Exception as e:
            await rep.report(f"User : {uid} | Error : {str(e)}", "error")
            await editMessage(temp, "<b>File Not Found !</b>")
    else:
        await editMessage(temp, "<b>Input Link is Invalid for Usage !</b>")

@bot.on_message(command('pause') & private & user(Var.ADMINS))
async def pause_fetch(client, message):
    ani_cache['fetch_animes'] = False
    await sendMessage(message, "`Successfully Paused Fetching Animes...`")

@bot.on_message(command('resume') & private & user(Var.ADMINS))
async def pause_fetch(client, message):
    ani_cache['fetch_animes'] = True
    await sendMessage(message, "`Successfully Resumed Fetching Animes...`")

@bot.on_message(command('log') & private & user(Var.ADMINS))
@new_task
async def _log(client, message):
    await message.reply_document("log.txt", quote=True)

@bot.on_message(command('addlink') & private & user(Var.ADMINS))
@new_task
async def add_task(client, message):
    if len(args := message.text.split()) <= 1:
        return await sendMessage(message, "<b>No Link Found to Add</b>")
    
    Var.RSS_ITEMS.append(args[0])
    req_msg = await sendMessage(message, f"`Global Link Added Successfully!`\n\n    • **All Link(s) :** {', '.join(Var.RSS_ITEMS)[:-2]}")

@bot.on_message(command('addtask') & private & user(Var.ADMINS))
@new_task
async def add_task(client, message):
    if len(args := message.text.split()) <= 1:
        return await sendMessage(message, "<b>No Task Found to Add</b>")
    
    index = int(args[2]) if len(args) > 2 and args[2].isdigit() else 0
    if not (taskInfo := await getfeed(args[1], index)):
        return await sendMessage(message, "<b>No Task Found to Add for the Provided Link</b>")
    
    ani_task = bot_loop.create_task(get_animes(taskInfo.title, taskInfo.link, True))
    await sendMessage(message, f"<i><b>Task Added Successfully!</b></i>\n\n    • <b>Task Name :</b> {taskInfo.title}\n    • <b>Task Link :</b> {args[1]}")



@bot.on_message(filters.command('add_fsub') & filters.private & filters.user(Var.ADMINS))
async def add_forcesub(client: Client, message: Message):
    pro = await message.reply("<b><i>Processing....</i></b>", quote=True)
    check = 0
    channel_ids = await db.get_all_channels()
    fsubs = message.text.split()[1:]

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Close ✖️", callback_data="close")]])

    if not fsubs:
        await pro.edit("<b>You need to add channel IDs\n<blockquote><u>EXAMPLE</u>:\n/add_fsub [channel_ids] :</b> You can add one or multiple channel IDs at a time.</blockquote>", reply_markup=reply_markup)
        return

    channel_list = ""
    for id in fsubs:
        try:
            id = int(id)
        except:
            channel_list += f"<b><blockquote>Invalid ID: <code>{id}</code></blockquote></b>\n\n"
            continue

        if id in channel_ids:
            channel_list += f"<blockquote><b>ID: <code>{id}</code>, already exists..</b></blockquote>\n\n"
            continue

        id = str(id)
        if id.startswith('-') and id[1:].isdigit() and len(id) == 14:
            try:
                data = await client.get_chat(id)
                link = data.invite_link
                cname = data.title

                if not link:
                    link = await client.export_chat_invite_link(id)

                channel_list += f"<b><blockquote>NAME: <a href={link}>{cname}</a> (ID: <code>{id}</code>)</blockquote></b>\n\n"
                check += 1

            except:
                channel_list += f"<b><blockquote>ID: <code>{id}</code>\n<i>Unable to add force-sub, check the channel ID or bot permissions properly..</i></blockquote></b>\n\n"

        else:
            channel_list += f"<b><blockquote>Invalid ID: <code>{id}</code></blockquote></b>\n\n"
            continue

    if check == len(fsubs):
        for id in fsubs:
            await db.add_channel(int(id))
        await pro.edit(f'<b>Force-sub channel added ✅</b>\n\n{channel_list}', reply_markup=reply_markup, disable_web_page_preview=True)

    else:
        await pro.edit(f'<b>❌ Error occurred while adding force-sub channels</b>\n\n{channel_list.strip()}\n\n<b><i>Please try again...</i></b>', reply_markup=reply_markup, disable_web_page_preview=True)


@bot.on_message(filters.command('del_fsub') & filters.private & filters.user(Var.ADMINS))
async def delete_all_forcesub(client: Client, message: Message):
    pro = await message.reply("<b><i>Processing....</i></b>", quote=True)
    channels = await db.get_all_channels()
    fsubs = message.text.split()[1:]

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Close ✖️", callback_data="close")]])

    if not fsubs:
        return await pro.edit("<b>⁉️ Please, provide valid IDs or arguments\n<blockquote><u>EXAMPLES</u>:\n/del_fsub [channel_ids] :</b> To delete one or multiple specified IDs\n<code>/del_fsub all</code>: To delete all available force-sub IDs</blockquote>", reply_markup=reply_markup)

    if len(fsubs) == 1 and fsubs[0].lower() == "all":
        if channels:
            for id in channels:
                await db.del_channel(id)

            ids = "\n".join(f"<blockquote><code>{channel}</code> ✅</blockquote>" for channel in channels)
            return await pro.edit(f"<b>⛔️ All available channel IDs are deleted:\n{ids}</b>", reply_markup=reply_markup)
        else:
            return await pro.edit("<b><blockquote>⁉️ No channel IDs available to delete</blockquote></b>", reply_markup=reply_markup)

    if len(channels) >= 1:
        passed = ''
        for sub_id in fsubs:
            try:
                id = int(sub_id)
            except:
                passed += f"<b><blockquote><i>Invalid ID: <code>{sub_id}</code></i></blockquote></b>\n"
                continue
            if id in channels:
                await db.del_channel(id)

                passed += f"<blockquote><code>{id}</code> ✅</blockquote>\n"
            else:
                passed += f"<b><blockquote><code>{id}</code> not in force-sub channels</blockquote></b>\n"

        await pro.edit(f"<b>⛔️ Provided channel IDs are deleted:\n\n{passed}</b>", reply_markup=reply_markup)

    else:
        await pro.edit("<b><blockquote>⁉️ No channel IDs available to delete</blockquote></b>", reply_markup=reply_markup)


@bot.on_message(filters.command('fsub_chnl') & filters.private & filters.user(Var.ADMINS))
async def get_forcesub(client: Client, message: Message):
    pro = await message.reply("<b><i>Processing....</i></b>", quote=True)
    channels = await db.get_all_channels()
    channel_list = "<b><blockquote>❌ No force sub channel found!</b></blockquote>"
    if channels:
        channel_list = ""
        for id in channels:
            await message.reply_chat_action(ChatAction.TYPING)
            try:
                data = await client.get_chat(id)
                link = data.invite_link
                cname = data.title

                if not link:
                    link = await client.export_chat_invite_link(id)

                channel_list += f"<b><blockquote>NAME: <a href={link}>{cname}</a>\n(ID: <code>{id}</code>)</blockquote></b>\n\n"

            except:
                channel_list += f"<b><blockquote>ID: <code>{id}</code>\n<i>Unable to load other details..</i></blockquote></b>\n\n"

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Close ✖️", callback_data="close")]])
    await message.reply_chat_action(ChatAction.CANCEL)
    await pro.edit(f"<b>⚡ Force-sub channel list:</b>\n\n{channel_list}", reply_markup=reply_markup, disable_web_page_preview=True)

#=====================================================================================##
#.........Extra Functions.......#
#=====================================================================================##

# Auto Delete Setting Commands
@bot.on_message(filters.command('auto_del') & filters.private & filters.user(Var.ADMINS))
async def autoDelete_settings(client, message):
    await message.reply_chat_action(ChatAction.TYPING)

    try:
            timer = convert_time(await db.get_del_timer())
            if await db.get_auto_delete():
                autodel_mode = on_txt
                mode = 'Dɪsᴀʙʟᴇ Mᴏᴅᴇ ❌'
            else:
                autodel_mode = off_txt
                mode = 'Eɴᴀʙʟᴇ Mᴏᴅᴇ ✅'

            await message.reply_photo(
                photo = autodel_cmd_pic,
                caption = AUTODEL_CMD_TXT.format(autodel_mode=autodel_mode, timer=timer),
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(mode, callback_data='chng_autodel'), InlineKeyboardButton('◈ Sᴇᴛ Tɪᴍᴇʀ ⏱', callback_data='set_timer')],
                    [InlineKeyboardButton('🔄 Rᴇғʀᴇsʜ', callback_data='autodel_cmd'), InlineKeyboardButton('Cʟᴏsᴇ ✖️', callback_data='close')]
                ]),
                message_effect_id = 5107584321108051014 #👍
            )
    except Exception as e:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cʟᴏsᴇ ✖️", callback_data = "close")]])
            await message.reply(f"<b>! Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ..\n<blockquote>Rᴇᴀsᴏɴ:</b> {e}</blockquote><b><i>Cᴏɴᴛᴀɴᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ: @rohit_1888</i></b>", reply_markup=reply_markup)


#Files related settings command
@bot.on_message(filters.command('files') & filters.private & filters.user(Var.ADMINS))
async def files_commands(client: Client, message: Message):
    await message.reply_chat_action(ChatAction.TYPING)

    try:
        protect_content = hide_caption = channel_button = off_txt
        pcd = hcd = cbd = '❌'
        if await db.get_protect_content():
            protect_content = on_txt
            pcd = '✅'
        if await db.get_hide_caption():
            hide_caption = on_txt
            hcd = '✅'
        if await db.get_channel_button():
            channel_button = on_txt
            cbd = '✅'
        name, link = await db.get_channel_button_link()

        await message.reply_photo(
            photo = files_cmd_pic,
            caption = FILES_CMD_TXT.format(
                protect_content = protect_content,
                hide_caption = hide_caption,
                channel_button = channel_button,
                name = name,
                link = link
            ),
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(f'Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ: {pcd}', callback_data='pc'), InlineKeyboardButton(f'Hɪᴅᴇ Cᴀᴘᴛɪᴏɴ: {hcd}', callback_data='hc')],
                [InlineKeyboardButton(f'Cʜᴀɴɴᴇʟ Bᴜᴛᴛᴏɴ: {cbd}', callback_data='cb'), InlineKeyboardButton(f'◈ Sᴇᴛ Bᴜᴛᴛᴏɴ ➪', callback_data='setcb')],
                [InlineKeyboardButton('🔄 Rᴇғʀᴇsʜ', callback_data='files_cmd'), InlineKeyboardButton('Cʟᴏsᴇ ✖️', callback_data='close')]
            ]),
            message_effect_id = 5107584321108051014 #👍
        )
    except Exception as e:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cʟᴏsᴇ ✖️", callback_data = "close")]])
        await message.reply(f"<b>! Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ..\n<blockquote>Rᴇᴀsᴏɴ:</b> {e}</blockquote><b><i>Cᴏɴᴛᴀɴᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ: @rohit_1888</i></b>", reply_markup=reply_markup)

#Request force sub mode commad,,,,,,
@bot.on_message(filters.command('req_fsub') & filters.private & filters.user(Var.ADMINS))
async def handle_reqFsub(client: Client, message: Message):
    await message.reply_chat_action(ChatAction.TYPING)
    try:
        on = off = ""
        if await db.get_request_forcesub():
            on = "🟢"
            texting = on_txt
        else:
            off = "🔴"
            texting = off_txt

        button = [
            [InlineKeyboardButton(f"{on} ON", "chng_req"), InlineKeyboardButton(f"{off} OFF", "chng_req")],
            [InlineKeyboardButton("⚙️ Mᴏʀᴇ Sᴇᴛᴛɪɴɢs ⚙️", "more_settings")]
        ]
        await message.reply(text=RFSUB_CMD_TXT.format(req_mode=texting), reply_markup=InlineKeyboardMarkup(button), message_effect_id=5046509860389126442)

    except Exception as e:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Cʟᴏsᴇ ✖️", callback_data = "close")]])
        await message.reply(f"<b>! Eʀʀᴏʀ Oᴄᴄᴜʀᴇᴅ..\n<blockquote>Rᴇᴀsᴏɴ:</b> {e}</blockquote><b><i>Cᴏɴᴛᴀɴᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ: @rohit_1888</i></b>", reply_markup=reply_markup)