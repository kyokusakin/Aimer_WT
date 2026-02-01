# -*- coding: utf-8 -*-
# 创建并配置统一的 logging.Logger，包括文件轮转写入与控制台输出，供后端各模块复用。

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_LOGGER_NAME = "WT_Voice_Manager"

_ui_callback: Callable[[str, logging.LogRecord], None] | None = None
_ui_emit_guard = threading.local()


def set_ui_callback(callback: Callable[[str, logging.LogRecord], None] | None) -> None:
    """
    设置前端 UI 日志回调。

    callback: 接收 (formatted_message: str, record: logging.LogRecord)。
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
            callback(self.format(record), record)
        except Exception:
            # 日志链路不应影响业务逻辑
            pass
        finally:
            _ui_emit_guard.active = False


def get_app_data_dir() -> Path:
    """获取应用数据存储目录"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

def _get_log_dir() -> Path:
    base_dir = get_app_data_dir()
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def setup_logger(name: str = APP_LOGGER_NAME) -> logging.Logger:
    # 初始化并返回应用日志记录器，提供文件轮转写入与控制台输出。
    logger = logging.getLogger(name)
    
    # 防止重复添加 handler
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    # 使用统一的日志目录逻辑
    log_dir = _get_log_dir()
    # log.info 此时尚未初始化完成，改用 print 或直接不输出，或者在 handler 添加后输出
    
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
