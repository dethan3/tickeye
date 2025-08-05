#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金监测工具 - 专门用于监测已购买基金的每日涨跌幅度
Author: TickEye Team
Date: 2025-08-04
"""

import sys
import os
import pandas as pd
import akshare as ak

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ==================== 基金配置加载函数 ====================
def load_funds_config(config_file='funds_config.txt'):
    """
    从配置文件加载基金信息
    
    Args:
        config_file: 配置文件路径，默认为 'funds_config.txt'
        
    Returns:
        tuple: (基金代码列表, 基金名称字典)
    """
    # 获取配置文件的完整路径
    if not os.path.isabs(config_file):
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
    
    owned_funds = []
    fund_names = {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue
                
                # 解析基金代码和名称
                if '|' in line:
                    # 格式：基金代码|基金名称
                    parts = line.split('|', 1)  # 只分割一次，防止名称中有 | 符号
                    if len(parts) == 2:
                        fund_code = parts[0].strip()
                        fund_name = parts[1].strip()
                        
                        if fund_code:
                            owned_funds.append(fund_code)
                            if fund_name:  # 如果提供了名称，使用配置的名称
                                fund_names[fund_code] = fund_name
                        else:
                            print(f"⚠️ 配置文件第 {line_num} 行格式错误：基金代码为空")
                    else:
                        print(f"⚠️ 配置文件第 {line_num} 行格式错误：分隔符 | 使用不当")
                else:
                    # 只有基金代码的情况
                    fund_code = line.strip()
                    if fund_code and fund_code.isdigit():  # 简单验证基金代码格式
                        owned_funds.append(fund_code)
                        # 不在这里设置名称，让get_fund_name函数通过API获取
                    else:
                        print(f"⚠️ 配置文件第 {line_num} 行格式错误：'{fund_code}' 不是有效的基金代码")
    
    except FileNotFoundError:
        print(f"❌ 配置文件 {config_file} 不存在！")
        print("请创建配置文件，支持以下格式：")
        print("# TickEye 基金配置文件")
        print("# 格式1：基金代码|基金名称")
        print("270042|广发纳指联接A")
        print("007360|易方达中短期美元债A")
        print("# 格式2：只有基金代码（名称自动获取）")
        print("001917")
        print("006195")
        return [], {}
    
    except Exception as e:
        print(f"❌ 读取配置文件时出错：{str(e)}")
        return [], {}
    
    if not owned_funds:
        print("⚠️ 配置文件中没有找到有效的基金配置！")
    else:
        print(f"✅ 成功加载 {len(owned_funds)} 只基金配置")
    
    return owned_funds, fund_names

# 加载基金配置
OWNED_FUNDS, FUND_NAMES = load_funds_config()

def get_fund_name(fund_code: str) -> str:
    """
    获取基金全名
    
    优先级顺序：
    1. 优先使用 akshare API 获取的基金名称（最准确）
    2. 如果 API 获取失败，使用配置文件中的名称作为备选
    3. 如果都失败，返回基金代码本身
    
    Args:
        fund_code: 基金代码
        
    Returns:
        str: 基金全名，如果获取失败则返回基金代码
    """
    # 优先尝试从 akshare API 获取单个基金的名称（始终优先使用API数据）
    try:
        # 使用 fund_individual_basic_info_xq 获取单个基金的基本信息
        fund_info = ak.fund_individual_basic_info_xq(symbol=fund_code)
        if fund_info is not None and not fund_info.empty:
            # 查找基金名称行
            name_row = fund_info[fund_info['item'] == '基金名称']
            if not name_row.empty:
                fund_name = name_row['value'].iloc[0]
                if fund_name and fund_name.strip():
                    return fund_name.strip()
        
    except Exception as e:
        # API 获取失败时，记录但不打印错误（避免过多输出）
        pass
    
    # 如果 API 获取失败，则使用配置文件中的名称作为备选
    if fund_code in FUND_NAMES:
        return FUND_NAMES[fund_code]
    
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
    print("=" * 100)
    
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
    
    print("\n" + "=" * 100)
    print("📊 已购买基金监测报告")
    print("=" * 100)
    
    # 创建表格标题 - 调整列宽以显示完整基金名称
    print(f"{'基金代码':<8} {'基金名称':<35} {'最新日期':<12} {'单位净值':<10} {'涨跌幅':<10} {'趋势':<4} {'状态':<10}")
    print("-" * 100)
    
    # 显示每只基金的数据
    total_funds = len(fund_summaries)
    success_count = 0
    up_count = 0
    down_count = 0
    
    for summary in fund_summaries:
        # 移除名称截断逻辑，显示完整名称
        fund_name = summary['fund_name']
        # 如果名称太长，可以考虑在合适的位置换行，但不截断
        if len(fund_name) > 35:
            fund_name = fund_name[:32] + "..."
        
        print(f"{summary['fund_code']:<8} {fund_name:<35} {summary['latest_date']:<12} {summary['net_value']:<10} {summary['change_pct']:<10} {summary['trend']:<4} {summary['status']:<10}")
        
        # 统计
        if summary['status'] == '正常':
            success_count += 1
            if summary['trend'] == '📈':
                up_count += 1
            elif summary['trend'] == '📉':
                down_count += 1
    
    print("-" * 100)
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
