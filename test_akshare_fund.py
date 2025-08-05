#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AKShare基金数据获取 - 全面测试不同参数组合
"""

import akshare as ak
import pandas as pd
import sys

def test_combination(param_name, param_value, indicator_value, fund_code):
    """测试特定参数组合"""
    print(f"\n测试组合: {param_name}={fund_code}, indicator={indicator_value}")
    try:
        if param_name == "fund":
            df = ak.fund_open_fund_info_em(fund=fund_code, indicator=indicator_value)
        elif param_name == "symbol":
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator=indicator_value)
        else:
            print(f"  ❌ 不支持的参数名: {param_name}")
            return
            
        if df is not None and not df.empty:
            print(f"  ✅ 成功获取数据，共 {len(df)} 行")
            print(f"  数据列: {df.columns.tolist()}")
            print(f"  前3行数据:\n{df.head(3)}")
        else:
            print("  ❌ 未能获取到数据 (返回空DataFrame)")
    except Exception as e:
        print(f"  ❌ 出错: {e}")

def main():
    """测试AKShare基金数据获取"""
    
    # 打印AKShare版本
    print(f"AKShare版本: {ak.__version__}")
    print(f"Python版本: {sys.version}")
    
    # 测试基金代码列表
    fund_codes = ["710001", "270042", "000001"]
    
    # 参数名列表
    param_names = ["fund", "symbol"]
    
    # 指标值列表
    indicator_values = ["单位净值走势", "历史净值"]
    
    # 测试所有组合
    print("\n===== 测试所有参数组合 =====")
    for fund_code in fund_codes:
        print(f"\n基金代码: {fund_code}")
        for param_name in param_names:
            for indicator_value in indicator_values:
                test_combination(param_name, fund_code, indicator_value, fund_code)
    
    # 尝试获取基金列表
    print("\n\n===== 测试获取基金列表 =====")
    try:
        print("尝试使用 fund_em_open_fund_daily 获取基金列表...")
        df = ak.fund_em_open_fund_daily()
        if df is not None and not df.empty:
            print(f"✅ 成功获取基金列表，共 {len(df)} 个基金")
            print(f"数据列: {df.columns.tolist()}")
            print(f"前3行数据:\n{df.head(3)}")
        else:
            print("❌ 未能获取到基金列表")
    except Exception as e:
        print(f"❌ 出错: {e}")

if __name__ == "__main__":
    main()
