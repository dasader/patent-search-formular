import json as _json
import logging

import httpx

from app.models.schemas import NormalizedPatent, SearchQuery
from app.services.searchers.base import PatentSearcher

logger = logging.getLogger(__name__)

PATENTSVIEW_BASE_URL = "https://search.patentsview.org/api/v1/patent"


class PatentsViewSearcher(PatentSearcher):
    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def get_country_code(self) -> str:
        return "US"

    async def is_available(self) -> bool:
        return True

    async def search(self, query: SearchQuery) -> tuple[list[NormalizedPatent], int]:
        # keyword_groups가 있으면 사용, 없으면 keywords_en 폴백
        if not query.keyword_groups_en and not query.keywords_en:
            return [], 0

        q_filter = self._build_query(query)
        payload = {
            "q": _json.loads(q_filter),
            "f": [
                "patent_id",
                "patent_title",
                "patent_date",
                "patent_abstract",
                "assignees_at_grant.assignee_organization",
                "cpcs.cpc_group_id",
            ],
            "per_page": 30,
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-Api-Key"] = self._api_key

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(PATENTSVIEW_BASE_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"PatentsView API error: {e}")
            raise

        total_count = data.get("total_patent_count", 0)
        return self._parse_response(data), total_count

    def _build_query(self, query: SearchQuery) -> str:
        conditions = []

        if query.keyword_groups_en:
            # 각 개념 그룹: 그룹 내 OR, 그룹 간 AND
            for group in query.keyword_groups_en:
                if len(group) == 1:
                    conditions.append({"_text_any": {"patent_abstract": group[0]}})
                elif len(group) > 1:
                    conditions.append(
                        {"_or": [{"_text_any": {"patent_abstract": term}} for term in group]}
                    )
        elif query.keywords_en:
            # 폴백: 기존 flat 키워드
            text_query = " ".join(query.keywords_en)
            conditions.append({"_text_any": {"patent_abstract": text_query}})

        # CPC 코드: OR 결합
        cpc_conditions = [{"_begins": {"cpcs.cpc_group_id": cpc}} for cpc in query.cpc_codes]
        if len(cpc_conditions) == 1:
            conditions.append(cpc_conditions[0])
        elif len(cpc_conditions) > 1:
            conditions.append({"_or": cpc_conditions})

        if not conditions:
            return "{}"
        if len(conditions) == 1:
            return _json.dumps(conditions[0])
        return _json.dumps({"_and": conditions})

    def _parse_response(self, data: dict) -> list[NormalizedPatent]:
        results: list[NormalizedPatent] = []
        patents = data.get("patents", [])

        for p in patents:
            title = p.get("patent_title", "")
            if not title:
                continue

            assignees = p.get("assignees_at_grant", [])
            applicant = assignees[0].get("assignee_organization", "") if assignees else None

            cpcs = p.get("cpcs", [])
            cpc_codes = list({c.get("cpc_group_id", "") for c in cpcs if c.get("cpc_group_id")})

            results.append(NormalizedPatent(
                country="US",
                title=title,
                application_number=p.get("patent_id", ""),
                application_date=p.get("patent_date"),
                abstract=p.get("patent_abstract"),
                applicant=applicant,
                ipc_codes=cpc_codes,
                url=f"https://patents.google.com/patent/US{p.get('patent_id', '')}",
            ))

        return results
