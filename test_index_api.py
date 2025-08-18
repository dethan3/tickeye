#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AKShare指数API功能
"""

import akshare as ak
import pandas as pd

def test_index_apis():
    """测试不同的指数API"""
    
    print("测试AKShare指数相关API...")
    print("=" * 50)
    
    # 测试1: 股票指数实时行情
    try:
        print("\n1. 测试 stock_zh_index_spot (指数实时行情):")
        index_spot = ak.stock_zh_index_spot()
        if not index_spot.empty:
            # 查找上证指数
            shanghai_index = index_spot[index_spot['代码'].str.contains('000001|1A0001', na=False)]
            if not shanghai_index.empty:
                print("找到上证指数相关数据:")
                print(shanghai_index[['代码', '名称', '最新价', '涨跌幅']].head())
            else:
                print("未找到上证指数数据")
                print("前5条指数数据:")
                print(index_spot[['代码', '名称', '最新价', '涨跌幅']].head())
    except Exception as e:
        print(f"stock_zh_index_spot API 失败: {e}")
    
    # 测试2: 指数历史数据
    try:
        print("\n2. 测试 stock_zh_index_daily (指数历史数据):")
        # 尝试获取上证指数历史数据
        for symbol in ['sh000001', '000001', '1A0001']:
            try:
                print(f"尝试代码: {symbol}")
                index_daily = ak.stock_zh_index_daily(symbol=symbol)
                if not index_daily.empty:
                    print(f"成功获取 {symbol} 数据:")
                    print(index_daily.tail(3))
                    break
            except Exception as e:
                print(f"代码 {symbol} 失败: {e}")
    except Exception as e:
        print(f"stock_zh_index_daily API 测试失败: {e}")
    
    # 测试3: 指数成分股
    try:
        print("\n3. 测试 index_stock_cons (指数成分股):")
        # 尝试获取上证指数成分股
        for symbol in ['000001', '1A0001']:
            try:
                print(f"尝试代码: {symbol}")
                index_cons = ak.index_stock_cons(symbol=symbol)
                if not index_cons.empty:
                    print(f"成功获取 {symbol} 成分股数据:")
                    print(f"共 {len(index_cons)} 只成分股")
                    break
            except Exception as e:
                print(f"代码 {symbol} 失败: {e}")
    except Exception as e:
        print(f"index_stock_cons API 测试失败: {e}")

if __name__ == "__main__":
    test_index_apis()
