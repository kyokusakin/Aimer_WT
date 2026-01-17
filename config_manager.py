# -*- coding: utf-8 -*-
# config_manager.py - 配置管理
import json
import os
from pathlib import Path

# 使用用户文档文件夹 Aimer_WT/settings.json
DOCS_DIR = Path.home() / "Documents" / "Aimer_WT"
CONFIG_FILE = DOCS_DIR / "settings.json"

class ConfigManager:
    def __init__(self):
        # 默认配置
        self.config = {
            "game_path": "",
            "theme_mode": "Light",  # 默认白色
            "is_first_run": True,   # [新增] 是否是第一次运行
            "agreement_version": "" # [新增] 用户同意的协议版本
        }
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config.update(data)
            except:
                pass

    def save_config(self):
        try:
            # 确保目录存在
            if not DOCS_DIR.exists():
                DOCS_DIR.mkdir(parents=True, exist_ok=True)
                
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except:
            pass

    def get_game_path(self):
        return self.config.get("game_path", "")

    def set_game_path(self, path):
        self.config["game_path"] = path
        self.save_config()

    # --- 新增主题相关方法 ---
    def get_theme_mode(self):
        return self.config.get("theme_mode", "Dark")

    def set_theme_mode(self, mode):
        self.config["theme_mode"] = mode
        self.save_config()

    def get_active_theme(self):
        return self.config.get("active_theme", "default.json")

    def set_active_theme(self, filename):
        self.config["active_theme"] = filename
        self.save_config()

    # --- 新增：记录当前安装的语音包 ---
    def get_current_mod(self):
        return self.config.get("current_mod", "")

    def set_current_mod(self, mod_id):
        self.config["current_mod"] = mod_id
        self.save_config()

    def get_is_first_run(self):
        return bool(self.config.get("is_first_run", True))

    def set_is_first_run(self, is_first_run):
        self.config["is_first_run"] = bool(is_first_run)
        self.save_config()

    def get_agreement_version(self):
        return self.config.get("agreement_version", "")

    def set_agreement_version(self, version):
        self.config["agreement_version"] = version
        self.save_config()
