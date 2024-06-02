import re
import time
from urllib.parse import urlparse, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

from scraping.car_parser import CarParser
from scraping.utilities import default_request_headers, strip_query_parameters

client = MongoClient('localhost', 27017)
db = client['car_database']
cars_collection = db['cars']
cars_collection.create_index('createdAt', expireAfterSeconds=3 * 24 * 60 * 60)


def save_car(details):
    cars_collection.replace_one(filter={'link': details['link']}, upsert=True, replacement=details)


def scrape_cars(car_list_url: str):
    response = requests.get(car_list_url, headers=default_request_headers)
    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    ad_pattern = re.compile(r'classified ad-\d+.*')
    ads = soup.find_all('article', class_=lambda x: x and ad_pattern.search(x))
    cars_counter = 0
    for ad in ads:
        link_tag = ad.find('a', class_='firstImage')
        car_link = strip_query_parameters(link_tag['href'])
        img_tag = link_tag.find('img', class_='lazy lead')
        img_link = img_tag['data-srcset'] if img_tag else None
        if car_link and not cars_collection.find_one({'link': car_link}):
            parser = CarParser(car_link, img_link)
            save_car(parser.get_car_details())
            time.sleep(0.3)
            cars_counter += 1
    return cars_counter


def update_page_number(url, new_page_number):
    parsed_url = urlparse(url)
    query_parameters = parse_qs(parsed_url.query)
    query_parameters['page'] = [str(new_page_number)]
    return parsed_url._replace(query=urlencode(query_parameters, doseq=True)).geturl()


if __name__ == "__main__":
    # Пример использования

    search_url = (
        "https://www.polovniautomobili.com/auto-oglasi/pretraga?brand=&brand2=&price_from=7000&price_to=8000"
        "&year_from=2010&year_to=&chassis%5B%5D=2631&chassis%5B%5D=278&chassis%5B%5D=2633&chassis%5B%5D=2636&chassis"
        "%5B%5D=2632&fuel%5B%5D=2309&flywheel=&atest=&door_num=3013&submit_1=&without_price=1&date_limit=&showOldNew"
        "=all&modeltxt=&engine_volume_from=1550&engine_volume_to=&power_from=74&power_to=&mileage_from=&mileage_to"
        "=250000&emission_class=&gearbox%5B%5D=10795&seat_num=&wheel_side=2630&air_condition%5B%5D=3159&air_condition"
        "%5B%5D=3160&registration=&country=RS&country_origin=&city=&damaged%5B%5D=3799&registration_price=&airbag=1"
        "&passenger_airbag=1&side_airbag=1&child_lock=1&abs=1&esp=1&asr=1&alarm=1&coded_key=1&engine_blocking=1"
        "&central_locking=1&zeder=1&dead_angle_sensor=1&OBD_protection=1&key_less_entry=1&lane_tracking=1&kneeAirbag"
        "=1&automaticBraking=1&sun_roof=1&page=8&sort=basic")
    for i in range(1, 8):
        updated_url = update_page_number(search_url, i)
        scrape_cars(updated_url.format(page=i))
