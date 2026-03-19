#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金监测与飞书通知集成脚本
结合 fund_analysis.py 的分析功能和 feishu_notifier.py 的通知功能
Author: TickEye Team
Date: 2025-08-06
"""

import sys
import os
from datetime import datetime
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fund_analysis import get_fund_summary, get_owned_funds
from feishu_notifier import FeishuNotifier
from feishu_config import get_config
from alert_manager import check_and_send_alerts, get_alert_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def convert_fund_data_for_feishu(fund_summaries):
    """
    将 fund_analysis.py 的数据格式转换为 feishu_notifier.py 期望的格式
    
    Args:
        fund_summaries: fund_analysis.py 返回的基金数据列表
        
    Returns:
        dict: 适合飞书通知的数据格式
    """
    feishu_data = {}
    
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
            
            feishu_data[fund_code] = {
                "name": summary['fund_name'],
                "price": price,
                "change": change
            }
    
    return feishu_data


def get_all_fund_summaries(days=1):
    """
    获取所有配置基金的分析数据
    
    Args:
        days: 分析最近多少天的数据
        
    Returns:
        list: 基金分析数据列表
    """
    owned_funds, _ = get_owned_funds()
    if not owned_funds:
        logger.error("未配置任何基金代码！")
        return []
    
    logger.info(f"开始获取 {len(owned_funds)} 个标的的数据...")
    
    fund_summaries = []
    for fund_code in owned_funds:
        logger.info(f"正在获取基金 {fund_code} 的数据...")
        summary = get_fund_summary(fund_code, days)
        fund_summaries.append(summary)
    
    return fund_summaries


def send_fund_analysis_to_feishu(days=1, send_summary=True, send_table=False):
    """
    执行基金分析并发送到飞书群组
    
    Args:
        days: 分析最近多少天的数据
        send_summary: 是否发送市场概览卡片
        send_table: 是否发送市场概览表格
        
    Returns:
        bool: 是否成功
    """
    print("🦉 TickEye 基金监测与飞书通知")
    print("=" * 60)
    
    # 检查飞书配置
    config = get_config()
    webhook_url = config.get_webhook_url()
    
    if not webhook_url:
        print("❌ 错误: 未配置飞书机器人webhook URL")
        print("\n请通过以下方式之一配置:")
        print("1. 设置环境变量: export FEISHU_WEBHOOK_URL='your_webhook_url'")
        print("2. 创建配置文件 feishu_config.json")
        return False
    
    if not config.is_enabled():
        print("⚠️  警告: 飞书通知已被禁用")
        return False
    
    print(f"📡 飞书通知已配置")
    print(f"📅 数据分析天数: {days} 天")
    print()
    
    # 获取基金分析数据
    print("🔍 正在获取基金数据...")
    fund_summaries = get_all_fund_summaries(days)
    
    if not fund_summaries:
        print("❌ 未获取到任何基金数据")
        return False
    
    # 统计分析结果
    total_funds = len(fund_summaries)
    success_funds = [s for s in fund_summaries if s['status'] == '正常']
    success_count = len(success_funds)
    
    print(f"📊 数据获取完成: {success_count}/{total_funds} 只基金数据正常")
    
    if success_count == 0:
        print("❌ 没有成功获取的基金数据，无法发送通知")
        return False
    
    # 转换数据格式
    feishu_data = convert_fund_data_for_feishu(success_funds)
    
    # 创建飞书通知器
    notifier = FeishuNotifier(webhook_url)
    
    # 发送通知
    print("\n📤 正在发送飞书通知...")
    
    success_notifications = 0
    total_notifications = 0
    
    if send_summary:
        total_notifications += 1
        print("  发送市场概览卡片...")
        if notifier.send_market_summary(feishu_data):
            print("  ✅ 市场概览卡片发送成功")
            success_notifications += 1
        else:
            print("  ❌ 市场概览卡片发送失败")
    
    if send_table:
        total_notifications += 1
        print("  发送市场概览表格...")
        if notifier.send_market_summary_table(feishu_data):
            print("  ✅ 市场概览表格发送成功")
            success_notifications += 1
        else:
            print("  ❌ 市场概览表格发送失败")
    
    # 输出结果
    print("\n" + "=" * 60)
    print("📋 执行结果汇总:")
    print(f"  📊 基金数据: {success_count}/{total_funds} 只成功")
    print(f"  📤 飞书通知: {success_notifications}/{total_notifications} 条成功")
    
    # 检查并发送告警
    print("\n🔔 正在检查告警规则...")
    try:
        alerts = check_and_send_alerts(feishu_data)
        if alerts:
            print(f"  ⚠️  触发了 {len(alerts)} 个告警:")
            for alert in alerts:
                print(f"    • {alert['message']}")
        else:
            print("  ✅ 未触发任何告警")
    except Exception as e:
        print(f"  ❌ 告警检查失败: {e}")
    
    if success_notifications == total_notifications:
        print("🎉 基金监测与通知任务完成！")
        return True
    else:
        print("⚠️  部分通知发送失败")
        return False


def main():
    """主函数"""
    # 默认参数
    days = 1
    send_summary = True
    send_table = False
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
            if days <= 0:
                print("❌ 天数必须大于0，使用默认值1天")
                days = 1
        except ValueError:
            print("❌ 请输入有效的天数，使用默认值1天")
            days = 1
    
    # 检查是否要发送表格格式
    if len(sys.argv) > 2 and sys.argv[2].lower() == 'table':
        send_table = True
        print("📋 将同时发送表格格式通知")
    
    # 执行基金分析和通知
    success = send_fund_analysis_to_feishu(days, send_summary, send_table)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
