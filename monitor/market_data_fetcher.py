#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场数据获取器 - 支持批量查询股票和基金涨跌幅
Author: TickEye Team
Date: 2025-01-24
"""

import akshare as ak
import pandas as pd
import logging
import time
from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseDataProvider(ABC):
    """数据提供商基类"""
    
    @abstractmethod
    def get_fund_realtime_data(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """获取基金实时数据"""
        pass
    
    @abstractmethod
    def get_stock_realtime_data(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """获取股票实时数据"""
        pass
    
    @abstractmethod
    def get_fund_history_data(self, code: str, days: int = 30) -> Optional[pd.DataFrame]:
        """获取基金历史数据"""
        pass

class AKShareProvider(BaseDataProvider):
    """AKShare 数据提供商"""
    
    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self.cache_duration = 60  # 缓存60秒
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache_time:
            return False
        return time.time() - self._cache_time[key] < self.cache_duration
    
    def get_fund_realtime_data(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """
        获取基金实时数据
        
        Args:
            codes: 基金代码列表
            
        Returns:
            pd.DataFrame: 包含基金代码、名称、净值、涨跌幅等信息
        """
        cache_key = "fund_realtime"
        
        if not self._is_cache_valid(cache_key):
            try:
                logger.info("正在获取基金实时数据...")
                # 使用正确的 AKShare API
                df = ak.fund_open_fund_daily_em()
                
                if df is not None and not df.empty:
                    self._cache[cache_key] = df
                    self._cache_time[cache_key] = time.time()
                    logger.info(f"成功获取 {len(df)} 只基金的实时数据")
                else:
                    logger.warning("获取的基金实时数据为空")
                    return None
                    
            except Exception as e:
                logger.error(f"获取基金实时数据失败: {e}")
                return None
        
        # 从缓存中筛选指定的基金代码
        all_data = self._cache.get(cache_key)
        if all_data is None or all_data.empty:
            return None
        
        # 查找基金代码列
        code_column = None
        for col in all_data.columns:
            if '基金代码' in col or '代码' in col:
                code_column = col
                break
        
        if code_column is None:
            logger.error("未找到基金代码列")
            return None
        
        # 筛选指定的基金代码
        filtered_data = all_data[all_data[code_column].isin(codes)].copy()
        logger.info(f"筛选出 {len(filtered_data)}/{len(codes)} 只基金")
        
        return filtered_data if not filtered_data.empty else None
    
    def get_stock_realtime_data(self, codes: List[str]) -> Optional[pd.DataFrame]:
        """
        获取股票实时数据
        
        Args:
            codes: 股票代码列表
            
        Returns:
            pd.DataFrame: 包含股票代码、名称、价格、涨跌幅等信息
        """
        try:
            logger.info(f"正在获取 {len(codes)} 只股票的实时数据...")
            
            # 批量获取股票数据
            stock_data_list = []
            for code in codes:
                try:
                    # 获取股票实时数据
                    df = ak.stock_zh_a_spot_em()
                    if df is not None and not df.empty:
                        # 查找对应的股票
                        stock_row = df[df['代码'] == code]
                        if not stock_row.empty:
                            stock_data_list.append(stock_row)
                except Exception as e:
                    logger.warning(f"获取股票 {code} 数据失败: {e}")
                    continue
            
            if stock_data_list:
                result = pd.concat(stock_data_list, ignore_index=True)
                logger.info(f"成功获取 {len(result)} 只股票数据")
                return result
            else:
                logger.warning("未获取到任何股票数据")
                return None
                
        except Exception as e:
            logger.error(f"获取股票实时数据失败: {e}")
            return None
    
    def get_fund_history_data(self, code: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        获取基金历史数据
        
        Args:
            code: 基金代码
            days: 获取天数
            
        Returns:
            pd.DataFrame: 历史净值数据
        """
        try:
            logger.info(f"正在获取基金 {code} 的历史数据...")
            
            # 尝试多种 AKShare API
            apis_to_try = [
                # 尝试基金历史净值API
                lambda: ak.fund_em_open_fund_info(fund=code, indicator="历史净值"),
                # 尝试其他可能的API
                lambda: ak.fund_individual_basic_info_xq(symbol=code),
            ]
            
            for i, api_func in enumerate(apis_to_try, 1):
                try:
                    df = api_func()
                    if df is not None and not df.empty:
                        logger.info(f"使用第 {i} 个API成功获取历史数据")
                        
                        # 数据处理和清理
                        df = df.copy()
                        
                        # 限制返回天数
                        if len(df) > days:
                            df = df.head(days)
                        
                        return df
                except Exception as e:
                    logger.debug(f"第 {i} 个API失败: {e}")
                    continue
            
            logger.warning(f"所有API都无法获取基金 {code} 的历史数据")
            return None
            
        except Exception as e:
            logger.error(f"获取基金 {code} 历史数据失败: {e}")
            return None

