import logging
import datetime
from telegram import Update, User, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    filters,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
)
from telegram.constants import ParseMode
from typing import Dict, Generator
from enum import Enum, auto
import re
from requests.exceptions import RequestException

import config
from database import Database
import api_queries


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


class States(Enum):
    SINGERS = 1
    STANDUPS = 2
    ADD_SINGER = auto()
    REMOVE_SINGER = auto()
    SEARCH_SINGER = auto()
    LIST_SINGER = auto()
    ADD_COMEDIAN = auto()
    REMOVE_COMEDIAN = auto()
    LIST_COMEDIAN = auto()
    SEARCH_COMEDIAN = auto()
    ACTION_BUTTON_CLICK = auto()
    SHOW_TYPE_CLICK = auto()


MAX_MESSAGE_LENGTH = 4096


HELP_MESSAGE = """
⚪ /start - הצג את התפריט הראשי.
⚪ /singer - הצג את תפריט ההופעות.
⚪ /standup - הצג את תפריט הסטנדאפ.
⚪ /help - הצג הודעה זו 

⚪ מומלץ לרשום את השם שמופיע בתמונה של ההופעה באתר של קופת תל-אביב, כיוון שלחלק מהזמרים שומרים את השם באנגלית *שיעול* נועה קירל *שיעול* 
⚪ הבוט יחפש הופעות לזמרים ברשימת החיפוש כל שעה ויודיע אם מצא.
⚪ בראשון בחודש, הבוט יחפש הופעות סטנדאפ לסטנדאפיסטים שברשימת החיפוש ויודיע אם מצא.
"""

db = Database()


async def register_user_if_not_exists(update: Update, user: User):
    if not db.check_if_user_exists(user.id):
        db.register_user(
            user.id,
            update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        db.create_new_singers_list(user.id)
        db.create_new_shown_concerts_list(user.id)
        db.create_new_comedians_list(user.id)
        db.create_new_shown_standups_list(user.id)


async def help_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, update.message.from_user)
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


def parse_names(text: str) -> Generator[None, None, str]:
    for name in text.split(","):
        if name:
            yield name.strip()


