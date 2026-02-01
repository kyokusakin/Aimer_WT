# -*- coding: utf-8 -*-
# 将“文件名 -> 所属语音包”与“语音包 -> 安装文件名列表”持久化到游戏目录，供安装前冲突检查与安装后记录使用。
import json
from pathlib import Path
from datetime import datetime
from logger import get_logger

log = get_logger(__name__)

class ManifestManager:
    # 管理语音包安装清单文件，提供加载、保存、冲突检测与记录维护。
    def __init__(self, game_root):
        # 绑定游戏根目录并加载清单文件到内存。
        self.game_root = Path(game_root)
        self.manifest_file = self.game_root / "sound" / "mod" / ".manifest.json"
        self.manifest = self._load_manifest()
    
    def _load_manifest(self):
        # 从 manifest_file 读取清单数据到内存。
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {"installed_mods": {}, "file_map": {}}
        return {"installed_mods": {}, "file_map": {}}
    
    def _save_manifest(self):
        # 将内存中的 self.manifest 持久化写入 manifest_file。
        try:
            self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.manifest_file, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning(f"无法保存清单文件: {e}")
    
    def check_conflicts(self, mod_name, files_to_install):
        # 对待安装文件名列表进行所有权查询，返回与当前安装目标不一致的占用记录。
        conflicts = []
        file_map = self.manifest.get("file_map", {})
        
        for file_name in files_to_install:
            if file_name in file_map:
                existing_mod = file_map[file_name]
                if existing_mod != mod_name:
                    conflicts.append({
                        "file": file_name,
                        "existing_mod": existing_mod,
                        "new_mod": mod_name
                    })
        return conflicts
    
    def record_installation(self, mod_name, installed_files):
        # 将某个语音包的安装结果写入清单（安装文件名列表与文件所有权映射）。
        self.manifest["installed_mods"][mod_name] = {
            "files": installed_files,
            "install_time": datetime.now().isoformat()
        }
        
        # 更新文件名所有权映射（file_name -> mod_name）
        for file_name in installed_files:
            self.manifest["file_map"][file_name] = mod_name
        
        self._save_manifest()
    
    def remove_mod_record(self, mod_name):
        # 按语音包维度移除清单记录，用于卸载或还原流程中的记录清理。
        if mod_name in self.manifest["installed_mods"]:
            files = self.manifest["installed_mods"][mod_name].get("files", [])
            
            # 仅在所有权仍指向当前语音包时，移除 file_map 映射
            for file_name in files:
                if self.manifest["file_map"].get(file_name) == mod_name:
                    del self.manifest["file_map"][file_name]
            
            del self.manifest["installed_mods"][mod_name]
            self._save_manifest()
            
    def clear_manifest(self):
        # 清空内存中的清单结构，并尝试删除清单文件。
        self.manifest = {"installed_mods": {}, "file_map": {}}
        if self.manifest_file.exists():
            try:
                self.manifest_file.unlink()
            except:
                pass
