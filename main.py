"""棒棒糖的每日综合简报插件 - 入口模块"""

import asyncio
import traceback

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Image
from astrbot.core.message.message_event_result import MessageChain

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import PluginConfig
from .fetchers import DataFetcherManager
from .renderer import ReportRenderer


@register("daily_report", "棒棒糖", "每日综合简报插件", "1.6.0")
class DailyReportPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = PluginConfig.from_dict(config)

        # 初始化缓存
        self.cache = {}

        # 限制并发数
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        # 初始化数据抓取器和渲染器
        self.fetcher_manager = DataFetcherManager(self.config, self.semaphore)
        self.renderer = ReportRenderer(
            config=self.config,
            fetcher_manager=self.fetcher_manager,
            render_func=self.html_render,
            cache=self.cache,
        )

        # 实例化调度器
        self.scheduler = AsyncIOScheduler()

        # 解析时间并添加定时任务
        try:
            hour, minute = self.config.send_time.split(":")
            self.scheduler.add_job(
                self.broadcast_report,
                "cron",
                hour=int(hour),
                minute=int(minute),
                id="daily_report_job",
            )
            self.scheduler.start()
            logger.info(f"棒棒糖的每日晨报：定时任务已创建{self.config.send_time}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：定时任务创建失败: {traceback.format_exc()}")
            logger.error(f"棒棒糖的每日晨报：定时任务创建失败: {e}")

    async def broadcast_report(self):
        """定时任务入口"""
        logger.info("棒棒糖的每日晨报：开始每日晨报定时任务...")
        try:
            html_urls = await self.renderer.generate()
            logger.info(f"棒棒糖的每日晨报：HTML 生成完成，共 {len(html_urls)} 张图片")
            message_chain = MessageChain([Image.fromURL(url) for url in html_urls])
            # 发送到配置的群
            for group_id in self.config.target_groups:
                logger.info(f"棒棒糖的每日晨报：向群组 {group_id} 发送图片")
                await self.context.send_message(group_id, message_chain)
                await asyncio.sleep(2)  # 防风控延迟

            logger.info("棒棒糖的每日晨报：每日报告广播完成。")

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：广播失败: {e}", exc_info=True)

    @filter.command("看看日报")
    async def manual_report(self, event: AstrMessageEvent):
        """手动触发日报生成"""
        try:
            html_urls = await self.renderer.generate()
            logger.info(f"棒棒糖的每日晨报：手动报告生成成功，共 {len(html_urls)} 张图片")
            yield event.chain_result([Image.fromURL(url) for url in html_urls])
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：手动报告生成失败: {e}", exc_info=True)
            yield event.plain_result(f"生成报告失败: {str(e)}")

    @filter.command("清除日报缓存")
    async def clear_cache_command(self, event: AstrMessageEvent):
        """允许用户强制清除缓存"""
        self.cache.clear()
        logger.info("棒棒糖的每日晨报：缓存已被手动清除")
        yield event.plain_result("日报缓存已清除，下次查询将获取最新数据。")

    @filter.llm_tool(name="clear_daily_report_cache")
    async def tool_clear_cache(self, event: AstrMessageEvent):
        """
        清理日报缓存


        """
        self.cache.clear()
        logger.info("棒棒糖的每日晨报：缓存已被手动清除")
        return "日报缓存已清除，下次查询将获取最新数据。"

    @filter.llm_tool(name="today_news")
    async def report_today_news(self, event: AstrMessageEvent):
        """
        发送今天的早报，看看今天发生了什么。


        """
        try:
            html_urls = await self.renderer.generate()
            logger.info(f"棒棒糖的每日晨报：LLM工具报告生成成功，共 {len(html_urls)} 张图片")
            yield event.chain_result([Image.fromURL(url) for url in html_urls])
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：LLM工具报告生成失败: {e}", exc_info=True)
            yield event.plain_result(f"生成报告失败: {str(e)}")

    async def terminate(self):
        logger.info("棒棒糖的每日晨报：开始卸载...")
        if self.scheduler.running:
            self.scheduler.remove_all_jobs()
            self.scheduler.shutdown(wait=False)
        logger.info("棒棒糖的每日晨报：定时任务已清理")
        logger.info("棒棒糖的每日晨报：完成卸载...")
