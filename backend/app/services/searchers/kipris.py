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

KIPRIS_BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getWordSearch"


class KiprisSearcher(PatentSearcher):
    def __init__(self):
        self._lock = asyncio.Lock()
        self._quota_file = Path(settings.data_dir) / "kipris_quota.json"

    def get_country_code(self) -> str:
        return "KR"

    async def is_available(self) -> bool:
        quota = await self._read_quota()
        return quota["used"] < settings.kipris_daily_limit

    async def search(self, query: SearchQuery) -> list[NormalizedPatent]:
        if not await self.is_available():
            logger.warning("KIPRIS daily quota exceeded")
            return []

        # keyword_groups가 있으면 각 그룹의 첫 번째 키워드 사용
        if query.keyword_groups_kr:
            keywords = " ".join(g[0] for g in query.keyword_groups_kr if g)
        else:
            keywords = " ".join(query.keywords_kr)

        if not keywords.strip():
            return []

        params = {
            "word": keywords,
            "patent": "true",
            "utility": "true",
            "numOfRows": 30,
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

    def _parse_xml(self, xml_text: str) -> list[NormalizedPatent]:
        results: list[NormalizedPatent] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            logger.error("Failed to parse KIPRIS XML response")
            return results

        # KIPRIS API 에러 감지 (HTTP 200이지만 실패 응답)
        success_yn = root.findtext(".//successYN")
        if success_yn == "N":
            result_msg = root.findtext(".//resultMsg") or "Unknown KIPRIS error"
            logger.error(f"KIPRIS API returned error: {result_msg}")
            raise RuntimeError(f"KIPRIS API error: {result_msg}")

        for item in root.iter("item"):
            title = self._get_text(item, "inventionTitle", "")
            if not title:
                continue
            results.append(NormalizedPatent(
                country="KR",
                title=title,
                application_number=self._get_text(item, "applicationNumber", ""),
                application_date=self._format_date(self._get_text(item, "applicationDate")),
                abstract=self._get_text(item, "astrtCont"),
                applicant=self._get_text(item, "applicantName"),
                ipc_codes=self._parse_ipc(self._get_text(item, "ipcNumber")),
                url=self._build_url(self._get_text(item, "applicationNumber")),
            ))
        return results

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

    def _build_url(self, app_num: str | None) -> str | None:
        if not app_num:
            return None
        return f"https://kpat.kipris.or.kr/kpat/biblioa.do?method=biblioFrame&applno={app_num}"

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
