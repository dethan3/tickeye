#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金监测工具 - 专门用于监测已购买基金的每日涨跌幅度
Author: TickEye Team
Date: 2025-08-04
"""

import sys
import os
import logging
import pandas as pd
import akshare as ak

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor.fetcher import SimpleFundDataFetcher
from utils.logger import setup_logger

# ==================== 已购买基金配置区域 ====================
# 请在下方列表中填入你已购买的基金代码（6位数字）
OWNED_FUNDS = [
    # 请在此处添加你的基金代码：
    '270042',  # 广发纳指联接A
    '007360',  # 易方达中短期美元债A
    '007361',  # 易方达中短期美元债C
    '001917',  # 招商量化精选股票A
    '019670',  # 广发港股创新药ETF联接A 
]

# 基金名称映射表（手动配置，确保显示正确的基金名称）
FUND_NAMES = {
    '270042': '广发纳指联接A',
    '007360': '易方达中短期美元债A', 
    '007361': '易方达中短期美元债C',
    '001917': '招商量化精选股票A',
    '019670': '广发港股创新药ETF联接A',
    # 请在此处添加更多基金的名称映射：
    # '基金代码': '基金全名',
}
# ============================================================

def get_fund_name(fund_code: str) -> str:
    """
    获取基金全名
    
    Args:
        fund_code: 基金代码
        
    Returns:
        str: 基金全名，如果获取失败则返回基金代码
    """
    # 优先使用手动配置的名称映射
    if fund_code in FUND_NAMES:
        return FUND_NAMES[fund_code]
    
    # 如果没有手动配置，尝试从数据源获取（简化版，减少错误输出）
    try:
        fetcher = SimpleFundDataFetcher()
        
        # 先尝试开放式基金
        open_funds = fetcher.get_open_fund_data()
        if open_funds is not None and not open_funds.empty:
            # 检查实际的列名
            columns = list(open_funds.columns)
            
            # 查找基金代码列和名称列
            code_col = None
            name_col = None
            
            for col in columns:
                if '代码' in col or 'code' in col.lower():
                    code_col = col
                if '名称' in col or '简称' in col or 'name' in col.lower():
                    name_col = col
            
            if code_col and name_col:
                fund_info = open_funds[open_funds[code_col] == fund_code]
                if not fund_info.empty:
                    return fund_info[name_col].iloc[0]
        
    except Exception:
        pass
    
    # 如果都失败了，返回基金代码
    return fund_code

def get_specific_fund_data(fund_code: str, days: int = 1):
    """
    直接获取指定基金代码的历史数据，借鉴AKShare官方示例
    
    Args:
        fund_code: 基金代码，如'270042'
        days: 获取最近多少天的数据
        
    Returns:
        pd.DataFrame: 包含基金历史数据的DataFrame
    """
    try:
        # 直接使用akshare获取指定基金的历史净值数据
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        
        if df is not None and not df.empty:
            # 数据清理和处理
            df = df.copy()
            
            # 确保日期列存在并转换为日期格式
            if '净值日期' in df.columns:
                df['净值日期'] = pd.to_datetime(df['净值日期'])
                df = df.sort_values('净值日期', ascending=False)  # 按日期降序排列
            
            # 计算每日涨跌幅（如果数据中没有的话）
            if '单位净值' in df.columns and '日增长率' not in df.columns:
                df['单位净值'] = pd.to_numeric(df['单位净值'], errors='coerce')
                df['前日净值'] = df['单位净值'].shift(-1)
                df['计算涨跌幅'] = ((df['单位净值'] - df['前日净值']) / df['前日净值'] * 100).round(4)
            
            # 取最近N天的数据
            if days > 0:
                df = df.head(days)
                
            return df
        else:
            return None
                
    except Exception as e:
        print(f"❌ 获取基金 {fund_code} 历史数据失败: {e}")
        return None

def get_fund_summary(fund_code: str, days: int = 1) -> dict:
    """
    获取基金的简要分析数据
    
    Args:
        fund_code: 基金代码
        days: 分析最近多少天的数据
        
    Returns:
        dict: 包含基金分析数据的字典
    """
    try:
        # 获取基金数据
        daily_changes = get_specific_fund_data(fund_code, days=days)
        
        if daily_changes is None or daily_changes.empty:
            return {
                'fund_code': fund_code,
                'fund_name': get_fund_name(fund_code),
                'status': '数据获取失败',
                'latest_date': 'N/A',
                'net_value': 'N/A',
                'change_pct': 'N/A',
                'trend': '❓'
            }
        
        # 选择需要的列
        columns_to_keep = ['净值日期', '单位净值']
        if '日增长率' in daily_changes.columns:
            columns_to_keep.append('日增长率')
        elif '计算涨跌幅' in daily_changes.columns:
            columns_to_keep.append('计算涨跌幅')
        
        result = daily_changes[columns_to_keep].copy()
        
        # 重命名列以便统一使用
        if '日增长率' in result.columns:
            result = result.rename(columns={'日增长率': '涨跌幅(%)'})
        elif '计算涨跌幅' in result.columns:
            result = result.rename(columns={'计算涨跌幅': '涨跌幅(%)'})
        
        # 获取最新数据
        latest_row = result.iloc[0]
        latest_date = latest_row['净值日期'].strftime('%Y-%m-%d')
        net_value = f"{latest_row['单位净值']:.4f}"
        
        # 处理涨跌幅
        if '涨跌幅(%)' in latest_row and pd.notna(latest_row['涨跌幅(%)']):
            change_pct = latest_row['涨跌幅(%)']
            if isinstance(change_pct, str):
                change_str = change_pct
                if '%' in change_pct:
                    try:
                        change_num = float(change_pct.replace('%', ''))
                        trend = "📈" if change_num > 0 else "📉" if change_num < 0 else "➡️"
                    except:
                        trend = "❓"
                else:
                    trend = "❓"
            else:
                change_str = f"{change_pct:.2f}%"
                trend = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
        else:
            change_str = "N/A"
            trend = "❓"
        
        return {
            'fund_code': fund_code,
            'fund_name': get_fund_name(fund_code),
            'status': '正常',
            'latest_date': latest_date,
            'net_value': net_value,
            'change_pct': change_str,
            'trend': trend
        }
        
    except Exception as e:
        return {
            'fund_code': fund_code,
            'fund_name': get_fund_name(fund_code),
            'status': f'分析失败: {str(e)}',
            'latest_date': 'N/A',
            'net_value': 'N/A',
            'change_pct': 'N/A',
            'trend': '❓'
        }

def monitor_owned_funds(days: int = 1):
    """
    监测已购买的基金
    
    Args:
        days: 分析最近多少天的数据
    """
    print("🦉 TickEye 基金监测工具")
    print("=" * 80)
    
    if not OWNED_FUNDS:
        print("❌ 未配置任何基金代码！")
        print("请在代码中的 OWNED_FUNDS 列表中添加你已购买的基金代码。")
        print("示例：OWNED_FUNDS = ['270042', '110022', '161725']")
        return
    
    print(f"📋 正在监测 {len(OWNED_FUNDS)} 只已购买基金...")
    print(f"📅 数据日期: 最近 {days} 天")
    print()
    
    # 获取所有基金的数据
    fund_summaries = []
    for fund_code in OWNED_FUNDS:
        print(f"🔍 正在获取基金 {fund_code} 的数据...")
        summary = get_fund_summary(fund_code, days)
        fund_summaries.append(summary)
    
    print("\n" + "=" * 80)
    print("📊 已购买基金监测报告")
    print("=" * 80)
    
    # 创建表格标题
    print(f"{'基金代码':<8} {'基金名称':<20} {'最新日期':<12} {'单位净值':<10} {'涨跌幅':<10} {'趋势':<4} {'状态':<10}")
    print("-" * 80)
    
    # 显示每只基金的数据
    total_funds = len(fund_summaries)
    success_count = 0
    up_count = 0
    down_count = 0
    
    for summary in fund_summaries:
        fund_name = summary['fund_name'][:18] + '..' if len(summary['fund_name']) > 20 else summary['fund_name']
        
        print(f"{summary['fund_code']:<8} {fund_name:<20} {summary['latest_date']:<12} {summary['net_value']:<10} {summary['change_pct']:<10} {summary['trend']:<4} {summary['status']:<10}")
        
        # 统计
        if summary['status'] == '正常':
            success_count += 1
            if summary['trend'] == '📈':
                up_count += 1
            elif summary['trend'] == '📉':
                down_count += 1
    
    print("-" * 80)
    print(f"📈 上涨: {up_count} 只  📉 下跌: {down_count} 只  ➡️ 平盘: {success_count - up_count - down_count} 只  ❌ 失败: {total_funds - success_count} 只")
    
    if success_count > 0:
        up_rate = (up_count / success_count) * 100
        print(f"📊 上涨比例: {up_rate:.1f}%")
    
    print("\n✅ 基金监测完成!")

def main():
    """主函数"""
    # 默认分析天数
    days = 1
    
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
    
    # 直接监测已购买的基金
    monitor_owned_funds(days)

if __name__ == "__main__":
    main()
