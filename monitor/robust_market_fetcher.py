#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健壮的市场数据获取器 - 优化批量查询性能和稳定性
Author: TickEye Team
Date: 2025-08-04
"""

import akshare as ak
import pandas as pd
import logging
import time
import random
from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class RobustMarketFetcher:
    """
    健壮的市场数据获取器
    特点：
    1. 重试机制
    2. 分批处理
    3. 缓存优化
    4. 错误恢复
    5. 并发控制
    """
    
    def __init__(self, max_retries: int = 3, batch_size: int = 50, cache_duration: int = 300):
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.cache_duration = cache_duration  # 5分钟缓存
        
        # 缓存系统
        self._cache = {}
        self._cache_time = {}
        
        # 配置请求会话
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache_time:
            return False
        return time.time() - self._cache_time[key] < self.cache_duration
    
    def _set_cache(self, key: str, data: pd.DataFrame):
        """设置缓存"""
        self._cache[key] = data.copy() if data is not None else None
        self._cache_time[key] = time.time()
    
    def _get_cache(self, key: str) -> Optional[pd.DataFrame]:
        """获取缓存"""
        if self._is_cache_valid(key):
            return self._cache.get(key)
        return None
    
    def _retry_api_call(self, api_func, max_retries: int = None) -> Optional[pd.DataFrame]:
        """
        带重试机制的API调用
        
        Args:
            api_func: API调用函数
            max_retries: 最大重试次数
            
        Returns:
            pd.DataFrame: API返回的数据
        """
        if max_retries is None:
            max_retries = self.max_retries
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # 添加随机延迟避免频繁请求
                if attempt > 0:
                    delay = random.uniform(1, 3) * attempt
                    logger.info(f"重试第 {attempt} 次，等待 {delay:.1f} 秒...")
                    time.sleep(delay)
                
                result = api_func()
                
                if result is not None and not result.empty:
                    logger.info(f"API调用成功 (尝试 {attempt + 1}/{max_retries + 1})")
                    return result
                else:
                    logger.warning(f"API返回空数据 (尝试 {attempt + 1}/{max_retries + 1})")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                
                # 如果是网络相关错误，等待更长时间
                if "Connection" in str(e) or "IncompleteRead" in str(e):
                    time.sleep(random.uniform(2, 5))
        
        logger.error(f"API调用最终失败，已重试 {max_retries} 次: {last_error}")
        return None
    
    def get_fund_data_robust(self, codes: List[str] = None) -> Optional[pd.DataFrame]:
        """
        健壮的基金数据获取
        
        Args:
            codes: 基金代码列表，如果为None则获取全部
            
        Returns:
            pd.DataFrame: 基金数据
        """
        cache_key = "fund_all_data"
        
        # 检查缓存
        cached_data = self._get_cache(cache_key)
        if cached_data is not None:
            logger.info("使用缓存的基金数据")
            if codes:
                return self._filter_by_codes(cached_data, codes, "基金")
            return cached_data
        
        # 获取新数据
        logger.info("获取基金数据...")
        
        def fetch_funds():
            return ak.fund_open_fund_daily_em()
        
        df = self._retry_api_call(fetch_funds)
        
        if df is not None and not df.empty:
            # 数据清理
            df = self._clean_fund_data(df)
            
            # 缓存数据
            self._set_cache(cache_key, df)
            logger.info(f"成功获取并缓存 {len(df)} 条基金数据")
            
            # 筛选指定代码
            if codes:
                return self._filter_by_codes(df, codes, "基金")
            return df
        
        return None
    
    def get_stock_data_robust(self, codes: List[str] = None) -> Optional[pd.DataFrame]:
        """
        健壮的股票数据获取
        
        Args:
            codes: 股票代码列表，如果为None则获取全部
            
        Returns:
            pd.DataFrame: 股票数据
        """
        cache_key = "stock_all_data"
        
        # 检查缓存
        cached_data = self._get_cache(cache_key)
        if cached_data is not None:
            logger.info("使用缓存的股票数据")
            if codes:
                return self._filter_by_codes(cached_data, codes, "股票")
            return cached_data
        
        # 获取新数据
        logger.info("获取股票数据...")
        
        def fetch_stocks():
            return ak.stock_zh_a_spot_em()
        
        df = self._retry_api_call(fetch_stocks)
        
        if df is not None and not df.empty:
            # 数据清理
            df = self._clean_stock_data(df)
            
            # 缓存数据
            self._set_cache(cache_key, df)
            logger.info(f"成功获取并缓存 {len(df)} 条股票数据")
            
            # 筛选指定代码
            if codes:
                return self._filter_by_codes(df, codes, "股票")
            return df
        
        return None
    
    def _clean_fund_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理基金数据"""
        if df is None or df.empty:
            return df
        
        # 移除无效的基金代码
        if '基金代码' in df.columns:
            df = df.dropna(subset=['基金代码'])
            df = df[df['基金代码'].str.len() == 6]  # 基金代码应该是6位
        
        # 处理数值列
        numeric_columns = ['日增长值', '日增长率']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df.reset_index(drop=True)
    
    def _clean_stock_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理股票数据"""
        if df is None or df.empty:
            return df
        
        # 移除无效的股票代码
        if '代码' in df.columns:
            df = df.dropna(subset=['代码'])
            df = df[df['代码'].str.len() == 6]  # 股票代码应该是6位
        
        # 处理数值列
        numeric_columns = ['最新价', '涨跌幅', '涨跌额', '成交量', '成交额']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df.reset_index(drop=True)
    
    def _filter_by_codes(self, df: pd.DataFrame, codes: List[str], data_type: str) -> Optional[pd.DataFrame]:
        """根据代码筛选数据"""
        if df is None or df.empty or not codes:
            return df
        
        # 确定代码列名
        code_column = None
        if data_type == "基金":
            code_column = next((col for col in df.columns if '基金代码' in col or '代码' in col), None)
        else:  # 股票
            code_column = next((col for col in df.columns if '代码' in col), None)
        
        if code_column is None:
            logger.error(f"未找到{data_type}代码列")
            return None
        
        # 筛选数据
        filtered_df = df[df[code_column].isin(codes)].copy()
        logger.info(f"筛选出 {len(filtered_df)}/{len(codes)} 只{data_type}")
        
        return filtered_df if not filtered_df.empty else None
    
    def batch_query(self, watchlist: List[Dict[str, str]]) -> Dict[str, pd.DataFrame]:
        """
        批量查询市场数据
        
        Args:
            watchlist: 监控列表 [{"code": "270042", "type": "fund"}, ...]
            
        Returns:
            Dict: {"funds": DataFrame, "stocks": DataFrame, "summary": Dict}
        """
        results = {
            "funds": None,
            "stocks": None,
            "summary": {
                "total_requested": len(watchlist),
                "funds_requested": 0,
                "stocks_requested": 0,
                "funds_found": 0,
                "stocks_found": 0,
                "success_rate": 0.0
            }
        }
        
        # 按类型分组
        fund_codes = [item["code"] for item in watchlist if item["type"] == "fund"]
        stock_codes = [item["code"] for item in watchlist if item["type"] == "stock"]
        
        results["summary"]["funds_requested"] = len(fund_codes)
        results["summary"]["stocks_requested"] = len(stock_codes)
        
        logger.info(f"开始批量查询: {len(fund_codes)} 只基金, {len(stock_codes)} 只股票")
        
        # 获取基金数据
        if fund_codes:
            logger.info("获取基金数据...")
            funds_df = self.get_fund_data_robust(fund_codes)
            if funds_df is not None and not funds_df.empty:
                results["funds"] = funds_df
                results["summary"]["funds_found"] = len(funds_df)
                logger.info(f"✅ 成功获取 {len(funds_df)} 只基金数据")
            else:
                logger.warning("❌ 未获取到基金数据")
        
        # 获取股票数据
        if stock_codes:
            logger.info("获取股票数据...")
            stocks_df = self.get_stock_data_robust(stock_codes)
            if stocks_df is not None and not stocks_df.empty:
                results["stocks"] = stocks_df
                results["summary"]["stocks_found"] = len(stocks_df)
                logger.info(f"✅ 成功获取 {len(stocks_df)} 只股票数据")
            else:
                logger.warning("❌ 未获取到股票数据")
        
        # 计算成功率
        total_found = results["summary"]["funds_found"] + results["summary"]["stocks_found"]
        total_requested = results["summary"]["total_requested"]
        results["summary"]["success_rate"] = (total_found / total_requested * 100) if total_requested > 0 else 0
        
        logger.info(f"批量查询完成: {total_found}/{total_requested} ({results['summary']['success_rate']:.1f}%)")
        
        return results
    
    def analyze_market_data(self, results: Dict[str, pd.DataFrame]) -> Dict[str, any]:
        """
        分析市场数据
        
        Args:
            results: batch_query返回的结果
            
        Returns:
            Dict: 分析结果
        """
        analysis = {
            "funds_analysis": {},
            "stocks_analysis": {},
            "market_overview": {}
        }
        
        # 分析基金数据
        if results.get("funds") is not None:
            funds_df = results["funds"]
            analysis["funds_analysis"] = self._analyze_funds(funds_df)
        
        # 分析股票数据
        if results.get("stocks") is not None:
            stocks_df = results["stocks"]
            analysis["stocks_analysis"] = self._analyze_stocks(stocks_df)
        
        # 市场概览
        analysis["market_overview"] = self._generate_market_overview(analysis)
        
        return analysis
    
    def _analyze_funds(self, df: pd.DataFrame) -> Dict:
        """分析基金数据"""
        analysis = {
            "count": len(df),
            "rising": 0,
            "falling": 0,
            "flat": 0,
            "top_gainers": [],
            "top_losers": []
        }
        
        # 查找涨跌幅列
        change_col = None
        for col in df.columns:
            if '日增长率' in col or '涨跌幅' in col:
                change_col = col
                break
        
        if change_col and change_col in df.columns:
            # 统计涨跌情况
            for _, row in df.iterrows():
                change = row.get(change_col)
                if pd.notna(change) and change != '':
                    try:
                        change_val = float(str(change).replace('%', ''))
                        if change_val > 0:
                            analysis["rising"] += 1
                        elif change_val < 0:
                            analysis["falling"] += 1
                        else:
                            analysis["flat"] += 1
                    except:
                        analysis["flat"] += 1
                else:
                    analysis["flat"] += 1
        
        return analysis
    
    def _analyze_stocks(self, df: pd.DataFrame) -> Dict:
        """分析股票数据"""
        analysis = {
            "count": len(df),
            "rising": 0,
            "falling": 0,
            "flat": 0,
            "avg_change": 0.0
        }
        
        # 查找涨跌幅列
        change_col = '涨跌幅'
        
        if change_col in df.columns:
            changes = []
            for _, row in df.iterrows():
                change = row.get(change_col)
                if pd.notna(change):
                    try:
                        change_val = float(change)
                        changes.append(change_val)
                        if change_val > 0:
                            analysis["rising"] += 1
                        elif change_val < 0:
                            analysis["falling"] += 1
                        else:
                            analysis["flat"] += 1
                    except:
                        analysis["flat"] += 1
                else:
                    analysis["flat"] += 1
            
            if changes:
                analysis["avg_change"] = sum(changes) / len(changes)
        
        return analysis
    
    def _generate_market_overview(self, analysis: Dict) -> Dict:
        """生成市场概览"""
        overview = {
            "total_instruments": 0,
            "total_rising": 0,
            "total_falling": 0,
            "market_sentiment": "中性"
        }
        
        # 汇总数据
        funds_analysis = analysis.get("funds_analysis", {})
        stocks_analysis = analysis.get("stocks_analysis", {})
        
        overview["total_instruments"] = funds_analysis.get("count", 0) + stocks_analysis.get("count", 0)
        overview["total_rising"] = funds_analysis.get("rising", 0) + stocks_analysis.get("rising", 0)
        overview["total_falling"] = funds_analysis.get("falling", 0) + stocks_analysis.get("falling", 0)
        
        # 判断市场情绪
        if overview["total_rising"] > overview["total_falling"]:
            overview["market_sentiment"] = "乐观"
        elif overview["total_falling"] > overview["total_rising"]:
            overview["market_sentiment"] = "悲观"
        
        return overview

# 创建全局实例
robust_fetcher = RobustMarketFetcher()
