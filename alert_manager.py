#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
告警管理器 - 处理基金/指数的涨跌阈值告警
Author: TickEye Team
Date: 2026-03-12
"""

import os
import json
import logging
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import requests
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlertRule:
    """告警规则类"""
    
    def __init__(self, rule_config: Dict[str, Any]):
        """
        初始化告警规则
        
        Args:
            rule_config: 规则配置字典
        """
        self.code = rule_config.get('code', '')
        self.name = rule_config.get('name', '')
        self.threshold = float(rule_config.get('threshold', 0.0))
        self.direction = rule_config.get('direction', 'up')  # 'up' or 'down'
        self.enabled = rule_config.get('enabled', True)
        self.notification_channels = rule_config.get('notification_channels', [])
        
        # 验证配置
        if not self.code:
            raise ValueError("告警规则必须包含代码(code)")
        if self.direction not in ['up', 'down']:
            raise ValueError("告警规则方向(direction)必须是'up'或'down'")
    
    def should_alert(self, change_pct: float) -> bool:
        """
        检查是否应该触发告警
        
        Args:
            change_pct: 涨跌幅百分比
            
        Returns:
            bool: 是否触发告警
        """
        if not self.enabled:
            return False
        
        if self.direction == 'up':
            return change_pct >= self.threshold
        else:  # down
            return change_pct <= self.threshold
    
    def get_alert_message(self, change_pct: float, current_value: float) -> Dict[str, Any]:
        """
        获取告警消息
        
        Args:
            change_pct: 涨跌幅百分比
            current_value: 当前值
            
        Returns:
            Dict: 告警消息
        """
        direction_text = "上涨" if self.direction == 'up' else "下跌"
        threshold_text = f"{abs(self.threshold)}%"
        
        return {
            "code": self.code,
            "name": self.name or self.code,
            "current_value": current_value,
            "change_pct": change_pct,
            "threshold": self.threshold,
            "direction": self.direction,
            "direction_text": direction_text,
            "threshold_text": threshold_text,
            "timestamp": datetime.now().isoformat(),
            "message": f"{self.name or self.code} {direction_text}超过{threshold_text}，当前涨跌幅: {change_pct:.2f}%"
        }


class NotificationChannel:
    """通知渠道基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
    
    def send(self, alert_message: Dict[str, Any]) -> bool:
        """发送通知"""
        raise NotImplementedError("子类必须实现send方法")


