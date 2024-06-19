import asyncio
import datetime
import re
import time
from math import ceil
from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode
import random

import requests
from bs4 import BeautifulSoup, Tag
from pymongo import UpdateOne

from mongo.car_repo import CarRepository
from mongo.database import DataBase, get_database
from scraping.car_parser import CarParser, CarAdvShortInfo
from scraping.utilities import default_request_headers, strip_query_parameters, get_soup_from_response


async def scrape_all_pages(car_list_url: str, db_connection: DataBase):
    page, total_cars = 1, 0
    while True:
        updated_url = update_page_number(car_list_url, page)
        response = requests.get(updated_url, headers=default_request_headers())
        if response.status_code != 200:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
            return
        soup = get_soup_from_response(response)
        total_cars += await scrape_one_search_page(response.text, db_connection)

        from_ad, to_ad, total_ads = await _get_ad_counter(soup)
        if to_ad == total_ads:
            break
        page += 1
    return total_cars


async def _get_ad_counter(soup: Tag) -> tuple[int, int, int]:
    text = soup.find(class_='js-hide-on-filter').find_next('small').text
    pattern = r'\d+'
    numbers = re.findall(pattern, text)
    from_ad = int(numbers[0])
    to_ad = int(numbers[1])
    total_ads = int(numbers[2])
    return from_ad, to_ad, total_ads


async def scrape_one_search_page(response_text, db_connection):
    repo = CarRepository(db_connection)
    soup = BeautifulSoup(response_text, 'html.parser')
    ad_pattern = re.compile(r'classified ad-\d+.*')
    ads = soup.find_all('article', class_=lambda x: x and ad_pattern.search(x) and 'uk-hidden' not in x)
    cars_counter = 0
    for ad in ads:
        link_tag = ad.find('a', class_='firstImage')
        car_link = strip_query_parameters(link_tag['href'])
        img_tag = link_tag.find('img', class_='lazy lead')
        if car_link and not await repo.get_car(car_link):
            car_url = 'https://www.polovniautomobili.com' + car_link
            response = requests.get(car_url, headers=default_request_headers())
            if not response.status_code == 200:
                time.sleep(random.uniform(0.5, 1.5))
                response = requests.get(car_url, headers=default_request_headers())

            parser = CarParser(CarAdvShortInfo(
                ad_link=car_link,
                img_link=img_tag['data-srcset'] if img_tag else None,
            ), get_soup_from_response(response))
            await repo.save_car(parser.get_car_details())
            time.sleep(random.uniform(0.5, 1.5))

            cars_counter += 1
    return cars_counter


def update_page_number(url, new_page_number):
    parsed_url = urlparse(url)
    query_parameters = parse_qs(parsed_url.query)
    query_parameters['page'] = [str(new_page_number)]
    return parsed_url._replace(query=urlencode(query_parameters, doseq=True)).geturl()


async def main():
    search_url = ("https://www.polovniautomobili.com/auto-oglasi/pretraga?brand=&brand2=&price_from=&price_to=8000"
                  "&year_from=&year_to=&fuel%5B%5D=45&fuel%5B%5D=2309&flywheel=&atest=&door_num=&submit_1"
                  "=&without_price=1&date_limit=&showOldNew=all&modeltxt=&engine_volume_from=1600&engine_volume_to"
                  "=&power_from=&power_to=&mileage_from=&mileage_to=&emission_class=&gearbox%5B%5D=3212&gearbox%5B%5D"
                  "=10795&seat_num=&wheel_side=&registration=&country=&country_origin=&city=&damaged%5B%5D=3799"
                  "&registration_price=&appleCarPlay=1&page=&sort=")
    db_connection = await get_database()

    await scrape_pipe(search_url)


if __name__ == "__main__":
    asyncio.run(main())
