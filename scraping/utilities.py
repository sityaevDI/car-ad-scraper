import random
import re
from logging import getLogger, DEBUG
from urllib.parse import urlparse

import brotli
from bs4 import Tag, BeautifulSoup

logger = getLogger("scraper")
logger.setLevel(DEBUG)
user_agent_list = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 '
    'Mobile/15E148 Safari/604.1',
    'Mozilla/4.0 (compatible; MSIE 9.0; Windows NT 6.1)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 '
    'Safari/537.36 Edg/87.0.664.75',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 '
    'Safari/537.36 Edge/18.18363',
]


def default_request_headers():
    return random.choice([
        {
            'User-Agent': user_agent_list[random.randint(0, len(user_agent_list) - 1)],
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        },
        {
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 "
                          "Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
                      "application/signed-exchange;v=b3;q=0.9",
            "sec-ch-ua": "\".Not/A)Brand\";v=\"99\", \"Google Chrome\";v=\"103\", \"Chromium\";v=\"103\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Linux\"",
            "sec-fetch-site": "none",
            "sec-fetch-mod": "",
            "sec-fetch-user": "?1",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "fr-CH,fr;q=0.9,en-US;q=0.8,en;q=0.7"
        }
    ])


def get_soup_from_response(response):
    if response.headers.get('Content-Encoding') == 'br':
        try:
            decompressed_data = brotli.decompress(response.content)
        except brotli.error:
            decompressed_data = response.content
        soup = BeautifulSoup(decompressed_data, 'html.parser')
    else:
        soup = BeautifulSoup(response.text, 'html.parser')
    return soup


def safe_extract_text(section: Tag, label: str):
    element = section.find(string=re.compile(rf'{label}\s*:?\s*'))
    if element:
        return element.find_next('div').text.strip()
    return None


def safe_extract_section(section: Tag, label: str):
    element = section.find(string=re.compile(rf'{label}\s*:?\s*'))
    if element:
        return element.find_next('div')
    return None


def strip_query_parameters(url: str):
    parsed_url = urlparse(url)
    return parsed_url.path
