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
import logging

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
                            print(f"配置文件第 {line_num} 行：基金代码为空")
                    else:
                        print(f"配置文件第 {line_num} 行：格式错误")
                else:
                    # 只有基金代码的情况
                    fund_code = line.strip()
                    if fund_code and is_valid_code(fund_code):  # 验证基金代码或指数代码格式
                        owned_funds.append(fund_code)
                        # 不在这里设置名称，让get_fund_name函数通过API获取
                    else:
                        print(f"配置文件第 {line_num} 行：'{fund_code}' 不是有效的基金代码或指数代码")
    
    except FileNotFoundError:
        print(f"配置文件 {config_file} 不存在！")
        return [], {}
    
    except Exception as e:
        print(f"读取配置文件时出错：{str(e)}")
        return [], {}
    
    if not owned_funds:
        print("配置文件中没有找到有效的基金配置！")
    
    return owned_funds, fund_names

def is_valid_code(code: str) -> bool:
    """
    验证基金代码或指数代码格式
    
    Args:
        code: 代码字符串
        
    Returns:
        bool: 是否为有效的基金代码或指数代码
    """
    if not code:
        return False
    
    # 基金代码：纯数字，通常6位
    if code.isdigit():
        return True
    
    # 国际指数代码：常见格式
    international_codes = ['HSI', 'NDX', 'SPX', 'VNINDEX', 'SENSEX', 'N225', 'HSCEI', 'AS51', 'TSX']
    if code.upper() in international_codes:
        return True
    
    # 中国指数代码：可能包含字母和数字的组合
    # 常见格式：1A0001 (上证指数), 399001 (深证成指) 等
    if len(code) >= 4 and code.replace('A', '').replace('B', '').replace('C', '').isdigit():
        return True
    
    return False

def is_index_code(code: str) -> bool:
    """
    判断是否为指数代码
    
    Args:
        code: 代码字符串
        
    Returns:
        bool: 是否为指数代码
    """
    # 国际指数代码
    international_codes = ['HSI', 'NDX', 'SPX', 'VNINDEX', 'SENSEX', 'N225', 'HSCEI', 'AS51', 'TSX']
    if code.upper() in international_codes:
        return True
    
    # 中国指数代码（包含字母或特定格式，但排除纯数字的中国指数如000001）
    if not code.isdigit() and is_valid_code(code):
        return True
    
    # 中国主要指数代码（纯数字）
    china_index_codes = ['000001', '399001', '399006', '000300']
    if code in china_index_codes:
        return True
    
    return False

# 加载基金配置
OWNED_FUNDS, FUND_NAMES = load_funds_config()

def get_fund_name(fund_code: str) -> str:
    """
    获取基金全名或指数名称
    
    优先级顺序：
    1. 优先使用 akshare API 获取的基金名称（最准确）
    2. 如果 API 获取失败，使用配置文件中的名称作为备选
    3. 如果都失败，返回基金代码本身
    
    Args:
        fund_code: 基金代码或指数代码
        
    Returns:
        str: 基金全名或指数名称，如果获取失败则返回代码本身
    """
    # 判断是否为指数代码
    if is_index_code(fund_code):
        # 处理指数代码
        try:
            # 中国指数
            if fund_code == '1A0001' or fund_code == '000001':
                return '上证指数'
            elif fund_code == '399001':
                return '深证成指'
            elif fund_code == '399006':
                return '创业板指'
            elif fund_code == '000300':
                return '沪深300'
            # 国际指数
            elif fund_code.upper() == 'HSI':
                return '恒生指数'
            elif fund_code.upper() == 'NDX':
                return '纳斯达克'
            elif fund_code.upper() == 'SPX':
                return '标普500'
            elif fund_code.upper() == 'VNINDEX':
                return '越南胡志明'
            elif fund_code.upper() == 'SENSEX':
                return '印度孟买SENSEX'
            elif fund_code.upper() == 'N225':
                return '日经225'
            elif fund_code.upper() == 'HSCEI':
                return '国企指数'
            # 可以继续添加更多常见指数
        except Exception:
            pass
    else:
        # 处理基金代码
        # 优先尝试从 akshare API 获取单个基金的名称（始终优先使用API数据）
        try:
            fund_info = ak.fund_em_fund_info(fund=fund_code)
            if not fund_info.empty and '基金全称' in fund_info.columns:
                api_name = fund_info['基金全称'].iloc[0]
                if api_name and api_name.strip():
                    return api_name.strip()
        except Exception:
            pass  # API 获取失败，继续尝试其他方式
    
    # 如果 API 获取失败，尝试使用配置文件中的名称
    if fund_code in FUND_NAMES:
        config_name = FUND_NAMES[fund_code]
        if config_name and config_name.strip():
            return config_name.strip()
    
    # 如果都失败，返回基金代码本身
    return fund_code

