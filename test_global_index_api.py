#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AKShare全球指数API - index_global_spot_em
"""

import akshare as ak
import pandas as pd

def test_global_index_api():
    """测试全球指数实时行情API"""
    
    print("测试 index_global_spot_em API...")
    print("=" * 60)
    
    try:
        # 获取全球指数实时行情
        global_data = ak.index_global_spot_em()
        
        if global_data.empty:
            print("✗ 全球指数数据为空")
            return
        
        print("✓ 成功获取全球指数数据")
        print(f"总共获取到 {len(global_data)} 个指数")
        print("\n数据列名:", list(global_data.columns))
        
        # 显示前10个指数
        print("\n前10个指数:")
        print(global_data.head(10).to_string(index=False))
        
        # 查找用户配置的指数代码
        target_codes = ['000001', 'HSI', 'NDX', 'SPX', 'VNINDEX', 'SENSEX']
        
        print(f"\n查找目标指数代码: {target_codes}")
        print("=" * 60)
        
        for code in target_codes:
            # 在代码列中查找
            matches = global_data[global_data['代码'].str.contains(code, case=False, na=False)]
            
            if not matches.empty:
                print(f"\n✓ 找到 {code}:")
                print(matches[['代码', '名称', '最新价', '涨跌幅']].to_string(index=False))
            else:
                # 在名称中查找
                name_matches = global_data[global_data['名称'].str.contains(code, case=False, na=False)]
                if not name_matches.empty:
                    print(f"\n✓ 在名称中找到 {code}:")
                    print(name_matches[['代码', '名称', '最新价', '涨跌幅']].to_string(index=False))
                else:
                    print(f"\n✗ 未找到 {code}")
        
        # 查找常见的国际指数
        print(f"\n查找常见国际指数:")
        print("=" * 60)
        
        keywords = ['纳斯达克', 'NASDAQ', '标普', 'S&P', '恒生', 'Hang Seng', '日经', 'Nikkei', '印度', 'SENSEX', '越南', 'VN']
        
        for keyword in keywords:
            matches = global_data[
                (global_data['代码'].str.contains(keyword, case=False, na=False)) |
                (global_data['名称'].str.contains(keyword, case=False, na=False))
            ]
            
            if not matches.empty:
                print(f"\n✓ 找到包含 '{keyword}' 的指数:")
                print(matches[['代码', '名称', '最新价', '涨跌幅']].head(3).to_string(index=False))
        
    except Exception as e:
        print(f"✗ API调用失败: {e}")

if __name__ == "__main__":
    test_global_index_api()
