"""价格数据抓取：DRAM内存价格、汇率"""

import asyncio
from typing import Dict, List

import aiohttp
from bs4 import BeautifulSoup

from astrbot.api import logger

from ..constants import USER_AGENT, DRAM_PRICE_URL
from ..config import PluginConfig


async def fetch_dram_price(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[Dict]:
    """抓取DRAM价格"""
    if not config.dram_mode:
        return []

    headers = {
        "User-Agent": USER_AGENT
    }
    data = []
    try:
        async with semaphore:  # 限制并发
            async with session.get(DRAM_PRICE_URL, headers=headers) as resp:
                # 显式指定编码，防止乱码
                text = await resp.text(encoding='utf-8')
                soup = BeautifulSoup(text, 'lxml')

                # 定位 id="price1" 下的 class="price-table"
                table = soup.select_one("#price1 table.price-table")

                if not table:
                    logger.warning("棒棒糖的每日晨报：未找到DRAM价格表格，页面结构可能已变更")
                    return []

                # 跳过表头，遍历数据行
                rows = table.find_all("tr")
                for row in rows[1:7]:
                    cols = row.find_all("td")
                    if len(cols) < 5:
                        continue

                    # 第0列: 产品名称 (DDR5...)
                    name = cols[0].get_text(strip=True)

                    # 第3列: 盘平均 (通常看平均价)
                    price = cols[3].get_text(strip=True)

                    # 第4列: 涨幅度 (包含 img 标签和文本)
                    change_td = cols[4]
                    change_text = change_td.get_text(strip=True)

                    # 处理涨跌符号
                    img = change_td.find("img")
                    if img:
                        src = img.get("src", "")
                        if "up" in src:
                            change_text = f"+{change_text}"
                        elif "down" in src:
                            change_text = f"-{change_text}"
                        # stable (平盘) 不做处理

                    data.append({
                        "name": name,
                        "price": price,
                        "change": change_text
                    })

    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取DRAM价格超时")
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取DRAM价格网络错误: {e}")
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：抓取DRAM价格失败: {e}")
    return data


async def fetch_exchange_rates(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> Dict:
    """获取汇率 (基准 CNY)"""
    if not config.exchangerate_key:
        return {"error": "未配置Key"}

    url = f"https://v6.exchangerate-api.com/v6/{config.exchangerate_key}/latest/CNY"
    try:
        async with semaphore:  # 限制并发
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if data.get("result") == "success":
                        rates = data.get("conversion_rates", {})
                        return {
                            "USD": f"{rates.get('USD', 0):.4f}",
                            "JPY": f"{rates.get('JPY', 0):.4f}",
                            "EUR": f"{rates.get('EUR', 0):.4f}",
                            "GBP": f"{rates.get('GBP', 0):.4f}",
                            "TWD": f"{rates.get('TWD', 0):.4f}",
                            "HKD": f"{rates.get('HKD', 0):.4f}"
                        }
                    else:
                        logger.warning("棒棒糖的每日晨报：获取汇率API返回非success结果")
                        return {"error": "获取失败"}
                else:
                    logger.warning(f"棒棒糖的每日晨报：获取汇率API返回非200状态码: {resp.status}")
                    return {"error": "获取失败"}

    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取汇率超时")
        return {"error": "获取失败 - 请求超时"}
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取汇率网络错误: {e}")
        return {"error": "获取失败 - 网络错误"}
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：获取汇率失败: {e}")
        return {"error": "获取失败"}