def get_global_index_data(fund_code: str) -> dict:
    """
    从全球指数API获取指数数据
    
    Args:
        fund_code: 指数代码
        
    Returns:
        dict: 包含指数数据的字典，如果失败返回空字典
    """
    try:
        global_data = ak.index_global_spot_em()
        if global_data.empty:
            return {}
        
        # 查找匹配的指数
        matches = global_data[global_data['代码'].str.upper() == fund_code.upper()]
        
        if matches.empty:
            return {}
        
        # 获取第一个匹配的指数数据
        index_row = matches.iloc[0]
        
        return {
            'code': index_row['代码'],
            'name': index_row['名称'],
            'latest_price': index_row['最新价'],
            'change_pct': index_row['涨跌幅'],
            'update_time': index_row['最新行情时间']
        }
        
    except Exception as e:
        logging.error(f"获取全球指数 {fund_code} 数据失败: {str(e)}")
        return {}

def get_specific_fund_data(fund_code: str, days: int = 1) -> pd.DataFrame:
    """
    直接获取指定基金代码或指数代码的历史数据
    
    Args:
        fund_code: 基金代码（如'270042'）或指数代码（如'000001', 'HSI'）
        days: 获取最近多少天的数据
        
    Returns:
        pd.DataFrame: 包含基金或指数历史数据的DataFrame
    """
    try:
        if is_index_code(fund_code):
            # 处理指数代码
            # 国际指数使用全球指数API
            international_codes = ['HSI', 'NDX', 'SPX', 'VNINDEX', 'SENSEX', 'N225', 'HSCEI', 'AS51', 'TSX']
            if fund_code.upper() in international_codes:
                # 使用全球指数API获取实时数据
                global_index_data = get_global_index_data(fund_code)
                if not global_index_data:
                    return pd.DataFrame()
                
                # 构造DataFrame格式以匹配基金数据格式
                import datetime
                current_time = datetime.datetime.now()
                
                data = {
                    '净值日期': [current_time],
                    '单位净值': [global_index_data['latest_price']],
                    '日增长率': [f"{global_index_data['change_pct']}%"]
                }
                
                index_data = pd.DataFrame(data)
                index_data['净值日期'] = pd.to_datetime(index_data['净值日期'])
                
                return index_data
            
            # 中国指数使用股票指数API
            elif fund_code == '1A0001' or fund_code == '000001':
                # 上证指数使用 sh000001
                index_data = ak.stock_zh_index_daily(symbol="sh000001")
            elif fund_code == '399001':
                # 深证成指使用 sz399001
                index_data = ak.stock_zh_index_daily(symbol="sz399001")
            elif fund_code == '399006':
                # 创业板指使用 sz399006
                index_data = ak.stock_zh_index_daily(symbol="sz399006")
            elif fund_code == '000300':
                # 沪深300使用 sh000300
                index_data = ak.stock_zh_index_daily(symbol="sh000300")
            else:
                # 其他指数代码，尝试直接使用
                index_data = ak.stock_zh_index_daily(symbol=fund_code)
            
            if index_data.empty:
                return pd.DataFrame()
            
            # 转换指数数据格式以匹配基金数据格式
            index_data = index_data.copy()
            index_data['净值日期'] = pd.to_datetime(index_data['date'])
            index_data['单位净值'] = index_data['close']
            
            # 计算日增长率
            if len(index_data) > 1:
                index_data = index_data.sort_values('净值日期', ascending=False)
                prev_close = index_data['close'].shift(-1)
                index_data['日增长率'] = ((index_data['close'] - prev_close) / prev_close * 100).round(2)
                index_data['日增长率'] = index_data['日增长率'].astype(str) + '%'
            
            # 确保数据按日期降序排列（最新数据在前）
            index_data = index_data.sort_values('净值日期', ascending=False)
            
            # 返回指定天数的数据
            return index_data.head(days)
        else:
            # 处理基金代码
            # 修正API调用：使用symbol参数而不是fund参数
            fund_data = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            
            if fund_data.empty:
                return pd.DataFrame()
            
            # 确保数据按日期降序排列（最新数据在前）
            fund_data = fund_data.sort_values('净值日期', ascending=False)
            
            # 返回指定天数的数据
            return fund_data.head(days)
        
    except Exception as e:
        logging.error(f"获取 {fund_code} 数据失败: {str(e)}")
        return pd.DataFrame()

