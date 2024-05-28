import logging
import re
import time
from datetime import datetime, timezone
from logging import getLogger
from urllib.parse import urlparse, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

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


def get_car_details(car_link, img_link):
    car_url = 'https://www.polovniautomobili.com' + car_link
    response = requests.get(car_url, headers=default_request_headers)
    logger.info("fetched %s page", car_link)
    soup = BeautifulSoup(response.text, 'html.parser')
    classified_content = soup.find('div', {'class': 'classified-content', 'id': 'classified-content'})

    car_info_section = classified_content.find('section', {'class': 'js_fixedContetLoad'})
    price = int(soup.find('span', {"class": re.compile(r"priceClassified\s")})
                .text.strip().split()[0].replace('.', ''))
    year = car_info_section.find(string='Godište').find_next('div').text.strip()
    year = int(year.replace('.', ''))

    mileage = car_info_section.find(string='Kilometraža').find_next('div').text.strip()
    mileage = int(mileage.split()[0].replace('.', ''))

    capacity, unit = car_info_section.find(string='Kubikaža').find_next('div').text.split()
    capacity = int(capacity if unit == 'cm3' else None)

    car_info = {
        'link': car_link,
        'img_src': img_link,
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

    additional_info_section = classified_content.find(string=re.compile(r'Dodatne informacije\s*')).find_next('div')
    car_info.update({
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

    })
    safety_info_section = safe_extract_section(classified_content, re.compile(r'Sigurnost\s*'))
    if safety_info_section:
        safety_features = [feature.text.strip() for feature in
                           safety_info_section.find_all('div', class_='uk-width-medium-1-4')]

        car_info['safety'] = safety_features

    equipment_info_section = safe_extract_section(classified_content, 'Oprema')
    if equipment_info_section:
        equipment_features = [feature.text.strip() for feature in
                              equipment_info_section.find_all('div', class_='uk-width-medium-1-4')]
        car_info['options'] = equipment_features

    condition_info_section = safe_extract_section(classified_content, 'Stanje')
    if condition_info_section:
        condition_features = [feature.text.strip() for feature in
                              condition_info_section.find_all('div', class_='uk-width-medium-1-4')]
        car_info['details'] = condition_features

    description_section = classified_content.find('div', {'id': 'classifiedReplaceDescription'})
    if description_section:
        car_info['description'] = description_section.find('div', class_='description-wrapper').text.strip()

    return car_info


def save_car(details):
    cars_collection.replace_one(filter={'link': details['link']}, upsert=True, replacement=details)


def scrape_cars(url: str):
    response = requests.get(url, headers=default_request_headers)
    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    ad_pattern = re.compile(r'classified ad-\d+')
    ads = soup.find_all('article', class_=lambda x: x and ad_pattern.search(x) and 'ordinaryClassified' in x)
    cars_counter = 0
    for ad in ads:
        link_tag = ad.find('a', class_='firstImage')
        car_link = strip_query_parameters(link_tag['href'])
        img_tag = link_tag.find('img', class_='lazy lead')
        img_link = img_tag['data-srcset'] if img_tag else None
        if car_link and not cars_collection.find_one({'link': car_link}):
            details = get_car_details(car_link, img_link)
            save_car(details)
            time.sleep(0.5)
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
        "https://www.polovniautomobili.com/auto-oglasi/pretraga?page=&sort=basic&price_from=1500&price_to"
        "=6500&year_from=2010&chassis%5B0%5D=277&chassis%5B1%5D=2631&chassis%5B2%5D=278&chassis%5B3%5D"
        "=2636&chassis%5B4%5D=2632&city=Beograd%7C44.820556%7C20.462222&city_distance=75&showOldNew=all"
        "&with_images=1&engine_volume_from=1500&power_from=74&mileage_to=250000&gearbox%5B0%5D=10795"
        "&door_num=3013&damaged%5B0%5D=3799&airbag=1&abs=1&passenger_airbag=1")
    for i in range(1, 8):
        updated_url = update_page_number(search_url, i)
        scrape_cars(updated_url.format(page=i))
