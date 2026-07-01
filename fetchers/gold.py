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
                    # 实际返回结构: {"code": 200, "data": {"date": "...", "metals": [{"name": "今日金价", "today_price": "870.68", "unit": "元/克", ...}]}}
                    if data.get("code") == 200 and "data" in data:
                        gold_data = data["data"]
                        metals = gold_data.get("metals", [])
                        
                        result = {
                            "international": "获取失败",
                            "domestic": "获取失败",
                            "update_time": gold_data.get("date", "获取失败"),
                        }
                        
                        # 遍历 metals 提取金价信息
                        for metal in metals:
                            name = metal.get("name", "")
                            price = metal.get("today_price", "获取失败")
                            unit = metal.get("unit", "")
                            
                            # 根据名称区分国际和国内金价
                            if "伦敦金" in name or "纽约黄金" in name or "国际" in name:
                                result["international"] = f"{price} {unit}"
                            elif "今日金价" in name or "黄金价格" in name:
                                result["domestic"] = f"{price} {unit}"
                        
                        return result
                    else:
                        logger.warning(f"棒棒糖的每日晨报：金价API返回数据格式异常: {data}")
                        return {"error": "获取失败"}
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
