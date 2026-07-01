"""金价数据抓取：国际与国内实时黄金价格"""

import asyncio
from typing import Dict

import aiohttp

from astrbot.api import logger

from ..constants import GOLD_PRICE_URL
from ..config import PluginConfig


async def fetch_gold_price(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> Dict:
    """获取当前黄金价格"""
    if not config.gold_mode:
        return {"error": "未开启"}

    try:
        async with semaphore:
            async with session.get(GOLD_PRICE_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "international": data.get("国际金价", "获取失败"),
                        "domestic": data.get("国内金价", "获取失败"),
                        "update_time": data.get("update_time", "获取失败"),
                    }
                else:
                    logger.warning(f"棒棒糖的每日晨报：获取金价API返回非200状态码: {resp.status}")
                    return {"error": "获取失败"}
    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取金价超时")
        return {"error": "获取失败 - 请求超时"}
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取金价网络错误: {e}")
        return {"error": "获取失败 - 网络错误"}
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：获取金价失败: {e}")
        return {"error": "获取失败"}
