import math
import os
import re
from typing import List
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from scraping.car_parser import CarAdvShortInfo
from scraping.utilities import default_request_headers


# --- основной парсер/класс ---
class PolovniAutoParser:
    # Если нужно изменить — передай page_size
    def __init__(self, page_size: int = 25, timeout: int = 15):
        self.page_size = page_size
        self.timeout = timeout
        self.session = requests.Session()
        self._maybe_setup_residential_proxy()

    def _maybe_setup_residential_proxy(self):
        host = os.getenv("RESIDENTIAL_PROXY_HOST")
        port = os.getenv("RESIDENTIAL_PROXY_PORT")
        user = os.getenv("RESIDENTIAL_PROXY_USER")
        pwd = os.getenv("RESIDENTIAL_PROXY_PWD")

        if host and port:
            if user and pwd:
                auth_part = f"{user}:{pwd}@"
            else:
                auth_part = ""
            proxy_url = f"http://{auth_part}{host}:{port}"
            self.session.proxies.update({"http": proxy_url, "https": proxy_url})

    def build_url_with_page_first(self, original_url: str, page: int) -> str:
        parsed = urlparse(original_url)
        qsl = parse_qsl(parsed.query, keep_blank_values=True)
        qsl = [(k, v) for (k, v) in qsl if k.lower() != "page"]
        new_qsl = [("page", str(page))] + qsl

        new_query = urlencode(new_qsl, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        return str(urlunparse(new_parsed))

    def fetch_url(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout, headers=default_request_headers())
        resp.raise_for_status()
        return resp.text

    def parse_from_file(self, file_path: str) -> List[CarAdvShortInfo]:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        soup = BeautifulSoup(text, "html.parser")
        return self._parse_soup_for_ads(soup)

    def parse_from_html(self, html: str) -> List[CarAdvShortInfo]:
        soup = BeautifulSoup(html, "html.parser")
        return self._parse_soup_for_ads(soup)

    def total_pages_from_html(self, html: str) -> int:
        m = re.search(r"od ukupno\s*([0-9\s\.]+)", html, flags=re.IGNORECASE)
        if not m:
            nums = re.findall(r"\d{1,}", html)
            if not nums:
                return 1
            total = int(nums[-1])
        else:
            total_str = m.group(1)
            total = int(re.sub(r"[^\d]", "", total_str))
        pages = math.ceil(total / self.page_size) if total > 0 else 1
        return max(1, pages)

    def _parse_soup_for_ads(self, soup: BeautifulSoup) -> List[CarAdvShortInfo]:
        results: List[CarAdvShortInfo] = []
        articles = soup.find_all("article")
        for art in articles:
            ad_link = None
            img_link = None

            if link_tag := art.find("a", href=True):
                ad_link = link_tag["href"].strip()
            if not ad_link:
                continue
            if img := art.find("img"):
                for attr in ("src", "data-src", "data-original", "data-lazy"):
                    val = img.get(attr)
                    if val:
                        img_link = val.strip()
                        break
            ad_number = self._get_ad_number(art, ad_link)

            info = CarAdvShortInfo(
                ad_number=ad_number or 0,
                ad_link=ad_link,
                img_link=img_link
            )
            results.append(info)

        return results

    @classmethod
    def _get_ad_number(cls, ad_tag, ad_link):
        if m := re.search(r"(\d{3,})", ad_link):
            try:
                return int(m.group(1))
            except ValueError:
                return None

        for attr in ("data-ad-id", "data-advert-id", "data-id", "data-ad"):
            v = ad_tag.get(attr)
            if v and v.isdigit():
                return int(v)

        if span_id := ad_tag.find(lambda tag: tag.name in ("span", "div") and tag.get_text(strip=True).isdigit()):
            try:
                return int(span_id.get_text(strip=True))
            except ValueError:
                return None
        return None

    # --- собрать все объявления со всех страниц (локально: через HTML или через сеть) ---
    def collect_all_from_base_url(self, base_url: str, fetch_remote: bool = True) -> List[CarAdvShortInfo]:
        """
        base_url — пример строки вида:
        https://www.polovniautomobili.com/auto-oglasi/pretraga?brand=&brand2=...&page=&sort=basic
        Если fetch_remote=True — будет делать HTTP-запросы с учётом прокси.
        Если fetch_remote=False — предполагается, что base_url вместо сети является путь к локальному HTML файлу
        (в этом случае метод parse_from_file можно вызывать напрямую).
        """
        # если fetch_remote == False, предполагаем что base_url — локальный файл
        if not fetch_remote:
            return self.parse_from_file(base_url)

        # 1) получаем первую страницу (page=1)
        first_page_url = self.build_url_with_page_first(base_url, 1)
        html = self.fetch_url(first_page_url)

        # 2) парсим объявления со страницы 1
        all_ads = self.parse_from_html(html)

        # 3) определяем общее число страниц
        pages = self.total_pages_from_html(html)

        # 4) для всех последующих страниц (2..pages) делаем fetch и добавляем
        for p in range(2, pages + 1):
            url_p = self.build_url_with_page_first(base_url, p)
            page_html = self.fetch_url(url_p)
            ads = self.parse_from_html(page_html)
            # Если сайт дублирует объявления между страницами, можно добавить фильтрацию по ad_number
            all_ads.extend(ads)

        return all_ads


# === Пример использования ===
if __name__ == "__main__":
    load_dotenv()
    parser = PolovniAutoParser()
    # Пример 1: парсинг локального файла (пример: skoda_list.html)
    local_ads = parser.parse_from_file("../../examples/skoda_list.html")
    print(f"Найдено {len(local_ads)} объявлений в локальном файле. Примеры:")
    for a in local_ads[:5]:
        print(a.model_dump_json())

    # Пример 2: сбор со всех страниц по базовому URL (выполнит HTTP-запросы через прокси из .env)
    # base_url = "https://www.polovniautomobili.com/auto-oglasi/pretraga?brand=&brand2=&...&page=&sort=basic"
    # all_ads = parser.collect_all_from_base_url(base_url, fetch_remote=True)
    # print(len(all_ads))
