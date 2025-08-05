from typing import List, Dict, Any, Callable
import pandas as pd
import logging
from abc import ABC, abstractmethod
import re

logger = logging.getLogger(__name__)


class Rule(ABC):
    """监控规则的抽象基类"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    @abstractmethod
    def check(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        检查规则是否触发
        
        Args:
            data: 基金数据DataFrame
            
        Returns:
            List[Dict]: 触发的警告信息列表，每个字典包含：
                - fund_code: 基金代码
                - fund_name: 基金名称  
                - message: 警告消息
                - value: 触发值
                - rule_name: 规则名称
        """
        pass


class FieldHelper:
    """字段名辅助工具，处理 AKShare 的动态字段名"""
    
    @staticmethod
    def find_column(df: pd.DataFrame, patterns: List[str]) -> str:
        """
        在 DataFrame 中查找匹配模式的列名
        
        Args:
            df: DataFrame
            patterns: 匹配模式列表
            
        Returns:
            str: 找到的列名，未找到返回 None
        """
        if df is None or df.empty:
            return None
        
        columns = df.columns.tolist()
        
        for pattern in patterns:
            # 精确匹配
            if pattern in columns:
                return pattern
            
            # 模糊匹配 - 包含关键词
            for col in columns:
                if pattern in col:
                    return col
        
        return None
    
    @staticmethod
    def get_fund_code_column(df: pd.DataFrame) -> str:
        """获取基金代码列名"""
        patterns = ['基金代码', 'fund_code', '代码']
        return FieldHelper.find_column(df, patterns)
    
    @staticmethod
    def get_fund_name_column(df: pd.DataFrame) -> str:
        """获取基金名称列名"""
        patterns = ['基金简称', '基金名称', 'fund_name', '简称', '名称']
        return FieldHelper.find_column(df, patterns)
    
    @staticmethod
    def get_net_value_column(df: pd.DataFrame) -> str:
        """获取单位净值列名"""
        patterns = ['单位净值', 'net_value', '净值']
        return FieldHelper.find_column(df, patterns)
    
    @staticmethod
    def get_change_rate_column(df: pd.DataFrame) -> str:
        """获取涨跌率列名"""
        patterns = ['日增长率', '增长率', '涨跌率', '涨幅', 'change_rate']
        return FieldHelper.find_column(df, patterns)
    
    @staticmethod
    def parse_percentage(value) -> float:
        """
        解析百分比值，支持多种格式
        
        Args:
            value: 原始值（可能包含%符号）
            
        Returns:
            float: 数值形式的百分比
        """
        if pd.isna(value):
            return 0.0
        
        try:
            # 转换为字符串并清理
            str_value = str(value).strip()
            
            # 移除百分号
            if '%' in str_value:
                str_value = str_value.replace('%', '')
            
            # 转换为数值
            return float(str_value)
            
        except (ValueError, TypeError):
            logger.warning(f"无法解析百分比值: {value}")
            return 0.0