def get_fund_summary(fund_code: str, days: int = 1) -> dict:
    """
    获取基金或指数的简要分析数据
    
    Args:
        fund_code: 基金代码或指数代码
        days: 分析最近多少天的数据
        
    Returns:
        dict: 包含基金或指数分析数据的字典
    """
    try:
        # 获取基金数据
        fund_data = get_specific_fund_data(fund_code, days + 1)  # 多获取一天用于计算涨跌幅
        
        if fund_data.empty:
            raise Exception("无法获取基金数据")
        
        # 获取最新数据
        latest_row = fund_data.iloc[0]
        latest_date = latest_row['净值日期'].strftime('%Y-%m-%d')
        net_value = latest_row['单位净值']
        
        # 计算涨跌幅
        if len(fund_data) >= 2:
            # 有前一天的数据，计算涨跌幅
            prev_row = fund_data.iloc[1]
            prev_value = prev_row['单位净值']
            
            if prev_value and prev_value != 0:
                change_pct = ((net_value - prev_value) / prev_value) * 100
                change_str = f"{change_pct:.2f}%"
                trend = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
            else:
                change_pct = 0
                change_str = "0.00%"
                trend = "➡️"
        else:
            # 只有一天的数据，尝试从日增长率列获取
            if '日增长率' in latest_row and pd.notna(latest_row['日增长率']):
                change_str = str(latest_row['日增长率']).strip()
                if change_str and change_str != '--' and change_str != 'N/A':
                    try:
                        # 去掉百分号并转换为数字
                        change_num = float(change_str.replace('%', ''))
                        change_str = f"{change_num:.2f}%"
                        trend = "📈" if change_num > 0 else "📉" if change_num < 0 else "➡️"
                    except:
                        change_str = "N/A"
                        trend = "❓"
                else:
                    change_str = "N/A"
                    trend = "❓"
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
    监测已购买的基金和关注的指数
    
    Args:
        days: 分析最近多少天的数据
    """
    print("TickEye 基金监测工具")
    print("=" * 80)
    
    if not OWNED_FUNDS:
        print("未配置任何基金代码或指数代码！")
        return
    
    # 统计基金和指数数量
    fund_count = sum(1 for code in OWNED_FUNDS if not is_index_code(code))
    index_count = sum(1 for code in OWNED_FUNDS if is_index_code(code))
    
    if fund_count > 0 and index_count > 0:
        print(f"正在监测 {fund_count} 只基金和 {index_count} 个指数 (最近 {days} 天)")
    elif fund_count > 0:
        print(f"正在监测 {fund_count} 只基金 (最近 {days} 天)")
    else:
        print(f"正在监测 {index_count} 个指数 (最近 {days} 天)")
    
    # 获取所有基金的数据
    fund_summaries = []
    for fund_code in OWNED_FUNDS:
        summary = get_fund_summary(fund_code, days)
        fund_summaries.append(summary)
    
    print("\n基金/指数监测报告")
    print("=" * 80)
    
    # 创建表格标题
    print(f"{'代码':<8} {'名称':<30} {'最新日期':<12} {'净值/点位':<10} {'涨跌幅':<10} {'趋势':<4}")
    print("-" * 80)
    
    # 显示每只基金的数据
    total_funds = len(fund_summaries)
    success_count = 0
    up_count = 0
    down_count = 0
    
    for summary in fund_summaries:
        item_name = summary['fund_name']
        if len(item_name) > 30:
            item_name = item_name[:27] + "..."
        
        print(f"{summary['fund_code']:<8} {item_name:<30} {summary['latest_date']:<12} {summary['net_value']:<10} {summary['change_pct']:<10} {summary['trend']:<4}")
        
        # 统计
        if summary['status'] == '正常':
            success_count += 1
            if summary['trend'] == '📈':
                up_count += 1
            elif summary['trend'] == '📉':
                down_count += 1
    
    print("-" * 80)
    print(f"上涨: {up_count} 只  下跌: {down_count} 只  平盘: {success_count - up_count - down_count} 只")
    
    if success_count > 0:
        up_rate = (up_count / success_count) * 100
        print(f"上涨比例: {up_rate:.1f}%")

def main():
    """主函数"""
    # 默认分析天数
    days = 1
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
            if days <= 0:
                days = 1
        except ValueError:
            days = 1
    
    # 直接监测已购买的基金
    monitor_owned_funds(days)

if __name__ == "__main__":
    main()
