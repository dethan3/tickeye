#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的告警检查脚本
可以单独运行来检查告警规则
Author: TickEye Team
Date: 2026-03-12
"""

import sys
import os
import logging
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fund_analysis import get_fund_summary, get_owned_funds
from alert_manager import check_and_send_alerts, get_alert_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def convert_fund_data_for_alerts(fund_summaries):
    """
    将 fund_analysis.py 的数据格式转换为告警管理器期望的格式
    
    Args:
        fund_summaries: fund_analysis.py 返回的基金数据列表
        
    Returns:
        dict: 适合告警检查的数据格式
    """
    alert_data = {}
    
    for summary in fund_summaries:
        # 只处理状态正常的基金
        if summary['status'] == '正常':
            fund_code = summary['fund_code']
            
            # 提取净值（去掉字符串格式）
            try:
                price = float(summary['net_value'])
            except (ValueError, TypeError):
                price = 0.0
            
            # 提取涨跌幅（去掉%符号）
            try:
                change_str = summary['change_pct']
                if change_str != 'N/A' and '%' in change_str:
                    change = float(change_str.replace('%', ''))
                else:
                    change = 0.0
            except (ValueError, TypeError):
                change = 0.0
            
            alert_data[fund_code] = {
                "name": summary['fund_name'],
                "price": price,
                "change": change
            }
    
    return alert_data


def get_all_fund_data(days=1):
    """
    获取所有配置基金的分析数据
    
    Args:
        days: 分析最近多少天的数据
        
    Returns:
        dict: 基金分析数据字典
    """
    owned_funds, _ = get_owned_funds()
    if not owned_funds:
        logger.error("未配置任何基金代码！")
        return {}
    
    logger.info(f"开始获取 {len(owned_funds)} 个标的的数据...")
    
    fund_summaries = []
    for fund_code in owned_funds:
        logger.info(f"正在获取基金 {fund_code} 的数据...")
        summary = get_fund_summary(fund_code, days)
        fund_summaries.append(summary)
    
    return convert_fund_data_for_alerts(fund_summaries)


def check_alerts_standalone(days=1):
    """
    独立的告警检查函数
    
    Args:
        days: 分析最近多少天的数据
        
    Returns:
        bool: 是否成功执行
    """
    print("🔔 TickEye 告警检查")
    print("=" * 60)
    
    # 检查告警配置
    alert_manager = get_alert_manager()
    if not alert_manager.config.get('enabled', False):
        print("⚠️  告警功能已禁用")
        print("请在 alerts_config.json 中启用告警功能")
        return False
    
    print("📊 告警配置已加载")
    print(f"📅 数据分析天数: {days} 天")
    print(f"📋 告警规则数: {len(alert_manager.rules)}")
    print(f"📱 通知渠道数: {len(alert_manager.channels)}")
    print()
    
    # 获取基金数据
    print("🔍 正在获取基金数据...")
    fund_data = get_all_fund_data(days)
    
    if not fund_data:
        print("❌ 未获取到任何基金数据")
        return False
    
    print(f"✅ 成功获取 {len(fund_data)} 个标的的数据")
    
    # 检查告警
    print("\n🔔 正在检查告警规则...")
    alerts = check_and_send_alerts(fund_data)
    
    if alerts:
        print(f"⚠️  触发了 {len(alerts)} 个告警:")
        for i, alert in enumerate(alerts, 1):
            print(f"\n  {i}. {alert['message']}")
            print(f"     代码: {alert['code']}")
            print(f"     当前值: {alert['current_value']}")
            print(f"     涨跌幅: {alert['change_pct']:.2f}%")
            print(f"     阈值: {alert['direction_text']} {alert['threshold']}%")
            print(f"     通知渠道: {', '.join(alert.get('sent_channels', []))}")
            print(f"     触发时间: {alert['timestamp']}")
    else:
        print("✅ 未触发任何告警")
    
    # 显示告警规则统计
    print("\n📊 告警规则统计:")
    for rule in alert_manager.rules:
        code = rule.code
        name = rule.name or code
        threshold = rule.threshold
        direction = "上涨" if rule.direction == 'up' else "下跌"
        channels = ', '.join(rule.notification_channels) if rule.notification_channels else "无"
        
        # 检查该代码是否有数据
        has_data = code in fund_data
        current_change = fund_data.get(code, {}).get('change', 'N/A') if has_data else 'N/A'
        
        status = "✅ 正常" if rule.enabled else "❌ 禁用"
        data_status = "📊 有数据" if has_data else "❌ 无数据"
        
        print(f"  • {name} ({code}): {direction} {threshold}% → {channels}")
        print(f"     状态: {status} | {data_status} | 当前涨跌幅: {current_change}%")
    
    return True


def show_alert_history():
    """显示告警历史"""
    alert_manager = get_alert_manager()
    history = alert_manager.history.history
    
    if not history:
        print("📝 告警历史为空")
        return
    
    print("📝 告警历史记录:")
    for code, alerts in history.items():
        print(f"\n  {code} ({len(alerts)} 条记录):")
        for alert in alerts[-5:]:  # 只显示最近5条
            timestamp = alert['timestamp']
            change_pct = alert['change_pct']
            threshold = alert['threshold']
            direction = "上涨" if alert['direction'] == 'up' else "下跌"
            print(f"    • {timestamp}: {direction} {threshold}% (实际: {change_pct:.2f}%)")


def main():
    """主函数"""
    # 默认参数
    days = 1
    show_history = False
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == 'history':
            show_history = True
        else:
            try:
                days = int(sys.argv[1])
                if days <= 0:
                    print("❌ 天数必须大于0，使用默认值1天")
                    days = 1
            except ValueError:
                print("❌ 请输入有效的天数，使用默认值1天")
                days = 1
    
    if show_history:
        show_alert_history()
    else:
        success = check_alerts_standalone(days)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()