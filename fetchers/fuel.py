"""油价数据抓取：国内各省份成品油价格"""

import asyncio
from typing import Dict

import aiohttp

from astrbot.api import logger

from ..constants import FUEL_PRICE_URL
from ..config import PluginConfig


async def fetch_fuel_price(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> Dict:
    """获取指定省份的油价"""
    if not config.fuel_mode:
        return {"error": "未开启", "province": config.fuel_province}

    province = config.fuel_province
    params = {"province": province}
    try:
        async with semaphore:
            async with session.get(FUEL_PRICE_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "province": data.get("province", province),
                        "gas_92": data.get("92号汽油", "获取失败"),
                        "gas_95": data.get("95号汽油", "获取失败"),
                        "gas_98": data.get("98号汽油", "获取失败"),
                        "diesel_0": data.get("0号柴油", "获取失败"),
                    }
                else:
                    logger.warning(f"棒棒糖的每日晨报：获取油价API返回非200状态码: {resp.status}")
                    return {"error": "获取失败", "province": province}
    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取油价超时")
        return {"error": "获取失败 - 请求超时", "province": province}
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取油价网络错误: {e}")
        return {"error": "获取失败 - 网络错误", "province": province}
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：获取油价失败: {e}")
        return {"error": "获取失败", "province": province}