class EmailNotification(NotificationChannel):
    """邮件通知"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_server = config.get('smtp_server', '')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username', '')
        self.smtp_password = config.get('smtp_password', '')
        self.sender_email = config.get('sender_email', '')
        self.receiver_emails = config.get('receiver_emails', [])
    
    def send(self, alert_message: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        
        try:
            # 创建邮件内容
            subject = f"📈 基金告警: {alert_message['name']} {alert_message['direction_text']}超过{alert_message['threshold_text']}"
            
            body = f"""
            <html>
            <body>
                <h2>📈 基金告警通知</h2>
                <p><strong>标的:</strong> {alert_message['name']} ({alert_message['code']})</p>
                <p><strong>当前值:</strong> {alert_message['current_value']}</p>
                <p><strong>涨跌幅:</strong> {alert_message['change_pct']:.2f}%</p>
                <p><strong>告警阈值:</strong> {alert_message['direction_text']} {alert_message['threshold']}%</p>
                <p><strong>触发时间:</strong> {alert_message['timestamp']}</p>
                <hr>
                <p><em>来自 TickEye 基金监测系统</em></p>
            </body>
            </html>
            """
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.receiver_emails)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"邮件告警发送成功: {alert_message['code']}")
            return True
            
        except Exception as e:
            logger.error(f"邮件告警发送失败: {e}")
            return False


class FeishuNotification(NotificationChannel):
    """飞书通知"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url', '')
        self.template = config.get('template', 'default')
    
    def send(self, alert_message: Dict[str, Any]) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        
        try:
            # 创建飞书消息卡片
            card = {
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"📈 基金告警: {alert_message['name']}"
                        },
                        "template": "red" if alert_message['direction'] == 'down' else "green"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**标的:** {alert_message['name']} ({alert_message['code']})\n"
                                          f"**当前值:** {alert_message['current_value']}\n"
                                          f"**涨跌幅:** {alert_message['change_pct']:.2f}%\n"
                                          f"**告警阈值:** {alert_message['direction_text']} {alert_message['threshold']}%\n"
                                          f"**触发时间:** {alert_message['timestamp']}"
                            }
                        },
                        {
                            "tag": "hr"
                        },
                        {
                            "tag": "note",
                            "elements": [
                                {
                                    "tag": "plain_text",
                                    "content": "来自 TickEye 基金监测系统"
                                }
                            ]
                        }
                    ]
                }
            }
            
            # 发送请求
            response = requests.post(
                self.webhook_url,
                json=card,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"飞书告警发送成功: {alert_message['code']}")
                return True
            else:
                logger.error(f"飞书告警发送失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"飞书告警发送失败: {e}")
            return False


class WechatWorkNotification(NotificationChannel):
    """企业微信通知"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url', '')
        self.key = config.get('key', '')
    
    def send(self, alert_message: Dict[str, Any]) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        
        try:
            # 创建企业微信消息
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"## 📈 基金告警通知\n"
                              f"> **标的:** {alert_message['name']} ({alert_message['code']})\n"
                              f"> **当前值:** {alert_message['current_value']}\n"
                              f"> **涨跌幅:** {alert_message['change_pct']:.2f}%\n"
                              f"> **告警阈值:** {alert_message['direction_text']} {alert_message['threshold']}%\n"
                              f"> **触发时间:** {alert_message['timestamp']}\n"
                              f"> \n"
                              f"> 来自 TickEye 基金监测系统"
                }
            }
            
            # 发送请求
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"企业微信告警发送成功: {alert_message['code']}")
                return True
            else:
                logger.error(f"企业微信告警发送失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"企业微信告警发送失败: {e}")
            return False


class DingTalkNotification(NotificationChannel):
    """钉钉通知"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url', '')
        self.secret = config.get('secret', '')
    
    def send(self, alert_message: Dict[str, Any]) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        
        try:
            import hmac
            import hashlib
            import base64
            import urllib.parse
            
            # 如果有secret，计算签名
            timestamp = str(round(time.time() * 1000))
            sign = ''
            
            if self.secret:
                secret_enc = self.secret.encode('utf-8')
                string_to_sign = f"{timestamp}\n{self.secret}"
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                webhook_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
            else:
                webhook_url = self.webhook_url
            
            # 创建钉钉消息
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"📈 基金告警: {alert_message['name']}",
                    "text": f"### 📈 基金告警通知\n"
                           f"**标的:** {alert_message['name']} ({alert_message['code']})\n\n"
                           f"**当前值:** {alert_message['current_value']}\n\n"
                           f"**涨跌幅:** {alert_message['change_pct']:.2f}%\n\n"
                           f"**告警阈值:** {alert_message['direction_text']} {alert_message['threshold']}%\n\n"
                           f"**触发时间:** {alert_message['timestamp']}\n\n"
                           f"---\n\n"
                           f"来自 TickEye 基金监测系统"
                }
            }
            
            # 发送请求
            response = requests.post(
                webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"钉钉告警发送成功: {alert_message['code']}")
                return True
            else:
                logger.error(f"钉钉告警发送失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"钉钉告警发送失败: {e}")
            return False


class TelegramNotification(NotificationChannel):
    """Telegram通知"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get('bot_token', '')
        self.chat_id = config.get('chat_id', '')
    
    def send(self, alert_message: Dict[str, Any]) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        
        try:
            # 创建Telegram消息
            text = f"📈 *基金告警通知*\n\n"
            text += f"*标的:* {alert_message['name']} ({alert_message['code']})\n"
            text += f"*当前值:* {alert_message['current_value']}\n"
            text += f"*涨跌幅:* {alert_message['change_pct']:.2f}%\n"
            text += f"*告警阈值:* {alert_message['direction_text']} {alert_message['threshold']}%\n"
            text += f"*触发时间:* {alert_message['timestamp']}\n\n"
            text += f"来自 TickEye 基金监测系统"
            
            # 发送请求
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Telegram告警发送成功: {alert_message['code']}")
                return True
            else:
                logger.error(f"Telegram告警发送失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram告警发送失败: {e}")
            return False


class AlertHistory:
    """告警历史记录"""
    
    def __init__(self, history_file: str = "alert_history.json"):
        self.history_file = history_file
        self.history = self._load_history()
    
    def _load_history(self) -> Dict[str, List[Dict]]:
        """加载历史记录"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载告警历史失败: {e}")
                return {}
        return {}
    
    def _save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存告警历史失败: {e}")
    
    def add_alert(self, code: str, alert_message: Dict[str, Any]):
        """添加告警记录"""
        if code not in self.history:
            self.history[code] = []
        
        self.history[code].append({
            "timestamp": alert_message['timestamp'],
            "change_pct": alert_message['change_pct'],
            "threshold": alert_message['threshold'],
            "direction": alert_message['direction']
        })
        
        # 只保留最近100条记录
        if len(self.history[code]) > 100:
            self.history[code] = self.history[code][-100:]
        
        self._save_history()
    
    def should_send_alert(self, code: str, cooldown_minutes: int = 30) -> bool:
        """
        检查是否应该发送告警（避免重复通知）
        
        Args:
            code: 基金/指数代码
            cooldown_minutes: 冷却时间（分钟）
            
        Returns:
            bool: 是否应该发送告警
        """
        if code not in self.history or not self.history[code]:
            return True
        
        last_alert = self.history[code][-1]
        last_time = datetime.fromisoformat(last_alert['timestamp'])
        now = datetime.now()
        
        # 检查是否在冷却时间内
        cooldown_seconds = cooldown_minutes * 60
        time_diff = (now - last_time).total_seconds()
        
        return time_diff > cooldown_seconds
    
    def get_today_alerts_count(self, code: str) -> int:
        """获取今天该代码的告警次数"""
        if code not in self.history:
            return 0
        
        today = datetime.now().date()
        count = 0
        
        for alert in self.history[code]:
            alert_date = datetime.fromisoformat(alert['timestamp']).date()
            if alert_date == today:
                count += 1
        
        return count


