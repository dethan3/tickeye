#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人配置管理模块
"""

import os
import json
from typing import Optional
import logging

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()  # 自动加载 .env 文件中的环境变量
except ImportError:
    # 如果没有安装 python-dotenv，跳过
    pass

logger = logging.getLogger(__name__)


class FeishuConfig:
    """飞书机器人配置管理器"""
    
    def __init__(self, config_file: str = "feishu_config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """
        加载配置文件
        
        Returns:
            dict: 配置字典
        """
        # 默认配置
        default_config = {
            "webhook_url": "",
            "enabled": True,
            "timeout": 10,
            "retry_times": 3
        }
        
        # 尝试从文件加载配置
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # 合并配置
                    default_config.update(file_config)
                    logger.info(f"已加载配置文件: {self.config_file}")
            except Exception as e:
                logger.warning(f"加载配置文件失败，使用默认配置: {e}")
        
        # 环境变量优先级最高
        env_webhook = os.getenv('FEISHU_WEBHOOK_URL')
        if env_webhook:
            default_config['webhook_url'] = env_webhook
            logger.info("使用环境变量中的webhook URL")
        
        return default_config
    
    def get_webhook_url(self) -> Optional[str]:
        """获取webhook URL"""
        url = self.config.get('webhook_url')
        return url if url else None
    
    def set_webhook_url(self, url: str) -> None:
        """设置webhook URL"""
        self.config['webhook_url'] = url
    
    def is_enabled(self) -> bool:
        """检查通知是否启用"""
        return self.config.get('enabled', True)
    
    def get_timeout(self) -> int:
        """获取请求超时时间"""
        return self.config.get('timeout', 10)
    
    def get_retry_times(self) -> int:
        """获取重试次数"""
        return self.config.get('retry_times', 3)


# 全局配置实例
feishu_config = FeishuConfig()


def get_config() -> FeishuConfig:
    """获取全局配置实例"""
    return feishu_config


if __name__ == "__main__":
    # 测试配置管理
    config = FeishuConfig()
    
    print("当前配置:")
    print(f"Webhook URL: {config.get_webhook_url()}")
    print(f"启用状态: {config.is_enabled()}")
    print(f"超时时间: {config.get_timeout()}秒")
    print(f"重试次数: {config.get_retry_times()}次")
    
    # 如果没有配置webhook URL，提示用户设置
    if not config.get_webhook_url():
        print("\n⚠️  请设置飞书机器人webhook URL:")
        print("方法1: 设置环境变量 FEISHU_WEBHOOK_URL")
        print("方法2: 创建 feishu_config.json 文件")
        print("方法3: 调用 config.set_webhook_url() 方法")
