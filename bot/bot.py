import logging
import datetime
from telegram import Update, User, BotCommand
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler,\
        CallbackContext, CommandHandler, filters, ConversationHandler, MessageHandler
from telegram.constants import ParseMode
from typing import Dict
from enum import Enum, auto

import config
from database import Database
import kupat_queries


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)


HELP_MESSAGE = """
פקודות:
⚪ /add - הוסף זמר לרשימה
⚪ /remove - הסר זמר מהרשימה 
⚪ /search - חפש הופעות לזמר
⚪ /list - הצג את רשימת החיפוש
⚪ /help - הצג הודעה זו 

⚪ מומלץ לרשום את השם שמופיע בתמונה של ההופעה באתר של קופת תל-אביב, כיוון שלחלק מהזמרים שומרים את השם באנגלית *שיעול* נועה קירל *שיעול* 
"""

db = Database()


#class Enum):
#    ADD = auto()
#    REMOVE = auto()
#    SEARCH = auto()
ADD, REMOVE, SEARCH = range(3)

async def register_user_if_not_exists(update: Update, user: User):
    if not db.check_if_user_exists(user.id):
        db.register_user(
                user.id,
                update.message.chat_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
        db.create_new_artist_list(user.id)
        db.create_new_shown_concerts_list(user.id)


async def help_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, update.message.from_user)
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def add_artist_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, update.message.from_user)

    await update.message.reply_text("איזה זמר/ת תרצה להוסיף?")
    return ADD
    #if not context.args or len(context.args) == 0:
    #    await update.message.reply_text("לא שלחת שם של זמר! נסה שנית.", parse_mode=ParseMode.HTML)
    #else:
    #    artist_name = " ".join(context.args)
    #    db.add_artist(user_id, artist_name)
    #    await update.message.reply_text(f"""{artist_name} התווסף לרשימת החיפוש!""", parse_mode=ParseMode.HTML)


async def add_artist(update: Update, context: CallbackContext):
    artist_name = update.message.text
    user_id = update.message.from_user.id
    db.add_artist(user_id, artist_name)
    await update.message.reply_text(f"""{artist_name} התווסף לרשימת החיפוש!""", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def remove_artist_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, update.message.from_user)

    await update.message.reply_text("איזה זמר/ת תרצה להסיר?")
    return REMOVE
    #user_id = update.message.from_user.id
    #if not context.args or len(context.args) == 0:
    #    await update.message.reply_text("לא שלחת שם של זמר! נסה שנית.", parse_mode=ParseMode.HTML)
    #else:
    #    artist_name = " ".join(context.args)
    #    db.remove_artist(user_id, artist_name)
    #    await update.message.reply_text(f"{artist_name} הוסר מרשימת החיפוש!", parse_mode=ParseMode.HTML)


