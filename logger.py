# -*- coding: utf-8 -*-
"""
日志管理模块
用于提供应用程序的持久化日志记录功能
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import os

def setup_logger(name="WT_Voice_Manager"):
    """
    配置并返回日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 防止重复添加 handler
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)
    
    # 确定日志目录 - 使用用户文档文件夹 Aimer_WT/logs
    try:
        user_documents = Path.home() / "Documents"
        base_dir = user_documents / "Aimer_WT"
        log_dir = base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # 如果无法访问文档目录，回退到原来的逻辑
        if getattr(sys, 'frozen', False):
            # 打包环境
            base_dir = Path(sys.executable).parent
        else:
            # 开发环境
            base_dir = Path(__file__).parent
        log_dir = base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. 文件处理器 (RotatingFileHandler)
    # 每个文件最大 10MB，最多保留 5 个备份
    try:
        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"无法初始化文件日志: {e}")
    
    # 2. 控制台处理器 (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logger.info(f"日志系统初始化完成，日志路径: {log_dir}")
    
    return logger
