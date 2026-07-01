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
                    # 实际返回结构: {"code": 200, "data": {"region": "北京", "items": [{"name": "92#汽油", "price": 7.94}]}}
                    if data.get("code") == 200 and "data" in data:
                        fuel_data = data["data"]
                        items = fuel_data.get("items", [])
                        
                        # 构建油价字典
                        result = {
                            "province": fuel_data.get("region", province),
                            "gas_92": "获取失败",
                            "gas_95": "获取失败",
                            "gas_98": "获取失败",
                            "diesel_0": "获取失败",
                        }
                        
                        # 遍历 items 提取对应油品价格
                        for item in items:
                            name = item.get("name", "")
                            price = item.get("price_desc", "获取失败")
                            
                            if "92" in name:
                                result["gas_92"] = price
                            elif "95" in name:
                                result["gas_95"] = price
                            elif "98" in name:
                                result["gas_98"] = price
                            elif "0" in name and "柴油" in name:
                                result["diesel_0"] = price
                        
                        return result
                    else:
                        logger.warning(f"棒棒糖的每日晨报：油价API返回数据格式异常: {data}")
                        return {"error": "获取失败", "province": province}
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
