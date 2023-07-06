import requests
from typing import Dict, List


requests.urllib3.disable_warnings()

API_URL = "https://tickets.kupat.co.il/api/presentations"


def get_concerts() -> List[Dict]:
    resp = requests.get(API_URL, verify=False)
    resp.raise_for_status()
    return resp.json()["presentations"]


def get_concerts_for_artist_name(artist: str) -> List[Dict]:
    concerts = get_concerts()
    concerts_of_artist = []
    for concert in concerts:
        if artist == concert["featureName"]:
            concerts_of_artist.append(concert)
    return concerts_of_artist
