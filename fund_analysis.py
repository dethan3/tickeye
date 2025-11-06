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
import time
from typing import Dict, List, Tuple, Optional, Union
from functools import wraps

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ==================== 常量定义 ====================
class DataColumns:
    """数据列名常量"""
    DATE = '净值日期'
    NET_VALUE = '单位净值'
    DAILY_CHANGE = '日增长率'
    CODE = '代码'
    NAME = '名称'
    FUND_NAME = '基金全称'
    LATEST_PRICE = '最新价'
    CHANGE_PCT = '涨跌幅'
    UPDATE_TIME = '最新行情时间'
    CLOSE = 'close'
    DATE_FIELD = 'date'

class RetryConfig:
    """重试配置常量"""
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    BACKOFF_FACTOR = 2.0

# ==================== 工具函数 ====================
def retry_api_call(max_retries: int = RetryConfig.MAX_RETRIES, 
                   delay: float = RetryConfig.RETRY_DELAY,
                   backoff_factor: float = RetryConfig.BACKOFF_FACTOR):
    """API调用重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff_factor ** attempt)
                        logging.warning(f"API调用失败，{wait_time:.1f}秒后重试 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"API调用最终失败 (尝试 {max_retries} 次): {str(e)}")
            raise last_exception
        return wrapper
    return decorator

def validate_dataframe(df: pd.DataFrame, required_columns: List[str]) -> bool:
    """验证DataFrame是否包含必需的列"""
    if df is None or df.empty:
        return False
    return all(col in df.columns for col in required_columns)

def safe_get_column_value(df: pd.DataFrame, row_idx: int, column: str, default=None):
    """安全获取DataFrame列值"""
    try:
        if column in df.columns and row_idx < len(df):
            value = df.iloc[row_idx][column]
            return value if pd.notna(value) else default
        return default
    except (IndexError, KeyError):
        return default

# ==================== 全局变量延迟初始化 ====================
_config_cache = {}
_fund_name_api_cache: Optional[Dict[str, str]] = None

def get_owned_funds() -> Tuple[List[str], Dict[str, str]]:
    """延迟加载基金配置，避免模块导入时失败"""
    if 'funds_config' not in _config_cache:
        try:
            _config_cache['funds_config'] = load_funds_config()
        except Exception as e:
            logging.error(f"加载基金配置失败: {str(e)}")
            _config_cache['funds_config'] = ([], {})
    return _config_cache['funds_config']

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

def get_index_config() -> dict:
    """延迟加载指数配置"""
    if 'index_config' not in _config_cache:
        _config_cache['index_config'] = load_index_aliases()
    return _config_cache['index_config']

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
    aliases = get_index_config().get('aliases', {})
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

def _load_fund_name_api_cache() -> Dict[str, str]:
    """
    调用 akshare 获取基金代码与名称映射并进行缓存
    """
    global _fund_name_api_cache
    if _fund_name_api_cache is not None:
        return _fund_name_api_cache

    try:
        from akshare.fund import fund_em as ak_fund_em
    except Exception:
        _fund_name_api_cache = {}
        return _fund_name_api_cache

    try:
        name_df = ak_fund_em.fund_name_em()
        if name_df is None or name_df.empty:
            _fund_name_api_cache = {}
            return _fund_name_api_cache

        required_cols = {'基金代码', '基金简称'}
        if not required_cols.issubset(set(name_df.columns)):
            logging.warning("基金名称接口返回数据缺少必需列: %s", required_cols)
            _fund_name_api_cache = {}
            return _fund_name_api_cache

        name_df['基金代码'] = name_df['基金代码'].astype(str).str.strip()
        name_df['基金简称'] = name_df['基金简称'].astype(str).str.strip()
        _fund_name_api_cache = {
            row['基金代码']: row['基金简称']
            for _, row in name_df.iterrows()
            if row['基金代码'] and row['基金简称']
        }
    except Exception as e:
        logging.warning("通过 akshare 获取基金名称失败: %s", e)
        _fund_name_api_cache = {}

    return _fund_name_api_cache

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

# 注意：OWNED_FUNDS 和 FUND_NAMES 已改为延迟加载，通过 get_owned_funds() 获取

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
        api_names = _load_fund_name_api_cache()
        api_name = api_names.get(fund_code)
        if not api_name and fund_code.lstrip('0'):
            api_name = api_names.get(fund_code.lstrip('0'))
        if api_name:
            return api_name
    
    # 如果 API 获取失败，尝试使用配置文件中的名称
    _, fund_names = get_owned_funds()
    if fund_code in fund_names:
        config_name = fund_names[fund_code]
        if config_name and config_name.strip():
            return config_name.strip()
    
    # 如果都失败，返回基金代码本身
    return fund_code

@retry_api_call()
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
        
        # 验证必需的列是否存在
        required_cols = [DataColumns.CODE, DataColumns.NAME, DataColumns.LATEST_PRICE, 
                        DataColumns.CHANGE_PCT, DataColumns.UPDATE_TIME]
        if not validate_dataframe(global_data, required_cols):
            logging.error(f"全球指数数据格式不正确，缺少必需列: {required_cols}")
            return {}
        
        # 查找匹配的指数
        matches = global_data[global_data[DataColumns.CODE].str.upper() == fund_code.upper()]
        
        if matches.empty:
            return {}
        
        # 获取第一个匹配的指数数据
        index_row = matches.iloc[0]
        
        return {
            'code': safe_get_column_value(matches, 0, DataColumns.CODE),
            'name': safe_get_column_value(matches, 0, DataColumns.NAME),
            'latest_price': safe_get_column_value(matches, 0, DataColumns.LATEST_PRICE),
            'change_pct': safe_get_column_value(matches, 0, DataColumns.CHANGE_PCT),
            'update_time': safe_get_column_value(matches, 0, DataColumns.UPDATE_TIME)
        }
        
    except (ConnectionError, TimeoutError) as e:
        logging.error(f"网络连接失败，获取全球指数 {fund_code} 数据: {str(e)}")
        return {}
    except KeyError as e:
        logging.error(f"数据格式错误，获取全球指数 {fund_code} 数据: {str(e)}")
        return {}
    except Exception as e:
        logging.error(f"获取全球指数 {fund_code} 数据失败: {str(e)}")
        return {}

# ===== 抽象：指数数据构建与规范化 =====
def _format_index_output(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """统一排序与截取最近 N 天输出。"""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if DataColumns.DATE in out.columns:
        out[DataColumns.DATE] = pd.to_datetime(out[DataColumns.DATE])
        out = out.sort_values(DataColumns.DATE, ascending=False)
    return out.head(days)

def _build_global_index_df(spot: dict) -> pd.DataFrame:
    """由全球指数 spot 字典创建标准输出DataFrame。"""
    if not spot:
        return pd.DataFrame()
    import datetime
    current_time = datetime.datetime.now()
    data = {
        DataColumns.DATE: [current_time],
        DataColumns.NET_VALUE: [spot['latest_price']],
        DataColumns.DAILY_CHANGE: [f"{spot['change_pct']}%"],
    }
    return pd.DataFrame(data)

def _build_cn_index_df(index_data: pd.DataFrame) -> pd.DataFrame:
    """由 A 股指数历史数据构建标准输出DataFrame，并计算日增长率。"""
    if index_data is None or index_data.empty:
        return pd.DataFrame()
    
    # 验证必需的列是否存在
    required_cols = [DataColumns.DATE_FIELD, DataColumns.CLOSE]
    if not validate_dataframe(index_data, required_cols):
        logging.error(f"A股指数数据格式不正确，缺少必需列: {required_cols}")
        return pd.DataFrame()
    
    df = index_data.copy()
    df[DataColumns.DATE] = pd.to_datetime(df[DataColumns.DATE_FIELD])
    df[DataColumns.NET_VALUE] = df[DataColumns.CLOSE]
    
    if len(df) > 1:
        df = df.sort_values(DataColumns.DATE, ascending=False)
        prev_close = df[DataColumns.CLOSE].shift(-1)
        df[DataColumns.DAILY_CHANGE] = ((df[DataColumns.CLOSE] - prev_close) / prev_close * 100).round(2)
        df[DataColumns.DAILY_CHANGE] = df[DataColumns.DAILY_CHANGE].astype(str) + '%'
    
    df = df.sort_values(DataColumns.DATE, ascending=False)
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
        
        # 验证必需的列是否存在
        required_cols = [DataColumns.CODE, DataColumns.LATEST_PRICE, DataColumns.CHANGE_PCT]
        if not validate_dataframe(spot, required_cols):
            logging.error(f"A股指数实时数据格式不正确，缺少必需列: {required_cols}")
            return pd.DataFrame()
        
        codes = spot[DataColumns.CODE].astype(str).str.upper()
        # 兼容 000001 / 000001.SH / 399001.SZ
        mask = (codes == core) | (codes == f"{core}.SH") | (codes == f"{core}.SZ")
        matches = spot[mask]
        if matches.empty:
            return pd.DataFrame()
        
        latest = safe_get_column_value(matches, 0, DataColumns.LATEST_PRICE)
        pct = safe_get_column_value(matches, 0, DataColumns.CHANGE_PCT)
        ts = pd.Timestamp.now()
        
        data = {
            DataColumns.DATE: [ts],
            DataColumns.NET_VALUE: [latest],
            DataColumns.DAILY_CHANGE: [f"{pct}%" if pct is not None and str(pct) != '' else 'N/A'],
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
        
        # 验证必需的列是否存在
        required_cols = [DataColumns.DATE, DataColumns.NET_VALUE]
        if not validate_dataframe(fund_data, required_cols):
            logging.error(f"基金数据格式不正确，缺少必需列: {required_cols}")
            return pd.DataFrame()
        
        fund_data = fund_data.sort_values(DataColumns.DATE, ascending=False)
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
        latest_date = safe_get_column_value(fund_data, 0, DataColumns.DATE)
        if latest_date and hasattr(latest_date, 'strftime'):
            latest_date = latest_date.strftime('%Y-%m-%d')
        else:
            latest_date = 'N/A'
        net_value = safe_get_column_value(fund_data, 0, DataColumns.NET_VALUE)
        
        # 计算涨跌幅
        if len(fund_data) >= 2:
            # 有前一天的数据，计算涨跌幅
            prev_value = safe_get_column_value(fund_data, 1, DataColumns.NET_VALUE)
            
            if prev_value and prev_value != 0 and net_value is not None:
                change_pct = ((net_value - prev_value) / prev_value) * 100
                change_str = f"{change_pct:.2f}%"
                trend = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
            else:
                change_pct = 0
                change_str = "0.00%"
                trend = "➡️"
        else:
            # 只有一天的数据，尝试从日增长率列获取
            daily_change = safe_get_column_value(fund_data, 0, DataColumns.DAILY_CHANGE)
            if daily_change and pd.notna(daily_change):
                change_str = str(daily_change).strip()
                if change_str and change_str != '--' and change_str != 'N/A':
                    try:
                        # 去掉百分号并转换为数字
                        change_num = float(change_str.replace('%', ''))
                        change_str = f"{change_num:.2f}%"
                        trend = "📈" if change_num > 0 else "📉" if change_num < 0 else "➡️"
                    except ValueError:
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
    
    # 使用延迟加载的配置
    owned_funds, _ = get_owned_funds()
    
    if not owned_funds:
        print("未配置任何基金代码或指数代码！")
        return
    
    # 统计基金和指数数量
    fund_count = sum(1 for code in owned_funds if not is_index_code(code))
    index_count = sum(1 for code in owned_funds if is_index_code(code))
    
    if fund_count > 0 and index_count > 0:
        print(f"正在监测 {fund_count} 只基金和 {index_count} 个指数 (最近 {days} 天)")
    elif fund_count > 0:
        print(f"正在监测 {fund_count} 只基金 (最近 {days} 天)")
    else:
        print(f"正在监测 {index_count} 个指数 (最近 {days} 天)")
    
    # 获取所有基金的数据
    fund_summaries = []
    for fund_code in owned_funds:
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
