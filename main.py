import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient

client = MongoClient('localhost', 27017)
db = client['car_database']
cars_collection = db['cars']


def safe_extract_text(section, label: str):
    element = section.find(string=re.compile(rf'{label}\s*:'))
    if element:
        return element.find_next('div').text.strip()
    return None


def safe_extract_section(section, label):
    element = section.find(string=re.compile(rf'{label}\s*:'))
    if element:
        return element.find_next('div')
    return None


def strip_query_parameters(url):
    parsed_url = urlparse(url)
    return parsed_url.path


def get_car_details(car_link, headers):
    car_url = 'https://www.polovniautomobili.com' + car_link
    response = requests.get(car_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    classified_content = soup.find('div', {'class': 'classified-content', 'id': 'classified-content'})

    car_info_section = classified_content.find('section', {'class': 'js_fixedContetLoad'})
    car_info = {
        'link': car_link,
        'condition': car_info_section.find(string='Stanje:').find_next('div').text.strip(),
        'make': car_info_section.find(string='Marka').find_next('div').text.strip(),
        'Model': car_info_section.find(string='Model').find_next('div').text.strip(),
        'year': car_info_section.find(string='Godište').find_next('div').text.strip(),
        'mileage': car_info_section.find(string='Kilometraža').find_next('div').text.strip(),
        'body_type': car_info_section.find(string='Karoserija').find_next('div').text.strip(),
        'fuel_type': car_info_section.find(string='Gorivo').find_next('div').text.strip(),
        'engine_capacity': car_info_section.find(string='Kubikaža').find_next('div').text.strip(),
        'engine_power': car_info_section.find(string='Snaga motora').find_next('div').text.strip(),
        'price': car_info_section.find(string='Fiksna cena').find_next('div').text.strip(),
        'exchange': car_info_section.find(string='Zamena:').find_next('div').text.strip(),
        'ad_number': car_info_section.find(string='Broj oglasa:').find_next('div').text.strip()
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
        'interior_material': additional_info_section.find(string='Materijal enterijera').find_next('div').text.strip(),
        'interior_color': safe_extract_text(additional_info_section, 'Boja enterijera'),
        'registered_until': additional_info_section.find(string='Registrovan do').find_next('div').text.strip(),
        'origin': additional_info_section.find(string='Poreklo vozila').find_next('div').text.strip(),
        'damage': additional_info_section.find(string='Oštećenje').find_next('div').text.strip(),
        'import_country': safe_extract_text(additional_info_section, 'Zemlja uvoza')
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
    if not cars_collection.find_one({'link': details['link']}):
        cars_collection.insert_one(details)


def scrape_cars(url, headers):
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    # Предполагается, что объявления находятся в тегах с классом 'car-ad'
    ad_pattern = re.compile(r'classified ad-\d+')
    ads = soup.find_all('article', class_=lambda x: x and ad_pattern.search(x) and 'ordinaryClassified' in x)
    for ad in ads:
        link_tag = ad.find('a', class_='firstImage')
        car_link = strip_query_parameters(link_tag['href'])
        if link_tag:
            if not cars_collection.find_one({'link': car_link}):
                details = get_car_details(car_link, headers)
                save_car(details)
                time.sleep(2)


def get_unique_options():
    pipeline = [
        {"$unwind": "$parameters.options"},
        {"$group": {"_id": None, "uniqueOptions": {"$addToSet": "$parameters.options"}}},
        {"$project": {"_id": 0, "uniqueOptions": 1}}
    ]

    result = list(cars_collection.aggregate(pipeline))
    if result:
        return result[0]['uniqueOptions']
    else:
        return []


if __name__ == "__main__":
    # Пример использования
    r_headers = {
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

    search_url = (r'https://www.polovniautomobili.com/auto-oglasi/pretraga?brand=audi&brand2=&price_from=&price_to=5000'
                  r'&year_from=2010&year_to=&fuel%5B%5D=2309&flywheel=&atest=&door_num=&submit_1=&without_price=1&date_limit'
                  r'=&showOldNew=all&modeltxt=&engine_volume_from=&engine_volume_to=&power_from=&power_to=&mileage_from'
                  r'=&mileage_to=&emission_class=&seat_num=&wheel_side=&registration=&country=&country_origin=&city'
                  r'=&registration_price=&page=&sort=')
    scrape_cars(search_url, r_headers)
    unique_options = get_unique_options()
    print(unique_options)
