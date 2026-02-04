import requests
from django.conf import settings
from django.utils import timezone

from places.models import Place


def fetch_coordinates_from_api(address):
    apikey = settings.YANDEX_GEOCODER_APIKEY
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None, None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return float(lat), float(lon)


def fetch_coordinates(address):
    place, created = Place.objects.get_or_create(
        address=address,
        defaults={'updated_at': timezone.now()}
    )

    if not created and place.lat is not None and place.lon is not None:
        return place.lat, place.lon

    lat, lon = fetch_coordinates_from_api(address)
    place.lat = lat
    place.lon = lon
    place.updated_at = timezone.now()
    place.save()

    if lat is None:
        return None

    return lat, lon
