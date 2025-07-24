#!/usr/bin/env python3
"""
诊断脚本：查看 AkShare 实际返回的数据结构
"""

import akshare as ak
import pandas as pd

def diagnose_akshare_data():
    """诊断 AkShare 数据结构"""
    print("🔍 AkShare 数据结构诊断")
    print("=" * 50)
    
    try:
        print("\n📊 获取开放式基金数据...")
        df_open = ak.fund_open_fund_daily_em()
        
        if df_open is not None and not df_open.empty:
            print(f"✅ 成功获取 {len(df_open)} 条开放式基金数据")
            
            # 显示数据结构信息
            print(f"\n📋 数据形状: {df_open.shape}")
            print(f"📋 数据类型: {type(df_open)}")
            
            # 显示列名
            print(f"\n📝 所有列名:")
            for i, col in enumerate(df_open.columns, 1):
                print(f"  {i:2d}. '{col}'")
            
            # 显示前3行数据
            print(f"\n📊 前3行数据预览:")
            print(df_open.head(3).to_string())
            
            # 显示数据类型
            print(f"\n🔢 各列数据类型:")
            for col, dtype in df_open.dtypes.items():
                print(f"  '{col}': {dtype}")
            
            # 查找相似的列名
            print(f"\n🔍 查找相似字段:")
            target_fields = ['单位净值', '涨跌率', '基金代码', '基金简称']
            
            for target in target_fields:
                found = False
                for col in df_open.columns:
                    if target in col or col in target:
                        print(f"  目标: '{target}' -> 找到: '{col}' ✅")
                        found = True
                        break
                if not found:
                    # 尝试模糊匹配
                    similar_cols = []
                    for col in df_open.columns:
                        if ('净值' in target and '净值' in col) or \
                           ('涨跌' in target and ('涨跌' in col or '涨幅' in col or '变动' in col)) or \
                           ('代码' in target and '代码' in col) or \
                           ('简称' in target and ('简称' in col or '名称' in col)):
                            similar_cols.append(col)
                    
                    if similar_cols:
                        print(f"  目标: '{target}' -> 相似字段: {similar_cols} ⚠️")
                    else:
                        print(f"  目标: '{target}' -> 未找到 ❌")
            
        else:
            print("❌ 获取开放式基金数据失败或为空")
            
    except Exception as e:
        print(f"❌ 获取开放式基金数据时出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 同样诊断ETF数据
    try:
        print(f"\n📊 获取ETF基金数据...")
        df_etf = ak.fund_etf_fund_daily_em()
        
        if df_etf is not None and not df_etf.empty:
            print(f"✅ 成功获取 {len(df_etf)} 条ETF基金数据")
            print(f"📝 ETF基金列名: {list(df_etf.columns)}")
            print(f"📊 ETF前2行数据:")
            print(df_etf.head(2).to_string())
        else:
            print("❌ 获取ETF基金数据失败或为空")
            
    except Exception as e:
        print(f"❌ 获取ETF基金数据时出错: {e}")

def test_specific_funds():
    """测试特定基金代码"""
    print(f"\n🎯 测试特定基金代码")
    print("=" * 30)
    
    test_codes = ["000001", "110022", "161725"]
    
    try:
        df = ak.fund_open_fund_daily_em()
        if df is not None and not df.empty:
            # 查找基金代码字段
            code_col = None
            for col in df.columns:
                if '代码' in col:
                    code_col = col
                    break
            
            if code_col:
                print(f"📋 基金代码字段: '{code_col}'")
                
                # 查看是否有我们的测试代码
                found_funds = df[df[code_col].isin(test_codes)]
                
                if not found_funds.empty:
                    print(f"✅ 找到 {len(found_funds)} 只测试基金:")
                    print(found_funds.to_string())
                else:
                    print("⚠️  未找到任何测试基金代码")
                    print(f"📋 数据中的前10个基金代码示例:")
                    print(df[code_col].head(10).tolist())
            else:
                print("❌ 未找到基金代码字段")
                
    except Exception as e:
        print(f"❌ 测试特定基金时出错: {e}")

if __name__ == "__main__":
    diagnose_akshare_data()
    test_specific_funds()
    
    print(f"\n💡 诊断完成！")
    print("根据上述信息修复 fetcher.py 中的字段名称问题。")
