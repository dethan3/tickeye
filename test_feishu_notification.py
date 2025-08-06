#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书通知功能测试脚本 - 市场概览专用
测试市场概览消息：卡片格式和表格格式
"""

import os
import sys
import time
from datetime import datetime
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from feishu_notifier import FeishuNotifier
from feishu_config import get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_market_summary(notifier: FeishuNotifier) -> bool:
    """测试市场概览消息（卡片格式）"""
    print("🧪 测试市场概览消息（卡片格式）...")
    
    # 模拟市场数据
    summary_data = {
        "270042": {
            "name": "广发纳指100ETF联接（QDII）人民币A",
            "price": 1.2345,
            "change": 2.56
        },
        "000001": {
            "name": "华夏成长混合",
            "price": 2.1567,
            "change": -1.23
        },
        "110022": {
            "name": "易方达消费行业股票",
            "price": 3.4567,
            "change": 0.89
        }
    }
    
    print("  发送市场概览卡片...")
    if notifier.send_market_summary(summary_data):
        print("  ✅ 市场概览消息发送成功")
        return True
    else:
        print("  ❌ 市场概览消息发送失败")
        return False


def test_market_summary_table(notifier: FeishuNotifier) -> bool:
    """测试市场概览表格消息"""
    print("🧪 测试市场概览表格消息...")
    
    # 模拟市场数据 - 包含更多样化的数据用于测试表格效果
    summary_data = {
        "270042": {
            "name": "广发纳指100ETF联接（QDII）人民币A",
            "price": 1.2345,
            "change": 2.56
        },
        "000001": {
            "name": "华夏成长混合",
            "price": 2.1567,
            "change": -1.23
        },
        "110022": {
            "name": "易方达消费行业股票",
            "price": 3.4567,
            "change": 0.89
        },
        "161725": {
            "name": "招商中证白酒指数分级",
            "price": 0.9876,
            "change": -3.45
        },
        "519674": {
            "name": "银河创新成长混合型证券投资基金",
            "price": 4.5678,
            "change": 0.00
        }
    }
    
    print("  发送市场概览表格...")
    if notifier.send_market_summary_table(summary_data):
        print("  ✅ 市场概览表格消息发送成功")
        return True
    else:
        print("  ❌ 市场概览表格消息发送失败")
        return False


def main():
    """主测试函数"""
    print("🚀 开始飞书市场概览消息测试")
    print("=" * 50)
    
    # 获取配置
    config = get_config()
    webhook_url = config.get_webhook_url()
    
    if not webhook_url:
        print("❌ 错误: 未配置飞书机器人webhook URL")
        print("\n请通过以下方式之一配置:")
        print("1. 设置环境变量: export FEISHU_WEBHOOK_URL='your_webhook_url'")
        print("2. 创建配置文件 feishu_config.json")
        print("3. 在代码中调用 config.set_webhook_url()")
        return False
    
    if not config.is_enabled():
        print("⚠️  警告: 飞书通知已被禁用")
        return False
    
    print(f"📡 使用webhook URL: {webhook_url[:50]}...")
    print(f"⚙️  超时设置: {config.get_timeout()}秒")
    print(f"🔄 重试次数: {config.get_retry_times()}次")
    print()
    
    # 创建通知器
    notifier = FeishuNotifier(webhook_url)
    
    # 执行测试
    test_results = []
    
    try:
        # 1. 测试市场概览（卡片格式）
        test_results.append(("市场概览（卡片格式）", test_market_summary(notifier)))
        print()
        
        # 等待一秒避免发送过快
        time.sleep(1)
        
        # 2. 测试市场概览（表格格式）
        test_results.append(("市场概览（表格格式）", test_market_summary_table(notifier)))
        print()
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        return False
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        return False
    
    # 输出测试结果
    print("=" * 50)
    print("📋 测试结果汇总:")
    
    success_count = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            success_count += 1
    
    print(f"\n🎯 总体结果: {success_count}/{len(test_results)} 项测试通过")
    
    if success_count == len(test_results):
        print("🎉 所有市场概览测试通过！")
        return True
    else:
        print("⚠️  部分测试失败，请检查配置和网络连接")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