async def remove_artist(update: Update, context: CallbackContext):
    artist_name = update.message.text
    user_id = update.message.from_user.id
    db.remove_artist(user_id, artist_name)
    await update.message.reply_text(f"{artist_name} הוסר מרשימת החיפוש!", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def search_shows_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, update.message.from_user)

    await update.message.reply_text("הופעות של איזה זמר/ת תרצה לחפש?")
    return SEARCH
    #user_id = update.message.from_user.id
    #if not context.args or len(context.args) == 0:
    #    await update.message.reply_text("לא שלחת שם של זמר! נסה שנית.", parse_mode=ParseMode.HTML)
    #else:
    #    artist_name = " ".join(context.args)
    #    logger.warning(f"Searching shows of {artist_name} for user {user_id}")
    #    concerts = kupat_queries.get_concerts_for_artist_name(artist_name)
    #    if not concerts:
    #        await update.message.reply_text(f"""לא נמצאו הופעות של {artist_name}""", parse_mode=ParseMode.HTML)
    #    else:
    #        text = f"נמצאו {len(concerts)} הופעות של {artist_name}:"
    #        for concert in concerts:
    #            text += "\n" + format_concert(concert)
    #        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def search_shows(update: Update, context: CallbackContext):
    artist_name = update.message.text
    logger.warning(f"Searching shows of {artist_name} for user {update.message.from_user.id}")
    concerts = kupat_queries.get_concerts_for_artist_name(artist_name)
    if not concerts:
        await update.message.reply_text(f"""לא נמצאו הופעות של {artist_name}""", parse_mode=ParseMode.HTML)
    else:
        text = f"נמצאו {len(concerts)} הופעות של {artist_name}:"
        for concert in concerts:
            text += "\n" + format_concert(concert)
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def list_artists_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, update.message.from_user)
    user_id = update.message.from_user.id
    artist_list = db.fetch_artists(user_id)
    if not artist_list or len(artist_list) == 0:
        text = "רשימת החיפוש שלך ריקה!"
    else:
        text = "הזמרים שכרגע בחיפוש הם:" + "\n" + ", ".join(artist_list)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def search_for_shows(context: CallbackContext):
    for user in db.user_collection.find():
        logger.warning(f"Looking for shows for user {user['_id']}")
        artists = db.fetch_artists(user["_id"])
        for artist in artists:
            concerts = kupat_queries.get_concerts_for_artist_name(artist)
            concerts = [concert for concert in concerts if not db.shown_concert(user["_id"], concert["id"])]
            if concerts:
                text = f"נמצאו {len(concerts)} הופעות של {artist}:" + "\n".join(format_concert(concert) for concert in concerts)
                await context.bot.send_message(chat_id=user["chat_id"], text=text)
                #db.add_concerts(user["_id"], concerts)


def format_concert(concert: Dict) -> str:
    def format_datetime(date_str: str, from_format: str, to_format: str) -> str:
        return datetime.datetime.strftime(
                datetime.datetime.strptime(
                    date_str,
                    from_format),
                to_format
                )
    location = concert["venueName"]
    # Dates format get switched around with Hebrew for some reason so switching format
    date = format_datetime(concert["dateTime"],
                           "%Y-%m-%d %H:%M",
                           "%H:%M %Y-%m-%d")
    sale_date = format_datetime(concert["ticketSaleStart"],
                                "%Y-%m-%d %H:%M:%S",
                                "%H:%M:%S %Y-%m-%d")
    return f"""
    מיקום: {location}
    תאריך: {date}
    פתיחת מכירת כרטיסים: {sale_date}
    """


async def post_init(app: Application):
    logger.info("Setting commands")
    await app.bot.set_my_commands([
        BotCommand("/add", "הוסף זמר"),
        BotCommand("/remove", "הסר זמר"),
        BotCommand("/search", "חפש הופעות לזמר"),
        BotCommand("/help", "הצג מסך עזרה"),
        BotCommand("/list", "הצג רשימת זמרים לחיפוש")
    ])
    # datetime.time is in UTC
    app.job_queue.run_daily(search_for_shows, time=datetime.time(hour=10, minute=0, second=00))


def run_bot():
    app = (
            ApplicationBuilder()
            .token(config.telegram_token)
            .concurrent_updates(True)
            .http_version("1.1")
            .get_updates_http_version("1.1")
            .post_init(post_init)
            .build()
    )
    user_filter = filters.ALL
    if len(config.allowed_telegram_usernames) > 0:
        usernames = [u for u in config.allowed_telegram_usernames if isinstance(u, str)]
        user_filter = filters.User(username=usernames)
    app.add_handler(CommandHandler("help", help_handle, filters=user_filter))
    app.add_handler(CommandHandler("list", list_artists_handle, filters=user_filter))
    conv_handler = ConversationHandler(
            entry_points=[CommandHandler("add", add_artist_handle, filters=user_filter),
                          CommandHandler("remove", remove_artist_handle, filters=user_filter),
                          CommandHandler("search", search_shows_handle, filters=user_filter)],
            fallbacks=[CommandHandler("cancel", cancel)],
            states={
                ADD: [MessageHandler(filters.TEXT, add_artist)],
                REMOVE: [MessageHandler(filters.TEXT, remove_artist)],
                SEARCH: [MessageHandler(filters.TEXT, search_shows)]
            }
        )
    app.add_handler(conv_handler)
    logger.info("Starting app")
    app.run_polling()

if __name__ == "__main__":
    run_bot()
