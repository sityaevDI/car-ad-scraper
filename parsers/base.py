from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseParser(ABC):
    source: str

    @abstractmethod
    async def list_tasks(self) -> AsyncIterator[str]:
        """Returns list of the parse tasks"""
        pass

    @abstractmethod
    async def parse(self, page_content: str) -> list[dict]:
        """
        Returns dict of parsed listing parameters.
        :param page_content: HTML content of the page
        :return:
        """
        pass
