import re
from logging import getLogger, DEBUG
from urllib.parse import urlparse

from bs4 import Tag

logger = getLogger("scraper")
logger.setLevel(DEBUG)

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
