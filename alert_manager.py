#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
告警管理器 - 处理基金/指数的涨跌阈值告警
Author: TickEye Team
Date: 2026-03-12
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import smtplib
import time
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Union

import requests

# 类型别名
ConfigDict = Dict[str, Any]
AlertMessage = Dict[str, Any]
HistoryRecord = Dict[str, Union[str, float]]
FundItem = Dict[str, Union[str, float, int]]
FundData = Dict[str, FundItem]

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AlertRule:
    """告警规则类"""

    DIRECTION_UP = "up"
    DIRECTION_DOWN = "down"
    VALID_DIRECTIONS = {DIRECTION_UP, DIRECTION_DOWN}
    DEFAULT_DIRECTION = DIRECTION_UP
    DEFAULT_THRESHOLD = 0.0
    DEFAULT_ENABLED = True
    DEFAULT_CODE = ""
    DEFAULT_NAME = ""
    DEFAULT_NOTIFICATION_CHANNELS: List[str] = []

    def __init__(self, rule_config: ConfigDict) -> None:
        """
        初始化告警规则

        Args:
            rule_config: 规则配置字典
        """
        self.code: str = str(rule_config.get("code", self.DEFAULT_CODE))
        self.name: str = str(rule_config.get("name", self.DEFAULT_NAME))
        self.threshold: float = float(
            rule_config.get("threshold", self.DEFAULT_THRESHOLD)
        )
        self.direction: str = str(
            rule_config.get("direction", self.DEFAULT_DIRECTION)
        )
        self.enabled: bool = bool(rule_config.get("enabled", self.DEFAULT_ENABLED))
        self.notification_channels: List[str] = list(
            rule_config.get(
                "notification_channels",
                self.DEFAULT_NOTIFICATION_CHANNELS,
            )
        )

        if not self.code:
            raise ValueError("告警规则必须包含代码(code)")
        if self.direction not in self.VALID_DIRECTIONS:
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

        if self.direction == self.DIRECTION_UP:
            return change_pct >= self.threshold
        return change_pct <= self.threshold

    def get_alert_message(
        self,
        change_pct: float,
        current_value: Union[int, float],
    ) -> AlertMessage:
        """
        获取告警消息

        Args:
            change_pct: 涨跌幅百分比
            current_value: 当前值

        Returns:
            AlertMessage: 告警消息
        """
        direction_text = "上涨" if self.direction == self.DIRECTION_UP else "下跌"
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
            "message": (
                f"{self.name or self.code} {direction_text}超过{threshold_text}，"
                f"当前涨跌幅: {change_pct:.2f}%"
            ),
        }


class NotificationChannel:
    """通知渠道基类"""

    DEFAULT_ENABLED = False

    def __init__(self, config: ConfigDict) -> None:
        self.config: ConfigDict = config
        self.enabled: bool = bool(config.get("enabled", self.DEFAULT_ENABLED))

    def send(self, alert_message: AlertMessage) -> bool:
        """发送通知"""
        raise NotImplementedError("子类必须实现send方法")


