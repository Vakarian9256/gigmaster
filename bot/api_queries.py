import requests
from typing import Dict, List
from enum import Enum, auto
import datetime


requests.urllib3.disable_warnings()

KUPAT_API_URL = "https://tickets.kupat.co.il/api/presentations"
LEAAN_API_URL = "https://www.leaan.co.il/feed/events?"
LEAAN_API_MUSIC_URL = f"{LEAAN_API_URL}genreId=9bdf635c-4958-4cb1-a714-94067933ffc3&json"
LEAAN_API_STANDUP_URL = f"{LEAAN_API_URL}genreId=d53b262a-087a-4da3-9c8e-18fe983cc73f&json"
EVENTIM_API_LIVE_SHOWS_URL = "https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__eventim-co-il&categories=%D7%94%D7%95%D7%A4%D7%A2%D7%95%D7%AA%20%D7%97%D7%99%D7%95%D7%AA&sort=DateAsc&in_stock=true"
EVENTIM_API_STANDUP_URL = "https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__eventim-co-il&language=IW&categories=סטנדאפ%20ובידור%7Cסטנדאפ&categories=null&sort=DateAsc&in_stock=true"
COMEDYBAR_API_URL = "https://comedybar.smarticket.co.il/iframe/api/shows"
CASTILIA_API_URL = "https://tickets.castilia.co.il/iframe/api/shows"


def format_datetime(date_str: str, from_format: str, to_format: str) -> str:
    return datetime.datetime.strftime(datetime.datetime.strptime(date_str, from_format), to_format)


def get_eventim_shows(url, standup: bool = False) -> List[Dict]:
    def filter(show):
        standup_filter = {"name": "סטנדאפ ובידור"}
        if standup:
            return standup_filter in show["categories"]
        return standup_filter not in show["categories"]

    events = []
    session = requests.Session()
    headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 OPR/99.0.0.0",
            "accept-encoding": "gzip, deflate, br", "accept-language": "en-US,en;q=0.9",
            "sec-fetch-site": "cross-site", "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty", "sec-ch-ua-platform": "Windows", "sec-cha-ua-mobile": "?0",
            "sec-cha-ua": '"Opera GX";v="99", "Chromium";v="113", "Not-A.Brand";v="24"',
            "origin": "https://www.eventim.co.il", "referer": "https://www.eventim.co.il"
            }
    while True:
        resp = session.get(url, verify=False, headers=headers)
        events.extend(show for show in resp.json()["productGroups"] if filter(show))
        try:
            url = resp.json()["_links"]["next"]["href"].replace("/search/", "/websearch/search/")
        except KeyError:
            break
    return events


def get_kupat_concerts() -> List[Dict]:
    resp = requests.get(KUPAT_API_URL, verify=False)
    resp.raise_for_status()
    presentations = resp.json()["presentations"]
    concerts = []
    for presentation in presentations:
        if not presentation["soldout"]:
            concert = {
                "title": presentation["featureName"],
                "date": format_datetime(presentation["dateTime"], "%Y-%m-%d %H:%M", "%H:%M %d/%m/%Y"),
                "venue": presentation["locationName"],
                "ticketSaleStart": format_datetime(
                    presentation["ticketSaleStart"], "%Y-%m-%d %H:%M:%S", "%H:%M:%S %d/%m/%Y"
                ),
                "ticketSaleStop": format_datetime(
                    presentation["ticketSaleStop"], "%Y-%m-%d %H:%M:%S", "%H:%M:%S %d/%m/%Y"
                ),
                "url": f"https://tickets.kupat.co.il/booking/features/{presentation['featureId']}?prsntId={presentation['id']}#tickets",
            }
            concerts.append(concert)
    return concerts


def get_leaan_concerts() -> List[Dict]:
    resp = requests.get(LEAAN_API_MUSIC_URL, verify=False)
    resp.raise_for_status()
    events = resp.json()["feed"]["Events"]["Event"]
    concerts = []
    for show in events:
        if "false" in show["SoldOut"]:
            concert = {
                "title": show["Show"]["Name"],
                "date": format_datetime(show["FormattedDate"], "%d/%m/%Y %H:%M", "%H:%M %d/%m/%Y"),
                "venue": show["HallName"],
                "ticketSaleStart": show["StartSaleFrom"],
                "ticketSaleStop": format_datetime(show["EndSaleAt"], "%Y-%m-%dT%H:%M:%S", "%H:%M:%S %d/%m/%Y"),
                "url": show["DirectLink"],
            }
            concerts.append(concert)
    return concerts


