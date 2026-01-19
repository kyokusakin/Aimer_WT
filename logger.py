# -*- coding: utf-8 -*-
"""
日志管理模块
用于提供应用程序的持久化日志记录功能
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_LOGGER_NAME = "WT_Voice_Manager"

_ui_callback: Callable[[str], None] | None = None
_ui_emit_guard = threading.local()


def set_ui_callback(callback: Callable[[str], None] | None) -> None:
    """
    设置前端 UI 日志回调。

    callback: 接收已格式化的日志字符串（可包含 `<br>`）。
    """
    global _ui_callback
    _ui_callback = callback


class UiCallbackHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        callback = _ui_callback
        if not callback:
            return

        if getattr(_ui_emit_guard, "active", False):
            return

        try:
            _ui_emit_guard.active = True
            callback(self.format(record))
        except Exception:
            # 日志链路不应影响业务逻辑
            pass
        finally:
            _ui_emit_guard.active = False


def _get_log_dir() -> Path:
    # 优先使用用户文档目录 Aimer_WT/logs
    try:
        user_documents = Path.home() / "Documents"
        base_dir = user_documents / "Aimer_WT"
        log_dir = base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    except Exception:
        # 回退：打包环境/开发环境所在目录
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
        log_dir = base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

def setup_logger(name: str = APP_LOGGER_NAME) -> logging.Logger:
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
    logger.propagate = False
    
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

    ui_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
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
        sys.stderr.write(f"无法初始化文件日志: {e}\n")
    
    # 2. 控制台处理器 (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 3. UI 处理器（回调为空时不输出）
    ui_handler = UiCallbackHandler()
    ui_handler.setLevel(logging.INFO)
    ui_handler.setFormatter(ui_formatter)
    logger.addHandler(ui_handler)
    
    logger.info(f"日志系统初始化完成，日志路径: {log_dir}")
    
    return logger


def get_logger(module_name: str | None = None) -> logging.Logger:
    """
    获取模块 logger：`WT_Voice_Manager.<module_name>`
    """
    base = setup_logger(APP_LOGGER_NAME)
    if not module_name or module_name == APP_LOGGER_NAME:
        return base
    return base.getChild(str(module_name))