class EmailNotification(NotificationChannel):
    """邮件通知"""

    DEFAULT_SMTP_SERVER = ""
    DEFAULT_SMTP_PORT = 587
    DEFAULT_SMTP_USERNAME = ""
    DEFAULT_SMTP_PASSWORD = ""
    DEFAULT_SENDER_EMAIL = ""
    DEFAULT_RECEIVER_EMAILS: List[str] = []
    SUBJECT_TEMPLATE = "📈 基金告警: {name} {direction_text}超过{threshold_text}"
    HTML_TEMPLATE = """
            <html>
            <body>
                <h2>📈 基金告警通知</h2>
                <p><strong>标的:</strong> {name} ({code})</p>
                <p><strong>当前值:</strong> {current_value}</p>
                <p><strong>涨跌幅:</strong> {change_pct:.2f}%</p>
                <p><strong>告警阈值:</strong> {direction_text} {threshold}%</p>
                <p><strong>触发时间:</strong> {timestamp}</p>
                <hr>
                <p><em>来自 TickEye 基金监测系统</em></p>
            </body>
            </html>
    """
    MIME_SUBTYPE_HTML = "html"

    def __init__(self, config: ConfigDict) -> None:
        super().__init__(config)
        self.smtp_server: str = str(
            config.get("smtp_server", self.DEFAULT_SMTP_SERVER)
        )
        self.smtp_port: int = int(config.get("smtp_port", self.DEFAULT_SMTP_PORT))
        self.smtp_username: str = str(
            config.get("smtp_username", self.DEFAULT_SMTP_USERNAME)
        )
        self.smtp_password: str = str(
            config.get("smtp_password", self.DEFAULT_SMTP_PASSWORD)
        )
        self.sender_email: str = str(
            config.get("sender_email", self.DEFAULT_SENDER_EMAIL)
        )
        self.receiver_emails: List[str] = list(
            config.get("receiver_emails", self.DEFAULT_RECEIVER_EMAILS)
        )

    def send(self, alert_message: AlertMessage) -> bool:
        if not self.enabled:
            return False

        try:
            subject = self.SUBJECT_TEMPLATE.format(
                name=alert_message["name"],
                direction_text=alert_message["direction_text"],
                threshold_text=alert_message["threshold_text"],
            )
            body = self.HTML_TEMPLATE.format(**alert_message)

            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(self.receiver_emails)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, self.MIME_SUBTYPE_HTML))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"邮件告警发送成功: {alert_message['code']}")
            return True

        except Exception as exc:
            logger.error(f"邮件告警发送失败: {exc}")
            return False