def get_eventim_concerts(search_term=None) -> List[Dict]:
    concerts = []
    url = EVENTIM_API_LIVE_SHOWS_URL
    if search_term:
        url += f"&search_term={search_term.replace(' ', '%20')}"
    for event in get_eventim_shows(url):
        for show in event["products"]:
            venue = show["typeAttributes"]["liveEntertainment"]["location"]["name"]
            if show["typeAttributes"]["liveEntertainment"]["location"].get("city"):
                venue += ", " + show["typeAttributes"]["liveEntertainment"]["location"].get("city")
            concert = {
                "title": event["name"],
                "date": format_datetime(
                    show["typeAttributes"]["liveEntertainment"]["startDate"],
                    "%Y-%m-%dT%H:%M:%S+%f:00",
                    "%H:%M:%S %d/%m/%Y",
                ),
                "venue": venue,
                "ticketSaleStart": None,
                "ticketSaleStop": None,
                "url": show["link"],
            }
            concerts.append(concert)
    return concerts


def get_concerts(eventim_search_term=None) -> List[Dict]:
    return get_kupat_concerts() + get_leaan_concerts() + get_eventim_concerts(search_term=eventim_search_term)


def get_concerts_for_singer(singer: str) -> List[Dict]:
    concerts = {}
    for concert in get_concerts(eventim_search_term=singer):
        if singer.lower() in concert["title"].lower():
            id = concert["date"]
            if id in concerts:
                concerts[id]["url"].append(concert["url"])
            else:
                concerts[id] = concert
                concert["url"] = [concert["url"]]
    return list(concerts.values())


def get_leaan_standups() -> List[Dict]:
    resp = requests.get(LEAAN_API_STANDUP_URL, verify=False)
    resp.raise_for_status()
    events = resp.json()["feed"]["Events"]["Event"]
    standups = []
    for show in events:
        if "false" in show["SoldOut"]:
            standup = {
                "title": show["Show"]["Name"],
                "date": format_datetime(show["FormattedDate"], "%d/%m/%Y %H:%M", "%H:%M %d/%m/%Y"),
                "venue": show["HallName"],
                "ticketSaleStart": show["StartSaleFrom"],
                "ticketSaleStop": format_datetime(show["EndSaleAt"], "%Y-%m-%dT%H:%M:%S", "%H:%M:%S %d/%m/%Y"),
                "url": show["DirectLink"],
            }
            standups.append(standup)
    return standups


def get_comedybar_standups() -> List[Dict]:
    resp = requests.get(COMEDYBAR_API_URL, verify=False)
    resp.raise_for_status()
    standups = []
    for show in resp.json():
        for event in show["events"]:
            standup = {
                "title": show["title"],
                "url": "https://comedybar.smarticket.co.il/iframe/event" + event["permalink"],
                "date": format_datetime(
                    f"""{event["show_date"]}T{event["show_time"]}""", "%Y-%m-%dT%H:%M", "%H:%M:%S %d/%m/%Y"
                ),
                "venue": event["event_place"],
            }
            standups.append(standup)
    return standups


def get_castilia_standups() -> List[Dict]:
    resp = requests.get(CASTILIA_API_URL, verify=False)
    resp.raise_for_status()
    standups = []
    for show in resp.json():
        for event in show["events"]:
            standup = {
                "title": show["title"],
                "url": "https://castilia.co.il/he/Event/Order?eventId=" + str(event["id"]),
                "date": format_datetime(
                    f"""{event["show_date"]}T{event["show_time"]}""", "%Y-%m-%dT%H:%M", "%H:%M:%S %d/%m/%Y"
                ),
                "venue": event["event_place"],
            }
            standups.append(standup)
    return standups


def get_eventim_standups(search_term=None) -> List[Dict]:
    standups = []
    url = EVENTIM_API_LIVE_SHOWS_URL
    if search_term:
        url += f"&search_term={search_term.replace(' ', '%20')}"
    for event in get_eventim_shows(url, standup=True):
        for show in event["products"]:
            venue = show["typeAttributes"]["liveEntertainment"]["location"]["name"]
            if show["typeAttributes"]["liveEntertainment"]["location"].get("city"):
                venue += ", " + show["typeAttributes"]["liveEntertainment"]["location"].get("city")
            standup = {
                "title": event["name"],
                "date": format_datetime(
                    show["typeAttributes"]["liveEntertainment"]["startDate"],
                    "%Y-%m-%dT%H:%M:%S+%f:00",
                    "%H:%M:%S %d/%m/%Y",
                ),
                "venue": venue,
                "url": show["link"],
            }
            standups.append(standup)
    return standups


def get_standups(eventim_search_term=None) -> List[Dict]:
    return get_castilia_standups() + get_comedybar_standups() +\
            get_eventim_standups(search_term=eventim_search_term) + get_leaan_standups()


def get_standups_for_comedian(comedian: str) -> List[Dict]:
    standups = {}
    for standup in get_standups(eventim_search_term=comedian):
        if comedian in standup["title"]:
            id = standup["date"]
            if id in standups:
                standups[id]["url"].append(standup["url"])
            else:
                standup["url"] = [standup["url"]]
                standups[id] = standup
    return list(standups.values())
