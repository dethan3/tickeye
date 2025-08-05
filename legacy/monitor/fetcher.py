import akshare as ak
import pandas as pd
import logging
import sys
from typing import List, Optional, Dict, Any
import time
from datetime import datetime

# Python 版本检查 (AKShare 要求 3.9+)
if sys.version_info < (3, 9):
    raise RuntimeError("TickEye requires Python 3.9 or higher (AKShare requirement)")

logger = logging.getLogger(__name__)

# 简化的缓存配置
CACHE_EXPIRE_TIME = 120  # 2分钟，适合交易时段的数据变化


class SimpleFundDataFetcher:
    """简化版基金数据获取器，遵循 AKShare 的简单哲学"""
    
    def __init__(self):
        self._last_fetch_time = {}  # 分类型的最后获取时间
        self._cache = {}  # 分类型的缓存数据
    
    def _is_cache_valid(self, cache_type: str) -> bool:
        """检查指定类型的缓存是否有效"""
        if cache_type not in self._last_fetch_time:
            return False
        return time.time() - self._last_fetch_time[cache_type] < CACHE_EXPIRE_TIME
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """基本的数据清理，移除无效行"""
        if df is None or df.empty:
            return df
        
        # 移除基金代码为空的行
        if '基金代码' in df.columns:
            df = df.dropna(subset=['基金代码'])
            df = df[df['基金代码'].str.len() == 6]  # 基金代码应该是6位
        
        return df.reset_index(drop=True)
    
    def get_open_fund_data(self, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        获取开放式基金数据 - 简化版
        
        Args:
            force_refresh: 强制刷新数据
            
        Returns:
            pd.DataFrame: 基金数据，使用 AKShare 的原始列名
        """
        cache_key = 'open_fund'
        
        # 检查缓存
        if not force_refresh and self._is_cache_valid(cache_key):
            logger.debug("使用缓存的开放式基金数据")
            return self._cache.get(cache_key)
        
        try:
            logger.info("正在获取开放式基金数据...")
            df = ak.fund_open_fund_info_em()
            
            if df is not None and not df.empty:
                df = self._clean_data(df)
                self._cache[cache_key] = df
                self._last_fetch_time[cache_key] = time.time()
                logger.info(f"成功获取 {len(df)} 只开放式基金数据")
                return df
            else:
                logger.warning("获取的开放式基金数据为空")
                return None
                
        except Exception as e:
            logger.error(f"获取开放式基金数据失败: {e}")
            # 返回缓存数据作为备用
            cached_data = self._cache.get(cache_key)
            if cached_data is not None:
                logger.warning("API失败，返回缓存数据")
                return cached_data
            return None
    
    def get_index_fund_data(self, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        获取指数基金/ETF数据 - 简化版
        
        Args:
            force_refresh: 强制刷新数据
            
        Returns:
            pd.DataFrame: 基金数据，使用 AKShare 的原始列名
        """
        cache_key = 'index_fund'
        
        # 检查缓存
        if not force_refresh and self._is_cache_valid(cache_key):
            logger.debug("使用缓存的指数基金数据")
            return self._cache.get(cache_key)
        
        try:
            logger.info("正在获取指数基金数据...")
            df = ak.fund_etf_fund_info_em()
            
            if df is not None and not df.empty:
                df = self._clean_data(df)
                self._cache[cache_key] = df
                self._last_fetch_time[cache_key] = time.time()
                logger.info(f"成功获取 {len(df)} 只指数基金数据")
                return df
            else:
                logger.warning("获取的指数基金数据为空")
                return None
                
        except Exception as e:
            logger.error(f"获取指数基金数据失败: {e}")
            # 返回缓存数据作为备用
            cached_data = self._cache.get(cache_key)
            if cached_data is not None:
                logger.warning("API失败，返回缓存数据")
                return cached_data
            return None
    
    def get_specific_funds(self, codes: List[str], fund_type: str = 'open') -> Optional[pd.DataFrame]:
        """
        获取指定基金代码的数据 - 简化版
        
        Args:
            codes: 基金代码列表
            fund_type: 基金类型 ('open' 或 'index')
            
        Returns:
            pd.DataFrame: 筛选后的基金数据
        """
        if not codes:
            return None
        
        # 直接获取全量数据并筛选 (AKShare 的简单方式)
        if fund_type == 'open':
            all_data = self.get_open_fund_data()
        else:
            all_data = self.get_index_fund_data()
        
        if all_data is None or all_data.empty:
            return None
        
        # 筛选指定的基金代码
        if '基金代码' in all_data.columns:
            filtered_data = all_data[all_data['基金代码'].isin(codes)]
            logger.info(f"筛选出 {len(filtered_data)}/{len(codes)} 只基金")
            return filtered_data
        else:
            logger.error("数据中缺少'基金代码'列")
            return None
    
    def get_funds_by_config(self, config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        根据配置获取基金数据 - 简化版
        
        Args:
            config: 配置字典
            
        Returns:
            pd.DataFrame: 合并后的基金数据
        """
        if not config or 'rules' not in config:
            return None
        
        all_codes = set()
        
        # 收集所有需要监控的基金代码
        for rule in config['rules']:
            if 'fund_codes' in rule:
                all_codes.update(rule['fund_codes'])
            elif 'fund_code' in rule:
                all_codes.add(rule['fund_code'])
        
        if not all_codes:
            logger.warning("配置中没有找到基金代码")
            return None
        
        codes_list = list(all_codes)
        logger.info(f"从配置中提取到 {len(codes_list)} 只基金代码")
        
        # 分别获取开放式和指数基金数据
        open_data = self.get_specific_funds(codes_list, 'open')
        index_data = self.get_specific_funds(codes_list, 'index')
        
        # 合并数据
        combined_data = []
        if open_data is not None and not open_data.empty:
            combined_data.append(open_data)
        if index_data is not None and not index_data.empty:
            combined_data.append(index_data)
        
        if combined_data:
            result = pd.concat(combined_data, ignore_index=True)
            # 去重
            if '基金代码' in result.columns:
                result = result.drop_duplicates(subset=['基金代码'])
            logger.info(f"最终获取到 {len(result)} 只基金数据")
            return result
        
        return None
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        info = {}
        for cache_type in ['open_fund', 'index_fund']:
            info[cache_type] = {
                'cached': cache_type in self._cache,
                'valid': self._is_cache_valid(cache_type),
                'last_update': self._last_fetch_time.get(cache_type),
                'record_count': len(self._cache[cache_type]) if cache_type in self._cache else 0
            }
        return info
    
    def get_fund_history_data(self, fund_code: str, period: str = "近1月") -> Optional[pd.DataFrame]:
        """
        获取指定基金的历史净值数据
        
        Args:
            fund_code: 基金代码 (如 '270042')
            period: 时间周期 ('近1周', '近1月', '近3月', '近6月', '近1年', '近2年', '近3年', '成立来')
            
        Returns:
            pd.DataFrame: 包含日期、净值、涨跌幅等信息的历史数据
        """
        try:
            logger.info(f"正在获取基金 {fund_code} 的历史净值数据...")
            
            # 使用 AKShare 获取基金历史净值数据
            df = ak.fund_open_fund_info_em(fund=fund_code, indicator="历史净值")
            
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
                
                logger.info(f"成功获取基金 {fund_code} 的 {len(df)} 条历史数据")
                return df
            else:
                logger.warning(f"基金 {fund_code} 的历史数据为空")
                return None
                
        except Exception as e:
            logger.error(f"获取基金 {fund_code} 历史数据失败: {e}")
            return None
    
    def get_fund_daily_changes(self, fund_code: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        获取基金最近N天的每日涨跌幅度
        
        Args:
            fund_code: 基金代码
            days: 获取最近多少天的数据
            
        Returns:
            pd.DataFrame: 包含日期和涨跌幅的数据
        """
        history_data = self.get_fund_history_data(fund_code)
        
        if history_data is None or history_data.empty:
            return None
        
        # 取最近N天的数据
        recent_data = history_data.head(days).copy()
        
        # 选择需要的列
        columns_to_keep = ['净值日期', '单位净值']
        if '日增长率' in recent_data.columns:
            columns_to_keep.append('日增长率')
        elif '计算涨跌幅' in recent_data.columns:
            columns_to_keep.append('计算涨跌幅')
        
        result = recent_data[columns_to_keep].copy()
        
        # 重命名列以便统一使用
        if '日增长率' in result.columns:
            result = result.rename(columns={'日增长率': '涨跌幅(%)'})
        elif '计算涨跌幅' in result.columns:
            result = result.rename(columns={'计算涨跌幅': '涨跌幅(%)'})
        
        return result


# 创建全局实例
fetcher = SimpleFundDataFetcher()

# 兼容性函数，保持向后兼容
def get_open_fund_data() -> Optional[pd.DataFrame]:
    """获取所有开放式基金数据（兼容性函数）"""
    return fetcher.get_open_fund_data()

def get_index_fund_data() -> Optional[pd.DataFrame]:
    """获取所有指数基金数据（兼容性函数）"""
    return fetcher.get_index_fund_data()

def get_specific_funds(codes: List[str], fund_type: str = 'open') -> Optional[pd.DataFrame]:
    """获取指定基金代码的数据（兼容性函数）"""
    return fetcher.get_specific_funds(codes, fund_type)
