from abc import ABC, abstractmethod

from app.models.schemas import NormalizedPatent, SearchQuery


class PatentSearcher(ABC):
    """특허 검색 어댑터 추상 인터페이스"""

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[NormalizedPatent]:
        ...

    @abstractmethod
    def get_country_code(self) -> str:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...
