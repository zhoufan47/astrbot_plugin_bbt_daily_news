"""插件配置数据类"""

from dataclasses import dataclass
from typing import List


@dataclass
class PluginConfig:
    """插件配置，从 AstrBot 配置字典初始化"""
    target_groups: List[str]
    send_time: str
    openrouter_key: str
    deepseek_key: str
    moonshot_key: str
    siliconflow_key: str
    yuafeng_key: str
    exchangerate_key: str
    rawg_key: str
    r18_mode: bool
    dram_mode: bool
    proxy_mode: bool
    movie_mode: bool
    animation_mode: bool
    ithome_mode: bool
    fuel_mode: bool
    fuel_province: str
    gold_mode: bool
    game_release_date_threshold: int
    report_jpeg_quality: int
    cache_ttl_minutes: int
    max_concurrent_requests: int

    @classmethod
    def from_dict(cls, config: dict) -> "PluginConfig":
        """从 AstrBot 配置字典创建 PluginConfig 实例"""
        return cls(
            target_groups=config.get("target_groups", []),
            send_time=config.get("send_time", "08:00"),
            openrouter_key=config.get("openrouter_key", ""),
            deepseek_key=config.get("deepseek_key", ""),
            moonshot_key=config.get("moonshot_key", ""),
            siliconflow_key=config.get("siliconflow_key", ""),
            yuafeng_key=config.get("yuafeng_key", ""),
            exchangerate_key=config.get("exchangerate_key", ""),
            rawg_key=config.get("rawg_key", ""),
            r18_mode=config.get("r18_mode", False),
            dram_mode=config.get("dram_mode", False),
            proxy_mode=config.get("proxy_mode", False),
            movie_mode=config.get("movie_mode", False),
            animation_mode=config.get("animation_mode", False),
            ithome_mode=config.get("ithome_mode", False),
            fuel_mode=config.get("fuel_mode", True),
            fuel_province=config.get("fuel_province", "北京"),
            gold_mode=config.get("gold_mode", True),
            game_release_date_threshold=config.get("game_release_date_threshold", 14),
            report_jpeg_quality=config.get("report_jpeg_quality", 80),
            cache_ttl_minutes=config.get("cache_ttl_minutes", 10),
            max_concurrent_requests=config.get("max_concurrent_requests", 5),
        )
