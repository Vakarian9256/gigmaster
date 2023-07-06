import os


telegram_token = os.getenv("TELEGRAM_TOKEN")
allowed_telegram_usernames = []  # if empty, the bot is available to anyone.
enable_message_streaming = True  # if set, messages will be shown to user word-by-word

mongodb_uri = "mongodb://mongo:27017"
