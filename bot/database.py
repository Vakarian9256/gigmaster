from typing import List, Dict
import pymongo
import uuid
import logging

import config


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Database():
    def __init__(self):
        self.client = pymongo.MongoClient(config.mongodb_uri)
        self.db = self.client["gigmaster"]
        logger.info("Initiated client and loaded DB")
        self.user_collection = self.db["users"]
        self.artists_collection = self.db["artists"]
        self.shown_concerts_collection = self.db["shown_concerts"]
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
            last_name: str = ""
            ):
        user_dict = {
                "_id": user_id,
                "chat_id": chat_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "artists_id": None,
                "shown_concerts_id": None
                }
        if not self.check_if_user_exists(user_id):
            logger.info(f"Registering new user {user_dict}")
            self.user_collection.insert_one(user_dict)

    def create_new_artist_list(self, user_id: int) -> str:
        self.check_if_user_exists(user_id, raise_exception=True)
        artists_id = str(uuid.uuid4())
        artists_dict = {
                "_id": artists_id,
                "artists": [],
            }
        self.artists_collection.insert_one(artists_dict)

        self.user_collection.update_one(
                {"_id": user_id},
                {"$set": {"artists_id": artists_id}}
            )
        return artists_id

    def create_new_shown_concerts_list(self, user_id: int) -> str:
        self.check_if_user_exists(user_id, raise_exception=True)
        concerts_id = str(uuid.uuid4())
        concerts_dict = {
                "_id": concerts_id,
                "shown_concerts": []
            }
        self.shown_concerts_collection.insert_one(concerts_dict)

        self.user_collection.update_one(
                {"_id": user_id},
                {"$set": {"shown_concerts_id": concerts_id}}
            )
        return concerts_id

    def fetch_artists(self, user_id: int) -> List[str]:
        self.check_if_user_exists(user_id, raise_exception=True)
        artists_id = self.user_collection.find_one({"_id": user_id})["artists_id"]
        return self.artists_collection.find_one({"_id": artists_id})["artists"]

    def has_artist(self, user_id: int, artist: str) -> bool:
        return artist in self.fetch_artists(user_id)

    def add_artist(self, user_id: int, artist: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        artists_id = self.user_collection.find_one({"_id": user_id})["artists_id"]
        artists = self.artists_collection.find_one({"_id": artists_id})["artists"]
        if artist not in artists:
            artists.append(artist)
            logger.warning("Adding %s to user id %s list of artists", artist, user_id)
            self.artists_collection.update_one(
                    {"_id": artists_id},
                    {"$set": {"artists": artists}}
                )

    def remove_artist(self, user_id: int, artist: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        artists_id = self.user_collection.find_one({"_id": user_id})["artists_id"]
        artists = self.artists_collection.find_one({"_id": artists_id})["artists"]
        if artist in artists:
            artists.remove(artist)
            logger.warning("Removing %s from user id %s list of artists", artist, user_id)
            self.artists_collection.update_one(
                    {"_id": artists_id},
                    {"$set": {"artists": artists}}
                )

    def add_concerts(self, user_id: int, concerts: List[Dict]):
        self.check_if_user_exists(user_id, raise_exception=True)
        concerts_id = self.user_collection.find_one({"_id": user_id})["shown_concerts_id"]
        shown_concerts = self.shown_concerts_collection.find_one({"_id": concerts_id})["shown_concerts"]
        for concert in concerts:
            id = concert["id"]
            if id not in shown_concerts:
                shown_concerts.append(id)
        self.shown_concerts_collection.update_one(
                {"_id": concerts_id},
                {"$set": {"shown_concerts": shown_concerts}}
            )

    def shown_concert(self, user_id: int, concert_id: int) -> bool:
        self.check_if_user_exists(user_id, raise_exception=True)
        concerts_id = self.user_collection.find_one({"_id": user_id})["shown_concerts_id"]
        concerts = self.shown_concerts_collection.find_one({"_id": concerts_id})
        return concerts["shown_concerts"] and concert_id in concerts["shown_concerts"]
