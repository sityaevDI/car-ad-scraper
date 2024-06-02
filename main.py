import logging
import re
import time
from datetime import datetime, timezone
from logging import getLogger
from urllib.parse import urlparse, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

from scraping.translation import safety_features_translation, additional_options_translation, \
    condition_translation

logger = getLogger("scraper")
logger.setLevel(logging.DEBUG)

client = MongoClient('localhost', 27017)
db = client['car_database']
cars_collection = db['cars']
cars_collection.create_index('createdAt', expireAfterSeconds=3 * 24 * 60 * 60)

default_request_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                  ' Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1'
}


def safe_extract_text(section, label: str):
    element = section.find(string=re.compile(rf'{label}\s*:?\s*'))
    if element:
        return element.find_next('div').text.strip()
    return None


def safe_extract_section(section, label):
    element = section.find(string=re.compile(rf'{label}\s*:?\s*'))
    if element:
        return element.find_next('div')
    return None


def strip_query_parameters(url):
    parsed_url = urlparse(url)
    return parsed_url.path


class CarParser:

    def __init__(self, car_link: str, image_link: str):
        self.car_info = {
            'link': car_link,
            'img_src': image_link,
        }
        self.car_link = car_link
        self.image_link = image_link
        self.car_url = 'https://www.polovniautomobili.com' + car_link

    def request_car_html(self):
        response = requests.get(self.car_url, headers=default_request_headers)
        logger.info("fetched %s page", self.car_link)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup

    def get_car_details(self):
        soup = self.request_car_html()
        classified_content = soup.find('div', {'class': 'classified-content', 'id': 'classified-content'})

        basic_car_info = self._get_basic_car_info(classified_content, soup)
        self.car_info.update(basic_car_info)

        additional_car_info = self._get_additional_info(classified_content)
        self.car_info.update(additional_car_info)

        safety_features = self._get_safety_features(classified_content)
        self.car_info["safety"] = safety_features

        equipment_features = self._get_options(classified_content)
        self.car_info['options'] = equipment_features

        condition_features = self._get_condition(classified_content)
        self.car_info['details'] = condition_features

        description_section = classified_content.find('div', {'id': 'classifiedReplaceDescription'})
        if description_section:
            basic_car_info['description'] = description_section.find('div', class_='description-wrapper').text.strip()

        return self.car_info

    @staticmethod
    def _get_condition(classified_content) -> list[str]:
        condition_info_section = safe_extract_section(classified_content, 'Stanje')
        if not condition_info_section:
            return []
        condition_features = [condition_translation.get(feature.text.strip()) for feature in
                              condition_info_section.find_all('div', class_='uk-width-medium-1-4')]
        return condition_features

    def _get_options(self, classified_content) -> list[str]:
        equipment_info_section = safe_extract_section(classified_content, 'Oprema')
        if not equipment_info_section:
            return []
        equipment_features = [additional_options_translation.get(feature.text.strip()) for feature in
                              equipment_info_section.find_all('div', class_='uk-width-medium-1-4')]
        return equipment_features

    @staticmethod
    def _get_safety_features(classified_content) -> list[str]:
        safety_info_section = safe_extract_section(classified_content, 'Sigurnost')
        if not safety_info_section:
            return []
        safety_features = [safety_features_translation.get(feature.text.strip()) for feature in
                           safety_info_section.find_all('div', class_='uk-width-medium-1-4')]
        return safety_features

    @staticmethod
    def _get_additional_info(classified_content):
        additional_info_section = classified_content.find(string=re.compile(r'Dodatne informacije\s*')).find_next('div')
        additional_car_info = {
            'emission_class': additional_info_section.find(string='Emisiona klasa motora').find_next(
                'div').text.strip(),
            'drive': additional_info_section.find(string='Pogon').find_next('div').text.strip(),
            'transmission': additional_info_section.find(string='Menjač').find_next('div').text.strip(),
            'doors': additional_info_section.find(string='Broj vrata').find_next('div').text.strip(),
            'seats': additional_info_section.find(string='Broj sedišta').find_next('div').text.strip(),
            'steering_side': additional_info_section.find(string='Strana volana').find_next('div').text.strip(),
            'climate_control': additional_info_section.find(string='Klima').find_next('div').text.strip(),
            'color': additional_info_section.find(string='Boja').find_next('div').text.strip(),
            'interior_material': safe_extract_text(additional_info_section, 'Materijal enterijera'),
            'interior_color': safe_extract_text(additional_info_section, 'Boja enterijera'),
            'registered_until': additional_info_section.find(string='Registrovan do').find_next('div').text.strip(),
            'origin': additional_info_section.find(string='Poreklo vozila').find_next('div').text.strip(),
            'damage': additional_info_section.find(string='Oštećenje').find_next('div').text.strip(),
            'import_country': safe_extract_text(additional_info_section, 'Zemlja uvoza'),
            'sale_method': safe_extract_text(additional_info_section, 'Način prodaje')

        }
        return additional_car_info

    @staticmethod
    def _get_basic_car_info(classified_content, soup):
        car_info_section = classified_content.find('section', {'class': 'js_fixedContetLoad'})
        price = int(soup.find('span', {"class": re.compile(r"priceClassified\s")})
                    .text.strip().split()[0].replace('.', ''))

        year = car_info_section.find(string='Godište').find_next('div').text.strip()
        year = int(year.replace('.', ''))

        mileage = car_info_section.find(string='Kilometraža').find_next('div').text.strip()
        mileage = int(mileage.split()[0].replace('.', ''))

        capacity, unit = car_info_section.find(string='Kubikaža').find_next('div').text.split()
        capacity = int(capacity if unit == 'cm3' else None)

        basic_car_info = {
            'condition': car_info_section.find(string='Stanje:').find_next('div').text.strip(),
            'make': car_info_section.find(string='Marka').find_next('div').text.strip(),
            'model': car_info_section.find(string='Model').find_next('div').text.strip(),
            'year': year,
            'mileage': mileage,
            'body_type': car_info_section.find(string='Karoserija').find_next('div').text.strip(),
            'fuel_type': car_info_section.find(string='Gorivo').find_next('div').text.strip(),
            'engine_capacity': capacity,
            'engine_power': car_info_section.find(string='Snaga motora').find_next('div').text.strip(),
            'fixed_price': car_info_section.find(string='Fiksna cena').find_next('div').text.strip(),
            'price': price,
            'exchange': car_info_section.find(string='Zamena:').find_next('div').text.strip(),
            'ad_number': car_info_section.find(string='Broj oglasa:').find_next('div').text.strip(),
            'createdAt': datetime.now(timezone.utc)
        }
        return basic_car_info


def save_car(details):
    cars_collection.replace_one(filter={'link': details['link']}, upsert=True, replacement=details)


def scrape_cars(url: str):
    response = requests.get(url, headers=default_request_headers)
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
