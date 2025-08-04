#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版 AKShare API 测试脚本
快速验证基金和股票数据获取功能
"""

import akshare as ak
import pandas as pd

def test_fund_api():
    """测试基金API"""
    print("🧪 测试基金API")
    print("=" * 40)
    
    try:
        print("1. 测试基金日常数据API...")
        df = ak.fund_open_fund_daily_em()
        
        if df is not None and not df.empty:
            print(f"   ✅ 成功获取 {len(df)} 条基金数据")
            print(f"   📋 列名: {list(df.columns)}")
            
            # 查找基金270042
            code_col = None
            for col in df.columns:
                if '代码' in col:
                    code_col = col
                    break
            
            if code_col:
                target_fund = df[df[code_col] == '270042']
                if not target_fund.empty:
                    print(f"   🎯 找到基金270042:")
                    print(f"   📊 数据预览:")
                    for col in target_fund.columns:
                        value = target_fund.iloc[0][col]
                        print(f"      {col}: {value}")
                    return True
                else:
                    print(f"   ⚠️  未找到基金270042")
                    print(f"   📋 可用基金代码示例: {df[code_col].head(5).tolist()}")
                    return False
            else:
                print(f"   ❌ 未找到代码列")
                return False
        else:
            print(f"   ❌ API返回空数据")
            return False
            
    except Exception as e:
        print(f"   ❌ API调用失败: {e}")
        return False

def test_stock_api():
    """测试股票API"""
    print("\n🧪 测试股票API")
    print("=" * 40)
    
    try:
        print("1. 测试股票实时数据API...")
        df = ak.stock_zh_a_spot_em()
        
        if df is not None and not df.empty:
            print(f"   ✅ 成功获取 {len(df)} 条股票数据")
            print(f"   📋 列名: {list(df.columns)}")
            
            # 查找股票000001
            code_col = None
            for col in df.columns:
                if '代码' in col:
                    code_col = col
                    break
            
            if code_col:
                target_stock = df[df[code_col] == '000001']
                if not target_stock.empty:
                    print(f"   🎯 找到股票000001:")
                    print(f"   📊 数据预览:")
                    for col in target_stock.columns[:8]:  # 只显示前8列
                        value = target_stock.iloc[0][col]
                        print(f"      {col}: {value}")
                    return True
                else:
                    print(f"   ⚠️  未找到股票000001")
                    return False
            else:
                print(f"   ❌ 未找到代码列")
                return False
        else:
            print(f"   ❌ API返回空数据")
            return False
            
    except Exception as e:
        print(f"   ❌ API调用失败: {e}")
        return False

def test_batch_query():
    """测试批量查询功能"""
    print("\n🧪 测试批量查询功能")
    print("=" * 40)
    
    # 测试目标列表
    targets = [
        {"code": "270042", "type": "fund", "name": "广发纯债债券A"},
        {"code": "000001", "type": "stock", "name": "平安银行"},
    ]
    
    results = {"funds": [], "stocks": []}
    
    # 获取基金数据
    fund_codes = [t["code"] for t in targets if t["type"] == "fund"]
    if fund_codes:
        try:
            df_funds = ak.fund_open_fund_daily_em()
            if df_funds is not None and not df_funds.empty:
                code_col = next((col for col in df_funds.columns if '代码' in col), None)
                if code_col:
                    for code in fund_codes:
                        fund_data = df_funds[df_funds[code_col] == code]
                        if not fund_data.empty:
                            results["funds"].append(fund_data.iloc[0])
                            print(f"   ✅ 找到基金 {code}")
        except Exception as e:
            print(f"   ❌ 基金批量查询失败: {e}")
    
    # 获取股票数据
    stock_codes = [t["code"] for t in targets if t["type"] == "stock"]
    if stock_codes:
        try:
            df_stocks = ak.stock_zh_a_spot_em()
            if df_stocks is not None and not df_stocks.empty:
                code_col = next((col for col in df_stocks.columns if '代码' in col), None)
                if code_col:
                    for code in stock_codes:
                        stock_data = df_stocks[df_stocks[code_col] == code]
                        if not stock_data.empty:
                            results["stocks"].append(stock_data.iloc[0])
                            print(f"   ✅ 找到股票 {code}")
        except Exception as e:
            print(f"   ❌ 股票批量查询失败: {e}")
    
    # 显示结果
    total_found = len(results["funds"]) + len(results["stocks"])
    print(f"\n📊 批量查询结果:")
    print(f"   目标数量: {len(targets)}")
    print(f"   成功找到: {total_found}")
    print(f"   基金: {len(results['funds'])} 只")
    print(f"   股票: {len(results['stocks'])} 只")
    
    return total_found > 0

def main():
    """主函数"""
    print("🦉 TickEye 简化版 API 测试")
    print("验证 AKShare 基金和股票数据获取功能")
    print("=" * 50)
    
    success_count = 0
    
    # 测试基金API
    if test_fund_api():
        success_count += 1
    
    # 测试股票API
    if test_stock_api():
        success_count += 1
    
    # 测试批量查询
    if test_batch_query():
        success_count += 1
    
    print(f"\n" + "="*50)
    print(f"📊 测试总结:")
    print(f"   成功测试: {success_count}/3")
    
    if success_count >= 2:
        print(f"   ✅ API 基本可用，可以继续开发批量查询功能")
    else:
        print(f"   ❌ API 存在问题，需要进一步调试")
    
    return success_count >= 2

if __name__ == "__main__":
    main()
