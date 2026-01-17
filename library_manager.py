# -*- coding: utf-8 -*-
# library_manager.py - 资源管理与智能分析 (V2.1)
import os
import sys
import shutil
import zipfile
import json
import re
import platform
import subprocess
from collections import Counter
from pathlib import Path

# 定义标准文件夹名称
DIR_PENDING = "WT待解压区"
DIR_LIBRARY = "WT语音包库"

class LibraryManager:
    def __init__(self, log_callback):
        self.log = log_callback
        
        # 使用用户文档文件夹 Aimer_WT 作为根目录
        self.root_dir = Path.home() / "Documents" / "Aimer_WT"
        
        # 也可以保留原逻辑作为备份，或者直接覆盖
        # if getattr(sys, 'frozen', False):
        #     application_path = Path(sys.executable).parent
        # else:
        #     application_path = Path(__file__).parent
            
        self.pending_dir = self.root_dir / DIR_PENDING
        self.library_dir = self.root_dir / DIR_LIBRARY
        
        self._ensure_dirs()

    def _ensure_dirs(self):
        if not self.pending_dir.exists():
            self.pending_dir.mkdir(parents=True)
        if not self.library_dir.exists():
            self.library_dir.mkdir(parents=True)

    def _open_folder_cross_platform(self, path):
        """Cross-platform folder opener"""
        try:
            path = str(path)
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", path])
            else:  # Linux
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"无法打开文件夹: {e}", "ERROR")

    def open_pending_folder(self):
        self._open_folder_cross_platform(self.pending_dir)

    def open_library_folder(self):
        self._open_folder_cross_platform(self.library_dir)

    def scan_library(self):
        """扫描已解压的语音包列表"""
        mods = []
        if self.library_dir.exists():
            for item in self.library_dir.iterdir():
                if item.is_dir():
                    mods.append(item.name)
        return mods

    def scan_pending(self):
        """扫描待解压的 Zip 文件"""
        zips = []
        if self.pending_dir.exists():
            for item in self.pending_dir.iterdir():
                if item.suffix.lower() == ".zip":
                    zips.append(item)
        return zips

    # --- 新增：获取语音包详细信息 ---
    def get_mod_details(self, mod_name):
        """读取语音包的所有元数据"""
        import time
        mod_dir = self.library_dir / mod_name
        info_file = mod_dir / "info.json"
        
        # 1. 默认数据
        # 尝试获取文件夹修改时间作为默认日期
        try:
            mtime = os.path.getmtime(mod_dir)
            default_date = time.strftime("%Y-%m-%d", time.localtime(mtime))
        except:
            default_date = "2026-01-07"

        details = {
            "title": mod_name,
            "author": "未知作者",
            "version": "1.0",
            "date": default_date,
            "note": "无详细介绍",
            "link_bilibili": "",
            "link_wtlive": "",
            "link_video": "",
            "tags": [],      # 存储标签列表 ["tank", "radio"]
            "language": [],  # 存储语言列表 ["中", "美"]
            "size_str": "0 MB",
            "cover_path": None,
            "capabilities": {} # 兼容前端旧逻辑
        }

        # 2. 读取 info.json
        if info_file.exists():
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 安全更新
                    for key in ["title", "author", "version", "date", "note", "link_bilibili", "link_wtlive", "link_video", "tags", "language"]:
                        if key in data: details[key] = data[key]
            except Exception as e:
                print(f"读取 info.json 失败: {e}")

        # 3. 智能检测 (Fallback Logic)
        # 仅检测 Tags (功能标签)，语言完全听作者的
        if not details["tags"]:
            details["tags"] = self._detect_smart_tags(mod_dir)
            
        # 如果作者没写语言，则显示"未识别"
        if not details["language"]:
            details["language"] = ["未识别"]

        # 4. 同步 tags 到 capabilities (兼容前端 UI)
        # 映射关系: 陆战->tank, 无线电->radio, 空战->air
        cap_map = {
            "tank": "tank", "陆战": "tank", "ground": "tank",
            "air": "air", "空战": "air", "aircraft": "air",
            "naval": "naval", "海战": "naval",
            "radio": "radio", "无线电": "radio",
            "status": "status", "局势播报": "status"
        }
        for t in details["tags"]:
            if t in cap_map:
                details["capabilities"][cap_map[t]] = True
            elif t in ["tank", "air", "naval", "radio", "status"]:
                 details["capabilities"][t] = True

        # 5. 计算大小
        details["size_str"] = self._get_dir_size_str(mod_dir)

        # 6. 检测图片
        for img_ext in [".png", ".jpg", ".jpeg"]:
            img_path = mod_dir / f"cover{img_ext}"
            if img_path.exists():
                details["cover_path"] = str(img_path)
                break
        
        # 7. 文件夹详情
        details["folders"] = self._detect_mod_folders(mod_dir)
        
        # [新增] Aimer 专属测试彩蛋
        if mod_name == "Aimer":
            details.update({
                "author": "Aimer",
                "size_str": "520 MB",
                "version": "v2.53",
                "note": "这是一个用于测试 UI 布局的专用模组。它包含了超长的文字介绍来测试省略号功能是否正常，鼠标悬停时应该能看到完整内容。同时它点亮了所有图标以检测布局美感。",
                "link_bilibili": "https://www.bilibili.com",
                "link_wtlive": "https://live.warthunder.com",
                "link_video": "https://www.youtube.com",
                "folders": ["陆战语音", "空战语音", "超长文件夹名称测试", "海战", "无线电"],
                "language": ["中", "美", "俄"],
                "capabilities": {"tank": True, "air": True, "naval": True, "radio": True}
            })
        
        return details

    def _detect_smart_tags(self, mod_dir):
        """
        智能检测标签 (仅 Tags)
        规则:
        陆战: _crew_dialogs_ground_xxx.assets.bank
        无线电: _crew_dialogs_common_xxx.assets.bank
        空战: aircraft_guns.assets.bank 或 aircraft_gui.assets.bank
        """
        detected_tags = set()
        
        try:
            # 遍历所有 .bank 文件
            for f in mod_dir.rglob("*.bank"):
                if not f.is_file(): continue
                name = f.name.lower()
                
                # 1. 陆战
                # 匹配: _crew_dialogs_ground_cn.assets.bank
                m_ground = re.match(r'(_)?crew_dialogs_ground_([a-z0-9]+)\.assets\.bank', name)
                if m_ground:
                    detected_tags.add("tank")
                    continue
                # 兼容无后缀
                if "crew_dialogs_ground.assets.bank" in name:
                    detected_tags.add("tank")
                    continue
                    
                # 2. 无线电
                m_radio = re.match(r'(_)?crew_dialogs_common_([a-z0-9]+)\.assets\.bank', name)
                if m_radio:
                    detected_tags.add("radio")
                    continue
                if "crew_dialogs_common.assets.bank" in name:
                    detected_tags.add("radio")
                    continue
                    
                # 3. 空战
                if name == "aircraft_guns.assets.bank" or name == "aircraft_gui.assets.bank":
                    detected_tags.add("air")
                    continue
                    
        except Exception as e:
            print(f"智能检测出错: {e}")
            
        return list(detected_tags)

    def _map_lang_code(self, code):
        """映射语言代码到 UI 显示字符"""
        mapping = {
            "zh": "中", "cn": "中", "chs": "中",
            "en": "美", "us": "美", "uk": "美",
            "ru": "俄",
            "de": "德",
            "jp": "日", "ja": "日",
            "fr": "法",
            "it": "意",
            "se": "瑞",
            "il": "以"
        }
        return mapping.get(code, code.upper())


    def _detect_mod_folders(self, mod_dir):
        """
        递归扫描 .bank 文件，返回它们所在的上一级文件夹名称（相对路径）
        去除重复，并按名称排序
        """
        folders_map = {}
        try:
            # 查找所有 .bank 文件 (不区分大小写，但 glob 通常区分，所以写两次或用正则)
            # Windows 下 glob 通常不区分大小写，但为了保险
            all_files = list(mod_dir.rglob("*.bank")) + list(mod_dir.rglob("*.BANK"))
            
            for f in all_files:
                if f.is_file():
                    parent = f.parent
                    try:
                        # 获取相对于 mod_dir 的路径
                        rel_path = parent.relative_to(mod_dir)
                        path_str = str(rel_path).replace("\\", "/") # 统一使用正斜杠
                        
                        if path_str not in folders_map:
                            folder_type = self._determine_folder_type(parent)
                            folders_map[path_str] = {
                                "path": path_str if path_str != "." else "根目录",
                                "type": folder_type,
                                "label": path_str if path_str != "." else "根目录"
                            }
                    except ValueError:
                        continue
        except Exception as e:
            print(f"扫描文件夹出错: {e}")
        
        return sorted(list(folders_map.values()), key=lambda x: x["path"])

    def _determine_folder_type(self, folder_path):
        """
        根据文件夹内的文件名判断文件夹类型
        优先级: 陆战 > 无线电 > 空战 > 默认
        """
        try:
            # 获取文件夹下所有文件名
            filenames = [f.name for f in folder_path.iterdir() if f.is_file()]
            
            # 1. 陆战语音: _crew_dialogs_ground_<国家缩写>.assets.bank
            # 兼容: crew_dialogs_ground.assets.bank (无前缀/后缀)
            for name in filenames:
                if re.match(r'(_)?crew_dialogs_ground.*\.assets\.bank', name, re.IGNORECASE):
                    return "ground"
            
            # 2. 无线电语音: _crew_dialogs_common_<国家缩写>.assets.bank
            # 兼容: crew_dialogs_common.assets.bank
            for name in filenames:
                if re.match(r'(_)?crew_dialogs_common.*\.assets\.bank', name, re.IGNORECASE):
                    return "radio"
            
            # 3. 空战音效: aircraft_guns.assets.bank 或 aircraft_gui.assets.bank
            for name in filenames:
                if re.match(r'aircraft_guns\.assets\.bank', name, re.IGNORECASE) or \
                   re.match(r'aircraft_gui\.assets\.bank', name, re.IGNORECASE):
                    return "aircraft"
            
            return "folder"
            
        except Exception:
            return "folder"

    def _detect_mod_capabilities(self, mod_dir):
        """[已废弃] 旧的检测逻辑"""
        return {}

    def _get_dir_size_str(self, path):
        """计算文件夹大小并格式化（优化版本）"""
        total_size = 0
        try:
            # 优化：限制遍历深度和文件数量，避免大目录卡死
            file_count = 0
            max_files = 5000  # 最多统计5000个文件
            max_depth = 10    # 最多遍历10层深度
            
            for dirpath, dirnames, filenames in os.walk(path):
                # 检查深度
                rel_path = os.path.relpath(dirpath, path)
                depth = rel_path.count(os.sep) if rel_path != '.' else 0
                if depth > max_depth:
                    continue
                
                for f in filenames:
                    if file_count >= max_files:
                        # 达到上限，返回估算值
                        mb_size = total_size / (1024 * 1024)
                        return f"~{int(mb_size)} MB+"
                    
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        try:
                            total_size += os.path.getsize(fp)
                        except:
                            pass
                    file_count += 1
        except Exception as e:
            print(f"计算目录大小失败: {e}")
            return "未知"
        
        mb_size = total_size / (1024 * 1024)
        if mb_size < 1:
            return "<1 MB"
        return f"{int(mb_size)} MB"

    def _detect_mod_capabilities(self, mod_dir):
        """
        [已废弃] 旧的检测逻辑，保留空函数防止报错
        """
        return {}

    def _is_safe_path(self, path, base_dir):
        """
        [安全检查] 确保 path 在 base_dir 目录下，防止路径穿越或误删
        [最高安全规则] 系统盘防误删保护 (加强版 - 跨平台)
        """
        try:
            abs_path = Path(path).resolve()
            abs_base = Path(base_dir).resolve()
            path_str = str(abs_path).lower()

            # 1. 绝对禁止删除系统根目录或关键系统目录
            forbidden_roots = [
                "c:\\", "c:/", "c:\\windows", "c:\\program files", "c:\\program files (x86)", "c:\\users",
                "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib64", "/media", "/mnt", "/opt",
                "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/tmp", "/usr", "/var"
            ]
            if path_str in forbidden_roots:
                return False

            # 2. 如果路径在 C 盘(Windows)，必须在 base_dir 白名单内
            if platform.system() == "Windows" and abs_path.drive.lower() == "c:":
                if not str(abs_path).startswith(str(abs_base)):
                    return False
            
            # 3. Linux/Mac 基础保护 (不允许操作 / 根目录)
            if platform.system() != "Windows":
                 if str(abs_path) == "/":
                     return False

            # 4. 基础检查：是否在 base_dir 内部
            # 兼容大小写不敏感系统(Windows/macOS) 和 敏感系统(Linux)
            if platform.system() == "Windows":
                 return str(abs_path).lower().startswith(str(abs_base).lower())
            else:
                 return str(abs_path).startswith(str(abs_base))
        except:
            return False

    def unzip_single_zip(self, zip_path, progress_callback=None):
        """导入单个 Zip 文件 (新功能)"""
        # 确保是 Path 对象
        zip_path = Path(zip_path)
        
        if not zip_path.exists():
            self.log(f"文件不存在: {zip_path}", "ERROR")
            return

        # [P2 修复] 磁盘空间检查
        try:
            zip_size = os.path.getsize(zip_path)
            # 估算解压后大小 (通常是压缩包的 2-3 倍，这里保守估计 3 倍)
            estimated_size = zip_size * 3
            # 需要至少 2 倍的估算空间作为安全余量 (解压过程可能产生临时文件)
            required_space = estimated_size * 2
            
            target_drive = Path(self.library_dir).anchor # 获取盘符 (如 C:\)
            if not target_drive: target_drive = self.library_dir
            
            import shutil
            total, used, free = shutil.disk_usage(target_drive)
            
            if free < required_space:
                free_mb = free / (1024 * 1024)
                required_mb = required_space / (1024 * 1024)
                self.log(f"磁盘空间不足! 可用: {free_mb:.0f}MB, 需要: {required_mb:.0f}MB", "ERROR")
                raise Exception(f"磁盘空间不足 (需 {required_mb:.0f}MB)")
                
        except Exception as e:
            if "磁盘空间不足" in str(e):
                raise e # 重新抛出给上层处理
            self.log(f"磁盘空间检查失败 (跳过检查): {e}", "WARN")

        mod_name = zip_path.stem
        target_dir = self.library_dir / mod_name
        
        if target_dir.exists():
            self.log(f"[SKIPPED] 跳过重复: {mod_name} (库中已存在)", "WARN")
            self.log("提示: 如果想重新导入，请先删除库中的同名文件夹。", "INFO")
            if progress_callback: progress_callback(100, "跳过重复文件")
            return
        
        try:
            target_dir.mkdir()
            self.log(f"[UNZIP] 正在导入: {zip_path.name}", "UNZIP")
            
            self._extract_zip_safely(zip_path, target_dir, progress_callback, 0, 100)
            self.log(f"[SUCCESS] 导入成功: {mod_name}", "SUCCESS")
        except Exception as e:
            self.log(f"[ERROR] 导入失败: {e}", "ERROR")
            if target_dir.exists():
                try: shutil.rmtree(target_dir)
                except: pass

    def unzip_zips_to_library(self, progress_callback=None):
        """解压 Zip 到语音包库（优化版本，添加进度反馈）"""
        zips = self.scan_pending()
        if not zips:
            self.log("待解压区没有 ZIP 文件。", "WARN")
            if progress_callback: progress_callback(100, "没有文件")
            return

        total = len(zips)
        self.log(f"发现 {total} 个待解压文件...", "INFO")
        
        success_count = 0
        skipped_count = 0
        
        for idx, zip_file in enumerate(zips):
            try:
                mod_name = zip_file.stem
                target_dir = self.library_dir / mod_name
                
                # 计算总体进度区间
                base_progress = (idx / total) * 100
                share_progress = (1 / total) * 100
                
                if target_dir.exists():
                    self.log(f"[SKIPPED] 跳过重复: {mod_name}", "WARN")
                    skipped_count += 1
                    if progress_callback:
                        progress_callback(base_progress + share_progress, f"跳过: {mod_name}")
                    continue
                
                target_dir.mkdir()
                self.log(f"[UNZIP] 正在解压 ({idx + 1}/{total}): {zip_file.name}", "UNZIP")
                
                # 优化：分批解压，避免大文件阻塞
                self._extract_zip_safely(zip_file, target_dir, progress_callback, base_progress, share_progress)
                
                success_count += 1
                self.log(f"[SUCCESS] 解压成功: {mod_name}", "SUCCESS")
                    
            except Exception as e:
                self.log(f"[ERROR] 解压 {zip_file.name} 失败: {e}", "ERROR")

        self.log(f"[INFO] 解压完成: 成功 {success_count}, 跳过 {skipped_count}", "INFO")
        if progress_callback: progress_callback(100, "全部完成")

    def _extract_zip_safely(self, zip_path, target_dir, progress_callback=None, base_progress=0, share_progress=100):
        """安全解压 ZIP，优化大文件处理"""
        import time
        target_root = Path(target_dir).resolve()
        with zipfile.ZipFile(zip_path, 'r') as zf:
            file_list = zf.infolist()
            total_files = len(file_list)
            last_update = 0.0
            extracted_bytes = 0
            total_bytes = 0
            if progress_callback:
                try:
                    progress_callback(int(base_progress), f"开始解压: {Path(zip_path).name}")
                except Exception:
                    pass
            if total_files > 0:
                for m in file_list:
                    if m.is_dir():
                        continue
                    name = m.filename
                    if "__MACOSX" in name or "desktop.ini" in name:
                        continue
                    try:
                        total_bytes += int(getattr(m, "file_size", 0) or 0)
                    except Exception:
                        pass
            
            for idx, member in enumerate(file_list):
                if idx % 50 == 0:
                    time.sleep(0.001)
                
                try:
                    filename = member.filename.encode('cp437').decode('utf-8')
                except:
                    try:
                        filename = member.filename.encode('cp437').decode('gbk')
                    except:
                        filename = member.filename

                if "__MACOSX" in filename or "desktop.ini" in filename: continue
                
                now = time.monotonic()
                should_push = (idx == 0) or (idx % 10 == 0) or (idx == total_files - 1)
                if progress_callback and total_files > 0 and should_push and (now - last_update) >= 0.05:
                    ratio = idx / total_files
                    current_percent = base_progress + ratio * share_progress
                    fname = filename
                    if len(fname) > 25:
                        fname = "..." + fname[-25:]
                    try:
                        progress_callback(int(current_percent), f"解压中: {fname}")
                    except Exception:
                        pass
                    last_update = now
                
                # [安全修复] 路径穿越检查
                # 如果 filename 包含 ".."，resolve 后可能会跑到 target_dir 外面
                # 这里我们先拼合，再检查
                full_target_path = (target_dir / filename).resolve()
                try:
                    is_inside = os.path.commonpath([str(full_target_path), str(target_root)]) == str(target_root)
                except Exception:
                    is_inside = False
                if not is_inside:
                     self.log(f"[WARN] 拦截恶意路径穿越文件: {filename}", "WARN")
                     continue

                target_path = target_dir / filename
                if member.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    # 分块复制大文件
                    with zf.open(member) as source, open(target_path, "wb") as target:
                        chunk_size = 8192  # 8KB chunks
                        while True:
                            chunk = source.read(chunk_size)
                            if not chunk:
                                break
                            target.write(chunk)
                            if total_bytes > 0:
                                extracted_bytes += len(chunk)
                            now = time.monotonic()
                            if progress_callback and total_files > 0 and (now - last_update) >= 0.2:
                                if total_bytes > 0:
                                    ratio = extracted_bytes / total_bytes
                                else:
                                    ratio = idx / total_files
                                current_percent = base_progress + ratio * share_progress
                                fname = filename
                                if len(fname) > 25:
                                    fname = "..." + fname[-25:]
                                progress_callback(int(current_percent), f"解压中: {fname}")
                                last_update = now
            
            if progress_callback:
                progress_callback(int(base_progress + share_progress), "解压完成")
