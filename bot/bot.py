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
from typing import Dict
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


HELP_MESSAGE = """
פקודות:
⚪ /start - הצג את התפריט הראשי.
⚪ /singer - הצג את תפריט ההופעות.
⚪ /comedian - הצג את תפריט הסטאנדפ.
⚪ /help - הצג הודעה זו 

⚪ מומלץ לרשום את השם שמופיע בתמונה של ההופעה באתר של קופת תל-אביב, כיוון שלחלק מהזמרים שומרים את השם באנגלית *שיעול* נועה קירל *שיעול* 
⚪ מדי יום, ב-13:00, הבוט יחפש הופעות לזמרים ברשימת החיפוש ויודיע אם מצא.
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


async def add_singer(update: Update, context: CallbackContext):
    singer_name = update.message.text
    user_id = update.message.from_user.id
    db.add_singer(user_id, singer_name)
    await update.message.reply_text(f"""{singer_name} התווסף לרשימת החיפוש!""", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def remove_singer(update: Update, context: CallbackContext):
    singer_name = update.message.text
    user_id = update.message.from_user.id
    db.remove_singer(user_id, singer_name)
    await update.message.reply_text(f"{singer_name} הוסר מרשימת החיפוש!", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def get_singer_from_user(update: Update, context: CallbackContext):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="הקלידו את שם הזמר בבקשה:", reply_markup=ForceReply()
    )
    return States(int(update.callback_query.data))


async def search_shows(update: Update, context: CallbackContext):
    singer_name = update.message.text
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
        text = f"""לא נמצאו הופעות של {singer_name}"""
    else:
        text = f"נמצאו {len(concerts)} הופעות של {singer_name}:"
        for concert in concerts:
            text += "\n" + format_concert(concert)
    await update.message.reply_text(text)
    return States.ACTION_BUTTON_CLICK


async def list_singers_handle(update: Update, context: CallbackContext) -> int:
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
            concerts = [concert for concert in concerts if not db.shown_concert(user["_id"], concert["id"])]
            if concerts:
                text = f"נמצאו {len(concerts)} הופעות של {singer}:" + "\n".join(
                    format_concert(concert) for concert in concerts
                )
                await context.bot.send_message(chat_id=user["chat_id"], text=text)
                db.add_concerts(user["_id"], concerts)


def format_datetime(date_str: str, from_format: str, to_format: str) -> str:
    return datetime.datetime.strftime(datetime.datetime.strptime(date_str, from_format), to_format)


def format_concert(concert: Dict) -> str:
    location = concert["venueName"]
    # Dates format get switched around with Hebrew for some reason so switching format
    date = format_datetime(concert["dateTime"], "%Y-%m-%d %H:%M", "%H:%M %d-%m-%Y")
    sale_date = format_datetime(concert["ticketSaleStart"], "%Y-%m-%d %H:%M:%S", "%H:%M:%S %d-%m-%Y")
    url = f"https://tickets.kupat.co.il/booking/features/{concert['featureId']}?prsntId={concert['id']}#tickets"
    return f"""
    מיקום: {location}
    תאריך: {date}
    פתיחת מכירת כרטיסים: {sale_date}
    קישור: {url}
    """


async def get_comedian_from_user(update: Update, context: CallbackContext):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="הקלידו את שם הסטנדאפיסט בבקשה:", reply_markup=ForceReply()
    )
    return States(int(update.callback_query.data))


async def list_comedian_handle(update: Update, context: CallbackContext) -> int:
    user_id = update.callback_query.from_user.id
    comedians_list = db.fetch_comedians(user_id)
    if not comedians_list or len(comedians_list) == 0:
        text = "רשימת החיפוש שלך ריקה!"
    else:
        text = "הסטנדאפיסטים שברשימת החיפוש הם:" + "\n" + ", ".join(comedians_list)
    await update.callback_query.answer("מחפש את רשימת הסטנדאפיסטים שלך...")
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return States.ACTION_BUTTON_CLICK


async def add_comedian(update: Update, context: CallbackContext):
    comedian_name = update.message.text
    user_id = update.message.from_user.id
    db.add_comedian(user_id, comedian_name)
    await update.message.reply_text(f"""{comedian_name} התווסף לרשימת החיפוש!""", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def remove_comedian(update: Update, context: CallbackContext):
    comedian_name = update.message.text
    user_id = update.message.from_user.id
    db.remove_comedian(user_id, comedian_name)
    await update.message.reply_text(f"{comedian_name} הוסר מרשימת החיפוש!", parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


async def search_standups(update: Update, context: CallbackContext):
    comedian_name = update.message.text
    logger.warning(f"Searching standups of {comedian_name} for user {update.message.from_user.id}")
    await update.message.chat.send_action(action="typing")
    text = ""
    try:
        standups = api_queries.get_standups_for_comedian(comedian_name)
    except RequestException:
        logger.exception(
            "Failed to reach either %s or %s for user %s",
            api_queries.CASTILIA_API_URL,
            api_queries.COMEDYBAR_API_URL,
            update.message.from_user.id,
        )
        await update.message.reply_text("לא הצלחתי להתחבר לאתר, אנא נסו שנית בעוד מספר שניות.")
        return States.ACTION_BUTTON_CLICK
    if not standups[api_queries.StandupSites.COMEDYBAR] and not standups[api_queries.StandupSites.CASTILIA]:
        text = f"לא נמצאו הופעות של {comedian_name}" ""
    else:
        actual_standups = []
        for site in standups:
            if not standups[site]:
                continue
            for standup in standups[site]["events"]:
                if standup["show_date"] in actual_standups:
                    continue
                actual_standups.append(standup["show_date"])
                text += "\n" + format_standup(standup, site)
        text = f"נמצאו {len(actual_standups)} הופעות סטדנאפ של {comedian_name}:" + text
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return States.ACTION_BUTTON_CLICK


def format_standup(standup: Dict, site: api_queries.StandupSites) -> str:
    base_urls = {
        api_queries.StandupSites.CASTILIA: "castilia.co.il/he/Event/Order?eventId=",
        api_queries.StandupSites.COMEDYBAR: "comedybar.smarticket.co.il/iframe/event/",
    }
    location = standup["event_place"]
    # Dates format get switched around with Hebrew for some reason so switching format
    date = format_datetime(standup["show_date"] + " " + standup["show_time"], "%Y-%m-%d %H:%M", "%H:%M %d-%m-%Y")
    url = base_urls[site] + str(standup["id"])
    return f"""
    מיקום: {location}
    תאריך: {date}
    קישור: {url}
    """


async def search_standups_for_users(context: CallbackContext):
    for user in db.user_collection.find():
        logger.warning(f"Looking for standups for user {user['_id']}")
        comedian = db.fetch_comedians(user["_id"])
        for comedian in comedian:
            try:
                standups = api_queries.get_standups_for_comedian(comedian)
                continue
            except RequestException:
                logger.exception(
                    "Failed to reach %s or %s for user %s",
                    api_queries.CASTILIA_API_URL,
                    api_queries.COMEDYBAR_API_URL,
                    user["_id"],
                )
            deduped = {}
            for site in standups:
                if not standups[site]:
                    continue
                for standup in standups[site]["events"]:
                    if standup["show_date"] not in deduped:
                        deduped[standup["show_date"]] = (standup, site)

            new_standups = [
                standup
                for standup in deduped.values()
                if not db.shown_standup(user["_id"], comedian + standup[0]["show_date"])
            ]
            if new_standups:
                text = f"נמצאו {len(new_standups)} הופעות של {comedian}:" + "\n".join(
                    format_standup(*standup) for standup in new_standups
                )
                await context.bot.send_message(chat_id=user["chat_id"], text=text)
                db.add_standups(user["_id"], comedian, [standup[0] for standup in new_standups])


def create_main_menu_keyboard():
    buttons = [
        [
            InlineKeyboardButton(text="זמר", callback_data=str(States.SINGERS.value)),
            InlineKeyboardButton(text="סטנדאפ", callback_data=str(States.STANDUPS.value)),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def create_singers_keyboard():
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


def create_standup_keyboard():
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
    # datetime.time is in UTC
    app.job_queue.run_daily(
        search_shows_for_users, time=datetime.time(hour=config.singers_search_hour, minute=0, second=00)
    )
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
    SINGER_NAME_REQUIRED_REGEX = re.compile(
        f"{str(States.ADD_SINGER.value)}|{str(States.SEARCH_SINGER.value)}|{str(States.REMOVE_SINGER.value)}"
    )
    COMEDIAN_NAME_REQUIRED_REGEX = re.compile(
        f"{str(States.ADD_COMEDIAN.value)}|{str(States.SEARCH_COMEDIAN.value)}|{str(States.REMOVE_COMEDIAN.value)}"
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
                CallbackQueryHandler(get_singer_from_user, pattern=SINGER_NAME_REQUIRED_REGEX),
                CallbackQueryHandler(list_singers_handle, pattern=str(States.LIST_SINGER.value)),
                CallbackQueryHandler(get_comedian_from_user, pattern=COMEDIAN_NAME_REQUIRED_REGEX),
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
