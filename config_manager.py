# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path
import sys
from logger import get_logger

log = get_logger(__name__)

# 配置文件所在目录逻辑：
# 1. 优先使用环境变量 AIMER_WT_CONFIG_DIR 指定的目录（用户自定义）
# 2. 其次检查默认位置的配置文件中是否设置了 custom_config_dir
# 3. 若都未设置，打包环境使用可执行文件同级目录，开发环境使用源码目录
def _get_default_config_dir():
    """获取默认配置文件目录"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent
def _get_config_dir():
    """获取配置文件目录，支持用户自定义路径"""
    # 1. 优先检查环境变量
    custom_dir = os.environ.get('AIMER_WT_CONFIG_DIR')
    if custom_dir:
        custom_path = Path(custom_dir)
        if custom_path.exists() or custom_path.parent.exists():
            return custom_path
    
    # 2. 检查默认位置的配置文件中是否有自定义路径设置
    default_dir = _get_default_config_dir()
    default_config = default_dir / "settings.json"
    if default_config.exists():
        try:
            with open(default_config, 'r', encoding='utf-8') as f:
                data = json.load(f)
                saved_custom_dir = data.get('custom_config_dir', '')
                if saved_custom_dir:
                    saved_path = Path(saved_custom_dir)
                    if saved_path.exists() or saved_path.parent.exists():
                        return saved_path
        except:
            pass
    
    # 3. 使用默认目录
    return default_dir

DOCS_DIR = _get_config_dir()
CONFIG_FILE = DOCS_DIR / "settings.json"

class ConfigManager:
    # 维护应用配置的内存表示，并提供按键读写与落盘保存能力。
    def __init__(self):
        # 初始化默认配置并尝试从 settings.json 加载覆盖。
        self.config = {
            "game_path": "",
            "theme_mode": "Light",  # 默认白色
            "is_first_run": True,
            "agreement_version": "",
            "sights_path": "",
            "pending_dir": "",   # 自定義待解壓區路徑
            "library_dir": ""    # 自定義語音包庫路徑
        }
        self.load_config()

    def _load_json_with_fallback(self, file_path):
        # 按编码回退策略读取 JSON 文件并解析为 Python 对象。
        encodings = ["utf-8-sig", "utf-8", "cp950", "big5", "gbk"]
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return json.load(f)
            except:
                continue
        return None

    def load_config(self):
        # 从 settings.json 加载配置并合并到当前配置字典。
        if os.path.exists(CONFIG_FILE):
            try:
                data = self._load_json_with_fallback(CONFIG_FILE)
                if isinstance(data, dict):
                    self.config.update(data)
            except Exception as e:
                log.warning(f"加载配置文件失败: {e}")

    def save_config(self):
        # 将当前配置字典写入 settings.json。
        try:
            # 确保目录存在
            if not DOCS_DIR.exists():
                DOCS_DIR.mkdir(parents=True, exist_ok=True)
                
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            log.error(f"保存配置文件失败: {e}")

    def get_game_path(self):
        # 读取当前配置中的游戏根目录路径。
        return self.config.get("game_path", "")

    def set_game_path(self, path):
        # 更新游戏根目录路径并写入 settings.json。
        self.config["game_path"] = path
        self.save_config()

    def get_sights_path(self):
        # 读取当前配置中的 UserSights 目录路径。
        return self.config.get("sights_path", "")

    def set_sights_path(self, path):
        # 更新 UserSights 目录路径并写入 settings.json。
        self.config["sights_path"] = path
        self.save_config()

    def get_theme_mode(self):
        # 读取当前主题模式（Light/Dark）。
        return self.config.get("theme_mode", "Light")

    def set_theme_mode(self, mode):
        # 更新主题模式并写入 settings.json。
        self.config["theme_mode"] = mode
        self.save_config()

    def get_active_theme(self):
        # 读取当前选择的主题文件名（自定义主题的配置项）。
        return self.config.get("active_theme", "default.json")

    def set_active_theme(self, filename):
        # 更新当前选择的主题文件名并写入 settings.json。
        self.config["active_theme"] = filename
        self.save_config()

    def get_current_mod(self):
        # 读取当前记录的已安装/已生效语音包标识。
        return self.config.get("current_mod", "")

    def set_current_mod(self, mod_id):
        # 更新当前已生效语音包标识并写入 settings.json。
        self.config["current_mod"] = mod_id
        self.save_config()

    def get_is_first_run(self):
        # 读取是否为首次运行的标志位。
        return bool(self.config.get("is_first_run", True))

    def set_is_first_run(self, is_first_run):
        # 更新首次运行标志位并写入 settings.json。
        self.config["is_first_run"] = bool(is_first_run)
        self.save_config()

    def get_agreement_version(self):
        # 读取用户已确认的协议版本号。
        return self.config.get("agreement_version", "")

    def set_agreement_version(self, version):
        # 更新用户已确认的协议版本号并写入 settings.json。
        self.config["agreement_version"] = version
        self.save_config()

    def get_config_dir(self):
        # 读取当前配置文件所在目录路径。
        return str(DOCS_DIR)

    def get_custom_config_dir(self):
        # 读取用户自定义的配置文件目录路径（存储在配置中的值）。
        return self.config.get("custom_config_dir", "")

    def set_custom_config_dir(self, path):
        # 更新用户自定义的配置文件目录路径并写入 settings.json。
        # 注意：此设置需要重启应用后才能生效。
        self.config["custom_config_dir"] = path
        self.save_config()

    def get_pending_dir(self):
        # 讀取自定義的待解壓區目錄路徑。
        return self.config.get("pending_dir", "")

    def set_pending_dir(self, path):
        # 更新待解壓區目錄路徑並寫入 settings.json。
        self.config["pending_dir"] = path
        self.save_config()

    def get_library_dir(self):
        # 讀取自定義的語音包庫目錄路徑。
        return self.config.get("library_dir", "")

    def set_library_dir(self, path):
        # 更新語音包庫目錄路徑並寫入 settings.json。
        self.config["library_dir"] = path
        self.save_config()