async def add_singer(update: Update, context: CallbackContext) -> States:
    user_id = update.message.from_user.id
    for singer_name in parse_names(update.message.text):
        try:
            db.add_singer(user_id, singer_name)
        except RuntimeError:
            await update.message.reply_text(
                "הגעת לכמות המקסימלית של זמרים ברשימת החיפוש. על מנת להוסיף זמרים חדשים עליך להסיר זמרים מהרשימה."
            )
        else:
            await update.message.reply_text(f"{singer_name} התווסף לרשימת החיפוש!", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def remove_singer(update: Update, context: CallbackContext) -> States:
    user_id = update.message.from_user.id
    for singer_name in parse_names(update.message.text):
        db.remove_singer(user_id, singer_name)
        await update.message.reply_text(f"{singer_name} הוסר מרשימת החיפוש!", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def get_names_from_user(update: Update, context: CallbackContext) -> States:
    state = States(int(update.callback_query.data))
    if state in (States.ADD_SINGER, States.REMOVE_SINGER, States.SEARCH_SINGER):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="הקלידו את שמות הזמרים, מופרדים על ידי פסיקים:",
            reply_markup=ForceReply(),
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="הקלידו את שמות הסטנדאפיסטים, מופרדים על ידי פסיקים:",
            reply_markup=ForceReply(),
        )
    return state


async def search_shows(update: Update, context: CallbackContext) -> States:
    for singer_name in parse_names(update.message.text):
        logger.warning(f"Searching shows of {singer_name} for user {update.message.from_user.id}")
        await update.effective_chat.send_action(action="typing")
        text = ""
        try:
            concerts = api_queries.get_concerts_for_singer(singer_name)
        except RequestException:
            logger.exception("Failed to connect to %s", api_queries.KUPAT_API_URL)
            await update.message.reply_text("לא הצלחתי להתחבר לאתר, אנא נסו שנית עוד מספר שניות.")
            return States.ACTION_BUTTON_CLICK
        if not concerts:
            text = f"לא נמצאו הופעות של {singer_name}"
        else:
            text = f"נמצאו {len(concerts)} הופעות של {singer_name}:" + "\n"
            for concert in concerts:
                concert_text = format_concert(concert) + "\n"
                if len(text + concert_text) > 4096:
                    await update.message.reply_text(text)
                    text = ""
                text += concert_text + "\n"
        await update.message.reply_text(text)
    return States.ACTION_BUTTON_CLICK


async def list_singers_handle(update: Update, context: CallbackContext) -> States:
    user_id = update.callback_query.from_user.id
    singer_list = db.fetch_singers(user_id)
    if not singer_list or len(singer_list) == 0:
        text = "רשימת החיפוש שלך ריקה!"
    else:
        text = "הזמרים שכרגע בחיפוש הם:" + "\n" + ", ".join(singer_list)
    await update.callback_query.answer("מחפש את רשימת הזמרים שלך..")
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return States.ACTION_BUTTON_CLICK


async def search_shows_for_users(context: CallbackContext):
    for user in db.user_collection.find():
        logger.warning(f"Looking for shows for user {user['_id']}")
        singers = db.fetch_singers(user["_id"])
        for singer in singers:
            try:
                concerts = api_queries.get_concerts_for_singer(singer)
            except RequestException:
                logger.exception("Failed to reach %s for user %s", api_queries.KUPAT_API_URL, user["_id"])
                continue
            concerts = [concert for concert in concerts if not db.shown_concert(user["_id"], singer, concert["date"])]
            if concerts:
                text = f"נמצאו {len(concerts)} הופעות של {singer}:" + "\n"
                for concert in concerts:
                    concert_text = format_concert(concert) + "\n"
                    if len(text + concert_text) > 4096:
                        await context.bot.send_message(chat_id=user["chat_id"], text=text)
                        text = ""
                    text += concert_text
                await context.bot.send_message(chat_id=user["chat_id"], text=text)
                db.add_concerts(user["_id"], singer, concerts)


def format_concert(concert: Dict) -> str:
    # Dates format get switched around with Hebrew for some reason so switching format
    urls = "\n".join(url.replace(" ", "%20") for url in concert["url"])
    if concert["ticketSaleStart"]:
        sale_start = f"""\nפתיחת מכירת כרטיסים: {concert["ticketSaleStart"]}"""
    else:
        sale_start = ""
    if concert["ticketSaleStop"]:
        sale_stop = f"""\nסגירת מכירת כרטיסים: {concert["ticketSaleStop"]}"""
    else:
        sale_stop = ""
    text = f"""מיקום: {concert["venue"]}\nתאריך: {concert["date"]}{sale_start}{sale_stop}\nקישורים:\n{urls}"""
    return text


async def list_comedian_handle(update: Update, context: CallbackContext) -> States:
    user_id = update.callback_query.from_user.id
    comedians_list = db.fetch_comedians(user_id)
    if not comedians_list or len(comedians_list) == 0:
        text = "רשימת החיפוש שלך ריקה!"
    else:
        text = "הסטנדאפיסטים שברשימת החיפוש הם:" + "\n" + ", ".join(comedians_list)
    await update.callback_query.answer("מחפש את רשימת הסטנדאפיסטים שלך...")
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return States.ACTION_BUTTON_CLICK


async def add_comedian(update: Update, context: CallbackContext) -> States:
    user_id = update.message.from_user.id
    for comedian_name in parse_names(update.message.text):
        try:
            db.add_comedian(user_id, comedian_name)
        except RuntimeError:
            await update.message.reply_text(
                "הגעת לכמות המקסימלית של סטנדאפיסטים ברשימת החיפוש. על מנת להוסיף חדשים עליך להסיר סטנדאפיסטים מהרשימה."
            )
        else:
            await update.message.reply_text(f"""{comedian_name} התווסף לרשימת החיפוש!""", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def remove_comedian(update: Update, context: CallbackContext) -> States:
    user_id = update.message.from_user.id
    for comedian_name in parse_names(update.message.text):
        db.remove_comedian(user_id, comedian_name)
        await update.message.reply_text(f"{comedian_name} הוסר מרשימת החיפוש!", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def search_standups(update: Update, context: CallbackContext) -> States:
    for comedian_name in parse_names(update.message.text):
        logger.warning(f"Searching standups of {comedian_name} for user {update.message.from_user.id}")
        await update.message.chat.send_action(action="typing")
        text = ""
        try:
            standups = api_queries.get_standups_for_comedian(comedian_name)
        except RequestException:
            logger.exception(
                "Failed to reach either site for user %s",
                update.message.from_user.id,
            )
            await update.message.reply_text("לא הצלחתי להתחבר לאתר, אנא נסו שנית בעוד מספר שניות.")
            return States.ACTION_BUTTON_CLICK
        if not standups:
            text = f"לא נמצאו הופעות של {comedian_name}" ""
        else:
            text = f"נמצאו {len(standups)} הופעות סטנדאפ של {comedian_name}:" + "\n"
            for standup in standups:
                standup_text = format_standup(standup) + "\n"
                if len(text + standup_text) > 4096:
                    await update.message.reply_text(text)
                    text = ""
                text += standup_text
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


def format_standup(standup: Dict) -> str:
    # Dates format get switched around with Hebrew for some reason so switching format
    urls = "\n".join(url.replace(" ", "%20") for url in standup["url"])
    return f"""מיקום: {standup["venue"]}\nתאריך: {standup["date"]}\nקישורים:\n{urls}
    """


async def search_standups_for_users(context: CallbackContext):
    for user in db.user_collection.find():
        logger.warning(f"Looking for standups for user {user['_id']}")
        comedian = db.fetch_comedians(user["_id"])
        for comedian in comedian:
            try:
                standups = api_queries.get_standups_for_comedian(comedian)
            except RequestException:
                logger.exception(
                    "Failed to reach site for user %s",
                    user["_id"],
                )
                continue
            standups = [
                standup for standup in standups if not db.shown_standup(user["_id"], comedian + standup[0]["show_date"])
            ]
            text = f"נמצאו {len(standups)} הופעות של {comedian}:" + "\n"
            if standups:
                for standup in standups:
                    standup_text = format_standup(standup) + "\n"
                    if len(text + standup_text) > 4096:
                        await context.bot.send_message(chat_id=user["chat_id"], text=text)
                        text = ""
                    text += standup_text
                await context.bot.send_message(chat_id=user["chat_id"], text=text)
                db.add_standups(user["_id"], comedian, standups)


def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="זמר", callback_data=str(States.SINGERS.value)),
            InlineKeyboardButton(text="סטנדאפ", callback_data=str(States.STANDUPS.value)),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def create_singers_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="הוסף", callback_data=str(States.ADD_SINGER.value)),
            InlineKeyboardButton(text="הסר", callback_data=str(States.REMOVE_SINGER.value)),
        ],
        [
            InlineKeyboardButton(text="חיפוש", callback_data=str(States.SEARCH_SINGER.value)),
            InlineKeyboardButton(text="הצג רשימה", callback_data=str(States.LIST_SINGER.value)),
        ],
        [InlineKeyboardButton(text="חזור", callback_data=str(States.SHOW_TYPE_CLICK.value))],
    ]
    return InlineKeyboardMarkup(buttons)


