# -*- coding: utf-8 -*-
# main.py - PyWebview 启动入口与 API 桥接层
import os
import sys
import threading
import time
import json
import random
import itertools
import webview
import base64
from pathlib import Path

AGREEMENT_VERSION = "2026-01-10"

# 引入之前的核心逻辑 (确保这三个文件在同级目录)
from core_logic import CoreService
from config_manager import ConfigManager
from library_manager import LibraryManager
from logger import setup_logger  # [P1 修复] 引入日志管理模块

# 解决 PyInstaller 打包后的路径问题
if getattr(sys, 'frozen', False):
    # [打包修复] 使用 _MEIPASS 获取临时目录中的资源
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

WEB_DIR = BASE_DIR / "web"

class AppApi:
    """
    这是 Python 和 Web 前端通信的桥梁。
    JS 可以通过 pywebview.api.method_name() 调用这里的方法。
    """
    def __init__(self):
        # [P1 修复] 引入线程锁保护并发操作
        self._lock = threading.Lock()
        
        # [P1 修复] 初始化持久化日志记录器
        self._logger = setup_logger()
        
        # [关键修复] 将 window 改为 _window。
        # 加下划线表示私有变量，pywebview 就不会尝试去扫描和序列化整个窗口对象，
        # 从而避免了 "window.native... maximum recursion depth" 错误。
        self._window = None
        
        # [关键修复] 同理，将管理器对象也改为私有，防止扫描 Path 对象导致递归溢出
        self._cfg_mgr = ConfigManager()
        self._lib_mgr = LibraryManager(self.log_from_backend)
        self._logic = CoreService()
        self._logic.set_callbacks(self.log_from_backend)
        
        self._search_running = False
        self._is_busy = False

    def set_window(self, window):
        self._window = window

    # --- 日志回调 ---
    def log_from_backend(self, message, level="INFO"):
        """核心逻辑产生的日志，通过这里推送到前端"""
        # [P1 修复] 同时记录到文件
        try:
            log_level_map = {
                "INFO": self._logger.info,
                "WARN": self._logger.warning,
                "ERROR": self._logger.error,
                "SUCCESS": self._logger.info,
                "SYS": self._logger.debug
            }
            log_func = log_level_map.get(level, self._logger.info)
            # 如果 message 已经包含了时间戳前缀，记录时可以不用去管，
            # 或者为了日志文件的整洁，可以尝试剥离前缀（这里暂且直接记录）
            log_func(f"[{level}] {message}")
        except Exception as e:
            print(f"日志文件写入失败: {e}")

        if self._window:
            try:
                # 兼容 LibraryManager 的多参数调用 (message, level)
                # 如果是 CoreService 调用的，message 已经包含了时间戳和级别，level 默认为 INFO
                # 如果是 LibraryManager 调用的，message 是纯文本，level 是显式传入的
                if level != "INFO" and f"[{level}]" not in message:
                    timestamp = time.strftime("%H:%M:%S")
                    message = f"[{timestamp}] [{level}] {message}"

                safe_msg = message.replace("\r", "").replace("\n", "<br>")
                msg_js = json.dumps(safe_msg, ensure_ascii=False)
                # 在主线程执行 JS
                webview.settings['ALLOW_DOWNLOADS'] = True
                self._window.evaluate_js(f"app.appendLog({msg_js})")
            except Exception as e:
                print(f"日志推送失败: {e}")

    # --- 窗口控制 ---
    def toggle_topmost(self, is_top):
        # [关键修复] 解决点击置顶按钮导致程序"未响应"/卡死的问题
        # 原因：直接在 API 调用中修改窗口属性会导致 JS 等待 Python，Python 等待 UI 线程的死锁。
        # 解决方法：开启一个独立线程去修改属性，让 API 立刻返回给前端。
        def _update_topmost():
            if self._window:
                try:
                    self._window.on_top = is_top
                except Exception as e:
                    print(f"置顶设置失败: {e}")

        t = threading.Thread(target=_update_topmost)
        t.daemon = True
        t.start()
        
        return True

    def drag_window(self):
        # PyWebview 某些模式支持拖拽，API预留
        pass

    # --- 新增窗口控制 API ---
    def minimize_window(self):
        """最小化窗口"""
        if self._window:
            self._window.minimize()

    def close_window(self):
        """关闭窗口"""
        if self._window:
            self._window.destroy()

    # --- 核心业务 API (供 JS 调用) ---

    def init_app_state(self):
        """初始化应用状态，前端加载完后调用"""
        path = self._cfg_mgr.get_game_path()
        theme = self._cfg_mgr.get_theme_mode()
        
        # 验证路径
        is_valid = False
        if path:
            is_valid, _ = self._logic.validate_game_path(path)
            if is_valid:
                self.log_from_backend(f"[INIT] 已加载配置路径: {path}")
            else:
                self.log_from_backend(f"[WARN] 配置路径失效: {path}")

        # 返回初始化数据给前端
        return {
            "game_path": path,
            "path_valid": is_valid,
            "theme": theme,
            "active_theme": self._cfg_mgr.get_active_theme(),
            "installed_mods": self._logic.get_installed_mods()  # 新增
        }

    def save_theme_selection(self, filename):
        self._cfg_mgr.set_active_theme(filename)

    def set_theme(self, mode):
        self._cfg_mgr.set_theme_mode(mode)

    def browse_folder(self):
        """打开文件夹选择框"""
        # 注意：这里调用的是 self._window
        folder = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if folder and len(folder) > 0:
            path = folder[0].replace(os.sep, '/')
            valid, msg = self._logic.validate_game_path(path)
            if valid:
                self._cfg_mgr.set_game_path(path)
                self.log_from_backend(f"[INFO] 手动加载路径: {path}")
                return {"valid": True, "path": path}
            else:
                self.log_from_backend(f"[ERROR] 路径无效: {msg}")
                return {"valid": False, "path": path, "msg": msg}
        return None

    def start_auto_search(self):
        """执行自动搜索，优化性能版本"""
        if self._search_running: return
        self._search_running = True
        
        def _run():
            self.log_from_backend("[SYS] 检索引擎初始化...")
            time.sleep(0.3)
            
            # 启动搜索
            found_path = self._logic.auto_detect_game_path()
            
            # 优化：减少 evaluate_js 调用频率，使用批量更新
            spinner = itertools.cycle(['|', '/', '—', '\\'])
            progress = 0
            update_interval = 0.15  # 每150ms更新一次UI
            last_update = time.time()
            
            while progress < 100:
                step = random.randint(3, 8)
                if 30 < progress < 50:
                    time.sleep(random.uniform(0.15, 0.25))
                    step = random.randint(8, 15)
                elif 80 < progress < 90:
                    time.sleep(random.uniform(0.25, 0.45))
                    step = 2
                else:
                    time.sleep(0.08)
                
                progress += step
                if progress > 100: progress = 100
                
                # 只在达到更新间隔时调用 evaluate_js
                current_time = time.time()
                if current_time - last_update >= update_interval or progress >= 100:
                    char = next(spinner)
                    # 注意：这里调用的是 self._window
                    msg_js = json.dumps(f"[扫描] 正在检索存储设备... [{char}] {progress}%", ensure_ascii=False)
                    self._window.evaluate_js(f"app.updateSearchLog({msg_js})")
                    last_update = current_time

            time.sleep(0.3)
            
            if found_path:
                self._cfg_mgr.set_game_path(found_path)
                self._logic.validate_game_path(found_path)
                self.log_from_backend("[SUCCESS] 自动搜索成功，路径已保存。")
                # 通知前端更新 UI
                path_js = json.dumps(found_path.replace(os.sep, '/'), ensure_ascii=False)
                self._window.evaluate_js(f"app.onSearchSuccess({path_js})")
            else:
                self.log_from_backend("[ERROR] 深度扫描未发现游戏客户端。")
                self._window.evaluate_js("app.onSearchFail()")
            
            self._search_running = False

        t = threading.Thread(target=_run)
        t.daemon = True
        t.start()

    def get_library_list(self):
        """获取语音包列表详情 (Base64 + 默认封面 终极版)"""
        mods = self._lib_mgr.scan_library()
        result = []
        
        # [新增] 定义默认封面的路径
        # 确保你的 assets 文件夹里真的有 card_image.png 这个文件！
        default_cover_path = WEB_DIR / "assets" / "card_image.png"

        for mod in mods:
            details = self._lib_mgr.get_mod_details(mod)
            
            # 1. 获取作者提供的封面路径
            cover_path = details.get("cover_path")
            details["cover_url"] = ""
            
            # [核心修改] 封面逻辑判断
            # 如果作者没提供图片 (cover_path是None) 或者提供的路径不存在
            if not cover_path or not os.path.exists(cover_path):
                # 就使用我们的默认封面
                cover_path = str(default_cover_path)
            
            # 2. 开始转码 (无论是作者的图，还是默认图，都走这套逻辑)
            if cover_path and os.path.exists(cover_path):
                try:
                    # 获取后缀名
                    ext = os.path.splitext(cover_path)[1].lower().replace('.', '')
                    if ext == 'jpg': ext = 'jpeg'
                    
                    with open(cover_path, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode('utf-8')
                        details["cover_url"] = f"data:image/{ext};base64,{b64_data}"
                except Exception as e:
                    print(f"图片转码失败: {e}")
            
            # 补充 ID
            details["id"] = mod
            result.append(details)
            
        return result

    def open_folder(self, folder_type):
        """只允许打开资源相关的文件夹"""
        if folder_type == "pending":
            self._lib_mgr.open_pending_folder()
        elif folder_type == "library":
            self._lib_mgr.open_library_folder()
        elif folder_type == "game":
            path = self._cfg_mgr.get_game_path()
            if path and os.path.exists(path):
                try:
                    os.startfile(path)
                except Exception as e:
                    self.log_from_backend(f"[ERROR] 打开游戏目录失败: {e}")
            else:
                self.log_from_backend("[WARN] 游戏路径无效或未设置")
        
        # [已删除] settings 和 themes 的打开逻辑
        # 即使前端恶意调用，后端也不予响应，保证安全

    # --- 辅助方法 ---
    def update_loading_ui(self, progress, message):
        """推送加载条更新到前端 (带平滑处理)"""
        if self._window:
            try:
                safe_msg = str(message).replace("\r", " ").replace("\n", " ")
                # 确保进度在 0-100 之间
                safe_progress = max(0, min(100, int(progress)))
                msg_js = json.dumps(safe_msg, ensure_ascii=False)
                self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.update({safe_progress}, {msg_js})")
            except Exception as e:
                print(f"Loading UI 更新失败: {e}")

    def import_zips(self):
        """解压 ZIP (在后台线程)"""
        if self._is_busy:
            self.log_from_backend("[WARN] 另一个任务正在进行中，请稍候...")
            return

        self._is_busy = True
        
        # 显示加载条 (false = 关闭自动模拟)
        if self._window:
            msg_js = json.dumps("正在准备导入...", ensure_ascii=False)
            self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.show(false, {msg_js})")
            self.update_loading_ui(1, "开始扫描待解压区...")

        def _run():
            try:
                self._lib_mgr.unzip_zips_to_library(progress_callback=self.update_loading_ui)
                # 完成后通知前端刷新列表
                if self._window:
                    self._window.evaluate_js("app.refreshLibrary()")
                    msg_js = json.dumps("导入完成", ensure_ascii=False)
                    self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.update(100, {msg_js})")
            except Exception as e:
                self.log_from_backend(f"[ERROR] 导入失败: {e}")
                if self._window:
                    msg_js = json.dumps("导入失败", ensure_ascii=False)
                    self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.update(100, {msg_js})")
            finally:
                self._is_busy = False
        
        t = threading.Thread(target=_run)
        t.daemon = True # [修复] 设置为守护线程
        t.start()

    def import_selected_zip(self):
        """让用户选择一个 Zip 文件并导入 (新功能)"""
        if self._is_busy:
            self.log_from_backend("[WARN] 另一个任务正在进行中，请稍候...")
            return

        # 打开文件选择对话框
        # create_file_dialog 返回的是一个列表 (即使是单选)
        file_types = ('Zip Files (*.zip)', 'All files (*.*)')
        # [修复] 使用 webview.FileDialog.OPEN 替代弃用的 API
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=file_types)
        
        if result and len(result) > 0:
            zip_path = result[0]
            # self.log_from_backend(f"[INFO] 准备导入: {zip_path}")
            
            self._is_busy = True
            
            # 显示加载条
            if self._window:
                msg_js = json.dumps(f"准备导入: {Path(zip_path).name}", ensure_ascii=False)
                self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.show(false, {msg_js})")
            
            def _run():
                try:
                    self.update_loading_ui(1, f"正在读取: {Path(zip_path).name}")
                    # 调用 LibraryManager 的新方法
                    self._lib_mgr.unzip_single_zip(Path(zip_path), progress_callback=self.update_loading_ui)
                    
                    # 完成后通知前端刷新列表
                    if self._window:
                        self._window.evaluate_js("app.refreshLibrary()")
                        msg_js = json.dumps("导入完成", ensure_ascii=False)
                        self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.update(100, {msg_js})")
                except Exception as e:
                     self.log_from_backend(f"[ERROR] 导入失败: {e}")
                     if self._window:
                         msg_js = json.dumps("导入失败", ensure_ascii=False)
                         self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.update(100, {msg_js})")
                finally:
                    self._is_busy = False
            
            t = threading.Thread(target=_run)
            t.daemon = True
            t.start()
        else:
            # 用户取消了选择
            pass

    def install_mod(self, mod_name, install_list):
        """安装语音包"""
        # [关键修复] 解析 install_list，支持 JSON 字符串格式
        # 打包后 pywebview 可能会有数组序列化问题，前端改为传 JSON 字符串
        if isinstance(install_list, str):
            try:
                install_list = json.loads(install_list)
            except json.JSONDecodeError:
                self.log_from_backend(f"[ERROR] 解析安装列表失败: {install_list}", "ERROR")
                return False
        
        # [P1 修复] 使用线程锁保护并发检查
        with self._lock:
            if self._is_busy:
                self.log_from_backend("[WARN] 另一个任务正在进行中，请稍候...", "WARN")
                return False
            self._is_busy = True

        path = self._cfg_mgr.get_game_path()
        valid, _ = self._logic.validate_game_path(path)
        if not valid:
            self.log_from_backend("[ERROR] 安装失败：未设置有效游戏路径", "ERROR")
            with self._lock:
                self._is_busy = False
            return False
            
        # 记录当前 mod
        self._cfg_mgr.set_current_mod(mod_name)

        def _run():
            try:
                mod_path = self._lib_mgr.library_dir / mod_name
                # install_list 是前端传来的数组 ['tank', 'radio'...]
                self._logic.install_from_library(mod_path, install_list, progress_callback=self.update_loading_ui)
                # 安装完成，通知前端
                if self._window:
                    self._window.evaluate_js(f"if(app.onInstallSuccess) app.onInstallSuccess('{mod_name}')")
                    msg_js = json.dumps("安装完成", ensure_ascii=False)
                    self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.update(100, {msg_js})")
            except Exception as e:
                self.log_from_backend(f"[ERROR] 安装失败: {e}", "ERROR")
                if self._window:
                    msg_js = json.dumps("安装失败", ensure_ascii=False)
                    self._window.evaluate_js(f"if(window.MinimalistLoading) MinimalistLoading.update(100, {msg_js})")
            finally:
                with self._lock:
                    self._is_busy = False
        
        t = threading.Thread(target=_run)
        t.daemon = True # [修复] 设置为守护线程
        t.start()
        return True

    def check_install_conflicts(self, mod_name, install_list):
        """
        [P2 修复] 检查安装冲突
        前端在安装前调用此接口
        """
        try:
            # [关键修复] 解析 install_list，支持 JSON 字符串格式
            if isinstance(install_list, str):
                try:
                    install_list = json.loads(install_list)
                except json.JSONDecodeError:
                    return []
            
            path = self._cfg_mgr.get_game_path()
            valid, _ = self._logic.validate_game_path(path)
            if not valid: return []
            
            # 需要先获取 mod 的源路径
            mod_path = self._lib_mgr.library_dir / mod_name
            if not mod_path.exists(): return []
            
            # 模拟遍历过程获取所有要安装的文件名 (逻辑复用 core_logic 的一部分，但这里只做文件名收集)
            # 为了避免重复逻辑，可以在 core_logic 增加一个 get_install_files 接口，
            # 或者在这里简单模拟一下。为了准确性，我们在 core_logic 加个接口比较好。
            # 但为了简单，我们先在这里直接实现
            
            files_to_install = []
            for folder_rel_path in install_list:
                src_dir = None
                if folder_rel_path == "根目录":
                    src_dir = mod_path
                else:
                    src_dir = mod_path / folder_rel_path
                
                if src_dir.exists():
                    for root, dirs, files in os.walk(src_dir):
                        for file in files:
                            files_to_install.append(file)
            
            # 调用 manifest_mgr 检查
            if self._logic.manifest_mgr:
                conflicts = self._logic.manifest_mgr.check_conflicts(mod_name, files_to_install)
                return conflicts
            return []
            
        except Exception as e:
            self.log_from_backend(f"[WARN] 冲突检测失败: {e}", "WARN")
            return []

    def delete_mod(self, mod_name):
        """删除语音包"""
        if self._is_busy:
            self.log_from_backend("[WARN] 另一个任务正在进行中，请稍候...")
            return False
            
        import shutil
        try:
            library_dir = Path(self._lib_mgr.library_dir).resolve()
            target = (library_dir / str(mod_name)).resolve()
            if os.path.commonpath([str(target), str(library_dir)]) != str(library_dir) or str(target) == str(library_dir):
                raise Exception("非法路径")
            shutil.rmtree(target)
            self.log_from_backend(f"[INFO] 已删除语音包: {mod_name}")
            return True
        except Exception as e:
            self.log_from_backend(f"[ERROR] 删除失败: {e}")
            return False

    def restore_game(self):
        """还原纯净模式"""
        if self._is_busy:
            self.log_from_backend("[WARN] 另一个任务正在进行中，请稍候...")
            return False

        path = self._cfg_mgr.get_game_path()
        valid, _ = self._logic.validate_game_path(path)
        if not valid: return False

        self._is_busy = True
        def _run():
            try:
                self._logic.restore_game()
                # 还原成功，清除状态
                self._cfg_mgr.set_current_mod("")
                if self._window:
                    self._window.evaluate_js("app.onRestoreSuccess()")
            finally:
                self._is_busy = False
        
        t = threading.Thread(target=_run)
        t.daemon = True # [修复] 设置为守护线程
        t.start()
        return True

    def clear_logs(self):
        # 后端其实不需要清空什么，主要是前端清空 DOM
        self.log_from_backend("[INFO] 日志已清空")

    # --- 首次运行状态 API ---
    def check_first_run(self):
        """前端调用，检查是否需要显示首次运行协议"""
        is_first = self._cfg_mgr.get_is_first_run()
        saved_ver = self._cfg_mgr.get_agreement_version()
        
        # 只要是首次运行，或者协议版本不一致，就返回 True
        needs_agreement = is_first or (saved_ver != AGREEMENT_VERSION)
        
        return {
            "status": needs_agreement,
            "version": AGREEMENT_VERSION
        }

    def agree_to_terms(self, version):
        """前端调用，用户同意协议"""
        self._cfg_mgr.set_is_first_run(False)
        self._cfg_mgr.set_agreement_version(version)
        return True

    # --- 主题管理 API ---
    def get_theme_list(self):
        """扫描 web/themes 目录下的所有 json 主题"""
        themes_dir = WEB_DIR / "themes"
        if not themes_dir.exists():
            return []
        
        theme_list = []
        # 遍历 json 文件
        for file in themes_dir.glob("*.json"):
            try:
                # 简单读取一下 Meta 信息
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    meta = data.get("meta", {})
                    theme_list.append({
                        "filename": file.name,           # 文件名 (ID)
                        "name": meta.get("name", file.stem), # 显示名称
                        "author": meta.get("author", "Unknown"),
                        "version": meta.get("version", "1.0")
                    })
            except Exception as e:
                print(f"读取主题 {file.name} 失败: {e}")
        
        return theme_list

    def load_theme_content(self, filename):
        """读取具体的主题内容"""
        themes_dir = (WEB_DIR / "themes").resolve()
        theme_path = (themes_dir / str(filename)).resolve()
        if os.path.commonpath([str(theme_path), str(themes_dir)]) != str(themes_dir):
            return None
        if theme_path.suffix.lower() != ".json":
            return None
        if not theme_path.exists():
            return None
            
        try:
            with open(theme_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载主题失败: {e}")
            return None


# --- 新增：关闭启动图的逻辑 ---
def on_app_started():
    """
    当 GUI 窗口创建完毕后执行此函数。
    用于关闭 PyInstaller 的 Splash Screen。
    """
    # 稍微延时 0.5 秒，防止窗口刚出来时是白的，
    # 等 HTML 渲染差不多了再把封面撤掉，实现无缝衔接。
    time.sleep(0.5)
    
    if getattr(sys, 'frozen', False):
        try:
            import pyi_splash
            pyi_splash.close()
            print("[INFO] Splash screen closed.", flush=True)
        except ImportError:
            pass
    
    for _ in range(10):
        try:
            if webview.windows:
                win = webview.windows[0]
                win.evaluate_js("if (window.app && app.recoverToSafeState) app.recoverToSafeState('backend_start');")
                state = win.evaluate_js("JSON.stringify({activePage: (document.querySelector('.page.active')||{}).id || null, openModals: Array.from(document.querySelectorAll('.modal-overlay.show')).map(x=>x.id)})")
                print(f"[UI_STATE] {state}", flush=True)
                break
        except Exception:
            time.sleep(0.2)

if __name__ == '__main__':
    # 1. 准备 API 对象
    api = AppApi()

    # 2. 创建窗口
    # 调整窗口大小
    window_width = 1200
    window_height = 740
    
    try:
        # 获取所有屏幕，通常第一个是主显示器
        screens = webview.screens
        if screens:
            primary = screens[0]
            # 计算居中坐标：(屏幕宽 - 窗口宽) / 2
            start_x = (primary.width - window_width) // 2
            start_y = (primary.height - window_height) // 2
        else:
            start_x = None
            start_y = None
    except Exception as e:
        print(f"获取屏幕信息失败: {e}")
        start_x = None
        start_y = None

    # 3. 创建窗口
    # 注意：x 和 y 参数决定了启动时的位置
    window = webview.create_window(
        title="Aimer WT v1 Beta",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=window_width,
        height=window_height,
        x=start_x,
        y=start_y,
        min_size=(1000, 700),
        background_color='#F5F7FA',
        resizable=True,
        text_select=False,
        frameless=True,
        easy_drag=True
    )
    
    # 3. 关联 API
    api.set_window(window)
    
    # 4. 启动
    icon_path = str(WEB_DIR / "assets" / "logo.ico")
    try:
        # 尝试使用 edgechromium 内核（性能更好）
        webview.start(debug=False, http_server=False, gui='edgechromium', func=on_app_started, icon=icon_path)
    except Exception as e:
        print(f"Edge Chromium 启动失败，尝试默认模式: {e}")
        # 降级启动
        webview.start(debug=False, http_server=False, func=on_app_started, icon=icon_path)
