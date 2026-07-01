"""数据抓取编排器：统一管理所有数据源的并发抓取"""

import asyncio
from typing import Dict, List

import aiohttp
from aiohttp import ClientTimeout

from astrbot.api import logger

from ..config import PluginConfig
from .news import fetch_60s_news, fetch_ithome_news, fetch_weibo_hot, fetch_toutiao_hot
from .media import fetch_bangumi_today, fetch_douban_movies, fetch_rawg_games
from .balance import (
    fetch_openrouter_credits,
    fetch_deepseek_balance,
    fetch_moonshot_balance,
    fetch_siliconflow_balance,
)
from .dmm import fetch_dmm_top
from .price import fetch_dram_price, fetch_exchange_rates
from .fuel import fetch_fuel_price
from .gold import fetch_gold_price


class DataFetcherManager:
    """数据抓取编排器，统一管理所有数据源的并发获取"""

    def __init__(self, config: PluginConfig, semaphore: asyncio.Semaphore):
        self.config = config
        self.semaphore = semaphore

    async def fetch_all_data(self) -> Dict:
        """
        并发获取所有常规数据源的数据（不含DMM）

        Returns:
            results_dict: 常规数据字典
        """
        timeout = ClientTimeout(total=30)

        # 定义数据获取任务：(key, fetcher_function)
        fetcher_tasks = [
            ("news_60s", lambda s: fetch_60s_news(s, self.semaphore)),
            ("ithome_news", lambda s: fetch_ithome_news(s, self.semaphore, self.config)),
            ("dram_price", lambda s: fetch_dram_price(s, self.semaphore, self.config)),
            ("bangumi_today", lambda s: fetch_bangumi_today(s, self.semaphore, self.config)),
            ("openrouter_credits", lambda s: fetch_openrouter_credits(s, self.semaphore, self.config)),
            ("deepseek_balance", lambda s: fetch_deepseek_balance(s, self.semaphore, self.config)),
            ("moonshot_balance", lambda s: fetch_moonshot_balance(s, self.semaphore, self.config)),
            ("siliconflow_balance", lambda s: fetch_siliconflow_balance(s, self.semaphore, self.config)),
            ("toutiao_hot", lambda s: fetch_toutiao_hot(s, self.semaphore, self.config)),
            ("weibo_hot", lambda s: fetch_weibo_hot(s, self.semaphore, self.config)),
            ("exchange_rates", lambda s: fetch_exchange_rates(s, self.semaphore, self.config)),
            ("douban_movies", lambda s: fetch_douban_movies(s, self.semaphore, self.config)),
            ("rawg_games", lambda s: fetch_rawg_games(s, self.semaphore, self.config)),
            ("fuel_price", lambda s: fetch_fuel_price(s, self.semaphore, self.config)),
            ("gold_price", lambda s: fetch_gold_price(s, self.semaphore, self.config)),
        ]

        logger.info("棒棒糖的每日晨报：开始并发获取数据")
        async with aiohttp.ClientSession(
            trust_env=self.config.proxy_mode, timeout=timeout
        ) as session:
            keys = [k for k, _ in fetcher_tasks]
            coroutines = [f(session) for _, f in fetcher_tasks]
            raw_results = await asyncio.gather(*coroutines, return_exceptions=True)

        return self._process_results(keys, raw_results)

    async def fetch_dmm_data(self) -> List:
        """
        单独获取DMM排行榜数据（使用代理会话，不放入缓存）

        Returns:
            dmm_top_list: DMM排行榜数据列表
        """
        if not self.config.r18_mode:
            return []

        timeout = ClientTimeout(total=30)
        async with aiohttp.ClientSession(trust_env=True, timeout=timeout) as session_proxy:
            dmm_result = await fetch_dmm_top(session_proxy, self.semaphore, self.config)
            return dmm_result if not isinstance(dmm_result, Exception) else []

    def _process_results(self, keys: List[str], raw_results: List) -> Dict:
        """处理原始结果，将其转换为字典格式"""
        results_dict = {}
        for key, result in zip(keys, raw_results):
            if isinstance(result, Exception):
                logger.error(f"数据获取任务 {key} 失败: {result}")
                # 根据任务类型返回默认值
                if key in ["news_60s"]:
                    results_dict[key] = {"news": ["获取失败 - 网络错误"]}
                elif key in [
                    "ithome_news",
                    "dram_price",
                    "bangumi_today",
                    "toutiao_hot",
                    "weibo_hot",
                    "douban_movies",
                    "rawg_games",
                ]:
                    results_dict[key] = []
                elif key in ["exchange_rates", "fuel_price", "gold_price"]:
                    results_dict[key] = {"error": "API请求失败"}
                else:  # 余额数据
                    results_dict[key] = {"error": "API请求失败"}
            else:
                results_dict[key] = result

        return results_dict
