import os


telegram_token = os.getenv("TELEGRAM_TOKEN")
allowed_telegram_usernames = []  # if empty, the bot is available to anyone.
enable_message_streaming = True  # if set, messages will be shown to user word-by-word

mongodb_uri = "mongodb://mongo:27017"
singers_search_interval = int(os.getenv("SINGERS_SEARCH_INTERVAL", 3600))
standup_search_hour = int(os.getenv("STANDUP_SEARCH_HOUR", 9))
prune_hour = int(os.getenv("PRUNE_HOUR", 20))
