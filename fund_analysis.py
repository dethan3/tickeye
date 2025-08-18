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
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ==================== 指数配置加载与代码解析 ====================
def load_index_aliases(config_file: str = 'indices_config.json') -> dict:
    """
    加载指数别名配置
    返回字典格式：{"aliases": { alias: {"symbol": str, "market": "cn"|"global", "name": str } }}
    """
    try:
        if not os.path.isabs(config_file):
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
        if not os.path.exists(config_file):
            return {"aliases": {}}
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'aliases' in data and isinstance(data['aliases'], dict):
                return data
            return {"aliases": {}}
    except Exception:
        return {"aliases": {}}

INDEX_CONFIG = load_index_aliases()

def resolve_code(code: str) -> dict:
    """
    解析输入代码，统一判断类型与市场，并提供实际数据源symbol
    返回：{ 'type': 'fund'|'index', 'market': 'cn'|'global'|None, 'symbol': str|None, 'alias_name': str|None }
    若无法识别，返回空字典 {}
    """
    if not code:
        return {}
    c = code.strip()
    if not c:
        return {}

    # 1) 命中配置别名（先精确，其次大写）
    aliases = INDEX_CONFIG.get('aliases', {})
    if c in aliases:
        v = aliases[c]
        return {"type": "index", "market": v.get('market'), "symbol": v.get('symbol', c), "alias_name": v.get('name')}
    cu = c.upper()
    if cu in aliases:
        v = aliases[cu]
        return {"type": "index", "market": v.get('market'), "symbol": v.get('symbol', cu), "alias_name": v.get('name')}

    # 2) 纯数字：视为基金
    if c.isdigit():
        return {"type": "fund", "market": None, "symbol": c, "alias_name": None}

    # 3) 中国指数直接symbol格式：sh000xxx 或 sz000xxx
    if (len(c) == 8 and (c.startswith('sh') or c.startswith('sz')) and c[2:].isdigit()):
        return {"type": "index", "market": "cn", "symbol": c, "alias_name": None}

    # 4) 全大写英文字母/数字短码，尝试视为全球指数（例如 HSI、SPX）
    if cu == c and 2 <= len(cu) <= 10 and cu.replace('_', '').isalnum():
        # 未在别名中定义区域时，默认标记为 'global'，下游以 startswith('global') 处理
        return {"type": "index", "market": "global", "symbol": cu, "alias_name": None}

    return {}

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
    
    # 优先尝试 JSON 配置（同名 .json）
    json_file = os.path.splitext(config_file)[0] + '.json'
    owned_funds = []
    fund_names = {}

    # 先读取 JSON
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 支持两种结构：{"items": [...]} 或 顶层数组 [...]
            items = []
            if isinstance(data, dict) and 'items' in data and isinstance(data['items'], list):
                items = data['items']
            elif isinstance(data, list):
                items = data
            else:
                print(f"JSON 配置格式不正确：应为包含 items 的对象或数组: {json_file}")
                return [], {}

            for idx, item in enumerate(items, 1):
                code, name = None, None
                if isinstance(item, dict):
                    code = str(item.get('code', '')).strip()
                    name = str(item.get('name', '')).strip() if item.get('name') is not None else ''
                elif isinstance(item, str):
                    line = item.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '|' in line:
                        parts = line.split('|', 1)
                        code = parts[0].strip()
                        name = parts[1].strip()
                    else:
                        code = line
                        name = ''
                else:
                    print(f"JSON 配置第 {idx} 项格式不正确，必须是对象或字符串")
                    continue

                if code and is_valid_code(code):
                    owned_funds.append(code)
                    if name:
                        fund_names[code] = name
                else:
                    print(f"JSON 配置第 {idx} 项：'{code}' 不是有效的基金代码或指数代码")

            if not owned_funds:
                print("JSON 配置中没有找到有效的基金/指数代码！")
            return owned_funds, fund_names
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"读取 JSON 配置文件时出错：{str(e)}，回退读取 TXT 配置")

    # 回退 TXT
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        fund_code = parts[0].strip()
                        fund_name = parts[1].strip()
                        if fund_code:
                            owned_funds.append(fund_code)
                            if fund_name:
                                fund_names[fund_code] = fund_name
                        else:
                            print(f"配置文件第 {line_num} 行：基金代码为空")
                    else:
                        print(f"配置文件第 {line_num} 行：格式错误")
                else:
                    fund_code = line.strip()
                    if fund_code and is_valid_code(fund_code):
                        owned_funds.append(fund_code)
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
    info = resolve_code(code)
    return bool(info)

