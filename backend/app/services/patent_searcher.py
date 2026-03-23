from app.core.config import settings
from app.services.searchers.base import PatentSearcher
from app.services.searchers.kipris import KiprisSearcher
from app.services.searchers.patentsview import PatentsViewSearcher

_REGISTRY: dict[str, PatentSearcher] = {}


def init_searchers():
    global _REGISTRY
    _REGISTRY = {
        "KR": KiprisSearcher(),
        "US": PatentsViewSearcher(api_key=settings.patentsview_api_key),
    }


def get_searcher(country_code: str) -> PatentSearcher | None:
    return _REGISTRY.get(country_code)


def get_all_searchers() -> dict[str, PatentSearcher]:
    return dict(_REGISTRY)
