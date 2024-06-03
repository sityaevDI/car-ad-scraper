import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from scraping.translation import safety_features_translation, additional_options_translation, \
    condition_translation
from scraping.utilities import safe_extract_section, safe_extract_text, default_request_headers, logger


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

        soup, classified_content, retries = None, None, 3

        while classified_content is None:
            soup = self.request_car_html()
            classified_content = soup.find('div', {'class': 'classified-content', 'id': 'classified-content'})
            if not classified_content:
                retries -= 1
                if retries == 0:
                    return None

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

        power = car_info_section.find(string='Snaga motora').find_next('div').text.strip()
        power = int(power.split('/')[0])

        make = ' '.join(str.capitalize(m) for m in
                        car_info_section.find(string='Marka').find_next('div').text.split('-'))
        model = ' '.join(str.capitalize(m) for m in
                         car_info_section.find(string='Model').find_next('div').text.split('-'))
        basic_car_info = {
            'make': make,
            'model': model,
            'condition': car_info_section.find(string='Stanje:').find_next('div').text.strip(),
            'year': year,
            'mileage': mileage,
            'body_type': car_info_section.find(string='Karoserija').find_next('div').text.strip(),
            'fuel_type': car_info_section.find(string='Gorivo').find_next('div').text.strip(),
            'engine_capacity': capacity,
            'engine_power': power,
            'fixed_price': car_info_section.find(string='Fiksna cena').find_next('div').text.strip(),
            'price': price,
            'exchange': car_info_section.find(string='Zamena:').find_next('div').text.strip(),
            'ad_number': car_info_section.find(string='Broj oglasa:').find_next('div').text.strip(),
            'createdAt': datetime.now(timezone.utc)
        }
        return basic_car_info
