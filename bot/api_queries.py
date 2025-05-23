import datetime
import logging
import ssl
import urllib3

import requests


requests.urllib3.disable_warnings()


logger = logging.getLogger("gigmaster.api")


KUPAT_API_URL = "https://tickets.kupat.co.il/api/presentations"
LEAAN_API_URL = "https://www.leaan.co.il/feed/events?"
LEAAN_API_MUSIC_URL = f"{LEAAN_API_URL}genreId=9bdf635c-4958-4cb1-a714-94067933ffc3&json"
LEAAN_API_STANDUP_URL = f"{LEAAN_API_URL}genreId=d53b262a-087a-4da3-9c8e-18fe983cc73f&json"
EVENTIM_API_LIVE_SHOWS_URL = "https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__eventim-co-il&categories=%D7%94%D7%95%D7%A4%D7%A2%D7%95%D7%AA%20%D7%97%D7%99%D7%95%D7%AA&sort=DateAsc&in_stock=true"
EVENTIM_API_STANDUP_URL = "https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__eventim-co-il&language=IW&categories=סטנדאפ%20ובידור%7Cסטנדאפ&categories=null&sort=DateAsc&in_stock=true"
COMEDYBAR_API_URL = "https://comedybar.smarticket.co.il/iframe/api/shows"
CASTILIA_API_URL = "https://tickets.castilia.co.il/iframe/api/shows"
TICKETMASTER_API_URL = "https://www.ticketmaster.co.il/wbtxapi/api/v1/bxcached/event/getAllTopEvent/iw"


def format_datetime(date_str: str, from_format: str, to_format: str) -> str:
    return datetime.datetime.strftime(datetime.datetime.strptime(date_str, from_format), to_format)


def get_eventim_shows(url, standup: bool = False) -> list[dict[str, str]]:
    def filter(show):
        standup_filter = {"name": "סטנדאפ ובידור"}
        if standup:
            return standup_filter in show["categories"]
        return standup_filter not in show["categories"]

    events = []
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 OPR/99.0.0.0",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.9",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "sec-ch-ua-platform": "Windows",
        "sec-cha-ua-mobile": "?0",
        "sec-cha-ua": '"Opera GX";v="99", "Chromium";v="113", "Not-A.Brand";v="24"',
        "origin": "https://www.eventim.co.il",
        "referer": "https://www.eventim.co.il",
    }
    while True:
        resp = session.get(url, verify=False, headers=headers)
        try:
            events.extend(show for show in resp.json()["productGroups"] if filter(show))
            url = resp.json()["_links"]["next"]["href"].replace("/search/", "/websearch/search/")
        except (KeyError, requests.exceptions.RequestException):
            break
    return events


def get_kupat_concerts() -> list[dict[str, str]]:
    concerts = []
    try:
        resp = requests.get(KUPAT_API_URL, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to query kupat tlv")
    else:
        presentations = resp.json()["presentations"]
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


def get_leaan_concerts() -> list[dict[str, str]]:
    concerts = []
    try:
        resp = requests.get(LEAAN_API_MUSIC_URL, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to query concerts from leaan")
    else:
        events = resp.json()["feed"]["Events"]["Event"]
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


def get_eventim_concerts(search_term=None) -> list[dict[str, str]]:
    concerts = []
    url = EVENTIM_API_LIVE_SHOWS_URL
    if search_term:
        url += f"&search_term={search_term.replace(' ', '%20')}"
    try:
        available_concerts = get_eventim_shows(url)
    except Exception:
        logger.exception("Failed to query concerts from eventim")
    else:
        for event in available_concerts:
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


def get_ticketmaster_concerts() -> list[dict[str, str]]:
    class CustomHttpAdapter(requests.adapters.HTTPAdapter):
        # "Transport adapter" that allows us to use custom ssl_context.

        def __init__(self, ssl_context=None, **kwargs):
            self.ssl_context = ssl_context
            super().__init__(**kwargs)

        def init_poolmanager(self, connections, maxsize, block=False):
            self.poolmanager = urllib3.poolmanager.PoolManager(
                num_pools=connections, maxsize=maxsize, block=block, ssl_context=self.ssl_context
            )

    def get_legacy_session():
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        session = requests.session()
        session.mount("https://", CustomHttpAdapter(ctx))
        return session

    concerts = []
    try:
        resp = get_legacy_session().get(TICKETMASTER_API_URL)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to query ticketmaster")
    else:
        for concert in resp.json()["data"]:
            venue = concert["venueCity"]
            if concert["venueName"]:
                venue += " " + concert["venueName"].strip()
            concerts.append(
                {
                    "title": concert["eventName"] or concert["eventGroupName"],
                    "date": datetime.datetime.fromtimestamp(concert["firstPerformanceDate"] / 1000).strftime(
                        "%H:%M:%S %d/%m/%Y"
                    )
                    if concert["firstPerformanceDate"]
                    else None,
                    "venue": venue,
                    "ticketSaleSart": None,
                    "ticketSaleStop": None,
                    "url": concert["customUrl"] or f"https://ticketmaster.co.il/event/{concert['btxEventId']}/ALL/iw",
                }
            )
    return concerts


def get_concerts(eventim_search_term=None) -> list[dict[str, str]]:
    return (
        get_kupat_concerts()
        + get_leaan_concerts()
        + get_eventim_concerts(search_term=eventim_search_term)
        + get_ticketmaster_concerts()
    )


def get_concerts_for_singer(singer: str) -> list[dict[str, str]]:
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


def get_leaan_standups() -> list[dict[str, str]]:
    standups = []
    try:
        resp = requests.get(LEAAN_API_STANDUP_URL, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to query leaan")
    else:
        events = resp.json()["feed"]["Events"]["Event"]
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


def get_comedybar_standups() -> list[dict[str, str]]:
    standups = []
    try:
        resp = requests.get(COMEDYBAR_API_URL, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to query ComedyBar")
    else:
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


def get_castilia_standups() -> list[dict[str, str]]:
    standups = []
    try:
        resp = requests.get(CASTILIA_API_URL, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to query Castilia")
    else:
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


def get_eventim_standups(search_term=None) -> list[dict[str, str]]:
    standups = []
    url = EVENTIM_API_LIVE_SHOWS_URL
    if search_term:
        url += f"&search_term={search_term.replace(' ', '%20')}"
    try:
        events = get_eventim_shows(url, standup=True)
    except Exception:
        logger.exception("Failed to query eventim API")
    else:
        for event in events:
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


def get_standups(eventim_search_term=None) -> list[dict[str, str]]:
    return (
        get_castilia_standups()
        + get_comedybar_standups()
        + get_eventim_standups(search_term=eventim_search_term)
        + get_leaan_standups()
    )


def get_standups_for_comedian(comedian: str) -> list[dict[str, str]]:
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
