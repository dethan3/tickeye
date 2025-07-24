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


if __name__ == "__main__":
    # 简化的测试代码
    print("=== TickEye 基金数据获取器（简化版）===")
    print(f"Python 版本: {sys.version}")
    
    # 测试获取少量基金
    print("\n📊 测试获取指定基金...")
    test_codes = ["000001", "110022", "161725"]
    df = get_specific_funds(test_codes)
    
    if df is not None and not df.empty:
        print(f"成功获取 {len(df)} 只基金")
        print("可用列:", list(df.columns))
        # 显示前几行数据
        print("\n数据示例:")
        print(df.head(3))
    else:
        print("未获取到数据")
    
    # 显示缓存信息
    print("\n💾 缓存信息:")
    cache_info = fetcher.get_cache_info()
    for key, info in cache_info.items():
        print(f"  {key}: 缓存={info['cached']}, 有效={info['valid']}, 记录数={info['record_count']}")