class FeishuNotification(NotificationChannel):
    """飞书通知"""

    DEFAULT_WEBHOOK_URL = ""
    DEFAULT_TEMPLATE = "default"
    REQUEST_TIMEOUT = 10
    CONTENT_TYPE_JSON = "application/json"
    HEADER_TEMPLATE_UP = "green"
    HEADER_TEMPLATE_DOWN = "red"
    SOURCE_TEXT = "来自 TickEye 基金监测系统"

    def __init__(self, config: ConfigDict) -> None:
        super().__init__(config)
        self.webhook_url: str = str(
            config.get("webhook_url", self.DEFAULT_WEBHOOK_URL)
        )
        self.template: str = str(config.get("template", self.DEFAULT_TEMPLATE))

    def send(self, alert_message: AlertMessage) -> bool:
        if not self.enabled or not self.webhook_url:
            return False

        try:
            card = {
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True,
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"📈 基金告警: {alert_message['name']}",
                        },
                        "template": (
                            self.HEADER_TEMPLATE_DOWN
                            if alert_message["direction"] == AlertRule.DIRECTION_DOWN
                            else self.HEADER_TEMPLATE_UP
                        ),
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": (
                                    f"**标的:** {alert_message['name']} "
                                    f"({alert_message['code']})\n"
                                    f"**当前值:** {alert_message['current_value']}\n"
                                    f"**涨跌幅:** {alert_message['change_pct']:.2f}%\n"
                                    f"**告警阈值:** "
                                    f"{alert_message['direction_text']} "
                                    f"{alert_message['threshold']}%\n"
                                    f"**触发时间:** {alert_message['timestamp']}"
                                ),
                            },
                        },
                        {
                            "tag": "hr",
                        },
                        {
                            "tag": "note",
                            "elements": [
                                {
                                    "tag": "plain_text",
                                    "content": self.SOURCE_TEXT,
                                }
                            ],
                        },
                    ],
                },
            }

            response = requests.post(
                self.webhook_url,
                json=card,
                headers={"Content-Type": self.CONTENT_TYPE_JSON},
                timeout=self.REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                logger.info(f"飞书告警发送成功: {alert_message['code']}")
                return True

            logger.error(
                f"飞书告警发送失败: {response.status_code} - {response.text}"
            )
            return False

        except Exception as exc:
            logger.error(f"飞书告警发送失败: {exc}")
            return False


class WechatWorkNotification(NotificationChannel):
    """企业微信通知"""

    DEFAULT_WEBHOOK_URL = ""
    DEFAULT_KEY = ""
    REQUEST_TIMEOUT = 10
    CONTENT_TYPE_JSON = "application/json"
    MESSAGE_TEMPLATE = (
        "## 📈 基金告警通知\n"
        "> **标的:** {name} ({code})\n"
        "> **当前值:** {current_value}\n"
        "> **涨跌幅:** {change_pct:.2f}%\n"
        "> **告警阈值:** {direction_text} {threshold}%\n"
        "> **触发时间:** {timestamp}\n"
        "> \n"
        "> 来自 TickEye 基金监测系统"
    )

    def __init__(self, config: ConfigDict) -> None:
        super().__init__(config)
        self.webhook_url: str = str(
            config.get("webhook_url", self.DEFAULT_WEBHOOK_URL)
        )
        self.key: str = str(config.get("key", self.DEFAULT_KEY))

    def send(self, alert_message: AlertMessage) -> bool:
        if not self.enabled or not self.webhook_url:
            return False

        try:
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": self.MESSAGE_TEMPLATE.format(**alert_message),
                },
            }

            response = requests.post(
                self.webhook_url,
                json=message,
                headers={"Content-Type": self.CONTENT_TYPE_JSON},
                timeout=self.REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                logger.info(f"企业微信告警发送成功: {alert_message['code']}")
                return True

            logger.error(
                f"企业微信告警发送失败: {response.status_code} - {response.text}"
            )
            return False

        except Exception as exc:
            logger.error(f"企业微信告警发送失败: {exc}")
            return False


class DingTalkNotification(NotificationChannel):
    """钉钉通知"""

    DEFAULT_WEBHOOK_URL = ""
    DEFAULT_SECRET = ""
    REQUEST_TIMEOUT = 10
    CONTENT_TYPE_JSON = "application/json"
    MESSAGE_TITLE_TEMPLATE = "📈 基金告警: {name}"
    MESSAGE_TEXT_TEMPLATE = (
        "### 📈 基金告警通知\n"
        "**标的:** {name} ({code})\n\n"
        "**当前值:** {current_value}\n\n"
        "**涨跌幅:** {change_pct:.2f}%\n\n"
        "**告警阈值:** {direction_text} {threshold}%\n\n"
        "**触发时间:** {timestamp}\n\n"
        "---\n\n"
        "来自 TickEye 基金监测系统"
    )
    TIMESTAMP_MULTIPLIER = 1000
    ENCODING = "utf-8"
    SIGN_SEPARATOR = "\n"
    SIGN_TIMESTAMP_PARAM = "timestamp"
    SIGN_PARAM = "sign"

    def __init__(self, config: ConfigDict) -> None:
        super().__init__(config)
        self.webhook_url: str = str(
            config.get("webhook_url", self.DEFAULT_WEBHOOK_URL)
        )
        self.secret: str = str(config.get("secret", self.DEFAULT_SECRET))

    def send(self, alert_message: AlertMessage) -> bool:
        if not self.enabled or not self.webhook_url:
            return False

        try:
            timestamp = str(round(time.time() * self.TIMESTAMP_MULTIPLIER))
            webhook_url = self.webhook_url

            if self.secret:
                secret_enc = self.secret.encode(self.ENCODING)
                string_to_sign = (
                    f"{timestamp}{self.SIGN_SEPARATOR}{self.secret}"
                ).encode(self.ENCODING)
                hmac_code = hmac.new(
                    secret_enc,
                    string_to_sign,
                    digestmod=hashlib.sha256,
                ).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                webhook_url = (
                    f"{self.webhook_url}&{self.SIGN_TIMESTAMP_PARAM}={timestamp}"
                    f"&{self.SIGN_PARAM}={sign}"
                )

            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": self.MESSAGE_TITLE_TEMPLATE.format(
                        name=alert_message["name"]
                    ),
                    "text": self.MESSAGE_TEXT_TEMPLATE.format(**alert_message),
                },
            }

            response = requests.post(
                webhook_url,
                json=message,
                headers={"Content-Type": self.CONTENT_TYPE_JSON},
                timeout=self.REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                logger.info(f"钉钉告警发送成功: {alert_message['code']}")
                return True

            logger.error(
                f"钉钉告警发送失败: {response.status_code} - {response.text}"
            )
            return False

        except Exception as exc:
            logger.error(f"钉钉告警发送失败: {exc}")
            return False


class TelegramNotification(NotificationChannel):
    """Telegram通知"""

    DEFAULT_BOT_TOKEN = ""
    DEFAULT_CHAT_ID = ""
    REQUEST_TIMEOUT = 10
    API_URL_TEMPLATE = "https://api.telegram.org/bot{bot_token}/sendMessage"
    PARSE_MODE = "Markdown"
    MESSAGE_TEMPLATE = (
        "📈 *基金告警通知*\n\n"
        "*标的:* {name} ({code})\n"
        "*当前值:* {current_value}\n"
        "*涨跌幅:* {change_pct:.2f}%\n"
        "*告警阈值:* {direction_text} {threshold}%\n"
        "*触发时间:* {timestamp}\n\n"
        "来自 TickEye 基金监测系统"
    )

    def __init__(self, config: ConfigDict) -> None:
        super().__init__(config)
        self.bot_token: str = str(
            config.get("bot_token", self.DEFAULT_BOT_TOKEN)
        )
        self.chat_id: str = str(config.get("chat_id", self.DEFAULT_CHAT_ID))

    def send(self, alert_message: AlertMessage) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False

        try:
            text = self.MESSAGE_TEMPLATE.format(**alert_message)
            url = self.API_URL_TEMPLATE.format(bot_token=self.bot_token)
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": self.PARSE_MODE,
            }

            response = requests.post(
                url,
                json=payload,
                timeout=self.REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                logger.info(f"Telegram告警发送成功: {alert_message['code']}")
                return True

            logger.error(
                f"Telegram告警发送失败: {response.status_code} - {response.text}"
            )
            return False

        except Exception as exc:
            logger.error(f"Telegram告警发送失败: {exc}")
            return False


class AlertHistory:
    """告警历史记录"""

    DEFAULT_HISTORY_FILE = "alert_history.json"
    DEFAULT_HISTORY: Dict[str, List[HistoryRecord]] = {}
    MAX_HISTORY_PER_CODE = 100
    DEFAULT_COOLDOWN_MINUTES = 30

    def __init__(self, history_file: str = DEFAULT_HISTORY_FILE) -> None:
        self.history_file: str = history_file
        self.history: Dict[str, List[HistoryRecord]] = self._load_history()

    def _load_history(self) -> Dict[str, List[HistoryRecord]]:
        """加载历史记录"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as file:
                    loaded = json.load(file)
                    return dict(loaded)
            except Exception as exc:
                logger.error(f"加载告警历史失败: {exc}")
                return {}
        return {}

    def _save_history(self) -> None:
        """保存历史记录"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as file:
                json.dump(self.history, file, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"保存告警历史失败: {exc}")

    def add_alert(self, code: str, alert_message: AlertMessage) -> None:
        """添加告警记录"""
        if code not in self.history:
            self.history[code] = []

        self.history[code].append(
            {
                "timestamp": str(alert_message["timestamp"]),
                "change_pct": float(alert_message["change_pct"]),
                "threshold": float(alert_message["threshold"]),
                "direction": str(alert_message["direction"]),
            }
        )

        if len(self.history[code]) > self.MAX_HISTORY_PER_CODE:
            self.history[code] = self.history[code][-self.MAX_HISTORY_PER_CODE :]

        self._save_history()

    def should_send_alert(
        self,
        code: str,
        cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
    ) -> bool:
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
        last_timestamp = last_alert.get("timestamp")
        if not isinstance(last_timestamp, str):
            return True

        last_time = datetime.fromisoformat(last_timestamp)
        now = datetime.now()
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
            timestamp = alert.get("timestamp")
            if not isinstance(timestamp, str):
                continue
            alert_date = datetime.fromisoformat(timestamp).date()
            if alert_date == today:
                count += 1

        return count


class AlertManager:
    """告警管理器"""

    DEFAULT_CONFIG_FILE = "alerts_config.json"
    DEFAULT_ENABLED = False
    DEFAULT_CONFIG = {"enabled": False}
    DEFAULT_GLOBAL_SETTINGS: ConfigDict = {}
    DEFAULT_COOLDOWN_MINUTES = 30
    DEFAULT_MAX_ALERTS_PER_DAY = 10
    DEFAULT_SUMMARY_TIME = "18:00"
    GLOBAL_SETTINGS_KEY = "global_settings"
    RULES_KEY = "rules"
    NOTIFICATION_CHANNELS_KEY = "notification_channels"
    SUMMARY_ENABLED_KEY = "enable_daily_summary"
    SUMMARY_TIME_KEY = "summary_time"
    COOLDOWN_KEY = "cooldown_minutes"
    MAX_ALERTS_PER_DAY_KEY = "max_alerts_per_day"

    CHANNEL_EMAIL = "email"
    CHANNEL_FEISHU = "feishu"
    CHANNEL_WECHAT_WORK = "wechat_work"
    CHANNEL_DINGTALK = "dingtalk"
    CHANNEL_TELEGRAM = "telegram"

    def __init__(self, config_file: str = DEFAULT_CONFIG_FILE) -> None:
        self.config_file: str = config_file
        self.config: ConfigDict = self._load_config()
        self.rules: List[AlertRule] = self._load_rules()
        self.channels: Dict[str, NotificationChannel] = self._load_channels()
        self.history: AlertHistory = AlertHistory()
        self.global_settings: ConfigDict = self.config.get(
            self.GLOBAL_SETTINGS_KEY,
            self.DEFAULT_GLOBAL_SETTINGS,
        )

    def _load_config(self) -> ConfigDict:
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            logger.warning(f"告警配置文件不存在: {self.config_file}")
            return dict(self.DEFAULT_CONFIG)

        try:
            with open(self.config_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as exc:
            logger.error(f"加载告警配置失败: {exc}")
            return dict(self.DEFAULT_CONFIG)

    def _load_rules(self) -> List[AlertRule]:
        """加载告警规则"""
        rules_config: List[ConfigDict] = list(
            self.config.get(self.RULES_KEY, [])
        )
        rules: List[AlertRule] = []

        for rule_config in rules_config:
            try:
                rule = AlertRule(rule_config)
                if rule.enabled:
                    rules.append(rule)
            except Exception as exc:
                logger.error(f"加载告警规则失败: {exc}")

        logger.info(f"加载了 {len(rules)} 个告警规则")
        return rules

    def _load_channels(self) -> Dict[str, NotificationChannel]:
        """加载通知渠道"""
        channels_config: ConfigDict = self.config.get(
            self.NOTIFICATION_CHANNELS_KEY,
            {},
        )
        channels: Dict[str, NotificationChannel] = {}

        if self.CHANNEL_EMAIL in channels_config:
            channels[self.CHANNEL_EMAIL] = EmailNotification(
                channels_config[self.CHANNEL_EMAIL]
            )

        if self.CHANNEL_FEISHU in channels_config:
            channels[self.CHANNEL_FEISHU] = FeishuNotification(
                channels_config[self.CHANNEL_FEISHU]
            )

        if self.CHANNEL_WECHAT_WORK in channels_config:
            channels[self.CHANNEL_WECHAT_WORK] = WechatWorkNotification(
                channels_config[self.CHANNEL_WECHAT_WORK]
            )

        if self.CHANNEL_DINGTALK in channels_config:
            channels[self.CHANNEL_DINGTALK] = DingTalkNotification(
                channels_config[self.CHANNEL_DINGTALK]
            )

        if self.CHANNEL_TELEGRAM in channels_config:
            channels[self.CHANNEL_TELEGRAM] = TelegramNotification(
                channels_config[self.CHANNEL_TELEGRAM]
            )

        logger.info(f"加载了 {len(channels)} 个通知渠道")
        return channels

    def check_alerts(self, fund_data: FundData) -> List[AlertMessage]:
        """
        检查所有基金数据，触发告警

        Args:
            fund_data: 基金数据字典，格式为 {code: {name, price, change}}

        Returns:
            List[AlertMessage]: 触发的告警列表
        """
        if not self.config.get("enabled", self.DEFAULT_ENABLED):
            logger.info("告警功能已禁用")
            return []

        triggered_alerts: List[AlertMessage] = []

        for rule in self.rules:
            code = rule.code

            if code not in fund_data:
                logger.debug(f"规则 {code} 对应的基金数据不存在")
                continue

            data = fund_data[code]
            change_pct = float(data.get("change", 0.0))
            current_value = float(data.get("price", 0.0))

            if rule.should_alert(change_pct):
                cooldown = int(
                    self.global_settings.get(
                        self.COOLDOWN_KEY,
                        self.DEFAULT_COOLDOWN_MINUTES,
                    )
                )
                if not self.history.should_send_alert(code, cooldown):
                    logger.info(f"代码 {code} 仍在冷却时间内，跳过告警")
                    continue

                max_per_day = int(
                    self.global_settings.get(
                        self.MAX_ALERTS_PER_DAY_KEY,
                        self.DEFAULT_MAX_ALERTS_PER_DAY,
                    )
                )
                today_count = self.history.get_today_alerts_count(code)
                if today_count >= max_per_day:
                    logger.warning(
                        f"代码 {code} 今日告警次数已达上限 ({max_per_day}次)"
                    )
                    continue

                alert_message = rule.get_alert_message(change_pct, current_value)

                sent_channels: List[str] = []
                for channel_name in rule.notification_channels:
                    channel: Optional[NotificationChannel] = self.channels.get(
                        channel_name
                    )
                    if channel and channel.send(alert_message):
                        sent_channels.append(channel_name)

                if sent_channels:
                    alert_message["sent_channels"] = sent_channels
                    triggered_alerts.append(alert_message)
                    self.history.add_alert(code, alert_message)

                    logger.info(
                        f"代码 {code} 触发告警，已通过 "
                        f"{', '.join(sent_channels)} 发送通知"
                    )

        return triggered_alerts

    def send_daily_summary(
        self,
        fund_data: FundData,
        triggered_alerts: List[AlertMessage],
    ) -> bool:
        """
        发送每日汇总报告

        Args:
            fund_data: 所有基金数据
            triggered_alerts: 今日触发的告警列表

        Returns:
            bool: 是否发送成功
        """
        if not self.global_settings.get(self.SUMMARY_ENABLED_KEY, False):
            return False

        summary_time = str(
            self.global_settings.get(
                self.SUMMARY_TIME_KEY,
                self.DEFAULT_SUMMARY_TIME,
            )
        )
        current_time = datetime.now().strftime("%H:%M")

        if current_time != summary_time:
            return False

        total_funds = len(fund_data)
        total_alerts = len(triggered_alerts)

        summary_message: AlertMessage = {
            "type": "daily_summary",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_funds": total_funds,
            "total_alerts": total_alerts,
            "triggered_alerts": triggered_alerts,
            "timestamp": datetime.now().isoformat(),
        }

        success = False
        for channel_name, channel in self.channels.items():
            if channel.enabled:
                logger.info(f"发送每日汇总到 {channel_name}")

        _ = summary_message
        return success


_alert_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """获取全局告警管理器实例"""
    global _alert_manager_instance
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager()
    return _alert_manager_instance


def check_and_send_alerts(fund_data: FundData) -> List[AlertMessage]:
    """
    检查并发送告警（便捷函数）

    Args:
        fund_data: 基金数据字典

    Returns:
        List[AlertMessage]: 触发的告警列表
    """
    manager = get_alert_manager()
    return manager.check_alerts(fund_data)


if __name__ == "__main__":
    test_data: FundData = {
        "000001": {"name": "上证指数", "price": 3200.0, "change": 5.5},
        "NDX": {"name": "纳斯达克", "price": 18000.0, "change": 2.8},
        "007360": {"name": "测试基金", "price": 1.2, "change": -3.5},
    }

    alerts = check_and_send_alerts(test_data)
    print(f"触发了 {len(alerts)} 个告警")
    for alert in alerts:
        print(f"告警: {alert['message']}")
