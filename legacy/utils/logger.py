#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志工具模块
Author: TickEye Team
Date: 2025-01-24
"""

import logging
import sys
from datetime import datetime
import os

def setup_logger(name: str, level: int = logging.INFO, 
                log_file: str = None, console: bool = True) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径（可选）
        console: 是否输出到控制台
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_default_logger() -> logging.Logger:
    """
    获取默认的TickEye日志记录器
    
    Returns:
        logging.Logger: 默认日志记录器
    """
    return setup_logger('tickeye', level=logging.INFO)