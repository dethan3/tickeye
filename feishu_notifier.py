#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人通知模块
支持文本、富文本和市场概览通知
"""

import json
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书机器人通知器"""
    
    def __init__(self, webhook_url: str):
        """
        初始化飞书通知器
        
        Args:
            webhook_url: 飞书机器人的webhook地址
        """
        self.webhook_url = webhook_url
        self.headers = {
            'Content-Type': 'application/json'
        }
    
    def _send_request(self, payload: Dict) -> bool:
        """
        发送HTTP请求到飞书webhook
        
        Args:
            payload: 消息载荷
            
        Returns:
            bool: 发送是否成功
        """
        try:
            response = requests.post(
                self.webhook_url,
                headers=self.headers,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info("飞书消息发送成功")
                    return True
                else:
                    logger.error(f"飞书消息发送失败: {result.get('msg', '未知错误')}")
                    return False
            else:
                logger.error(f"HTTP请求失败: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求异常: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"发送消息时发生未知错误: {str(e)}")
            return False
    
    def send_text(self, text: str) -> bool:
        """
        发送文本消息
        
        Args:
            text: 文本内容
            
        Returns:
            bool: 发送是否成功
        """
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        return self._send_request(payload)
    
    def send_rich_text(self, title: str, content: List[List[Dict]]) -> bool:
        """
        发送富文本消息
        
        Args:
            title: 消息标题
            content: 富文本内容，格式为嵌套列表
                    
        Returns:
            bool: 发送是否成功
        """
        payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": content
                    }
                }
            }
        }
        return self._send_request(payload)
    
    def send_market_summary(self, summary_data: Dict) -> bool:
        """
        发送市场概览消息（交互式卡片格式）
        
        Args:
            summary_data: 市场概览数据
            
        Returns:
            bool: 发送是否成功
        """
        if not summary_data:
            logger.warning("市场概览数据为空")
            return False
        
        # 计算统计数据
        total_funds = len(summary_data)
        up_funds = sum(1 for data in summary_data.values() if data.get('change', 0) > 0)
        down_funds = sum(1 for data in summary_data.values() if data.get('change', 0) < 0)
        flat_funds = total_funds - up_funds - down_funds
        
        # 构建卡片内容
        card_content = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "content": "📊 TickEye 基金市场概览",
                    "tag": "plain_text"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"**监控时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n**基金总数**: {total_funds} 只\n**上涨**: {up_funds} 只 | **下跌**: {down_funds} 只 | **平盘**: {flat_funds} 只",
                        "tag": "lark_md"
                    }
                },
                {
                    "tag": "hr"
                }
            ]
        }
        
        # 添加基金详情
        for fund_code, data in summary_data.items():
            fund_name = data.get('name', 'N/A')
            price = data.get('price', 0)
            change = data.get('change', 0)
            
            # 确定趋势图标和颜色
            if change > 0:
                trend_icon = "📈"
                change_color = "green"
            elif change < 0:
                trend_icon = "📉"
                change_color = "red"
            else:
                trend_icon = "➖"
                change_color = "grey"
            
            # 添加基金信息元素
            fund_element = {
                "tag": "div",
                "text": {
                    "content": f"**{fund_code}** {fund_name}\n净值: ¥{price:.4f} | 涨跌: <font color='{change_color}'>{trend_icon} {change:+.2f}%</font>",
                    "tag": "lark_md"
                }
            }
            card_content["elements"].append(fund_element)
        
        # 添加底部信息
        card_content["elements"].extend([
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "content": "数据来源: TickEye 监控系统",
                    "tag": "plain_text"
                }
            }
        ])
        
        payload = {
            "msg_type": "interactive",
            "card": card_content
        }
        
        return self._send_request(payload)
    
    def send_market_summary_table(self, summary_data: Dict) -> bool:
        """
        发送市场概览消息（表格格式）
        
        Args:
            summary_data: 市场概览数据
            
        Returns:
            bool: 发送是否成功
        """
        if not summary_data:
            logger.warning("市场概览数据为空")
            return False
        
        # 构建富文本表格内容
        content = []
        
        # 标题
        content.append([
            {"tag": "text", "text": f"📊 基金市场概览 ({datetime.now().strftime('%Y-%m-%d %H:%M')})", "style": ["bold"]}
        ])
        
        # 空行
        content.append([{"tag": "text", "text": ""}])
        
        # 表头
        content.append([
            {"tag": "text", "text": "基金代码", "style": ["bold"]},
            {"tag": "text", "text": " | "},
            {"tag": "text", "text": "基金名称", "style": ["bold"]},
            {"tag": "text", "text": " | "},
            {"tag": "text", "text": "当前净值", "style": ["bold"]},
            {"tag": "text", "text": " | "},
            {"tag": "text", "text": "涨跌幅", "style": ["bold"]}
        ])
        
        # 表头分割线
        content.append([
            {"tag": "text", "text": "────────┼─────────────────────┼──────────┼──────────"}
        ])
        
        # 数据行
        for fund_code, data in summary_data.items():
            fund_name = data.get('name', 'N/A')
            price = data.get('price', 0)
            change = data.get('change', 0)
            
            # 格式化涨跌幅，添加颜色标识
            if change > 0:
                change_text = f"📈 +{change:.2f}%"
                change_style = ["bold"]
            elif change < 0:
                change_text = f"📉 {change:.2f}%"
                change_style = ["bold"]
            else:
                change_text = f"➖ {change:.2f}%"
                change_style = []
            
            # 截断过长的基金名称
            display_name = fund_name[:18] + ".." if len(fund_name) > 18 else fund_name
            
            # 格式化数据，使用固定宽度对齐
            code_padded = f"{fund_code:<8}"
            name_padded = f"{display_name:<20}"
            price_padded = f"¥{price:.4f}".rjust(10)
            
            content.append([
                {"tag": "text", "text": code_padded},
                {"tag": "text", "text": " │ "},
                {"tag": "text", "text": name_padded},
                {"tag": "text", "text": " │ "},
                {"tag": "text", "text": price_padded},
                {"tag": "text", "text": " │ "},
                {"tag": "text", "text": change_text, "style": change_style}
            ])
        
        # 底部分割线
        content.append([
            {"tag": "text", "text": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"}
        ])
        
        # 数据来源
        content.append([
            {"tag": "text", "text": "数据来源: TickEye 监控系统", "style": ["italic"]}
        ])
        
        return self.send_rich_text("📊 市场概览", content)


def create_notifier_from_env() -> Optional[FeishuNotifier]:
    """
    从环境变量创建飞书通知器
    
    Returns:
        FeishuNotifier: 通知器实例，如果环境变量未设置则返回None
    """
    import os
    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("未设置FEISHU_WEBHOOK_URL环境变量")
        return None
    
    return FeishuNotifier(webhook_url)
