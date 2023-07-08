from typing import List, Dict
import pymongo
import uuid
import logging

import config


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.client = pymongo.MongoClient(config.mongodb_uri)
        self.db = self.client["gigmaster"]
        logger.info("Initiated client and loaded DB")
        self.user_collection = self.db["users"]
        self.singers_collection = self.db["singers"]
        self.shown_concerts_collection = self.db["shown_concerts"]
        self.comedians_collection = self.db["comedians"]
        self.shown_standups_collection = self.db["shown_standups"]
        logger.info("Loaded collections")

    def check_if_user_exists(self, user_id: int, raise_exception: bool = False) -> bool:
        if self.user_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
            else:
                logger.warning("User %s does not exist in the database!", user_id)
                return False

    def register_user(
        self,
        user_id: int,
        chat_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ):
        user_dict = {
            "_id": user_id,
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "singers_id": None,
            "shown_concerts_id": None,
            "comedians_id": None,
            "shown_standups_id": None
        }
        if not self.check_if_user_exists(user_id):
            logger.info(f"Registering new user {user_dict}")
            self.user_collection.insert_one(user_dict)

    def create_new_singers_list(self, user_id: int) -> str:
        self.check_if_user_exists(user_id, raise_exception=True)
        singers_id = str(uuid.uuid4())
        singers_dict = {
            "_id": singers_id,
            "singers": [],
        }
        self.singers_collection.insert_one(singers_dict)

        self.user_collection.update_one({"_id": user_id}, {"$set": {"singers_id": singers_id}})
        return singers_id

    def create_new_shown_concerts_list(self, user_id: int) -> str:
        self.check_if_user_exists(user_id, raise_exception=True)
        concerts_id = str(uuid.uuid4())
        concerts_dict = {"_id": concerts_id, "shown_concerts": []}
        self.shown_concerts_collection.insert_one(concerts_dict)

        self.user_collection.update_one({"_id": user_id}, {"$set": {"shown_concerts_id": concerts_id}})
        return concerts_id

    def create_new_comedians_list(self, user_id: int) -> str:
        self.check_if_user_exists(user_id, raise_exception=True)
        comedians_id = str(uuid.uuid4())
        comedians_dict = {"_id": comedians_id, "comedians": []}
        self.comedians_collection.insert_one(comedians_dict)
        self.user_collection.update_one({"_id": user_id}, {"$set": {"comedians_id": comedians_id}})
        return comedians_id

    def create_new_shown_standups_list(self, user_id: int) -> str:
        self.check_if_user_exists(user_id, raise_exception=True)
        standups_id = str(uuid.uuid4())
        standups_dict = {"_id": standups_id, "shown_standups": []}
        self.shown_standups_collection.insert_one(standups_dict)

        self.user_collection.update_one({"_id": user_id}, {"$set": {"shown_standups_id": standups_id}})
        return standups_id


    def fetch_singers(self, user_id: int) -> List[str]:
        self.check_if_user_exists(user_id, raise_exception=True)
        singers_id = self.user_collection.find_one({"_id": user_id})["singers_id"]
        return self.singers_collection.find_one({"_id": singers_id})["singers"]

    def has_singer(self, user_id: int, singer: str) -> bool:
        return singer in self.fetch_singers(user_id)

    def add_singer(self, user_id: int, singer: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        singers_id = self.user_collection.find_one({"_id": user_id})["singers_id"]
        singers = self.singers_collection.find_one({"_id": singers_id})["singers"]
        if singer not in singers:
            singers.append(singer)
            logger.warning("Adding %s to user id %s list of singers", singer, user_id)
            self.singers_collection.update_one({"_id": singers_id}, {"$set": {"singers": singers}})

    def remove_singer(self, user_id: int, singer: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        singers_id = self.user_collection.find_one({"_id": user_id})["singers_id"]
        singers = self.singers_collection.find_one({"_id": singers_id})["singers"]
        if singer in singers:
            singers.remove(singer)
            logger.warning("Removing %s from user id %s list of singers", singer, user_id)
            self.singers_collection.update_one({"_id": singers_id}, {"$set": {"singers": singers}})

    def add_concerts(self, user_id: int, concerts: List[Dict]):
        self.check_if_user_exists(user_id, raise_exception=True)
        concerts_id = self.user_collection.find_one({"_id": user_id})["shown_concerts_id"]
        shown_concerts = self.shown_concerts_collection.find_one({"_id": concerts_id})["shown_concerts"]
        for concert in concerts:
            id = concert["id"]
            if id not in shown_concerts:
                shown_concerts.append(id)
        self.shown_concerts_collection.update_one({"_id": concerts_id}, {"$set": {"shown_concerts": shown_concerts}})

    def shown_concert(self, user_id: int, concert_id: int) -> bool:
        self.check_if_user_exists(user_id, raise_exception=True)
        concerts_id = self.user_collection.find_one({"_id": user_id})["shown_concerts_id"]
        concerts = self.shown_concerts_collection.find_one({"_id": concerts_id})
        return concerts["shown_concerts"] and concert_id in concerts["shown_concerts"]

    def fetch_comedians(self, user_id: int) -> List[str]:
        self.check_if_user_exists(user_id, raise_exception=True)
        comedians_id = self.user_collection.find_one({"_id": user_id})["comedians_id"]
        return self.comedians_collection.find_one({"_id": comedians_id})["comedians"]

    def has_comedian(self, user_id: int, comedian: str) -> bool:
        return comedian in self.fetch_comedians(user_id)

    def add_comedian(self, user_id: int, comedian: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        comedians_id = self.user_collection.find_one({"_id": user_id})["comedians_id"]
        comedians = self.comedians_collection.find_one({"_id": comedians_id})["comedians"]
        if comedian not in comedians:
            comedians.append(comedian)
            logger.warning("Adding %s to user id %s list of comedians", comedian, user_id)
            self.comedians_collection.update_one({"_id": comedians_id}, {"$set": {"comedians": comedians}})

    def remove_comedian(self, user_id: int, comedian: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        comedians_id = self.user_collection.find_one({"_id": user_id})["comedians_id"]
        comedians = self.comedians_collection.find_one({"_id": comedians_id})["comedians"]
        if comedian in comedians:
            comedians.remove(comedian)
            logger.warning("Removing %s from user id %s list of comedians", comedian, user_id)
            self.comedians_collection.update_one({"_id": comedians_id}, {"$set": {"comedians": comedians}})

    def add_standups(self, user_id: int, comedian_name: str, standups: List[Dict]):
        self.check_if_user_exists(user_id, raise_exception=True)
        standups_id = self.user_collection.find_one({"_id": user_id})["shown_standups_id"]
        shown_standups = self.shown_standups_collection.find_one({"_id": standups_id})["shown_standups"]
        for standup in standups:
            standup_date = standup["show_date"]
            id = comedian_name+standup_date
            if id not in shown_standups:
                shown_standups.append(id)
        self.shown_standups_collection.update_one({"_id": standups_id}, {"$set": {"shown_standups": shown_standups}})

    def shown_standup(self, user_id: int, standup_id: str) -> bool:
        self.check_if_user_exists(user_id, raise_exception=True)
        standups_id = self.user_collection.find_one({"_id": user_id})["shown_standups_id"]
        standups = self.shown_standups_collection.find_one({"_id": standups_id})
        return standups["shown_standups"] and standup_id in standups["shown_standups"]