class PercentageDropRule(Rule):
    """跌幅监控规则 - 优化版"""
    
    def __init__(self, name: str, threshold: float, fund_codes: List[str] = None):
        """
        Args:
            name: 规则名称
            threshold: 跌幅阈值（正数，如3表示跌幅超过3%）
            fund_codes: 监控的基金代码列表，None表示监控所有基金
        """
        super().__init__(name, f"监控基金跌幅超过{threshold}%")
        self.threshold = threshold
        self.fund_codes = fund_codes or []
    
    def check(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        alerts = []
        
        if data is None or data.empty:
            return alerts
        
        # 动态获取字段名
        code_col = FieldHelper.get_fund_code_column(data)
        name_col = FieldHelper.get_fund_name_column(data)
        rate_col = FieldHelper.get_change_rate_column(data)
        
        if not all([code_col, name_col, rate_col]):
            missing = []
            if not code_col: missing.append("基金代码")
            if not name_col: missing.append("基金名称")
            if not rate_col: missing.append("涨跌率")
            logger.error(f"缺少必要字段: {missing}")
            return alerts
        
        # 筛选要监控的基金
        if self.fund_codes:
            filtered_data = data[data[code_col].isin(self.fund_codes)]
            if filtered_data.empty:
                logger.warning(f"规则 {self.name}: 未找到指定的基金代码")
                return alerts
        else:
            filtered_data = data
        
        # 检查跌幅超过阈值的基金
        try:
            triggered_count = 0
            
            for _, fund in filtered_data.iterrows():
                change_rate = FieldHelper.parse_percentage(fund[rate_col])
                
                # 检查是否超过跌幅阈值
                if change_rate <= -self.threshold:
                    alerts.append({
                        'fund_code': fund[code_col],
                        'fund_name': fund[name_col],
                        'message': f"基金 {fund[name_col]}({fund[code_col]}) 跌幅{change_rate:.2f}%，超过阈值-{self.threshold}%",
                        'value': change_rate,
                        'rule_name': self.name
                    })
                    triggered_count += 1
            
            if triggered_count > 0:
                logger.info(f"规则 {self.name}: 触发 {triggered_count} 个警告")
                    
        except Exception as e:
            logger.error(f"规则 {self.name} 执行时出错: {e}")
        
        return alerts


class PriceThresholdRule(Rule):
    """净值阈值监控规则 - 优化版"""
    
    def __init__(self, name: str, fund_code: str, threshold: float, operator: str = "below"):
        """
        Args:
            name: 规则名称
            fund_code: 基金代码
            threshold: 净值阈值
            operator: 比较操作符 ("below", "above")
        """
        op_text = "低于" if operator == "below" else "高于"
        super().__init__(name, f"监控基金{fund_code}净值{op_text}{threshold}")
        self.fund_code = fund_code
        self.threshold = threshold
        self.operator = operator
    
    def check(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        alerts = []
        
        if data is None or data.empty:
            return alerts
        
        # 动态获取字段名
        code_col = FieldHelper.get_fund_code_column(data)
        name_col = FieldHelper.get_fund_name_column(data)
        value_col = FieldHelper.get_net_value_column(data)
        
        if not all([code_col, name_col, value_col]):
            missing = []
            if not code_col: missing.append("基金代码")  
            if not name_col: missing.append("基金名称")
            if not value_col: missing.append("单位净值")
            logger.error(f"缺少必要字段: {missing}")
            return alerts
            
        # 查找指定基金
        fund_data = data[data[code_col] == self.fund_code]
        
        if fund_data.empty:
            logger.warning(f"规则 {self.name}: 未找到基金代码 {self.fund_code}")
            return alerts
        
        try:
            fund = fund_data.iloc[0]
            current_value = float(fund[value_col])
            
            triggered = False
            if self.operator == "below" and current_value < self.threshold:
                triggered = True
                op_text = "低于"
            elif self.operator == "above" and current_value > self.threshold:
                triggered = True
                op_text = "高于"
            
            if triggered:
                alerts.append({
                    'fund_code': fund[code_col],
                    'fund_name': fund[name_col],
                    'message': f"基金 {fund[name_col]}({fund[code_col]}) 净值{current_value}{op_text}阈值{self.threshold}",
                    'value': current_value,
                    'rule_name': self.name
                })
                logger.info(f"规则 {self.name}: 触发净值警告")
                
        except Exception as e:
            logger.error(f"规则 {self.name} 执行时出错: {e}")
        
        return alerts


class RuleEngine:
    """规则引擎，管理和执行所有监控规则"""
    
    def __init__(self):
        self.rules: List[Rule] = []
    
    def add_rule(self, rule: Rule):
        """添加监控规则"""
        self.rules.append(rule)
        logger.info(f"已添加规则: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """移除监控规则"""
        initial_count = len(self.rules)
        self.rules = [rule for rule in self.rules if rule.name != rule_name]
        if len(self.rules) < initial_count:
            logger.info(f"已移除规则: {rule_name}")
        else:
            logger.warning(f"未找到规则: {rule_name}")
    
    def check_all_rules(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        执行所有规则检查
        
        Args:
            data: 基金数据DataFrame
            
        Returns:
            List[Dict]: 所有触发的警告信息
        """
        if data is None or data.empty:
            logger.warning("规则引擎: 输入数据为空")
            return []
        
        all_alerts = []
        successful_rules = 0
        
        logger.info(f"开始执行 {len(self.rules)} 个规则检查...")
        
        for rule in self.rules:
            try:
                alerts = rule.check(data)
                all_alerts.extend(alerts)
                successful_rules += 1
                logger.debug(f"规则 {rule.name}: 触发 {len(alerts)} 个警告")
            except Exception as e:
                logger.error(f"规则 {rule.name} 执行失败: {e}")
        
        logger.info(f"规则检查完成: {successful_rules}/{len(self.rules)} 个规则成功执行，共触发 {len(all_alerts)} 个警告")
        return all_alerts
    
    def get_rules_summary(self) -> List[Dict[str, str]]:
        """获取所有规则的摘要信息"""
        return [
            {
                'name': rule.name,
                'description': rule.description,
                'type': rule.__class__.__name__
            }
            for rule in self.rules
        ]


def create_rules_from_config(config: Dict[str, Any]) -> RuleEngine:
    """
    从配置创建规则引擎
    
    Args:
        config: 配置字典，应包含rules部分
        
    Returns:
        RuleEngine: 配置好的规则引擎
    """
    engine = RuleEngine()
    
    rules_config = config.get('rules', [])
    created_rules = 0
    
    for rule_config in rules_config:
        rule_type = rule_config.get('type')
        rule_name = rule_config.get('name', f"规则_{created_rules + 1}")
        
        try:
            if rule_type == 'percentage_drop':
                rule = PercentageDropRule(
                    name=rule_name,
                    threshold=rule_config.get('threshold', 3.0),
                    fund_codes=rule_config.get('fund_codes', [])
                )
                engine.add_rule(rule)
                created_rules += 1
                
            elif rule_type == 'price_threshold':
                fund_code = rule_config.get('fund_code')
                if not fund_code:
                    logger.error(f"价格阈值规则缺少基金代码: {rule_name}")
                    continue
                    
                rule = PriceThresholdRule(
                    name=rule_name,
                    fund_code=fund_code,
                    threshold=rule_config.get('threshold', 1.0),
                    operator=rule_config.get('operator', 'below')
                )
                engine.add_rule(rule)
                created_rules += 1
                
            else:
                logger.warning(f"未知的规则类型: {rule_type}")
                
        except Exception as e:
            logger.error(f"创建规则 {rule_name} 时出错: {e}")
    
    logger.info(f"从配置创建了 {created_rules} 个规则")
    return engine


if __name__ == "__main__":
    # 简化的测试示例
    from monitor.fetcher import get_specific_funds
    
    print("=== TickEye 规则引擎测试（优化版）===")
    
    # 创建规则引擎
    engine = RuleEngine()
    
    # 添加跌幅监控规则
    drop_rule = PercentageDropRule("市场跌幅监控", 3.0)
    engine.add_rule(drop_rule)
    
    # 添加特定基金跌幅监控
    specific_drop_rule = PercentageDropRule(
        "重点基金监控", 
        2.0, 
        fund_codes=["000001", "110022"]
    )
    engine.add_rule(specific_drop_rule)
    
    # 测试规则配置创建
    test_config = {
        'rules': [
            {
                'type': 'percentage_drop',
                'name': '配置测试规则',
                'threshold': 2.5,
                'fund_codes': ['000001']
            }
        ]
    }
    config_engine = create_rules_from_config(test_config)
    
    print(f"✅ 手动创建了 {len(engine.rules)} 个规则")
    print(f"✅ 从配置创建了 {len(config_engine.rules)} 个规则")
    
    # 获取测试数据并检查规则
    print("\n📊 获取测试数据...")
    test_codes = ["000001", "110022", "161725"]
    data = get_specific_funds(test_codes)
    
    if data is not None and not data.empty:
        print(f"获取到 {len(data)} 只基金数据")
        print("可用字段:", list(data.columns))
        
        # 执行规则检查
        alerts = engine.check_all_rules(data)
        print(f"\n🚨 触发 {len(alerts)} 个警告:")
        for alert in alerts:
            print(f"  - {alert['message']}")
    else:
        print("❌ 未获取到测试数据")
        
    # 显示规则摘要
    print(f"\n📋 规则摘要:")
    for rule_info in engine.get_rules_summary():
        print(f"  {rule_info['name']}: {rule_info['description']}")