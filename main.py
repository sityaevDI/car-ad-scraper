import asyncio
import random
import re
import time
from urllib.parse import urlparse, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup, Tag
from requests import Response

from mongo.car_repo import CarRepository
from mongo.database import DataBase, get_database
from scraping.car_parser import CarParser, CarAdvShortInfo
from scraping.utilities import default_request_headers, strip_query_parameters, get_soup_from_response, logger


def get_with_retry(url, params=None, **kwargs):
    result: Response = requests.get(url, params, **kwargs)
    time.sleep(random.uniform(0.5, 1.5))
    retries = 5
    while result.status_code != 200:
        result: Response = requests.get(url, params, **kwargs)
        time.sleep(random.uniform(1, 2))
        retries -= 1
    if result.status_code != 200:
        logger.warning(f"Failed to retrieve the page. Page url: %s", url)
    return result


async def scrape_all_pages(car_list_url: str, db_connection: DataBase):
    page, total_cars = 1, 0
    while True:
        updated_url = update_page_number(car_list_url, page)
        response = get_with_retry(updated_url, headers=default_request_headers())
        if response.status_code != 200:
            return
        soup = get_soup_from_response(response)
        total_cars += await scrape_one_search_page(response.text, db_connection)

        from_ad, to_ad, total_ads = await _get_ad_counter(soup)
        if to_ad == total_ads:
            break
        page += 1
    logger.info("Scrape completed. Page scraped: %s, new ads: %s, total ads: %s", page, total_cars, total_ads)
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
    ad_number_pattern = r'/auto-oglasi/(\d+)/'

    ads = soup.find_all('article', class_=lambda x: x and ad_pattern.search(x) and 'uk-hidden' not in x)
    cars_counter = 0
    cars_to_update = []
    for ad in ads:
        link_tag = ad.find('a', class_='firstImage')
        car_link = strip_query_parameters(link_tag['href'])
        img_tag = link_tag.find('img', class_='lazy lead')
        match = re.search(ad_number_pattern, car_link)
        ad_number = int(match.group(1))
        car_info = CarAdvShortInfo(
            ad_number=ad_number,
            ad_link=car_link,
            img_link=img_tag['data-srcset'] if img_tag else None)

        if car_link and not await repo.get_car(ad_number):
            car_url = 'https://www.polovniautomobili.com' + car_link
            response = get_with_retry(car_url, headers=default_request_headers())

            parser = CarParser(car_info, get_soup_from_response(response))
            await repo.save_car(parser.get_car_details())
            cars_counter += 1
        else:
            cars_to_update.append(car_info)

    await repo.update_short_car_info(cars_to_update, db_connection)
    return cars_counter


def update_page_number(url, new_page_number):
    parsed_url = urlparse(url)
    query_parameters = parse_qs(parsed_url.query)
    query_parameters['page'] = [str(new_page_number)]
    query_parameters.pop('tag', None)
    return parsed_url._replace(query=urlencode(query_parameters, doseq=True)).geturl()


async def main():
    search_url = ("https://www.polovniautomobili.com/auto-oglasi/pretraga?brand=&brand2=&price_from=&price_to=8000"
                  "&year_from=&year_to=&fuel%5B%5D=45&fuel%5B%5D=2309&flywheel=&atest=&door_num=&submit_1"
                  "=&without_price=1&date_limit=&showOldNew=all&modeltxt=&engine_volume_from=1600&engine_volume_to"
                  "=&power_from=&power_to=&mileage_from=&mileage_to=&emission_class=&gearbox%5B%5D=3212&gearbox%5B%5D"
                  "=10795&seat_num=&wheel_side=&registration=&country=&country_origin=&city=&damaged%5B%5D=3799"
                  "&registration_price=&appleCarPlay=1&page=&sort=")
    db_connection = await get_database()

    await scrape_all_pages(search_url, db_connection)


if __name__ == "__main__":
    asyncio.run(main())
