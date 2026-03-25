import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import httpx

from app.core.config import settings
from app.models.schemas import NormalizedPatent, SearchQuery
from app.services.searchers.base import PatentSearcher

logger = logging.getLogger(__name__)

KIPRIS_BASE_URL = "http://kipo-api.kipi.or.kr/openapi/service/patUtiModInfoSearchSevice/getAdvancedSearch"


class KiprisSearcher(PatentSearcher):
    def __init__(self):
        self._lock = asyncio.Lock()
        self._quota_file = Path(settings.data_dir) / "kipris_quota.json"

    def get_country_code(self) -> str:
        return "KR"

    async def is_available(self) -> bool:
        quota = await self._read_quota()
        return quota["used"] < settings.kipris_daily_limit

    def _build_date_range(self) -> str:
        """현재연도 제외 최근 N년 범위 (예: 20230101~20251231)"""
        current_year = datetime.now().year
        end_year = current_year - 1
        start_year = current_year - settings.kipris_search_years
        return f"{start_year}0101~{end_year}1231"

    async def search(self, query: SearchQuery) -> tuple[list[NormalizedPatent], int]:
        if not await self.is_available():
            logger.warning("KIPRIS daily quota exceeded")
            return [], 0

        # getAllSearch: 발명의 명칭 + 초록에 키워드를 넣어 검색
        # KIPRIS 검색 연산자: AND(*), OR(+), NOT(!)
        if query.keyword_groups_kr:
            groups = []
            for g in query.keyword_groups_kr:
                if not g:
                    continue
                if len(g) == 1:
                    groups.append(g[0])
                else:
                    groups.append(f"({'+'.join(g)})")
            keywords = "*".join(groups)
        else:
            keywords = "*".join(query.keywords_kr)

        if not keywords.strip():
            return [], 0

        date_range = self._build_date_range()
        logger.info(f"KIPRIS getAllSearch query: {keywords}, date: {date_range}")

        params = {
            "astrtCont": keywords,
            "applicationDate": date_range,
            "patent": "true",
            "utility": "false",
            "lastvalue": "true",
            "numOfRows": 500,
            "pageNo": 1,
            "ServiceKey": settings.kipris_api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(KIPRIS_BASE_URL, params=params)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"KIPRIS API error: {e}")
            raise

        await self._increment_quota()
        return self._parse_xml(resp.text)

    def _parse_xml(self, xml_text: str) -> tuple[list[NormalizedPatent], int]:
        results: list[NormalizedPatent] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            logger.error("Failed to parse KIPRIS XML response")
            return results, 0

        # KIPRIS API 에러 감지 (HTTP 200이지만 실패 응답)
        success_yn = root.findtext(".//successYN")
        if success_yn == "N":
            result_msg = root.findtext(".//resultMsg") or "Unknown KIPRIS error"
            logger.error(f"KIPRIS API returned error: {result_msg}")
            raise RuntimeError(f"KIPRIS API error: {result_msg}")

        total_count = int(root.findtext(".//totalCount") or "0")

        for item in root.iter("item"):
            title = self._get_text(item, "inventionTitle", "")
            if not title:
                continue
            app_num = self._get_text(item, "applicationNumber", "")
            open_num = self._get_text(item, "openNumber")
            register_num = self._get_text(item, "registerNumber")
            results.append(NormalizedPatent(
                country="KR",
                title=title,
                application_number=app_num,
                application_date=self._format_date(self._get_text(item, "applicationDate")),
                abstract=self._get_text(item, "astrtCont"),
                applicant=self._get_text(item, "applicantName"),
                ipc_codes=self._parse_ipc(self._get_text(item, "ipcNumber")),
                url=self._build_url(open_num, register_num),
                register_status=self._get_text(item, "registerStatus"),
            ))
        return results, total_count

    def _get_text(self, el: ElementTree.Element, tag: str, default: str | None = None) -> str | None:
        child = el.find(tag)
        return child.text.strip() if child is not None and child.text else default

    def _format_date(self, date_str: str | None) -> str | None:
        if not date_str or len(date_str) < 8:
            return date_str
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    def _parse_ipc(self, ipc_str: str | None) -> list[str]:
        if not ipc_str:
            return []
        return [c.strip() for c in ipc_str.split(",") if c.strip()]

    def _build_url(self, open_num: str | None, register_num: str | None) -> str | None:
        # Google Patents URL 형식:
        #   공개: KR + 번호(앞2자리 "10" 제거) + A  예) 1020250100930 → KR20250100930A
        #   등록: KR + 번호(뒤4자리 "0000" 제거) + B1  예) 1022617910000 → KR102261791B1
        if open_num and len(open_num) > 2:
            return f"https://patents.google.com/patent/KR{open_num[2:]}A"
        if register_num and register_num.endswith("0000"):
            return f"https://patents.google.com/patent/KR{register_num[:-4]}B1"
        return None

    async def _read_quota(self) -> dict:
        async with self._lock:
            return self._read_quota_sync()

    def _read_quota_sync(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            data = json.loads(self._quota_file.read_text(encoding="utf-8"))
            if data.get("date") != today:
                data = {"date": today, "used": 0}
                self._quota_file.write_text(json.dumps(data), encoding="utf-8")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            data = {"date": today, "used": 0}
            self._quota_file.parent.mkdir(parents=True, exist_ok=True)
            self._quota_file.write_text(json.dumps(data), encoding="utf-8")
        return data

    async def _increment_quota(self):
        async with self._lock:
            data = self._read_quota_sync()
            data["used"] = data.get("used", 0) + 1
            self._quota_file.write_text(json.dumps(data), encoding="utf-8")

    async def get_quota(self) -> dict:
        data = await self._read_quota()
        remaining = max(0, settings.kipris_daily_limit - data["used"])
        from datetime import timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return {
            "used": data["used"],
            "limit": settings.kipris_daily_limit,
            "remaining": remaining,
            "resets_at": tomorrow,
        }