class MarketDataFetcher:
    """
    市场数据获取器 - 支持批量查询的扩展性架构
    """
    
    def __init__(self, provider: BaseDataProvider = None):
        self.provider = provider or AKShareProvider()
    
    def get_batch_changes(self, symbols: List[Dict[str, str]], 
                         include_history: bool = False) -> Dict[str, pd.DataFrame]:
        """
        批量获取股票/基金的涨跌幅数据
        
        Args:
            symbols: 符号列表，格式: [{"code": "270042", "type": "fund"}, {"code": "000001", "type": "stock"}]
            include_history: 是否包含历史数据
            
        Returns:
            Dict: 按类型分组的数据 {"funds": DataFrame, "stocks": DataFrame}
        """
        results = {"funds": None, "stocks": None, "history": {}}
        
        # 按类型分组
        fund_codes = [s["code"] for s in symbols if s["type"] == "fund"]
        stock_codes = [s["code"] for s in symbols if s["type"] == "stock"]
        
        # 获取基金数据
        if fund_codes:
            logger.info(f"正在获取 {len(fund_codes)} 只基金的数据...")
            results["funds"] = self.provider.get_fund_realtime_data(fund_codes)
        
        # 获取股票数据
        if stock_codes:
            logger.info(f"正在获取 {len(stock_codes)} 只股票的数据...")
            results["stocks"] = self.provider.get_stock_realtime_data(stock_codes)
        
        # 获取历史数据（如果需要）
        if include_history:
            for symbol in symbols:
                if symbol["type"] == "fund":
                    hist_data = self.provider.get_fund_history_data(symbol["code"])
                    if hist_data is not None:
                        results["history"][symbol["code"]] = hist_data
        
        return results
    
    def analyze_changes(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        分析涨跌幅数据
        
        Args:
            data_dict: get_batch_changes 返回的数据
            
        Returns:
            Dict: 分析结果
        """
        analysis = {"summary": {}, "details": {}}
        
        # 分析基金数据
        if data_dict.get("funds") is not None:
            funds_df = data_dict["funds"]
            analysis["details"]["funds"] = self._analyze_dataframe(funds_df, "fund")
            analysis["summary"]["funds_count"] = len(funds_df)
        
        # 分析股票数据
        if data_dict.get("stocks") is not None:
            stocks_df = data_dict["stocks"]
            analysis["details"]["stocks"] = self._analyze_dataframe(stocks_df, "stock")
            analysis["summary"]["stocks_count"] = len(stocks_df)
        
        return analysis
    
    def _analyze_dataframe(self, df: pd.DataFrame, data_type: str) -> Dict:
        """分析单个DataFrame的涨跌幅情况"""
        analysis = {"positive": 0, "negative": 0, "neutral": 0, "items": []}
        
        # 查找涨跌幅列
        change_column = None
        for col in df.columns:
            if any(keyword in col for keyword in ['涨跌幅', '涨跌', '变化', '增长率']):
                change_column = col
                break
        
        if change_column is None:
            logger.warning(f"未找到 {data_type} 数据的涨跌幅列")
            return analysis
        
        # 统计涨跌情况
        for _, row in df.iterrows():
            change_value = row.get(change_column)
            
            # 处理不同格式的涨跌幅数据
            if pd.isna(change_value):
                analysis["neutral"] += 1
                continue
            
            # 转换为数值
            if isinstance(change_value, str):
                try:
                    change_value = float(change_value.replace('%', ''))
                except:
                    analysis["neutral"] += 1
                    continue
            
            # 分类统计
            if change_value > 0:
                analysis["positive"] += 1
            elif change_value < 0:
                analysis["negative"] += 1
            else:
                analysis["neutral"] += 1
            
            # 记录详细信息
            code_col = None
            name_col = None
            for col in df.columns:
                if '代码' in col:
                    code_col = col
                elif '名称' in col or '简称' in col:
                    name_col = col
            
            item_info = {
                "code": row.get(code_col, "N/A"),
                "name": row.get(name_col, "N/A"),
                "change": change_value
            }
            analysis["items"].append(item_info)
        
        return analysis

# 创建全局实例
market_fetcher = MarketDataFetcher()
