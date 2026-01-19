# -*- coding: utf-8 -*-
"""
清单管理器
用于追踪已安装的 Mod 文件，防止文件冲突
"""

import json
import os
from pathlib import Path
from datetime import datetime
from logger import get_logger

log = get_logger(__name__)

class ManifestManager:
    """语音包安装清单管理器"""
    
    def __init__(self, game_root):
        self.game_root = Path(game_root)
        self.manifest_file = self.game_root / "sound" / "mod" / ".manifest.json"
        self.manifest = self._load_manifest()
    
    def _load_manifest(self):
        """加载清单文件"""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                # 如果文件损坏，返回空清单
                return {"installed_mods": {}, "file_map": {}}
        return {"installed_mods": {}, "file_map": {}}
    
    def _save_manifest(self):
        """保存清单文件"""
        try:
            # 确保父目录存在
            self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.manifest_file, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning(f"无法保存清单文件: {e}")
    
    def check_conflicts(self, mod_name, files_to_install):
        """
        检查文件冲突
        
        Args:
            mod_name: 准备安装的 Mod 名称
            files_to_install: 准备安装的文件名列表
            
        Returns:
            list: 冲突信息列表 [{"file": "x.bank", "existing_mod": "old_mod", "new_mod": "new_mod"}]
        """
        conflicts = []
        file_map = self.manifest.get("file_map", {})
        
        for file_name in files_to_install:
            if file_name in file_map:
                existing_mod = file_map[file_name]
                # 如果是同一个 Mod 的重复安装，不算冲突
                if existing_mod != mod_name:
                    conflicts.append({
                        "file": file_name,
                        "existing_mod": existing_mod,
                        "new_mod": mod_name
                    })
        return conflicts
    
    def record_installation(self, mod_name, installed_files):
        """
        记录安装信息
        
        Args:
            mod_name: Mod 名称
            installed_files: 已安装的文件名列表
        """
        # 1. 更新已安装 Mod 列表
        self.manifest["installed_mods"][mod_name] = {
            "files": installed_files,
            "install_time": datetime.now().isoformat()
        }
        
        # 2. 更新文件映射 (File -> Mod)
        # 先清除旧映射中属于该 Mod 的记录 (如果是覆盖安装)
        # 但这里直接覆盖 file_map 即可，因为我们要声明所有权
        for file_name in installed_files:
            self.manifest["file_map"][file_name] = mod_name
        
        self._save_manifest()
    
    def remove_mod_record(self, mod_name):
        """
        移除语音包记录 (用于卸载或还原)
        """
        if mod_name in self.manifest["installed_mods"]:
            # 获取该 Mod 拥有的文件
            files = self.manifest["installed_mods"][mod_name].get("files", [])
            
            # 从文件映射中移除这些文件
            # 注意：如果文件被其他 Mod 覆盖了（理论上我们应该防止这种情况），
            # 那么 file_map[file] 可能已经是别人的名字了，这时候不能删
            for file_name in files:
                if self.manifest["file_map"].get(file_name) == mod_name:
                    del self.manifest["file_map"][file_name]
            
            # 移除 Mod 记录
            del self.manifest["installed_mods"][mod_name]
            self._save_manifest()
            
    def clear_manifest(self):
        """清空清单 (用于还原纯净模式)"""
        self.manifest = {"installed_mods": {}, "file_map": {}}
        # 也可以直接删除文件
        if self.manifest_file.exists():
            try:
                self.manifest_file.unlink()
            except:
                pass