def create_standup_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="הוסף", callback_data=str(States.ADD_COMEDIAN.value)),
            InlineKeyboardButton(text="הסר", callback_data=str(States.REMOVE_COMEDIAN.value)),
        ],
        [
            InlineKeyboardButton(text="חיפוש", callback_data=str(States.SEARCH_COMEDIAN.value)),
            InlineKeyboardButton(text="הצג רשימה", callback_data=str(States.LIST_COMEDIAN.value)),
        ],
        [InlineKeyboardButton(text="חזור", callback_data=str(States.SHOW_TYPE_CLICK.value))],
    ]

    return InlineKeyboardMarkup(buttons)


async def handle_start(update: Update, context: CallbackContext) -> States:
    await register_user_if_not_exists(update, update.message.from_user)
    await update.message.reply_text("היי! אני GigMaster, החבר שלכם למציאת הופעות וסטנדאפים!")
    await update.message.reply_text(text="בחרו את התפריט הרצוי:", reply_markup=create_main_menu_keyboard())
    return States.SHOW_TYPE_CLICK


async def handle_singers_entry(update: Update, context: CallbackContext) -> States:
    await register_user_if_not_exists(update, update.message.from_user)
    await update.message.reply_text(text="בחרו את הפעולה הרצויה:", reply_markup=create_singers_keyboard())
    return States.ACTION_BUTTON_CLICK