class AlertManager:
    """告警管理器"""
    
    def __init__(self, config_file: str = "alerts_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self.rules = self._load_rules()
        self.channels = self._load_channels()
        self.history = AlertHistory()
        self.global_settings = self.config.get('global_settings', {})
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            logger.warning(f"告警配置文件不存在: {self.config_file}")
            return {"enabled": False}
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载告警配置失败: {e}")
            return {"enabled": False}
    
    def _load_rules(self) -> List[AlertRule]:
        """加载告警规则"""
        rules_config = self.config.get('rules', [])
        rules = []
        
        for rule_config in rules_config:
            try:
                rule = AlertRule(rule_config)
                if rule.enabled:
                    rules.append(rule)
            except Exception as e:
                logger.error(f"加载告警规则失败: {e}")
        
        logger.info(f"加载了 {len(rules)} 个告警规则")
        return rules
    
    def _load_channels(self) -> Dict[str, NotificationChannel]:
        """加载通知渠道"""
        channels_config = self.config.get('notification_channels', {})
        channels = {}
        
        # 邮件渠道
        if 'email' in channels_config:
            channels['email'] = EmailNotification(channels_config['email'])
        
        # 飞书渠道
        if 'feishu' in channels_config:
            channels['feishu'] = FeishuNotification(channels_config['feishu'])
        
        # 企业微信渠道
        if 'wechat_work' in channels_config:
            channels['wechat_work'] = WechatWorkNotification(channels_config['wechat_work'])
        
        # 钉钉渠道
        if 'dingtalk' in channels_config:
            channels['dingtalk'] = DingTalkNotification(channels_config['dingtalk'])
        
        # Telegram渠道
        if 'telegram' in channels_config:
            channels['telegram'] = TelegramNotification(channels_config['telegram'])
        
        logger.info(f"加载了 {len(channels)} 个通知渠道")
        return channels
    
    def check_alerts(self, fund_data: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """
        检查所有基金数据，触发告警
        
        Args:
            fund_data: 基金数据字典，格式为 {code: {name, price, change}}
            
        Returns:
            List: 触发的告警列表
        """
        if not self.config.get('enabled', False):
            logger.info("告警功能已禁用")
            return []
        
        triggered_alerts = []
        
        for rule in self.rules:
            code = rule.code
            
            if code not in fund_data:
                logger.debug(f"规则 {code} 对应的基金数据不存在")
                continue
            
            data = fund_data[code]
            change_pct = data.get('change', 0.0)
            current_value = data.get('price', 0.0)
            
            # 检查是否应该触发告警
            if rule.should_alert(change_pct):
                # 检查冷却时间
                cooldown = self.global_settings.get('cooldown_minutes', 30)
                if not self.history.should_send_alert(code, cooldown):
                    logger.info(f"代码 {code} 仍在冷却时间内，跳过告警")
                    continue
                
                # 检查每日最大告警次数
                max_per_day = self.global_settings.get('max_alerts_per_day', 10)
                today_count = self.history.get_today_alerts_count(code)
                if today_count >= max_per_day:
                    logger.warning(f"代码 {code} 今日告警次数已达上限 ({max_per_day}次)")
                    continue
                
                # 创建告警消息
                alert_message = rule.get_alert_message(change_pct, current_value)
                
                # 发送通知
                sent_channels = []
                for channel_name in rule.notification_channels:
                    if channel_name in self.channels:
                        channel = self.channels[channel_name]
                        if channel.send(alert_message):
                            sent_channels.append(channel_name)
                
                if sent_channels:
                    alert_message['sent_channels'] = sent_channels
                    triggered_alerts.append(alert_message)
                    
                    # 记录到历史
                    self.history.add_alert(code, alert_message)
                    
                    logger.info(f"代码 {code} 触发告警，已通过 {', '.join(sent_channels)} 发送通知")
        
        return triggered_alerts
    
    def send_daily_summary(self, fund_data: Dict[str, Dict], triggered_alerts: List[Dict[str, Any]]) -> bool:
        """
        发送每日汇总报告
        
        Args:
            fund_data: 所有基金数据
            triggered_alerts: 今日触发的告警列表
            
        Returns:
            bool: 是否发送成功
        """
        if not self.global_settings.get('enable_daily_summary', False):
            return False
        
        # 检查是否应该发送每日汇总
        summary_time = self.global_settings.get('summary_time', '18:00')
        current_time = datetime.now().strftime('%H:%M')
        
        if current_time != summary_time:
            return False
        
        # 创建汇总消息
        total_funds = len(fund_data)
        total_alerts = len(triggered_alerts)
        
        summary_message = {
            "type": "daily_summary",
            "date": datetime.now().strftime('%Y-%m-%d'),
            "total_funds": total_funds,
            "total_alerts": total_alerts,
            "triggered_alerts": triggered_alerts,
            "timestamp": datetime.now().isoformat()
        }
        
        # 发送到所有启用的渠道
        success = False
        for channel_name, channel in self.channels.items():
            if channel.enabled:
                # 这里需要为每个渠道实现汇总消息的发送
                # 暂时只记录日志
                logger.info(f"发送每日汇总到 {channel_name}")
        
        return success


# 全局告警管理器实例
_alert_manager_instance = None

def get_alert_manager() -> AlertManager:
    """获取全局告警管理器实例"""
    global _alert_manager_instance
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager()
    return _alert_manager_instance


def check_and_send_alerts(fund_data: Dict[str, Dict]) -> List[Dict[str, Any]]:
    """
    检查并发送告警（便捷函数）
    
    Args:
        fund_data: 基金数据字典
        
    Returns:
        List: 触发的告警列表
    """
    manager = get_alert_manager()
    return manager.check_alerts(fund_data)


if __name__ == "__main__":
    # 测试代码
    test_data = {
        "000001": {"name": "上证指数", "price": 3200.0, "change": 5.5},
        "NDX": {"name": "纳斯达克", "price": 18000.0, "change": 2.8},
        "007360": {"name": "测试基金", "price": 1.2, "change": -3.5}
    }
    
    alerts = check_and_send_alerts(test_data)
    print(f"触发了 {len(alerts)} 个告警")
    for alert in alerts:
        print(f"告警: {alert['message']}")