"""新闻和热榜数据抓取：60秒读懂世界、IT之家热榜、微博热榜、今日头条热榜"""

import asyncio
from typing import Dict, List

import aiohttp
from bs4 import BeautifulSoup

from astrbot.api import logger

from constants import USER_AGENT, NEWS_API_URL, ITHOME_RANK_URL
from config import PluginConfig


async def fetch_60s_news(session, semaphore: asyncio.Semaphore) -> Dict:
    """获取60秒读懂世界"""
    try:
        async with semaphore:  # 限制并发
            async with session.get(NEWS_API_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"news": data.get("data", {}).get("news", [])}
                else:
                    logger.warning(f"棒棒糖的每日晨报：获取60秒新闻API返回非200状态码: {resp.status}")
                    return {"news": ["获取失败"]}
    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取60秒新闻超时")
        return {"news": ["获取失败 - 请求超时"]}
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取60秒新闻网络错误: {e}")
        return {"news": ["获取失败 - 网络错误"]}
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：获取60秒新闻失败: {e}")
    return {"news": ["获取失败"]}


async def fetch_ithome_news(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[str]:
    """抓取IT之家热榜"""
    if not config.ithome_mode:
        return []

    headers = {
        "User-Agent": USER_AGENT
    }
    news_list = []
    try:
        async with semaphore:  # 限制并发
            async with session.get(ITHOME_RANK_URL, headers=headers) as resp:
                text = await resp.text()
                soup = BeautifulSoup(text, 'lxml')

                # 日榜在 id="d-1" 的 ul 标签下
                daily_list = soup.select_one("ul#d-1")

                if daily_list:
                    links = daily_list.select("li a")

                    for link in links:
                        title = link.get_text(strip=True)
                        if title:
                            news_list.append(title)
                else:
                    logger.warning("棒棒糖的每日晨报：未找到IT之家热榜容器(ul#d-1)")

    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取IT之家热榜超时")
        news_list.append("获取失败 - 请求超时")
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取IT之家热榜网络错误: {e}")
        news_list.append("获取失败 - 网络错误")
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：抓取IT之家热榜失败: {e}")
        news_list.append("获取失败 - 未知错误")

    # 返回前 10 条，避免太长
    return news_list[:10]


async def fetch_weibo_hot(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[str]:
    """获取微博热榜"""
    if not config.yuafeng_key:
        return []

    results = []
    url = "https://api-v2.yuafeng.cn/API/jinri_hot.php"
    params = {
        'apikey': config.yuafeng_key,
        'action': '微博热榜',
        'page': '1',
    }
    try:
        async with semaphore:  # 限制并发
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    info = data.get("data", [])
                    for item in info:
                        results.append(item["title"])
                    return results
                else:
                    logger.warning(f"棒棒糖的每日晨报：获取微博热榜API返回非200状态码: {resp.status}")
                    return []

    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取微博热榜超时")
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取微博热榜网络错误: {e}")
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：获取微博热榜失败: {e}")
    return []


async def fetch_toutiao_hot(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[str]:
    """获取今日头条热榜"""
    if not config.yuafeng_key:
        return []

    results = []
    url = "https://api-v2.yuafeng.cn/API/jinri_hot.php"
    params = {
        'apikey': config.yuafeng_key,
        'action': '今日头条热榜',
        'page': '1',
    }
    try:
        async with semaphore:  # 限制并发
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    info = data.get("data", [])
                    for item in info:
                        results.append(item["title"])
                    return results
                else:
                    logger.warning(f"棒棒糖的每日晨报：获取今日头条热榜API返回非200状态码: {resp.status}")
                    return []
    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取今日头条热榜超时")
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取今日头条热榜网络错误: {e}")
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：获取今日头条热榜失败: {e}")
    return []
