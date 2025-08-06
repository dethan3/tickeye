#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人通知模块
支持多种消息类型：文本、富文本、图片、交互卡片
"""

import json
import requests
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime
import base64
import os

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
                    外层列表表示段落，内层列表表示段落内的元素
                    
        Returns:
            bool: 发送是否成功
            
        Example:
            content = [
                [{"tag": "text", "text": "项目: "}],
                [{"tag": "text", "text": "状态: ", "style": ["bold"]}, 
                 {"tag": "text", "text": "正常", "style": ["bold"]}]
            ]
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
    
    def send_image(self, image_key: str) -> bool:
        """
        发送图片消息
        
        Args:
            image_key: 图片的key，需要先上传图片获取
            
        Returns:
            bool: 发送是否成功
        """
        payload = {
            "msg_type": "image",
            "content": {
                "image_key": image_key
            }
        }
        return self._send_request(payload)
    
    def send_interactive_card(self, card_content: Dict) -> bool:
        """
        发送交互式卡片消息
        
        Args:
            card_content: 卡片内容，遵循飞书卡片格式
            
        Returns:
            bool: 发送是否成功
        """
        payload = {
            "msg_type": "interactive",
            "card": card_content
        }
        return self._send_request(payload)
    
    def send_fund_alert(self, fund_code: str, fund_name: str, 
                       current_price: float, change_percent: float,
                       alert_type: str, alert_message: str) -> bool:
        """
        发送基金告警消息（富文本格式）
        
        Args:
            fund_code: 基金代码
            fund_name: 基金名称
            current_price: 当前价格
            change_percent: 涨跌幅
            alert_type: 告警类型
            alert_message: 告警信息
            
        Returns:
            bool: 发送是否成功
        """
        # 根据涨跌幅确定颜色
        color = "green" if change_percent > 0 else "red" if change_percent < 0 else "grey"
        change_symbol = "📈" if change_percent > 0 else "📉" if change_percent < 0 else "➡️"
        
        title = f"🚨 基金告警 - {alert_type}"
        
        content = [
            [{"tag": "text", "text": f"基金代码: {fund_code}"}],
            [{"tag": "text", "text": f"基金名称: {fund_name}"}],
            [{"tag": "text", "text": f"当前净值: ¥{current_price:.4f}"}],
            [{"tag": "text", "text": f"涨跌幅: {change_symbol} {change_percent:+.2f}%", 
              "style": ["bold"]}],
            [{"tag": "text", "text": f"告警信息: {alert_message}", 
              "style": ["bold"]}],
            [{"tag": "text", "text": f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}]
        ]
        
        return self.send_rich_text(title, content)
    
    def send_market_summary(self, summary_data: Dict) -> bool:
        """
        发送市场概览消息（交互式卡片格式）
        
        Args:
            summary_data: 市场概览数据
            
        Returns:
            bool: 发送是否成功
        """
        card_content = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📊 每日市场概览"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                },
                {
                    "tag": "hr"
                }
            ]
        }
        
        # 添加基金数据
        for fund_code, data in summary_data.items():
            change = data.get('change', 0)
            
            # 根据涨跌情况选择标识和颜色
            if change > 0:
                change_indicator = "📈"
                change_text = f"<font color='red'>**涨跌**: {change_indicator} +{change:.2f}%</font>"
            elif change < 0:
                change_indicator = "📉"
                change_text = f"<font color='green'>**涨跌**: {change_indicator} {change:.2f}%</font>"
            else:
                change_indicator = "➖"
                change_text = f"**涨跌**: {change_indicator} {change:.2f}%"
            
            element = {
                "tag": "div",
                "fields": [
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**{fund_code}**\n{data.get('name', 'N/A')}"
                        }
                    },
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**净值**: ¥{data.get('price', 0):.4f}\n{change_text}"
                        }
                    }
                ]
            }
            card_content["elements"].append(element)
        
        return self.send_interactive_card(card_content)
    
    def send_market_summary_table(self, summary_data: Dict) -> bool:
        """
        发送市场概览消息（表格格式）
        
        Args:
            summary_data: 市场概览数据
            
        Returns:
            bool: 发送是否成功
        """
        # 构建富文本内容，使用文本格式模拟表格
        content = []
        
        # 标题行
        content.append([
            {"tag": "text", "text": "📊 市场概览", "style": ["bold"]}
        ])
        
        # 更新时间
        content.append([
            {"tag": "text", "text": f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
        ])
        
        # 分割线
        content.append([
            {"tag": "text", "text": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"}
        ])
        
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
    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("未设置FEISHU_WEBHOOK_URL环境变量")
        return None
    
    return FeishuNotifier(webhook_url)


# 示例用法
if __name__ == "__main__":
    # 从环境变量获取webhook URL
    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("请设置FEISHU_WEBHOOK_URL环境变量")
        exit(1)
    
    # 创建通知器
    notifier = FeishuNotifier(webhook_url)
    
    # 测试文本消息
    print("测试文本消息...")
    notifier.send_text("TickEye 系统启动成功！")
    
    # 测试富文本消息
    print("测试富文本消息...")
    content = [
        [{"tag": "text", "text": "系统状态报告"}],
        [{"tag": "text", "text": "状态: ", "style": ["bold"]}, 
         {"tag": "text", "text": "正常运行", "style": ["bold"]}],
        [{"tag": "text", "text": "监控基金数量: 5"}]
    ]
    notifier.send_rich_text("📊 TickEye 状态", content)
    
    # 测试基金告警
    print("测试基金告警...")
    notifier.send_fund_alert(
        fund_code="270042",
        fund_name="广发纳指100ETF联接（QDII）人民币A",
        current_price=1.2345,
        change_percent=2.56,
        alert_type="价格上涨",
        alert_message="基金净值上涨超过2%"
    )
