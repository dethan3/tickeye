#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TickEye 快速全面功能测试
从头开始测试所有功能模块
"""

import sys
import os
import time
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_header(test_name):
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print(f"{'='*60}")

def test_result(name, success, message="", duration=0):
    status = "✅ PASS" if success else "❌ FAIL"
    duration_str = f" ({duration:.2f}s)" if duration > 0 else ""
    print(f"{status} {name}{duration_str}")
    if message:
        print(f"    {message}")
    return success

def main():
    print("🦉 TickEye 快速全面功能测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    total_tests = 0
    passed_tests = 0
    start_time = time.time()
    
    # 测试1: 基础依赖导入
    test_header("测试 1: 基础依赖导入")
    test_start = time.time()
    try:
        import akshare as ak
        import pandas as pd
        import requests
        print("✓ 基础库导入成功: akshare, pandas, requests")
        success = test_result("基础依赖导入", True, "所有基础库导入正常", time.time() - test_start)
    except Exception as e:
        success = test_result("基础依赖导入", False, f"导入失败: {e}", time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 测试2: 项目模块导入
    test_header("测试 2: 项目模块导入")
    test_start = time.time()
    try:
        from monitor.fetcher import SimpleFundDataFetcher
        from monitor.robust_market_fetcher import RobustMarketFetcher
        from utils.logger import setup_logger
        print("✓ 项目模块导入成功")
        success = test_result("项目模块导入", True, "所有项目模块导入正常", time.time() - test_start)
    except Exception as e:
        success = test_result("项目模块导入", False, f"导入失败: {e}", time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 测试3: AKShare API连接性
    test_header("测试 3: AKShare API连接性")
    test_start = time.time()
    try:
        import akshare as ak
        
        # 测试基金API
        print("  正在测试基金API...")
        df_funds = ak.fund_open_fund_daily_em()
        funds_count = len(df_funds) if df_funds is not None else 0
        
        # 测试股票API
        print("  正在测试股票API...")
        df_stocks = ak.stock_zh_a_spot_em()
        stocks_count = len(df_stocks) if df_stocks is not None else 0
        
        if funds_count > 0 and stocks_count > 0:
            message = f"基金数据: {funds_count} 条, 股票数据: {stocks_count} 条"
            success = test_result("AKShare API连接性", True, message, time.time() - test_start)
        else:
            success = test_result("AKShare API连接性", False, "API返回空数据", time.time() - test_start)
            
    except Exception as e:
        success = test_result("AKShare API连接性", False, f"API连接失败: {e}", time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 测试4: 原始数据获取器
    test_header("测试 4: 原始数据获取器")
    test_start = time.time()
    try:
        from monitor.fetcher import SimpleFundDataFetcher
        
        fetcher = SimpleFundDataFetcher()
        print("  正在测试开放式基金数据获取...")
        funds_data = fetcher.get_open_fund_data()
        
        if funds_data is not None and not funds_data.empty:
            message = f"成功获取 {len(funds_data)} 条基金数据"
            success = test_result("原始数据获取器", True, message, time.time() - test_start)
        else:
            success = test_result("原始数据获取器", False, "数据获取失败", time.time() - test_start)
            
    except Exception as e:
        success = test_result("原始数据获取器", False, f"测试失败: {e}", time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 测试5: 健壮数据获取器
    test_header("测试 5: 健壮数据获取器")
    test_start = time.time()
    try:
        from monitor.robust_market_fetcher import RobustMarketFetcher
        
        fetcher = RobustMarketFetcher(max_retries=2, cache_duration=60)
        print("  正在测试健壮基金数据获取...")
        
        # 测试基金数据
        funds_data = fetcher.get_fund_data_robust(['270042', '000001'])
        funds_found = len(funds_data) if funds_data is not None else 0
        
        # 测试股票数据
        print("  正在测试健壮股票数据获取...")
        stocks_data = fetcher.get_stock_data_robust(['000001', '600036'])
        stocks_found = len(stocks_data) if stocks_data is not None else 0
        
        if funds_found > 0 or stocks_found > 0:
            message = f"基金: {funds_found} 条, 股票: {stocks_found} 条"
            success = test_result("健壮数据获取器", True, message, time.time() - test_start)
        else:
            success = test_result("健壮数据获取器", False, "未获取到数据", time.time() - test_start)
            
    except Exception as e:
        success = test_result("健壮数据获取器", False, f"测试失败: {e}", time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 测试6: 批量查询功能
    test_header("测试 6: 批量查询功能")
    test_start = time.time()
    try:
        from monitor.robust_market_fetcher import RobustMarketFetcher
        
        fetcher = RobustMarketFetcher()
        
        # 创建测试监控列表
        watchlist = [
            {"code": "270042", "type": "fund", "name": "广发纳斯达克100ETF"},
            {"code": "000001", "type": "fund", "name": "华夏成长混合"},
            {"code": "000001", "type": "stock", "name": "平安银行"},
            {"code": "600036", "type": "stock", "name": "招商银行"},
        ]
        
        print(f"  正在批量查询 {len(watchlist)} 只证券...")
        results = fetcher.batch_query(watchlist)
        
        # 检查结果
        summary = results.get("summary", {})
        total_found = summary.get("funds_found", 0) + summary.get("stocks_found", 0)
        success_rate = summary.get("success_rate", 0)
        
        if total_found > 0:
            message = f"成功率: {success_rate:.1f}%, 找到: {total_found}/{len(watchlist)} 只"
            success = test_result("批量查询功能", True, message, time.time() - test_start)
        else:
            success = test_result("批量查询功能", False, "批量查询无结果", time.time() - test_start)
            
    except Exception as e:
        success = test_result("批量查询功能", False, f"测试失败: {e}", time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 测试7: 基金270042专项测试
    test_header("测试 7: 基金270042专项测试")
    test_start = time.time()
    try:
        import akshare as ak
        
        print("  正在查询基金270042...")
        df = ak.fund_open_fund_daily_em()
        
        if df is not None and not df.empty:
            # 查找基金270042
            code_col = None
            for col in df.columns:
                if '基金代码' in col or '代码' in col:
                    code_col = col
                    break
            
            if code_col:
                fund_270042 = df[df[code_col] == '270042']
                if not fund_270042.empty:
                    fund_info = fund_270042.iloc[0]
                    fund_name = fund_info.get('基金简称', 'N/A')
                    message = f"找到基金270042: {fund_name}"
                    success = test_result("基金270042专项测试", True, message, time.time() - test_start)
                else:
                    success = test_result("基金270042专项测试", False, "未找到基金270042", time.time() - test_start)
            else:
                success = test_result("基金270042专项测试", False, "未找到基金代码列", time.time() - test_start)
        else:
            success = test_result("基金270042专项测试", False, "基金数据获取失败", time.time() - test_start)
            
    except Exception as e:
        success = test_result("基金270042专项测试", False, f"测试失败: {e}", time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 测试8: 分析工具检查
    test_header("测试 8: 分析工具检查")
    test_start = time.time()
    
    tools_found = 0
    tools_checked = 0
    
    # 检查各种分析工具文件
    analysis_tools = [
        'enhanced_batch_analyzer.py',
        'batch_market_analyzer.py', 
        'simple_api_test.py',
        'fund_analysis.py',
        'test_fund_270042.py'
    ]
    
    for tool in analysis_tools:
        tools_checked += 1
        if os.path.exists(tool):
            tools_found += 1
            print(f"  ✓ {tool}")
        else:
            print(f"  ✗ {tool}")
    
    if tools_found >= tools_checked * 0.8:  # 80%以上工具存在
        message = f"找到 {tools_found}/{tools_checked} 个分析工具"
        success = test_result("分析工具检查", True, message, time.time() - test_start)
    else:
        message = f"仅找到 {tools_found}/{tools_checked} 个分析工具"
        success = test_result("分析工具检查", False, message, time.time() - test_start)
    
    total_tests += 1
    if success: passed_tests += 1
    
    # 显示测试总结
    total_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print("📊 测试总结")
    print(f"{'='*60}")
    
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"失败测试: {total_tests - passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    print(f"总耗时: {total_time:.2f} 秒")
    
    # 给出建议
    print(f"\n💡 建议:")
    if passed_tests == total_tests:
        print("  🎉 所有测试通过！TickEye 项目功能完整，可以正常使用。")
    elif passed_tests >= total_tests * 0.8:
        print("  ✅ 大部分功能正常，少数问题不影响核心功能。")
    else:
        print("  ⚠️  存在较多问题，建议检查网络连接和依赖安装。")
    
    print(f"\n🚀 TickEye 项目当前具备的核心功能:")
    print(f"  • 基金和股票数据获取")
    print(f"  • 批量查询和监控")
    print(f"  • 智能缓存和重试机制")
    print(f"  • 市场数据分析")
    print(f"  • 多种分析工具")
    
    print(f"\n📋 可用的分析工具:")
    for tool in analysis_tools:
        if os.path.exists(tool):
            print(f"  • python {tool}")

if __name__ == "__main__":
    main()
