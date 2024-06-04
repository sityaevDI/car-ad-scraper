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


async def scrape_all_pages(car_list_url: str):
    page, total_cars = 1, 0
    while True:
        updated_url = update_page_number(car_list_url, page)
        response = requests.get(updated_url, headers=default_request_headers)
        if response.status_code != 200:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        total_cars += scrape_one_search_page(response.text)

        text = soup.find(class_='js-hide-on-filter').find_next('small').text
        pattern = r'\d+'
        numbers = re.findall(pattern, text)
        to_ad = int(numbers[1])
        total_ads = int(numbers[2])
        if to_ad == total_ads:
            break
        page += 1


def scrape_cars(car_list_url: str):
    response = requests.get(car_list_url, headers=default_request_headers)
    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return
    return scrape_one_search_page(response.text)


def scrape_one_search_page(response_text):
    soup = BeautifulSoup(response_text, 'html.parser')
    ad_pattern = re.compile(r'classified ad-\d+.*')
    ads = soup.find_all('article', class_=lambda x: x and ad_pattern.search(x) and 'uk-hidden' not in x)
    cars_counter = 0
    for ad in ads:
        link_tag = ad.find('a', class_='firstImage')
        car_link = strip_query_parameters(link_tag['href'])
        img_tag = link_tag.find('img', class_='lazy lead')
        img_link = img_tag['data-srcset'] if img_tag else None
        if car_link and not cars_collection.find_one({'link': car_link}):
            parser = CarParser(car_link, img_link)
            save_car(parser.get_car_details())
            time.sleep(0.2)
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
        "https://www.polovniautomobili.com/auto-oglasi/pretraga?brand=&brand2=&price_from=1000&price_to=2000&year_from"
        "=2005&year_to=&flywheel=&atest=&door_num=&submit_1=&without_price=1&date_limit=&showOldNew=all&modeltxt"
        "=&engine_volume_from=&engine_volume_to=&power_from=&power_to=&mileage_from=&mileage_to=&emission_class"
        "=&seat_num=3197&wheel_side=&registration=&country=&country_origin=&city=&registration_price=&page=2&sort=basic")
    scrape_all_pages(search_url)