def is_index_code(code: str) -> bool:
    """
    判断是否为指数代码
    
    Args:
        code: 代码字符串
        
    Returns:
        bool: 是否为指数代码
    """
    info = resolve_code(code)
    return bool(info) and info.get('type') == 'index'

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
    info = resolve_code(fund_code)
    if not info:
        return fund_code

    if info.get('type') == 'index':
        # 优先使用别名配置中的名称
        if info.get('alias_name'):
            return info['alias_name']
        # global 指数尝试从实时接口获取名称（兼容 global_* 分区）
        market = str(info.get('market') or '')
        if market.startswith('global'):
            try:
                global_data = ak.index_global_spot_em()
                if not global_data.empty and '名称' in global_data.columns and '代码' in global_data.columns:
                    matches = global_data[global_data['代码'].str.upper() == info.get('symbol', fund_code).upper()]
                    if not matches.empty:
                        name = matches.iloc[0]['名称']
                        if isinstance(name, str) and name.strip():
                            return name.strip()
            except Exception:
                pass
        # cn 指数若无名称，回退代码
        return fund_code
    else:
        # 基金名称优先用 API
        try:
            fund_info = ak.fund_em_fund_info(fund=fund_code)
            if not fund_info.empty and '基金全称' in fund_info.columns:
                api_name = fund_info['基金全称'].iloc[0]
                if isinstance(api_name, str) and api_name.strip():
                    return api_name.strip()
        except Exception:
            pass
    
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

# ===== 抽象：指数数据构建与规范化 =====
def _format_index_output(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """统一排序与截取最近 N 天输出。"""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if '净值日期' in out.columns:
        out['净值日期'] = pd.to_datetime(out['净值日期'])
        out = out.sort_values('净值日期', ascending=False)
    return out.head(days)

def _build_global_index_df(spot: dict) -> pd.DataFrame:
    """由全球指数 spot 字典创建标准输出DataFrame。"""
    if not spot:
        return pd.DataFrame()
    import datetime
    current_time = datetime.datetime.now()
    data = {
        '净值日期': [current_time],
        '单位净值': [spot['latest_price']],
        '日增长率': [f"{spot['change_pct']}%"],
    }
    return pd.DataFrame(data)

def _build_cn_index_df(index_data: pd.DataFrame) -> pd.DataFrame:
    """由 A 股指数历史数据构建标准输出DataFrame，并计算日增长率。"""
    if index_data is None or index_data.empty:
        return pd.DataFrame()
    df = index_data.copy()
    df['净值日期'] = pd.to_datetime(df['date'])
    df['单位净值'] = df['close']
    if len(df) > 1:
        df = df.sort_values('净值日期', ascending=False)
        prev_close = df['close'].shift(-1)
        df['日增长率'] = ((df['close'] - prev_close) / prev_close * 100).round(2)
        df['日增长率'] = df['日增长率'].astype(str) + '%'
    df = df.sort_values('净值日期', ascending=False)
    return df

def _build_cn_index_spot_df(symbol: str) -> pd.DataFrame:
    """使用 ak.stock_zh_index_spot_em 获取实时指数快照并构造标准输出列。
    兼容 symbol 为 'sh000001' / 'sz399001' 等，匹配时按后6位或带后缀 '.SH' '.SZ' 归一。
    """
    try:
        spot = ak.stock_zh_index_spot_em()
        if spot is None or spot.empty:
            return pd.DataFrame()
        core = symbol[-6:].upper() if symbol else ''
        if not core or not core.isdigit():
            return pd.DataFrame()
        codes = spot['代码'].astype(str).str.upper()
        # 兼容 000001 / 000001.SH / 399001.SZ
        mask = (codes == core) | (codes == f"{core}.SH") | (codes == f"{core}.SZ")
        matches = spot[mask]
        if matches.empty:
            return pd.DataFrame()
        row = matches.iloc[0]
        latest = row['最新价'] if '最新价' in row else None
        pct = row['涨跌幅'] if '涨跌幅' in row else None
        ts = pd.Timestamp.now()
        data = {
            '净值日期': [ts],
            '单位净值': [latest],
            '日增长率': [f"{pct}%" if pct is not None and str(pct) != '' else 'N/A'],
        }
        return pd.DataFrame(data)
    except Exception as e:
        logging.error(f"获取 A股指数实时数据失败: {symbol}, {e}")
        return pd.DataFrame()

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
        info = resolve_code(fund_code)
        if not info:
            return pd.DataFrame()

        if info.get('type') == 'index':
            # 全球指数：实时（兼容 global_* 分区）
            market = str(info.get('market') or '')
            if market.startswith('global'):
                spot = get_global_index_data(info.get('symbol', fund_code))
                return _format_index_output(_build_global_index_df(spot), days)

            # 中国指数：实时优先（始终优先使用当日实时，失败再回退历史）
            symbol = info.get('symbol', fund_code)
            spot_df = _build_cn_index_spot_df(symbol)
            if spot_df is not None and not spot_df.empty:
                return _format_index_output(spot_df, days)
            daily = ak.stock_zh_index_daily(symbol=symbol)
            return _format_index_output(_build_cn_index_df(daily), days)

        # 基金：历史
        fund_data = ak.fund_open_fund_info_em(symbol=info.get('symbol', fund_code), indicator="单位净值走势")
        if fund_data.empty:
            return pd.DataFrame()
        fund_data = fund_data.sort_values('净值日期', ascending=False)
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
