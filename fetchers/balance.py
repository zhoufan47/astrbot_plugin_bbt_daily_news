"""AI平台余额查询：OpenRouter、DeepSeek、Moonshot、SiliconFlow"""

import asyncio
from typing import Dict, Callable

import aiohttp

from astrbot.api import logger

from ..config import PluginConfig


async def fetch_api_balance(
    session,
    semaphore: asyncio.Semaphore,
    api_name: str,
    api_url: str,
    headers: dict,
    parse_func: Callable,
) -> Dict:
    """通用API余额查询方法"""
    if not headers.get("Authorization"):
        return {"name": api_name, "error": "未配置Key"}

    try:
        async with semaphore:  # 限制并发
            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return parse_func(data)
                elif resp.status == 401:
                    logger.warning(f"棒棒糖的每日晨报：{api_name} API认证失败，可能是API密钥无效")
                    return {"name": api_name, "status": "API认证失败 (401)", "balance": "0.00"}
                elif resp.status == 429:
                    logger.warning(f"棒棒糖的每日晨报：{api_name} API请求频率超限")
                    return {"name": api_name, "status": "请求频率超限 (429)", "balance": "0.00"}
                else:
                    logger.error(f"棒棒糖的每日晨报：{api_name} API请求失败，状态码: {resp.status}")
                    return {"name": api_name, "status": f"API请求失败 (状态码: {resp.status})", "balance": "0.00"}
    except asyncio.TimeoutError:
        logger.error(f"棒棒糖的每日晨报：获取{api_name}余额超时")
        return {"name": api_name, "status": "API请求超时", "balance": "0.00"}
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取{api_name}余额网络错误: {e}")
        return {"name": api_name, "status": "网络错误", "balance": "0.00"}
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：获取{api_name}余额失败: {e}")
        return {"name": api_name, "status": "API请求失败", "balance": "0.00"}


def _parse_openrouter_data(data: dict) -> Dict:
    info = data.get("data", {})
    usage = info.get("usage", 0)
    limit_remaining = info.get("limit_remaining", 0)
    usage_daily = info.get("usage_daily", 0)
    return {
        "usage_daily": f"${usage_daily:.4f}",
        "usage": f"${usage:.4f}",
        "limit_remaining": f"${limit_remaining:.4f}" if limit_remaining else "No Limit",
    }


async def fetch_openrouter_credits(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> Dict:
    """获取OpenRouter余额"""
    if not config.openrouter_key:
        return {"error": "未配置Key"}

    url = "https://openrouter.ai/api/v1/auth/key"
    headers = {"Authorization": f"Bearer {config.openrouter_key}"}

    return await fetch_api_balance(session, semaphore, "OpenRouter", url, headers, _parse_openrouter_data)


def _parse_deepseek_data(data: dict) -> Dict:
    infos = data.get("balance_infos", [])
    balance_str = "0.00"
    currency = "CNY"

    if infos:
        item = infos[0]
        balance_str = item.get("total_balance", "0.00")
        currency = item.get("currency", "CNY")

    return {
        "name": "DeepSeek",
        "balance": f"{balance_str} {currency}",
        "status": "正常" if data.get("is_available") else "已停用"
    }


async def fetch_deepseek_balance(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> Dict:
    """获取 DeepSeek 余额"""
    if not config.deepseek_key:
        return {"name": "DeepSeek", "error": "未配置Key"}

    url = "https://api.deepseek.com/user/balance"
    headers = {"Authorization": f"Bearer {config.deepseek_key}"}

    return await fetch_api_balance(session, semaphore, "DeepSeek", url, headers, _parse_deepseek_data)


def _parse_moonshot_data(data: dict) -> Dict:
    info = data.get("data", {})
    available = info.get("available_balance", 0)
    return {
        "name": "Moonshot",
        "balance": f"¥{available:.2f}",
        "status": "正常" if data.get("status") else "已停用"
    }


async def fetch_moonshot_balance(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> Dict:
    """获取 Moonshot (Kimi) 余额"""
    if not config.moonshot_key:
        return {"name": "Moonshot", "error": "未配置Key"}

    url = "https://api.moonshot.cn/v1/users/me/balance"
    headers = {"Authorization": f"Bearer {config.moonshot_key}"}

    return await fetch_api_balance(session, semaphore, "Moonshot", url, headers, _parse_moonshot_data)


def _parse_siliconflow_data(data: dict) -> Dict:
    info = data.get("data", {})
    balance = info.get("balance", "0")
    return {
        "name": "SiliconFlow",
        "balance": f"¥{balance}",
        "status": "Active"
    }


async def fetch_siliconflow_balance(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> Dict:
    """获取 硅基流动 (SiliconFlow) 余额"""
    if not config.siliconflow_key:
        return {"name": "SiliconFlow", "error": "未配置Key"}

    url = "https://api.siliconflow.cn/v1/user/info"
    headers = {"Authorization": f"Bearer {config.siliconflow_key}"}

    return await fetch_api_balance(session, semaphore, "SiliconFlow", url, headers, _parse_siliconflow_data)
