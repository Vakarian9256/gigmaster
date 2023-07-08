import requests
from typing import Dict, List


requests.urllib3.disable_warnings()

KUPAT_API_URL = "https://tickets.kupat.co.il/api/presentations"
COMEDYBAR_API_URL = "https://comedybar.smarticket.co.il/iframe/api/shows"
CASTILIA_API_URL = "https://tickets.castilia.co.il/iframe/api/shows"


"""
Relevant information about JSON structure:
{
    "presentations": [
        {
            "id": int,  // unique identifier of concert
            "dateTime": str, // datetime object as string
            "featureName": str, // name of artist
            "featureId": int, // unique identifier of artist
            "locationName": str, // which venue the concert is at
            "ticketsSaleStart": str, // when tickets start selling
            "ticketSaleStop": str // when tickets stop selling
            }
        ]
}
"""


def get_concerts() -> List[Dict]:
    resp = requests.get(KUPAT_API_URL, verify=False)
    resp.raise_for_status()
    return resp.json()["presentations"]


def get_concerts_for_artist_name(artist: str) -> List[Dict]:
    concerts = get_concerts()
    concerts_of_artist = []
    for concert in concerts:
        if artist == concert["featureName"]:
            concerts_of_artist.append(concert)
    return concerts_of_artist


"""
Relevant information about JSON structure:
{
    {
        "id": int // id of show
        "title": str, // name of show
        "url", str // endpoint of show
        "events": { // list of events of show
                "id": int, // id of event
                "tickets_available": bool, // are tickets available
                "visibility": bool, // is event visible to users
                "show_date": str, // date of event
                "show_time": str, // H:M:S time of event
                "event_place": str, // location of event
                "permalink": str // endpoint of event
            }
    }
}
"""


def get_comedybar_standups() -> List[Dict]:
    resp = requests.get(COMEDYBAR_API_URL, verify=False)
    resp.raise_for_status()
    return resp.json()


"""
Relevant information about JSON structure:
{
    {
        "id": int // id of show
        "title": str, // name of show
        "url", str // endpoint of show
        "events": { // list of events of show
                "id": int, // id of event
                "tickets_available": bool, // are tickets available
                "visibility": bool, // is event visible to users
                "show_date": str, // date of event
                "show_time": str, // H:M:S time of event
                "event_place": str, // location of event
                "permalink": str // endpoint of event
            }
    }
}
"""


def get_castilia_standups() -> List[Dict]:
    resp = requests.get(CASTILIA_API_URL, verify=False)
    resp.raise_for_status()
    return resp.json()
