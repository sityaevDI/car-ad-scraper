import re
from datetime import datetime, timezone
from typing import Optional

from bs4 import Tag
from pydantic import BaseModel

from scraping.translation import safety_features_translation, additional_options_translation, \
    condition_translation
from scraping.utilities import safe_extract_section, safe_extract_text


class CarAdvShortInfo(BaseModel):
    ad_number: Optional[int] = 0
    ad_link: str
    img_link: Optional[str]


class CarParser:

    def __init__(self, car_ad: CarAdvShortInfo, soup: Tag):
        self.car_info = {
            'link': car_ad.ad_link,
            'img_src': car_ad.img_link,
            'ad_number': car_ad.ad_number
        }
        self.car_ad = car_ad
        self.soup = soup

    def get_car_details(self):
        soup = self.soup
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

        if description_section := classified_content.find('div', {'id': 'classifiedReplaceDescription'}):
            basic_car_info['description'] = description_section.find('div', class_='description-wrapper').text.strip()

        return self.car_info

    @staticmethod
    def _get_condition(classified_content) -> list[str]:
        if not (condition_info_section := safe_extract_section(classified_content, 'Stanje')):
            return []
        return [condition_translation.get(feature.text.strip()) for feature in
                condition_info_section.find_all('div', class_='uk-width-medium-1-4')]

    @staticmethod
    def _get_options(classified_content) -> list[str]:
        if not (equipment_info_section := safe_extract_section(classified_content, 'Oprema')):
            return []
        return [additional_options_translation.get(feature.text.strip()) for feature in
                equipment_info_section.find_all('div', class_='uk-width-medium-1-4')]

    @staticmethod
    def _get_safety_features(classified_content) -> list[str]:
        if not (safety_info_section := safe_extract_section(classified_content, 'Sigurnost')):
            return []
        return [safety_features_translation.get(feature.text.strip()) for feature in
                safety_info_section.find_all('div', class_='uk-width-medium-1-4')]

    @staticmethod
    def _get_additional_info(classified_content):
        additional_info_section = classified_content.find(string=re.compile(r'Dodatne informacije\s*')).find_next('div')
        additional_car_info = {
            'emission_class': safe_extract_text(additional_info_section, 'Emisiona klasa motora'),
            'drive': additional_info_section.find(string='Pogon').find_next('div').text.strip(),
            'transmission': additional_info_section.find(string='Menjač').find_next('div').text.strip(),
            'doors': safe_extract_text(additional_info_section, 'Broj vrata'),
            'seats': additional_info_section.find(string='Broj sedišta').find_next('div').text.strip(),
            'steering_side': additional_info_section.find(string='Strana volana').find_next('div').text.strip(),
            'climate_control': additional_info_section.find(string='Klima').find_next('div').text.strip(),
            'color': additional_info_section.find(string='Boja').find_next('div').text.strip(),
            'interior_material': safe_extract_text(additional_info_section, 'Materijal enterijera'),
            'interior_color': safe_extract_text(additional_info_section, 'Boja enterijera'),
            'registered_until': safe_extract_text(additional_info_section, 'Registrovan do'),
            'origin': additional_info_section.find(string='Poreklo vozila').find_next('div').text.strip(),
            'damage': additional_info_section.find(string='Oštećenje').find_next('div').text.strip(),
            'import_country': safe_extract_text(additional_info_section, 'Zemlja uvoza'),
            'sale_method': safe_extract_text(additional_info_section, 'Način prodaje'),
        }
        if bat_rng := safe_extract_text(additional_info_section, 'Domet sa punom baterijom (km)'):
            additional_car_info['battery_range'] = int(bat_rng)
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

        if capacity_tag := car_info_section.find(string='Kubikaža'):
            capacity, unit = capacity_tag.find_next('div').text.split()
            capacity = int(capacity if unit == 'cm3' else None)
        else:
            capacity = 0

        power = car_info_section.find(string='Snaga motora').find_next('div').text.strip()
        power = int(power.split('/')[0])

        make = ' '.join(str.capitalize(m) for m in
                        re.split('[- ]', car_info_section.find(string='Marka').find_next('div').text))
        model = ' '.join(str.capitalize(m) for m in
                         re.split('[- ]', car_info_section.find(string='Model').find_next('div').text))
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
            'ad_number': int(car_info_section.find(string='Broj oglasa:').find_next('div').text.strip()),
            'createdAt': datetime.now(timezone.utc),
            'updatedAt': datetime.now(timezone.utc)
        }
        return basic_car_info
