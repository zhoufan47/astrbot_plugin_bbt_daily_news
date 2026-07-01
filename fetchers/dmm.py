"""DMM排行榜数据抓取"""

import asyncio
from typing import Dict, List

from astrbot.api import logger

from constants import DMM_HEADERS, DMM_RANKING_URL, RANKING_QUERY, TERM_FILTER_MAP
from config import PluginConfig
from utils import get_cover_url, parse_javid, url_to_base64


async def fetch_dmm_top(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[Dict]:
    """通过 GraphQL API 获取 DMM 排名数据"""
    if not config.r18_mode:
        return []

    query_term = "daily"
    filter_val = TERM_FILTER_MAP.get(query_term, TERM_FILTER_MAP["daily"])
    payload = {
        "operationName": "ContentRankingPage",
        "query": RANKING_QUERY,
        "variables": {
            "filter": filter_val,
            "isAmateur": False,
            "limit": 10,
            "offset": 0,
        },
    }

    logger.info(f"棒棒糖的每日晨报：正在请求 GraphQL API, term={query_term}")
    try:
        async with session.post(
            DMM_RANKING_URL,
            headers=DMM_HEADERS,
            json=payload
        ) as resp:
            if resp.status != 200:
                logger.error(f"棒棒糖的每日晨报：GraphQL 请求失败, status={resp.status}")
                data = await resp.json()
                logger.error(f"棒棒糖的每日晨报：错误详情: {data}")
                return []

            data = await resp.json()
            items = data.get("data", {}).get("ppvContentRanking", {}).get("items", [])
            logger.info(f"棒棒糖的每日晨报：获取到 {len(items)} 个排名作品")

            results = []
            index = 0
            for item in items:
                index = index + 1
                if index > 20:
                    break
                rank = item.get("rank", "")
                content = item.get("content", {})
                title = content.get("title", "未找到标题")
                content_id = item.get("id", "")

                # 封面图 URL
                cover_url = get_cover_url(content.get("packageImage"))

                # 番号
                jav_id = parse_javid(content_id) if content_id else ""

                # 出演者
                performers = []
                actresses = content.get("actresses", [])
                if actresses:
                    for actress in actresses:
                        performers.append(actress.get("name", ""))
                if not performers:
                    performers = ["未公开/未知"]

                b64_cover = await url_to_base64(session, semaphore, cover_url, referer=DMM_RANKING_URL)

                results.append({
                    "jav_id": jav_id,
                    "rank": str(rank),
                    "title": title,
                    "performers": performers,
                    "cover": b64_cover,
                })

            return results
    except Exception as e:
        logger.exception(f"棒棒糖的每日晨报：获取 DMM 数据失败: {e}")
        return []