async def handle_standup_entry(update: Update, context: CallbackContext) -> States:
    await register_user_if_not_exists(update, update.message.from_user)
    await update.message.reply_text(text="בחרו את הפעולה הרצויה:", reply_markup=create_standup_keyboard())
    return States.ACTION_BUTTON_CLICK


async def singers_menu_2nd_level(update: Update, context: CallbackContext) -> States:
    query = update.callback_query
    await query.message.edit_text(text="בחרו את הפעולה הרצויה:", reply_markup=create_singers_keyboard())
    return States.ACTION_BUTTON_CLICK


async def standup_menu_2nd_level(update: Update, context: CallbackContext) -> States:
    query = update.callback_query
    await query.edit_message_text(text="בחרו את הפעולה הרצויה:", reply_markup=create_standup_keyboard())
    return States.ACTION_BUTTON_CLICK


async def start_over(update: Update, context: CallbackContext) -> States:
    if update.message:
        await update.message.reply_text(text="בחרו את סוג ההופעה:", reply_markup=create_main_menu_keyboard())
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="בחרו את סוג ההופעה:", reply_markup=create_main_menu_keyboard()
        )
    return States.SHOW_TYPE_CLICK


async def post_init(app: Application):
    await app.bot.set_my_commands(
        [
            BotCommand("/help", "הצג מסך עזרה"),
            BotCommand("/start", "התחל שיחה עם הבוט"),
            BotCommand("/singer", "הצג תפריט זמרים"),
            BotCommand("/standup", "הצג תפריט סטנדאפ"),
        ]
    )
    # interval in seconds
    starting_singers_time = datetime.datetime.now().time()
    starting_singers_time = starting_singers_time.replace(
        microsecond=0, second=0, minute=0, hour=(starting_singers_time.hour + 1) % 24
    )
    app.job_queue.run_repeating(
        search_shows_for_users, interval=config.singers_search_interval, first=starting_singers_time
    )
    # datetime.time is in UTC
    app.job_queue.run_monthly(
        search_standups_for_users, day=1, when=datetime.time(hour=config.standup_search_hour, minute=0, second=00)
    )


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
    NAMES_REQUIRED_REGEX = re.compile(
        f"{str(States.ADD_SINGER.value)}|{str(States.SEARCH_SINGER.value)}|{str(States.REMOVE_SINGER.value)}|"
        + f"{str(States.ADD_COMEDIAN.value)}|{str(States.SEARCH_COMEDIAN.value)}|{str(States.REMOVE_COMEDIAN.value)}"
    )
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", handle_start, filters=user_filter),
            CommandHandler("singer", handle_singers_entry, filters=user_filter),
            CommandHandler("standup", handle_standup_entry, filters=user_filter),
        ],
        fallbacks=[CommandHandler("start_over", start_over, filters=user_filter)],
        states={
            States.SHOW_TYPE_CLICK: [
                CallbackQueryHandler(singers_menu_2nd_level, pattern=str(States.SINGERS.value)),
                CallbackQueryHandler(standup_menu_2nd_level, pattern=str(States.STANDUPS.value)),
            ],
            States.ACTION_BUTTON_CLICK: [
                CallbackQueryHandler(get_names_from_user, pattern=NAMES_REQUIRED_REGEX),
                CallbackQueryHandler(list_singers_handle, pattern=str(States.LIST_SINGER.value)),
                CallbackQueryHandler(list_comedian_handle, pattern=str(States.LIST_COMEDIAN.value)),
                CallbackQueryHandler(start_over, pattern=str(States.SHOW_TYPE_CLICK.value)),
            ],
            States.SEARCH_SINGER: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_shows)],
            States.ADD_SINGER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_singer)],
            States.REMOVE_SINGER: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_singer)],
            States.SEARCH_COMEDIAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_standups)],
            States.ADD_COMEDIAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_comedian)],
            States.REMOVE_COMEDIAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_comedian)],
        },
        allow_reentry=True,
    )
    app.add_handler(conv_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run_bot()
