import requests  # 导入requests库，用于发送HTTP请求获取加密货币数据
import json  # 导入json库，用于处理JSON格式数据
import sys  # 导入sys库，用于访问Python解释器相关的变量和函数
import os  # 导入os库，用于与操作系统交互，如文件路径操作
import ctypes  # 导入ctypes库，用于调用底层C语言库函数
import logging  # 导入logging库，用于记录程序运行日志
from datetime import datetime, timedelta  # 从datetime模块导入datetime类和timedelta类，用于日期和时间处理
from threading import Thread, Lock  # 从threading模块导入Thread和Lock，用于多线程编程
from dotenv import load_dotenv  # 从dotenv导入load_dotenv函数，用于加载环境变量
from dateutil import parser  # 导入dateutil的parser模块，用于更强大的日期解析功能
import winreg as reg
import copy # <--- 添加导入
from PySide6.QtGui import QCloseEvent # Import QCloseEvent for closeEvent override
import traceback # Ensure traceback is imported

# 导入PySide6库中的Qt组件，用于创建图形用户界面
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QCheckBox, QToolTip, QMessageBox)
from PySide6.QtCore import Qt, QTimer, Signal, Slot  # 导入Qt核心组件
from PySide6.QtGui import QColor, QFont, QMouseEvent, QIcon  # 导入Qt图形界面组件

# 如果是Windows，导入win32gui用于直接操作窗口
if sys.platform == 'win32':
    try:
        import win32gui  # type: ignore
        import win32con  # type: ignore
        HAS_WIN32API = True
    except ImportError:
        HAS_WIN32API = False
        logging.warning("win32gui模块未安装，将使用标准方式切换窗口置顶状态")
else:
    HAS_WIN32API = False

"""
加密货币价格监控器
主要功能:
1. 显示BTC、ETH、BERA和IBGT的实时价格和24小时变化
2. 显示恐惧与贪婪指数
3. 支持窗口置顶和拖动
4. 自动更新数据
"""

# ===================================
# 日志配置
# ===================================

def setup_logger():
    """配置日志记录器，用于记录程序运行过程中的信息"""
    try: # 保留 try-except 结构
        log_dir_base = None
        try:
            # --- 删除: 临时测试直接写入文件代码 ---

            # --- 改动：优先使用 %LOCALAPPDATA% ---
            if sys.platform == 'win32':
                appdata = os.getenv('LOCALAPPDATA') # 使用 LOCALAPPDATA 存储日志更合适
                if appdata:
                    log_dir_base = os.path.join(appdata, 'BeraHelper', 'logs')
                    logging.info(f"日志目录将使用 LOCALAPPDATA: {log_dir_base}")

            # --- 改动：如果获取 %LOCALAPPDATA% 失败或非 Windows，则回退 ---
            if not log_dir_base:
                # 回退到可执行文件/脚本文件所在的目录下的 logs 文件夹
                if getattr(sys, 'frozen', False): # 打包后的 .exe 环境
                    exe_dir = os.path.dirname(sys.executable)
                else: # 开发环境 (.py)
                    exe_dir = os.path.dirname(os.path.abspath(__file__))
                log_dir_base = os.path.join(exe_dir, 'logs')
                logging.warning(f"无法获取 LOCALAPPDATA 或非 Windows，日志目录回退至: {log_dir_base}")

            # 创建日志目录（如果不存在）
            if not os.path.exists(log_dir_base):
                os.makedirs(log_dir_base, exist_ok=True) # exist_ok=True 避免目录已存在时报错
                logging.info(f"已创建日志目录: {log_dir_base}")

            # 获取当前时间作为日志文件名
            current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir_base, f'bera_helper_{current_time}.log') # 确保使用绝对路径

            # 配置日志格式
            log_format = '%(asctime)s [%(levelname)s] %(message)s'
            date_format = '%Y-%m-%d %H:%M:%S'

            # --- 保留: 重置日志系统 ---
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)

            # 配置根日志记录器
            logging.basicConfig(
                level=logging.DEBUG, # <-- 保留 DEBUG 级别
                format=log_format,
                datefmt=date_format,
                handlers=[
                    logging.FileHandler(log_file, encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )

            # 设置第三方库的日志级别为WARNING，以减少日志输出量
            # 可选择的日志级别包括：
            # - CRITICAL (50): 仅记录严重错误，程序可能无法继续运行
            # - ERROR (40): 记录错误信息，但程序仍可继续运行
            # - WARNING (30): 记录警告信息，表示可能的问题
            # - INFO (20): 记录一般信息，确认程序按预期运行
            # - DEBUG (10): 记录详细的调试信息
            # - NOTSET (0): 不设置级别，继承父记录器的级别
            logging.getLogger('urllib3').setLevel(logging.WARNING)  # 设置HTTP请求库的日志级别
            logging.getLogger('requests').setLevel(logging.WARNING) # 设置请求库的日志级别

            logging.info('日志系统初始化完成')
            logging.info(f'日志文件实际路径: {log_file}')
            
            # --- 删除: 测试警告消息、强制刷新和 atexit 机制 ---

        except Exception as log_setup_error:
            # 如果文件日志配置失败，提供基本的控制台日志作为后备
            logging.basicConfig(level=logging.ERROR) # 重新配置，至少保证 ERROR 级别能输出
            logging.critical(f"!!! 无法配置基于文件的日志系统: {log_setup_error}")
            logging.critical("!!! 日志将仅输出到控制台/stderr")

    except Exception as outer_e:
        # 捕获 setup_logger 内部未能捕获的任何意外错误
        print(f"CRITICAL ERROR during logger setup: {outer_e}")

# 初始化日志系统
setup_logger()

# ===================================
# 工具函数
# ===================================

def resource_path(relative_path):
    """获取资源的绝对路径，适用于开发环境和打包后的环境"""
    try:
        # PyInstaller创建临时文件夹，将路径存储在_MEIPASS中
        base_path = sys._MEIPASS  # 尝试获取PyInstaller打包后的临时文件夹路径
        logging.debug(f"使用PyInstaller路径: {base_path}")
    except Exception:
        # 如果不是打包环境，尝试多种可能的路径
        # 1. 当前文件所在目录
        base_path = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(os.path.join(base_path, relative_path)):
            # 2. 当前工作目录
            base_path = os.path.abspath(".")
            if not os.path.exists(os.path.join(base_path, relative_path)):
                # 3. 可执行文件所在目录
                base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
                
        logging.debug(f"使用非打包环境路径: {base_path}")
    
    result_path = os.path.join(base_path, relative_path)
    logging.debug(f"资源路径解析: {relative_path} -> {result_path}")
    return result_path  # 返回资源的绝对路径

# ===================================
# 主应用类
# ===================================

class CryptoPriceWidget(QWidget):
    """加密货币价格和变化显示组件，用于显示单个加密货币的价格和24小时变化率"""
    
    def __init__(self, label_text, font, parent=None):
        super().__init__(parent)  # 调用父类的初始化方法
        self.setObjectName("priceWidget")  # 设置对象名称，便于样式表选择
        
        # 创建水平布局
        layout = QHBoxLayout(self)  # 创建水平布局管理器
        layout.setContentsMargins(0, 0, 0, 0)  # 设置布局的边距为0
        layout.setAlignment(Qt.AlignCenter)  # 设置布局中的组件居中对齐
        
        # 标签
        self.label = QLabel(label_text)  # 创建标签，显示加密货币名称
        self.label.setStyleSheet("color: #FFD700;")  # 设置标签文本颜色为金色
        self.label.setFont(font)  # 设置标签字体
        
        # 价格
        self.price = QLabel("$--.--")  # 创建价格标签，初始显示为$--.--
        self.price.setStyleSheet("color: #FFD700;")  # 设置价格文本颜色为金色
        self.price.setFont(font)  # 设置价格标签字体
        
        # 变化百分比
        self.change = QLabel("--.--%")  # 创建变化率标签，初始显示为--.--%
        self.change.setFont(font)  # 设置变化率标签字体
        
        # 添加到布局
        layout.addWidget(self.label)  # 将加密货币名称标签添加到布局
        layout.addWidget(self.price)  # 将价格标签添加到布局
        layout.addWidget(self.change)  # 将变化率标签添加到布局
        
    def update_price(self, price, change):
        """更新价格和变化率显示"""
        if price is not None:
            self.price.setText(price)  # 更新价格标签文本
            
            # 如果价格是"加载中..."或"获取失败"等特殊状态，则不显示变化率
            if price in ["加载中...", "获取失败", "$--.--"]:
                self.change.setText("")
                self.change.setStyleSheet("")
            else:
                self.change.setText(change)  # 更新变化率标签文本
                
                # 设置颜色
                if change.startswith("+"):
                    self.change.setStyleSheet("color: #00FF7F;")  # 上涨时设置为绿色
                elif change.startswith("-"):
                    self.change.setStyleSheet("color: #FF4500;")  # 下跌时设置为红色
                else:
                    self.change.setStyleSheet("color: #FFFFFF;")  # 无变化或无数据时设置为白色
        else:
            self.price.setText("$--.--")  # 如果价格为空，显示默认值
            self.change.setText("")  # 如果变化率为空，不显示
            self.change.setStyleSheet("")  # 重置样式

class BeraHelperApp(QMainWindow):
    """主应用窗口，显示加密货币价格和恐惧贪婪指数"""
    
    data_updated = Signal()  # 定义数据更新信号，用于通知UI更新
    initial_data_ready = Signal(object, object, str) # 新增信号，用于传递首次获取的数据
    
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint)
        self.setWindowTitle("Bera Helper")

        # 设置应用图标
        icon_path = resource_path('bera.ico')
        if os.path.exists(icon_path):
            try:
                icon = QIcon(icon_path)
                self.setWindowIcon(icon)
                # 设置任务栏图标 (暂时注释掉 ctypes 调用)
                if sys.platform == 'win32':
                    try:
                        myappid = 'BeraHelper.1.0'
                        # ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid) # <--- 注释掉这一行
                        logging.info(f"Skipped SetCurrentProcessExplicitAppUserModelID.") # <--- 修改日志
                    except Exception as e:
                        logging.error(f"ERROR during SetCurrentProcessExplicitAppUserModelID (skipped but logged): {e}") # <--- 修改日志
                        logging.error(f'设置任务栏图标ID时发生错误 (即使已跳过): {e}')
                logging.info(f"App icon setup logic completed (taskbar ID skipped). Path: {icon_path}") # <--- 修改日志
            except Exception as icon_load_err:
                 logging.error(f"ERROR loading or setting icon: {icon_load_err}")
                 logging.error(f"加载或设置图标时出错: {icon_load_err}")
        else:
            logging.warning(f"Icon file does NOT exist: {icon_path}") # <--- 修改日志
            logging.warning(f'图标文件不存在: {icon_path}')

        logging.info("Icon setup attempted section finished.") # <--- 修改原检查点日志内容

        # 初始化变量
        self.init_variables()
        logging.info("init_variables completed.") # <--- Checkpoint after

        # 加载配置文件
        self.load_config()
        logging.info("load_config completed.") # <--- Checkpoint after

        # 创建UI
        self.setup_ui()
        logging.info("setup_ui completed.") # <--- Checkpoint after
        
        # 连接信号
        self.data_updated.connect(self.update_ui)  # 将数据更新信号连接到更新UI的槽函数
        self.initial_data_ready.connect(self.handle_initial_data) # 连接新信号
        
        # 创建更新定时器 (先创建，但不在这里启动)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_data)
        
        # 设置窗口置顶
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)  # 设置窗口置顶标志
        self.is_topmost = True  # 设置置顶状态变量为True
        self.update_pin_button_status()  # 更新置顶按钮状态
        
        # --- 修改：立即显示加载中，并在后台启动首次获取 ---
        logging.info("UI 初始化完成，准备后台获取首次数据")
        for token_id, widget in self.token_widgets.items():
            widget.update_price("加载中...", "") # 立即显示加载状态

        # 启动后台线程执行首次数据获取
        # 使用 QTimer 稍微延迟启动线程，确保主窗口已显示
        QTimer.singleShot(500, self.start_initial_fetch_thread) # 延迟 500ms
    
    def start_initial_fetch_thread(self):
        """启动一个后台线程来执行首次数据获取"""
        logging.info("启动首次数据获取线程...")
        initial_fetch_thread = Thread(target=self._initial_fetch_thread, daemon=True)
        initial_fetch_thread.start()

    def _initial_fetch_thread(self):
        """在后台线程中执行首次数据获取"""
        logging.info("首次数据获取线程开始执行...")
        price_data = None
        fear_greed_data = None
        current_time = datetime.now().strftime("%H:%M:%S")
        try:
            # 获取价格数据
            price_data = self.get_prices()

            # 获取恐惧贪婪指数
            fear_greed_data = self.get_fear_greed_index(force_update=True) # 强制更新

            logging.info("首次数据获取线程完成")

        except Exception as e:
            logging.error(f"首次数据获取线程失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # 即使失败，也发送信号，让主线程知道
        finally:
            # 使用信号将结果传递回主线程
            self.initial_data_ready.emit(price_data, fear_greed_data, current_time)

    @Slot(object, object, str)
    def handle_initial_data(self, price_data, fear_greed_data, current_time):
        """处理后台线程返回的首次数据，更新UI并启动定时器"""
        logging.info("接收到首次数据，准备更新 UI 并启动定时器")
        self.price_data = price_data
        self.fear_greed_data = fear_greed_data
        self.current_time = current_time

        # 检查获取的数据是否有效
        if self.price_data is None or not self.price_data:
             logging.warning("首次获取的价格数据无效或为空，部分UI可能显示错误状态")
             # 可以选择在这里为所有 widget 设置错误状态
             for token_id, widget in self.token_widgets.items():
                 if not self.price_data or token_id not in self.price_data:
                      widget.update_price("获取失败", "--.--%")

        if self.fear_greed_data is None:
             logging.warning("首次获取的恐惧贪婪指数数据无效")
             # UI 更新时会自动处理 None 的情况

        # 更新 UI (会使用 self.price_data 和 self.fear_greed_data)
        self.update_ui()

        # --- 在首次数据获取完成后再启动定时器 ---
        self.timer.start(self.update_interval * 1000)
        logging.info(f"首次数据显示完成，定时更新已启动，间隔: {self.update_interval}秒")

    def init_variables(self):
        """初始化变量和状态"""
        # 加载环境变量（API密钥）
        load_dotenv(resource_path('.env'))  # 从.env文件加载环境变量

        # 初始化恐惧指数缓存和数据缓存
        self.fear_greed_cache = None  # 恐惧贪婪指数缓存
        self.fear_greed_last_update = None  # 恐惧贪婪指数最后更新时间
        self.fear_greed_lock = Lock()  # 创建线程锁，用于保护恐惧贪婪指数数据
        self.fear_greed_data = None  # 恐惧贪婪指数数据
        self.price_data = None  # 价格数据
        self.current_time = None  # 当前时间
        
        # 窗口拖动相关
        self.dragging = False  # 是否正在拖动窗口
        self.drag_position = None  # 拖动起始位置
        
        # 置顶状态
        self.is_topmost = True  # 窗口是否置顶
        
        # 用户自定义代币列表
        self.user_tokens = []  # 用户选择显示的代币列表
        self.available_tokens = []  # 可用代币列表
        self.token_widgets = {}  # 代币显示组件字典
        
        # 添加自启动操作锁
        self.autostart_lock = False  # 防止多次点击自启动按钮

        # --- Autostart State ---
        self.pending_autostart_state = None # None: no pending change, True: enable pending, False: disable pending
        self.autostart_save_timer = QTimer(self)
        self.autostart_save_timer.setSingleShot(True)
        self.autostart_save_timer.setInterval(60000) # 1 minute delay
        self.autostart_save_timer.timeout.connect(self._apply_pending_autostart_setting)

    def load_config(self):
        """加载配置文件，设置应用参数 (所有代币均可切换显示模式)"""
        try:
            config_path = resource_path('bera_helper_config.json')
            logging.info(f'正在加载配置文件: {config_path}')
            config = {} # 初始化为空字典
            if not os.path.exists(config_path):
                 logging.warning(f"配置文件不存在: {config_path}。将使用并创建默认配置。")
                 # 定义基础的默认配置结构
                 config = {
                     # tokens部分会在后面填充默认值
                     "tokens": {},
                     
                     # 样式配置
                     "styles": {
                         "FONT_NORMAL": ["Arial", 11],
                         "UP_COLOR": "#00FF7F",      # 上涨颜色
                         "DOWN_COLOR": "#FF4500",    # 下跌颜色
                         "TEXT_COLOR": "#FFD700",    # 文本颜色
                         "EXTREME_FEAR_COLOR": "#FF0000",  # 极度恐惧颜色
                         "FEAR_COLOR": "#FF7F00",         # 恐惧颜色
                         "NEUTRAL_COLOR": "#FFFF00",      # 中性颜色
                         "GREED_COLOR": "#7FFF00",        # 贪婪颜色
                         "EXTREME_GREED_COLOR": "#00FF00" # 极度贪婪颜色
                     },
                     
                     # 窗口配置
                     "window": {
                         "update_interval": 60  # 更新间隔(秒)
                     },
                     
                     # API配置
                     "api": {
                         "coinmarketcap": {
                             "enabled": True,
                             "base_url": "https://pro-api.coinmarketcap.com/v3",
                             "endpoints": {
                                 "fear_greed": "/fear-and-greed/historical"
                             },
                             "params": {
                                 "fear_greed": {
                                     "start": 1,
                                     "limit": 1
                                 }
                             },
                             "update_interval": 3600  # API更新间隔(秒)
                         }
                     }
                 }
                 # 尝试保存一次初始配置，但不强制要求成功
                 try:
                     with open(config_path, 'w', encoding='utf-8') as f_default:
                         json.dump(config, f_default, indent=2)
                     logging.info(f"已创建基础配置文件: {config_path}")
                 except Exception as create_err:
                     logging.error(f"创建默认配置文件失败: {create_err}，将继续使用内存中的默认配置。")
            else:
                 # 文件存在，正常加载
                 try:
                     with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                 except json.JSONDecodeError as e:
                     logging.error(f"配置文件 {config_path} 格式错误: {e}。将使用默认配置。")
                     # 保留上面定义的默认 config 结构
                 except Exception as load_err:
                     logging.error(f"加载配置文件时发生错误: {load_err}。将使用默认配置。")
                     # 保留上面定义的默认 config 结构

            # --- 字体设置 ---
            styles_config = config.get('styles', {})
            font_config = styles_config.get('FONT_NORMAL', ['Arial', 11])
            self.app_font = QFont(font_config[0], font_config[1])
            logging.debug(f'配置的字体: {font_config[0]}, 大小: {font_config[1]}')

            # --- 代币ID配置 (从配置文件加载，提供默认值) ---
            tokens_config = config.get('tokens', {})
            self.BERA_ID = tokens_config.get('BERA_ID', "berachain-bera")
            self.IBGT_ID = tokens_config.get('IBGT_ID', "infrafred-bgt")
            self.BTC_ID = tokens_config.get('BTC_ID', "bitcoin")
            self.ETH_ID = tokens_config.get('ETH_ID', "ethereum")
            # XBERA_ID, XBGT_ID 不再是特殊变量，用户需要在 user_tokens.json 中添加它们

            # --- 不再需要 RELEVANT_BERA_TOKENS 集合 ---
            # self.RELEVANT_BERA_TOKENS = {...} # 删除或注释掉这部分

            # --- 准备基础的默认代币列表 (无特殊标志) ---
            # 这些是程序首次运行时或者加载用户配置失败时使用的
            base_default_tokens = [
                {"id": self.BTC_ID, "symbol": "BTC", "name": "Bitcoin"},
                {"id": self.ETH_ID, "symbol": "ETH", "name": "Ethereum"},
                {"id": self.BERA_ID, "symbol": "BERA", "name": "Berachain"},
                {"id": self.IBGT_ID, "symbol": "IBGT", "name": "Infrafred"},
            ]
            # 为默认列表添加 display_as_bera_ratio=False 标志
            default_tokens_with_flags = []
            for token in base_default_tokens:
                 token["display_as_bera_ratio"] = False # 所有代币默认显示价格
                 default_tokens_with_flags.append(token)

            # --- 加载用户代币设置 ---
            user_tokens_loaded = False
            user_tokens_path = ""
            try:
                user_data_dir = self.get_user_data_dir()
                user_tokens_path = os.path.join(user_data_dir, 'user_tokens.json')
                logging.info(f'尝试加载用户代币设置: {user_tokens_path}')

                if os.path.exists(user_tokens_path):
                    with open(user_tokens_path, 'r', encoding='utf-8') as f:
                        loaded_data = json.load(f)

                    loaded_tokens = []
                    if isinstance(loaded_data, dict) and "tokens" in loaded_data:
                        if isinstance(loaded_data["tokens"], list): loaded_tokens = loaded_data["tokens"]
                        else: logging.warning("user_tokens.json 'tokens' key is not a list.")
                    elif isinstance(loaded_data, list): # 兼容旧格式
                        loaded_tokens = loaded_data
                    else: logging.error(f"Invalid format in user_tokens.json: {type(loaded_data)}.")

                    if loaded_tokens:
                        self.user_tokens = []
                        processed_ids = set()
                        for token_data in loaded_tokens:
                            if isinstance(token_data, dict) and "id" in token_data and token_data["id"] not in processed_ids:
                                # **确保所有加载的代币都有标志，默认为 False**
                                if "display_as_bera_ratio" not in token_data:
                                    token_data["display_as_bera_ratio"] = False
                                self.user_tokens.append(token_data)
                                processed_ids.add(token_data["id"])
                            else: logging.warning(f"Skipping invalid/duplicate token data: {token_data}")

                        if self.user_tokens:
                             logging.info(f'已加载用户代币设置: {len(self.user_tokens)} 个代币')
                             user_tokens_loaded = True
                             for token in self.user_tokens: logging.debug(f'  加载: {token.get("symbol", "?")} ({token.get("id", "?ID")}), Ratio: {token.get("display_as_bera_ratio")}') # 明确显示布尔值
                        else: logging.warning("User token list is empty after processing.")
                else:
                    logging.warning(f'用户代币配置文件不存在: {user_tokens_path}. 将首次使用默认代币.')

            except json.JSONDecodeError as e: logging.error(f'解析 user_tokens.json 失败: {e}.')
            except Exception as e:
                logging.error(f'加载用户代币设置时发生错误: {e}.')
                import traceback; logging.error(traceback.format_exc())

            if not user_tokens_loaded:
                logging.info('使用默认代币列表。')
                self.user_tokens = default_tokens_with_flags # 使用带 False 标志的默认列表
                if user_tokens_path and not os.path.exists(user_tokens_path):
                    try: self.save_user_tokens()
                    except Exception as save_e: logging.error(f"首次保存默认代币列表失败: {save_e}")

            # --- 加载其他配置 (保持不变) ---
            self.load_available_tokens()
            self.update_interval = config.get('window', {}).get('update_interval', 60)
            self.api_config = config.get('api', {})
            self.up_color = QColor(styles_config.get('UP_COLOR', "#00FF7F"))
            self.down_color = QColor(styles_config.get('DOWN_COLOR', "#FF4500"))
            self.text_color = QColor(styles_config.get('TEXT_COLOR', "#FFD700"))
            self.extreme_fear_color = QColor(styles_config.get('EXTREME_FEAR_COLOR', "#FF0000"))
            self.fear_color = QColor(styles_config.get('FEAR_COLOR', "#FF7F00"))
            self.neutral_color = QColor(styles_config.get('NEUTRAL_COLOR', "#FFFF00"))
            self.greed_color = QColor(styles_config.get('GREED_COLOR', "#7FFF00"))
            self.extreme_greed_color = QColor(styles_config.get('EXTREME_GREED_COLOR', "#00FF00"))

            logging.info('配置加载完成')

        except Exception as e:
            # --- 极端情况下的硬编码默认值 (保持不变) ---
            logging.error(f'!!! 配置文件加载/创建过程中发生严重错误: {e}')
            import traceback; logging.error(traceback.format_exc())
            logging.warning("将使用硬编码的程序默认值！")
            # ... (保持之前的硬编码默认值设置) ...
            self.app_font = QFont('Arial', 11); self.BERA_ID = "berachain-bera"; self.IBGT_ID = "infrafred-bgt"; self.BTC_ID = "bitcoin"; self.ETH_ID = "ethereum"; self.update_interval = 60; self.api_config = {"coinmarketcap": {"enabled": True, "base_url": "https://pro-api.coinmarketcap.com/v3", "endpoints": {"fear_greed": "/fear-and-greed/historical"}, "params": {"fear_greed": {"start": 1, "limit": 1}}, "update_interval": 3600}}; self.up_color = QColor("#00FF7F"); self.down_color = QColor("#FF4500"); self.text_color = QColor("#FFD700"); self.extreme_fear_color = QColor("#FF0000"); self.fear_color = QColor("#FF7F00"); self.neutral_color = QColor("#FFFF00"); self.greed_color = QColor("#7FFF00"); self.extreme_greed_color = QColor("#00FF00")
            # 极端默认列表，全都不显示比率
            self.user_tokens = [ {"id": self.BTC_ID, "symbol": "BTC", "name": "Bitcoin", "display_as_bera_ratio": False}, {"id": self.ETH_ID, "symbol": "ETH", "name": "Ethereum", "display_as_bera_ratio": False}, {"id": self.BERA_ID, "symbol": "BERA", "name": "Berachain", "display_as_bera_ratio": False}, {"id": self.IBGT_ID, "symbol": "IBGT", "name": "Infrafred", "display_as_bera_ratio": False}, ]
            self.available_tokens = []
            try: self.load_available_tokens()
            except Exception as load_list_e: logging.error(f"紧急默认设置下加载可用代币列表失败: {load_list_e}")

    def load_available_tokens(self):
        """加载可用的代币列表，并检查是否需要更新"""
        try:
            # 获取代币列表文件路径
            tokens_path = resource_path('coingecko.list')
            logging.info(f'尝试加载代币列表文件: {tokens_path}')
            
            # 检查文件是否存在
            if os.path.exists(tokens_path):
                try:
                    # 检查文件修改时间，决定是否需要提示用户更新
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(tokens_path))
                    now = datetime.now()
                    days_since_update = (now - file_mod_time).days
                    
                    with open(tokens_path, 'r', encoding='utf-8') as f:
                        self.available_tokens = json.load(f)
                        
                    logging.info(f'已加载可用代币列表: {len(self.available_tokens)}个代币')
                    
                    # 如果列表文件超过30天未更新，弹出提示
                    if days_since_update > 30:
                        from PySide6.QtWidgets import QMessageBox
                        update_msg = QMessageBox(self)
                        update_msg.setIcon(QMessageBox.Information)
                        update_msg.setText(f"代币列表已有{days_since_update}天未更新。\n是否现在更新？")
                        update_msg.setWindowTitle("代币列表更新")
                        update_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        if update_msg.exec() == QMessageBox.Yes:
                            QTimer.singleShot(1000, self.check_token_list_updates)
                    
                except Exception as e:
                    logging.error(f'读取代币列表文件时出错: {e}')
                    self.available_tokens = self.user_tokens.copy()
            else:
                # 文件不存在，直接触发下载
                logging.warning(f'代币列表文件不存在: {tokens_path}')
                QTimer.singleShot(1000, self.check_token_list_updates)
                self.available_tokens = self.user_tokens.copy()
        except Exception as e:
            logging.error(f'加载代币列表失败: {e}')
            self.available_tokens = self.user_tokens.copy()
    
    def save_user_tokens(self):
        """保存用户的代币设置"""
        try:
            # 获取用户数据目录
            user_data_dir = self.get_user_data_dir()
            
            # 确保目录存在
            if not os.path.exists(user_data_dir):
                os.makedirs(user_data_dir)
            
            # 设置代币配置文件路径
            user_tokens_path = os.path.join(user_data_dir, 'user_tokens.json')
            
            # 保存代币设置
            with open(user_tokens_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_tokens, f, ensure_ascii=False, indent=2)
            
            logging.info(f'已保存用户代币设置到: {user_tokens_path}')
            logging.debug(f'保存的代币数量: {len(self.user_tokens)}')
            
            # 验证保存结果
            if os.path.exists(user_tokens_path):
                try:
                    with open(user_tokens_path, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)
                    logging.debug(f'验证保存: 文件中的代币数量 {len(saved_data)}')
                except Exception as e:
                    logging.error(f'验证保存失败: {e}')
            else:
                logging.error(f'保存失败: 文件不存在 {user_tokens_path}')
                
        except Exception as e:
            logging.error(f'保存用户代币设置失败: {e}')
    
    def get_user_data_dir(self):
        """获取用户数据目录，确保所有相关函数使用相同的路径"""
        if sys.platform == 'win32':
            # Windows: 使用 %APPDATA%\BeraHelper
            appdata = os.getenv('APPDATA')
            if appdata:
                return os.path.join(appdata, 'BeraHelper')
        
        # 其他系统或未找到 APPDATA: 使用程序所在目录
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    
    def setup_ui(self):
        """设置用户界面，创建和布局UI组件"""
        # 主容器
        central_widget = QWidget()  # 创建中央窗口部件
        self.setCentralWidget(central_widget)  # 设置中央窗口部件
        
        # 设置窗口样式和字体
        self.setStyleSheet("""
            QMainWindow {
                background-color: #000000;
                border: 1 px solid #FFD700; /* 添加金色边框 */
            }
        """)  # 设置窗口背景颜色为黑色，添加金色边框
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)  # 创建垂直布局管理器
        main_layout.setContentsMargins(10, 5, 10, 5)  # 设置布局的边距
        main_layout.setAlignment(Qt.AlignCenter)  # 设置布局中的组件居中对齐
        main_layout.setSpacing(2)  # 减小布局中各组件之间的间距为2像素
        
        # 1. 控制栏
        control_bar = QWidget()  # 创建控制栏部件
        control_layout = QHBoxLayout(control_bar)  # 创建水平布局管理器
        control_layout.setContentsMargins(0, 0, 0, 0)  # 设置布局的边距为0
        
        # 置顶按钮
        self.pin_button = QPushButton("📌")  # 创建置顶按钮，使用图钉emoji
        self.pin_button.setFont(self.app_font)  # 设置按钮字体
        self.pin_button.setToolTip("窗口置顶")  # 设置工具提示
        self.pin_button.clicked.connect(self.toggle_topmost)  # 连接按钮点击信号到切换置顶状态的函数
        
        # 添加代币列表更新按钮
        self.update_tokens_button = QPushButton("🔄")  # 创建更新按钮，使用循环箭头emoji
        self.update_tokens_button.setFont(self.app_font)  # 设置按钮字体
        self.update_tokens_button.setToolTip("更新代币列表")  # 设置工具提示
        self.update_tokens_button.clicked.connect(self.check_token_list_updates)  # 连接按钮点击信号
        self.update_tokens_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: #FFD700;
                font-weight: bold;
                padding: 2px;
                margin: 0px;
                background-color: transparent;
            }
            QPushButton:hover {
                color: #FFA500;
            }
""")  # 设置与其他控制按钮一致的样式
        
        # 自启动按钮
        self.autostart_button = QPushButton("🚀")  # 创建自启动按钮，使用火箭emoji
        self.autostart_button.setFont(self.app_font)  # 设置按钮字体
        self.autostart_button.setToolTip("开机自启动")  # 设置工具提示
        self.autostart_button.clicked.connect(self.toggle_autostart)  # 连接按钮点击信号
        
        # 代币管理按钮
        self.token_button = QPushButton("💰")  # 创建代币管理按钮，使用钱袋emoji
        self.token_button.setFont(self.app_font)  # 设置按钮字体
        self.token_button.setToolTip("代币管理")  # 设置工具提示
        self.token_button.clicked.connect(self.show_token_manager)  # 连接按钮点击信号
        self.token_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: #FFD700;
                font-weight: bold;
                padding: 2px;
                margin: 0px;
                background-color: transparent;
            }
            QPushButton:hover {
                color: #FFA500;
            }
        """)  # 设置按钮样式与其他控制按钮一致
        
        # 关闭按钮
        close_button = QPushButton("×")  # 创建关闭按钮，显示为×符号
        close_button.setFont(self.app_font)  # 设置按钮字体
        close_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: #FFD700;
            }
            QPushButton:hover {
                color: #FFA500;
            }
        """)  # 设置按钮样式：无边框，金色文本，悬停时为橙色
        close_button.clicked.connect(self.close)  # 连接按钮点击信号到关闭窗口的函数
        
        control_layout.addWidget(self.pin_button)  # 将置顶按钮添加到控制栏布局
        control_layout.addWidget(self.update_tokens_button)  # 将更新按钮添加到控制栏布局
        control_layout.addWidget(self.autostart_button)  # 将自启动按钮添加到控制栏布局
        control_layout.addWidget(self.token_button)  # 将代币管理按钮添加到控制栏布局
        control_layout.addStretch()  # 添加弹性空间，使关闭按钮靠右显示
        control_layout.addWidget(close_button)  # 将关闭按钮添加到控制栏布局
        
        # 2. 恐惧贪婪指数时间
        self.fear_greed_time = QLabel()  # 创建恐惧贪婪指数时间标签
        self.fear_greed_time.setFont(self.app_font)  # 设置标签字体
        self.fear_greed_time.setStyleSheet("color: #FFFFFF;")  # 设置标签文本颜色为白色
        self.fear_greed_time.setAlignment(Qt.AlignCenter)  # 设置标签文本居中对齐
        
        # 3. 恐惧贪婪指数
        fear_greed_frame = QWidget()  # 创建恐惧贪婪指数框架部件
        fear_greed_layout = QHBoxLayout(fear_greed_frame)  # 创建水平布局管理器
        fear_greed_layout.setContentsMargins(0, 0, 0, 0)  # 设置布局的边距为0
        fear_greed_layout.setAlignment(Qt.AlignCenter)  # 设置布局中的组件居中对齐
        
        fear_greed_label = QLabel("Fear & Greed:")  # 创建恐惧贪婪指数标签
        fear_greed_label.setFont(self.app_font)  # 设置标签字体
        fear_greed_label.setStyleSheet("color: #FFD700;")  # 设置标签文本颜色为金色
        
        self.fear_greed_value = QLabel()  # 创建恐惧贪婪指数值标签
        self.fear_greed_value.setFont(self.app_font)  # 设置标签字体
        self.fear_greed_value.setStyleSheet("color: #FFD700;")  # 设置标签文本颜色为金色
        
        self.fear_greed_class = QLabel()  # 创建恐惧贪婪指数分类标签
        self.fear_greed_class.setFont(self.app_font)  # 设置标签字体
        
        fear_greed_layout.addWidget(fear_greed_label)  # 将恐惧贪婪指数标签添加到布局
        fear_greed_layout.addWidget(self.fear_greed_value)  # 将恐惧贪婪指数值标签添加到布局
        fear_greed_layout.addWidget(self.fear_greed_class)  # 将恐惧贪婪指数分类标签添加到布局
        
        # 4. 最后更新时间
        self.time_label = QLabel()  # 创建最后更新时间标签
        self.time_label.setFont(self.app_font)  # 设置标签字体
        self.time_label.setStyleSheet("color: #FFFFFF;")  # 设置标签文本颜色为白色
        self.time_label.setAlignment(Qt.AlignCenter)  # 设置标签文本居中对齐
        
        # 5. 创建价格显示容器
        self.price_container = QWidget()  # 创建价格显示容器部件
        self.price_layout = QVBoxLayout(self.price_container)  # 创建垂直布局管理器
        self.price_layout.setContentsMargins(0, 0, 0, 0)  # 设置布局的边距为0
        self.price_layout.setSpacing(2)  # 减小价格组件之间的间距为2像素
        
        # 创建并添加代币价格组件
        self.create_token_widgets()
        
        # 添加所有组件到主布局
        main_layout.addWidget(control_bar)  # 将控制栏添加到主布局
        main_layout.addWidget(self.fear_greed_time)  # 将恐惧贪婪指数时间标签添加到主布局
        main_layout.addWidget(fear_greed_frame)  # 将恐惧贪婪指数框架添加到主布局
        main_layout.addWidget(self.time_label)  # 将最后更新时间标签添加到主布局
        main_layout.addWidget(self.price_container)  # 将价格容器添加到主布局
        
        # 设置固定宽度，高度将根据代币数量动态调整
        self.set_dynamic_window_size()
        
        # 设置窗口置顶
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)  # 设置窗口置顶标志
        
        # 显示当前状态
        self.update_pin_button_status()  # 更新置顶按钮状态
        self.update_autostart_button_status()  # 更新自启动按钮状态
    
    def set_dynamic_window_size(self):
        """根据代币数量动态设置窗口大小"""
        # 基础高度（控制栏、恐惧贪婪指数、时间标签等）
        base_height = 110
        
        # 每个代币项高度（包含间距）
        token_height = 18
        
        # 根据代币数量计算总高度
        total_height = base_height + (len(self.user_tokens) * token_height)
        
        # 设置最小和最大高度限制
        min_height = 170  # 最小高度
        max_height = 400  # 最大高度（避免窗口过大）
        
        # 确保高度在合理范围内
        if total_height < min_height:
            total_height = min_height
        elif total_height > max_height:
            total_height = max_height
            
        # 固定宽度，动态高度
        self.setFixedSize(260, total_height)
        
        logging.debug(f'窗口大小已调整: 宽度=260, 高度={total_height} (代币数量: {len(self.user_tokens)})')
    
    def create_token_widgets(self):
        """创建代币价格显示组件，并根据设置调整标签"""
        logging.debug("执行 create_token_widgets") # Add log
        # 清空现有组件
        for widget in self.token_widgets.values():
            self.price_layout.removeWidget(widget)
            widget.deleteLater()
        self.token_widgets.clear()

        # 根据用户代币列表创建组件
        for token in self.user_tokens:
            token_id = token["id"]
            token_symbol = token["symbol"].upper()

            # 检查是否需要显示为 BERA 比率
            display_ratio = token.get("display_as_bera_ratio", False)
            # --- Add Logging Here ---
            logging.debug(f"  为 {token_symbol} 创建 widget: display_as_bera_ratio = {display_ratio}")
            # --- End Add Logging ---

            # 设置标签文本
            if display_ratio:
                label_text = f"{token_symbol}/BERA:" # 比率模式标签
            else:
                label_text = f"{token_symbol}:" # 正常美元价格标签

            widget = CryptoPriceWidget(label_text, self.app_font)
            self.token_widgets[token_id] = widget
            self.price_layout.addWidget(widget)

        self.set_dynamic_window_size()
    
    def update_pin_button_status(self):
        """更新置顶按钮显示状态，根据当前置顶状态设置按钮样式"""
        logging.debug(f'更新置顶按钮状态: is_topmost={self.is_topmost}')  # 记录更新按钮状态的调试信息
        
        if self.is_topmost:
            # 置顶状态 - 明亮金色，正常大小
            style = """
                QPushButton {
                    border: none;
                    color: #FFD700;
                    font-weight: bold;
                    font-size: 16px;
                    padding: 2px;
                    margin: 0px;
                    background-color: transparent;
                }
                QPushButton:hover {
                    color: #FFA500;
                }
            """  # 置顶状态下的按钮样式：无边框，金色文本，粗体，悬停时为橙色
        else:
            # 非置顶状态 - 暗淡灰色，图标变小
            style = """
                QPushButton {
                    border: none;
                    color: #808080;
                    font-weight: normal;
                    font-size: 12px;
                    padding: 2px;
                    margin: 0px;
                    background-color: transparent;
                }
                QPushButton:hover {
                    color: #A9A9A9;
                }
            """
        
        self.pin_button.setStyleSheet(style)
        self.pin_button.update()  # 强制更新按钮外观
        logging.debug(f'按钮样式已更新: is_topmost={self.is_topmost}')
    
    # 窗口拖动相关方法
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging = False
    
    def toggle_topmost(self):
        """切换窗口置顶状态"""
        logging.debug('切换置顶状态')
        self.is_topmost = not self.is_topmost
        
        # Windows平台使用Win32 API直接设置窗口属性
        if sys.platform == 'win32' and HAS_WIN32API:
            try:
                # 获取窗口句柄
                hwnd = self.winId()
                
                if hwnd:
                    # 获取当前窗口样式
                    style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    
                    if self.is_topmost:
                        # 添加TOPMOST标志
                        new_style = style | win32con.WS_EX_TOPMOST
                        # 设置窗口为TOPMOST
                        win32gui.SetWindowPos(
                            hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                        )
                    else:
                        # 移除TOPMOST标志
                        new_style = style & ~win32con.WS_EX_TOPMOST
                        # 设置窗口为非TOPMOST
                        win32gui.SetWindowPos(
                            hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                        )
                    
                    # 应用新样式
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
                    
                    logging.info("使用Win32 API设置窗口置顶状态")
                else:
                    logging.error("无法获取窗口句柄")
                    self._toggle_topmost_qt()  # 回退到Qt方式
                    
            except Exception as e:
                logging.error(f"使用Win32 API设置窗口置顶状态失败: {e}")
                # 回退到Qt方式
                self._toggle_topmost_qt()
        else:
            # 非Windows平台或未安装win32gui，使用Qt方式
            self._toggle_topmost_qt()
        
        # 更新按钮状态显示
        self.update_pin_button_status()
        
        # 显示成功提示
        if self.is_topmost:
            QToolTip.showText(self.pin_button.mapToGlobal(self.pin_button.rect().bottomLeft()), 
                            "窗口已置顶", self)
        else:
            QToolTip.showText(self.pin_button.mapToGlobal(self.pin_button.rect().bottomLeft()), 
                            "窗口取消置顶", self)
        
        logging.info(f'置顶状态已切换: is_topmost={self.is_topmost}')

    def _toggle_topmost_qt(self):
        """使用Qt方式切换窗口置顶状态（有闪烁）"""
        # 保存当前窗口位置
        current_pos = self.pos()
        
        # 使用Qt的窗口标志方式设置置顶
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.is_topmost)
        
        # 恢复窗口位置并显示
        self.move(current_pos)
        self.show()

    def get_prices(self):
        """从 CoinGecko API 获取所有代币的价格数据"""
        try:
            # 检查代币列表是否为空
            if not self.user_tokens:
                logging.warning("用户代币列表为空")
                return {}
            
            # 获取所有代币ID
            token_ids = [token["id"] for token in self.user_tokens]
            token_ids_str = ",".join(token_ids)
            
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": token_ids_str,
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            }
            
            logging.debug(f'请求价格数据: {url}')
            logging.debug(f'请求参数: {params}')
            
            try:
                response = requests.get(url, params=params, timeout=10)  # 添加超时
                
                if response.status_code != 200:
                    logging.error(f'价格数据请求失败: HTTP {response.status_code}')
                    logging.debug(f'错误响应: {response.text}')
                    return {}
                    
                data = response.json()
                logging.debug(f'获取到价格数据: {json.dumps(data, indent=2)}')
                
                # 验证数据有效性
                if not isinstance(data, dict):
                    logging.error(f'无效的价格数据格式: {type(data)}')
                    return {}
                
                # 记录哪些代币获取到了数据，哪些没有
                for token in self.user_tokens:
                    token_id = token["id"]
                    if token_id in data:
                        logging.debug(f'成功获取 {token["symbol"]} 价格数据')
                    else:
                        logging.warning(f'未能获取 {token["symbol"]} 价格数据')
                        
                # 尝试单独获取缺失的代币
                missing_tokens = [token for token in self.user_tokens if token["id"] not in data]
                if missing_tokens:
                    logging.info(f'尝试单独获取 {len(missing_tokens)} 个缺失代币的价格')
                    for token in missing_tokens:
                        try:
                            single_params = {
                                "ids": token["id"],
                                "vs_currencies": "usd",
                                "include_24hr_change": "true"
                            }
                            single_response = requests.get(url, params=single_params, timeout=5)
                            if single_response.status_code == 200:
                                single_data = single_response.json()
                                if token["id"] in single_data:
                                    data[token["id"]] = single_data[token["id"]]
                                    logging.info(f'单独获取 {token["symbol"]} 价格成功')
                                else:
                                    logging.warning(f'单独获取 {token["symbol"]} 价格返回空数据')
                            else:
                                logging.warning(f'单独获取 {token["symbol"]} 价格失败: HTTP {single_response.status_code}')
                        except Exception as e:
                            logging.error(f'单独获取 {token["symbol"]} 价格时出错: {e}')
                
                return data
                
            except requests.RequestException as e:
                logging.error(f'请求价格数据时网络错误: {e}')
                return {}
                
        except Exception as e:
            logging.error(f'获取价格数据时发生错误: {e}')
            import traceback
            logging.error(traceback.format_exc())
            return {}

    def get_fear_greed_index(self, force_update=False):
        """从 CoinMarketCap API 获取恐惧和贪婪指数，缓存逻辑基于隔日8点更新"""
        with self.fear_greed_lock:
            now = datetime.now()
            should_fetch = False
            reason = ""

            if force_update:
                should_fetch = True
                reason = "强制更新"
            elif self.fear_greed_cache is None or self.fear_greed_last_update is None:
                should_fetch = True
                reason = "缓存为空或无时间戳"
            else:
                # 计算下次应该更新的时间点：上次更新日期的第二天早上8点
                last_update_date = self.fear_greed_last_update.date()
                next_day_date = last_update_date + timedelta(days=1)
                # 使用 datetime.combine 确保时间是准确的 8:00:00
                target_update_datetime = datetime.combine(next_day_date, datetime.min.time().replace(hour=8))

                if now >= target_update_datetime:
                    should_fetch = True
                    reason = f"当前时间 {now.strftime('%Y-%m-%d %H:%M')} >= 目标更新时间 {target_update_datetime.strftime('%Y-%m-%d %H:%M')}"
                else:
                    reason = f"当前时间 {now.strftime('%Y-%m-%d %H:%M')} < 目标更新时间 {target_update_datetime.strftime('%Y-%m-%d %H:%M')}"

            logging.debug(f'检查是否获取新指数: {should_fetch}. 原因: {reason}')

            if not should_fetch:
                logging.debug('使用缓存的恐惧贪婪指数数据')
                return self.fear_greed_cache

            # --- 如果需要获取，则执行以下代码 ---
            logging.info('尝试获取新的恐惧贪婪指数数据...')
            try:
                if not self.api_config.get('coinmarketcap', {}).get('enabled', False): # 更安全的检查
                    logging.warning('CoinMarketCap API 未启用')
                    return self.fear_greed_cache # 获取失败时返回旧缓存

                api_key = os.getenv('CMC_API_KEY')
                if not api_key:
                    logging.error('未找到 CoinMarketCap API 密钥')
                    return self.fear_greed_cache # 获取失败时返回旧缓存

                # API 请求部分保持不变
                url = f"{self.api_config['coinmarketcap']['base_url']}{self.api_config['coinmarketcap']['endpoints']['fear_greed']}"
                headers = {'X-CMC_PRO_API_KEY': api_key}
                params = self.api_config['coinmarketcap']['params']['fear_greed']

                logging.debug(f'请求恐惧贪婪指数: {url}')
                response = requests.get(url, headers=headers, params=params, timeout=10) # 添加超时

                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and len(data['data']) > 0:
                        new_data = data['data'][0]
                        self.fear_greed_cache = new_data
                        self.fear_greed_last_update = now # 使用当前的获取时间作为下次判断的基准
                        logging.info(f'恐惧贪婪指数更新成功: {self.fear_greed_cache["value"]} ({self.fear_greed_cache["value_classification"]})')
                        return self.fear_greed_cache
                    else:
                        logging.warning('恐惧贪婪指数 API 返回数据为空')
                        return self.fear_greed_cache # 获取失败时返回旧缓存
                else:
                    logging.error(f'恐惧贪婪指数请求失败: HTTP {response.status_code}')
                    logging.debug(f'错误响应: {response.text}')
                    return self.fear_greed_cache # 获取失败时返回旧缓存

            except requests.RequestException as e:
                 logging.error(f'请求恐惧贪婪指数时网络错误: {e}')
                 return self.fear_greed_cache # 获取失败时返回旧缓存
            except Exception as e:
                logging.error(f'获取恐惧贪婪指数时发生错误: {e}')
                import traceback
                logging.error(traceback.format_exc())
                return self.fear_greed_cache # 获取失败时返回旧缓存

    @Slot()
    def fetch_data(self):
        """获取数据（在单独线程中执行）"""
        Thread(target=self._fetch_data_thread, daemon=True).start()
    
    def _fetch_data_thread(self):
        """在线程中获取数据"""
        try:
            logging.debug('开始获取数据...')

            # 获取价格数据
            price_data = self.get_prices()

            # --- 简化: 直接调用 get_fear_greed_index ---
            fear_greed_data = self.get_fear_greed_index() # 不再需要 force_update

            # 存储数据以供UI更新 (fear_greed_data 可能是来自缓存或新获取的)
            self.price_data = price_data
            with self.fear_greed_lock:
                self.fear_greed_data = fear_greed_data # 更新 UI 使用的数据
            self.current_time = datetime.now().strftime("%H:%M:%S")

            # 触发UI更新信号
            logging.debug('触发UI更新信号')
            self.data_updated.emit()

        except Exception as e:
            logging.error(f"数据获取错误: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    @Slot()
    def update_ui(self):
        """更新UI显示 (支持美元价格和BERA比率模式)"""
        try:
            self.time_label.setText(f"Last Updated: {self.current_time}")
            logging.debug("执行 update_ui") # Add log

            if hasattr(self, 'price_data') and self.price_data:
                bera_price_usd = None
                if self.BERA_ID in self.price_data and "usd" in self.price_data[self.BERA_ID]:
                    bera_price_usd = self.price_data[self.BERA_ID]["usd"]
                    if bera_price_usd is None or bera_price_usd <= 0:
                        logging.warning(f"BERA价格无效 ({bera_price_usd})，无法计算比率。")
                        bera_price_usd = None

                for token in self.user_tokens:
                    try:
                        token_id = token["id"]
                        token_symbol = token["symbol"].upper()

                        if token_id not in self.token_widgets:
                            logging.warning(f"update_ui: 找不到组件 for {token_id}")
                            continue

                        widget = self.token_widgets[token_id]
                        display_ratio = token.get("display_as_bera_ratio", False)
                        # --- Add Logging Here ---
                        logging.debug(f"  更新 {token_symbol}: display_as_bera_ratio = {display_ratio}")
                        # --- End Add Logging ---

                        # 获取当前代币的美元价格和变化率 (保持不变)
                        token_price_data = self.price_data.get(token_id)
                        token_price_usd = None
                        change_usd = None
                        change_text = "--.--%"
                        if token_price_data and "usd" in token_price_data:
                            token_price_usd = token_price_data["usd"]
                            change_usd = token_price_data.get("usd_24h_change")
                            if change_usd is not None: change_text = f"{change_usd:+.2f}%"
                            else: logging.debug(f"{token_symbol} 变化为 null")

                        # --- 开始判断显示模式 ---
                        if display_ratio:
                            # --- 比率显示模式 ---
                            # ... (ratio calculation logic remains the same) ...
                            if token_price_usd is not None and bera_price_usd is not None:
                                try:
                                    ratio = (token_price_usd / bera_price_usd) * 100
                                    if ratio < 1: ratio_text = f" {ratio:.4f}%"
                                    elif ratio < 10: ratio_text = f" {ratio:.2f}%"
                                    else: ratio_text = f" {ratio:.1f}%"
                                    widget.update_price(ratio_text, change_text)
                                    # logging.debug(f"    更新 {token_symbol} 比率: {ratio_text}") # Keep or remove this inner log
                                except ZeroDivisionError: widget.update_price("Error", "--.--%"); logging.error(f"计算 {token_symbol}/BERA 比率时除零错误。")
                                except Exception as e: widget.update_price("Error", "--.--%"); logging.error(f"计算 {token_symbol}/BERA 比率时出错: {e}")
                            elif bera_price_usd is None: widget.update_price("No BERA", change_text); logging.debug(f"无法计算 {token_symbol}/BERA 比率，BERA价格不可用")
                            else: widget.update_price("N/A", "--.--%"); logging.debug(f"无法计算 {token_symbol}/BERA 比率，{token_symbol}价格不可用")
                        else:
                            # --- 美元价格显示模式 ---
                            # ... (USD price display logic remains the same) ...
                            if token_price_usd is not None:
                                try:
                                    if token_id in [self.BTC_ID, self.ETH_ID]: price_text = f" ${token_price_usd:,.0f}"
                                    else:
                                        if token_price_usd < 0.001: price_text = f" ${token_price_usd:.6f}"
                                        elif token_price_usd < 0.01: price_text = f" ${token_price_usd:.5f}"
                                        elif token_price_usd < 0.1: price_text = f" ${token_price_usd:.4f}"
                                        elif token_price_usd < 1: price_text = f" ${token_price_usd:.3f}"
                                        elif token_price_usd < 1000: price_text = f" ${token_price_usd:.2f}"
                                        else: price_text = f" ${token_price_usd:,.2f}"
                                    widget.update_price(price_text, change_text)
                                    # logging.debug(f"    更新 {token_symbol} 价格: {price_text}") # Keep or remove
                                except Exception as e: widget.update_price("$--.--", "--.--%"); logging.error(f"格式化 {token_symbol} 价格时出错: {e}")
                            else: widget.update_price("$--.--", "--.--%"); logging.debug(f"找不到 {token_symbol} 的价格数据")

                    except Exception as token_error:
                        logging.error(f"处理代币 {token.get('symbol', '未知')} 时发生错误: {token_error}")
                        try:
                            if token_id in self.token_widgets: self.token_widgets[token_id].update_price("$Error$", "--.--%")
                        except Exception: pass
            else:
                for token_id, widget in self.token_widgets.items(): widget.update_price("$--.--", "--.--%")
                logging.warning("update_ui: 没有可用的价格数据")

            self.update_fear_greed_display()

        except Exception as e:
            logging.error(f"更新界面时出错: {e}")
            import traceback; logging.error(traceback.format_exc())
    
    def update_fear_greed_display(self):
        """更新恐惧和贪婪指数显示"""
        if not hasattr(self, 'fear_greed_data') or not self.fear_greed_data:
            self.fear_greed_value.setText(" --")
            self.fear_greed_class.setText("(Unknown)")
            self.fear_greed_time.setText("")
            return
        
        try:
            fear_greed_data = self.fear_greed_data
            value = int(fear_greed_data['value'])
            classification = fear_greed_data['value_classification']
            
            # 处理时间戳
            timestamp = fear_greed_data.get('timestamp', '')
            time_str = "Unknown time"
            tz_display = ""
            
            try:
                # 获取当前系统时区偏移
                local_now = datetime.now().astimezone()
                utc_offset = local_now.utcoffset()
                if utc_offset:
                    # 计算小时偏移
                    offset_hours = int(utc_offset.total_seconds() / 3600)
                    # 格式化为 (+8) 或 (-5) 这样的格式
                    tz_display = f"({'+' if offset_hours >= 0 else ''}{offset_hours})"
                else:
                    tz_display = "(+0)"  # UTC
                
                # 尝试将时间戳转换为可读格式
                if timestamp:
                    # 是的，API返回的时间戳格式可能有多种：
                    # 1. Unix时间戳（整数，表示从1970年1月1日起的秒数）
                    # 2. ISO 8601格式的字符串（如：2023-04-15T08:30:00Z 或 2023-04-15T08:30:00+00:00）
                    # 3. 其他自定义格式的日期时间字符串
                    
                    # 处理Unix时间戳（整数秒）
                    if str(timestamp).isdigit():
                        timestamp_int = int(timestamp)
                        # 检查是否是合理的Unix时间戳（秒）
                        if timestamp_int > 1000000000:  # 大约是2001年以后的时间戳
                            # 转换为本地时区的日期时间
                            dt = datetime.fromtimestamp(timestamp_int)
                            time_str = dt.strftime("%m-%d %H:%M")
                        else:
                            time_str = f"Timestamp: {timestamp}"
                    # 处理ISO格式时间字符串
                    elif 'T' in str(timestamp) and ('Z' in str(timestamp) or '+' in str(timestamp)):
                        # 处理ISO格式时间字符串
                        ts_str = str(timestamp)
                        # 如果以Z结尾，替换为+00:00（UTC）
                        if ts_str.endswith('Z'):
                            ts_str = ts_str.replace('Z', '+00:00')
                        
                        # 解析ISO格式时间字符串
                        try:
                            dt = datetime.fromisoformat(ts_str)
                            # 转换为本地时区
                            local_dt = dt.astimezone()
                            time_str = local_dt.strftime("%m-%d %H:%M")
                        except ValueError:
                            # 尝试使用更灵活的parser解析
                            try:
                                dt = parser.parse(ts_str)
                                local_dt = dt.astimezone()
                                time_str = local_dt.strftime("%m-%d %H:%M")
                            except Exception:
                                time_str = f"Date: {timestamp}"
                    else:
                        # 尝试使用dateutil解析任意格式的日期字符串
                        try:
                            dt = parser.parse(str(timestamp))
                            local_dt = dt.astimezone()
                            time_str = local_dt.strftime("%m-%d %H:%M")
                        except Exception:
                            time_str = f"Date: {timestamp}"
            except Exception as e:
                logging.error(f"处理时间戳时出错: {e}")
                time_str = f"Date: {timestamp}"
                tz_display = ""
            
            # 根据分类设置颜色
            if classification == "Extreme fear":
                color = "#FF0000"  # 极度恐惧 - 红色
            elif classification == "Fear":
                color = "#FF7F00"  # 恐惧 - 橙色
            elif classification == "Neutral":
                color = "#FFFF00"  # 中性 - 黄色
            elif classification == "Greed":
                color = "#7FFF00"  # 贪婪 - 淡绿色
            elif classification == "Extreme greed":
                color = "#00FF00"  # 极度贪婪 - 绿色
            else:
                color = "#FFFFFF"  # 未知 - 白色
            
            # 更新UI显示
            self.fear_greed_value.setText(f" {value}")
            self.fear_greed_class.setText(f"({classification})")
            self.fear_greed_class.setStyleSheet(f"color: {color};")
            
            # 显示时间和时区偏移
            if tz_display:
                self.fear_greed_time.setText(f"Last Updated: {time_str} {tz_display}")
            else:
                self.fear_greed_time.setText(f"Last Updated: {time_str}")
            
        except Exception as e:
            logging.error(f"更新恐惧贪婪指数显示时出错: {e}")
            import traceback
            logging.error(traceback.format_exc())
            self.fear_greed_value.setText(" --")
            self.fear_greed_class.setText("(Unknown)")
            self.fear_greed_time.setText("")

    def _write_autostart_registry(self, enable: bool):
        """Helper function to write or delete the registry key. Returns True on success."""
        if sys.platform != 'win32':
            return False

        app_name = "BeraHelper"
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = reg.HKEY_CURRENT_USER

        try:
            if enable:
                # --- Add registry entry ---
                logging.info(f"写入注册表: 启用自启动 '{app_name}'")
                app_path_raw = os.path.abspath(sys.argv[0])
                if not os.path.exists(app_path_raw):
                    raise FileNotFoundError(f"找不到应用程序路径: {app_path_raw}")

                if app_path_raw.lower().endswith('.py'):
                    pythonw_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                    if not os.path.exists(pythonw_path):
                        logging.warning(f"找不到 pythonw.exe，将使用 python.exe")
                        pythonw_path = sys.executable
                    registry_value = f'"{pythonw_path}" "{app_path_raw}" --minimized --no-splash --no-log'
                else:
                    registry_value = f'"{app_path_raw}" --minimized --no-splash --no-log'

                logging.debug(f"写入注册表的值: {registry_value}")
                reg_key = reg.OpenKey(key, key_path, 0, reg.KEY_WRITE)
                try:
                    reg.SetValueEx(reg_key, app_name, 0, reg.REG_SZ, registry_value)
                    logging.info("成功写入注册表项。")
                finally:
                    reg.CloseKey(reg_key)
            else:
                # --- Delete registry entry ---
                logging.info(f"写入注册表: 禁用自启动 '{app_name}'")
                try:
                    reg_key = reg.OpenKey(key, key_path, 0, reg.KEY_WRITE)
                    try:
                        reg.DeleteValue(reg_key, app_name)
                        logging.info("成功删除注册表项。")
                    except FileNotFoundError:
                        logging.warning(f"尝试删除注册表项 '{app_name}' 时发现它已不存在。")
                    finally:
                        reg.CloseKey(reg_key)
                except FileNotFoundError:
                     logging.warning(f"尝试打开注册表键以删除 '{app_name}' 时，键路径不存在。")


            return True # Indicate success

        except PermissionError as e:
            logging.error(f"注册表操作权限错误: {e}")
            QMessageBox.warning(self, "权限不足", f"注册表操作失败: {e}\n\n可能需要管理员权限。")
            return False
        except Exception as e:
            logging.error(f"注册表操作时发生错误: {e}")
            import traceback
            logging.error(traceback.format_exc())
            QMessageBox.warning(self, "错误", f"注册表操作时发生错误:\n{e}")
            return False

    def _apply_pending_autostart_setting(self):
        """Applies the pending autostart setting to the registry."""
        if self.pending_autostart_state is not None:
            logging.info(f"延迟计时器触发，应用挂起的自启动设置: {self.pending_autostart_state}")
            success = self._write_autostart_registry(enable=self.pending_autostart_state)
            if success:
                self.pending_autostart_state = None # Reset pending state only if write succeeded
                # Optionally re-verify and update button based on actual state now
                # self.update_autostart_button_status()
            else:
                # If write failed, keep pending state so maybe exit save can try again? Or reset?
                # Let's reset for now to avoid potential loops if permission is always denied.
                logging.warning("应用挂起的自启动设置失败，重置挂起状态。")
                self.pending_autostart_state = None
                # Update button back to actual state
                self.update_autostart_button_status()


    def update_autostart_button_status(self):
        """更新自启动按钮状态 (反映挂起状态优先)"""
        try:
            # Determine the state to display
            actual_state = self.is_autostart_enabled() # Check actual registry state
            display_state = self.pending_autostart_state if self.pending_autostart_state is not None else actual_state
            logging.debug(f'更新自启动按钮状态: 实际={actual_state}, 挂起={self.pending_autostart_state}, 显示={display_state}')

            if display_state:
                # Style for ENABLED (or pending enable)
                style = """
                    QPushButton { /* Style for enabled */ }
                    /* ... (copy enabled style from previous version) ... */
                    QPushButton {
                        border: none;
                        color: #FFD700;
                        font-weight: bold;
                        padding: 2px;
                        margin: 0px;
                        background-color: transparent;
                    }
                    QPushButton:hover {
                        color: #FFA500;
                    }
                """
                tooltip = "开机自启动 (已启用)"
                if self.pending_autostart_state is True:
                     tooltip = "开机自启动 (将在1分钟后或退出时启用)"
            else:
                # Style for DISABLED (or pending disable)
                style = """
                    QPushButton { /* Style for disabled */ }
                    /* ... (copy disabled style from previous version) ... */
                    QPushButton {
                        border: none;
                        color: #808080;
                        font-weight: normal;
                        padding: 2px;
                        margin: 0px;
                        background-color: transparent;
                    }
                    QPushButton:hover {
                        color: #A9A9A9;
                    }
                """
                tooltip = "开机自启动 (已禁用)"
                if self.pending_autostart_state is False:
                    tooltip = "开机自启动 (将在1分钟后或退出时禁用)"

            self.autostart_button.setStyleSheet(style)
            self.autostart_button.setToolTip(tooltip) # Update tooltip as well
            self.autostart_button.update()
        except Exception as e:
            logging.error(f"更新自启动按钮状态失败: {e}")

    def is_autostart_enabled(self):
        """检查是否已通过注册表启用开机自启动"""
        if sys.platform != 'win32':
            return False

        app_name = "BeraHelper" # 应用在注册表中的名称
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        try:
            # 打开注册表项 HKEY_CURRENT_USER
            key = reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_READ)
            try:
                # 尝试查询名为 app_name 的值
                reg.QueryValueEx(key, app_name)
                logging.debug(f"注册表自启动项 '{app_name}' 存在。")
                return True # 如果查询成功，说明已存在
            except FileNotFoundError:
                logging.debug(f"注册表自启动项 '{app_name}' 不存在。")
                return False # 如果查询时找不到值，说明不存在
            finally:
                reg.CloseKey(key) # 确保关闭注册表项
        except Exception as e:
            logging.error(f"检查注册表自启动状态失败: {e}")
            return False # 发生任何其他错误，都认为未启用

    def toggle_autostart(self):
        """切换挂起的自启动状态，并启动延迟保存计时器"""
        if sys.platform != 'win32':
             QMessageBox.warning(self, "不支持", "此功能仅支持 Windows。")
             return

        if self.autostart_lock:
            logging.debug("自启动操作正在进行中，忽略重复点击")
            return

        self.autostart_lock = True
        try:
            # Determine the *next* state based on the *current displayed* state
            # This handles the case where a pending state exists
            actual_state = self.is_autostart_enabled()
            current_display_state = self.pending_autostart_state if self.pending_autostart_state is not None else actual_state
            next_state = not current_display_state

            self.pending_autostart_state = next_state
            logging.info(f"切换挂起的自启动状态为: {self.pending_autostart_state}")

            # 1. 立即更新按钮外观和它存储的 ToolTip 内容 (反映挂起状态，用于鼠标悬停)
            self.update_autostart_button_status() # 这会设置正确的悬停提示

            # --- 2. 强制显示 *不同的* ToolTip 作为即时反馈 (反映切换动作) ---
            # 根据 next_state 决定即时反馈的文本
            if next_state:
                immediate_feedback_text = "已切换为启用自启动"
            else:
                immediate_feedback_text = "已切换为禁用自启动"

            # 使用上面确定的文本显示即时 Tooltip
            if immediate_feedback_text: # 确保文本不是空的
                QToolTip.showText(
                    # --- Positional arguments (required) ---
                    self.autostart_button.mapToGlobal(self.autostart_button.rect().bottomLeft()), # pos
                    immediate_feedback_text, # <--- 使用区分状态的即时反馈文本
                    # --- Keyword arguments (optional, after '/') ---
                    w=self.autostart_button,  # Use keyword 'w' for the widget
                    msecShowTime=2000         # Use keyword 'msecShowTime' for duration
                )
            # --- 即时反馈结束 ---

            # 3. 启动/重启 1 分钟的延迟保存计时器
            logging.debug("启动/重启自启动设置延迟保存计时器 (60秒)")
            self.autostart_save_timer.start() # Default interval is 60000ms

        except Exception as e:
             # This part should ideally not fail, but just in case
             logging.error(f"切换挂起自启动状态时出错: {e}")
             QMessageBox.warning(self, "错误", f"切换自启动状态时出错:\n{e}")
             # Reset pending state on error?
             self.pending_autostart_state = None
             self.update_autostart_button_status() # Revert button to actual state
        finally:
            # Use a shorter lock just to prevent UI race conditions,
            # the 1-min timer handles the debouncing for registry writes.
            QTimer.singleShot(1000, self.release_autostart_lock) # 1 second lock

    def release_autostart_lock(self):
        """释放自启动操作锁"""
        self.autostart_lock = False
        logging.debug("自启动操作锁已释放")

    def closeEvent(self, event: QCloseEvent):
        """Override close event to save pending autostart setting."""
        logging.info("接收到关闭事件，检查挂起的自启动设置...")
        # Stop the timer first to prevent race condition
        self.autostart_save_timer.stop()
        logging.debug("延迟保存计时器已停止。")

        # Apply pending setting if exists
        self._apply_pending_autostart_setting()

        logging.info("允许窗口关闭。")
        event.accept() # Allow the window to close

    def show_token_manager(self):
        """显示代币管理对话框 (所有代币都可切换显示模式，操作副本保证取消有效)"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                      QListWidget, QPushButton, QLineEdit,
                                      QLabel, QListWidgetItem)
        from PySide6.QtCore import QTimer, Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("代币管理")
        dialog.setMinimumSize(400, 500)

        layout = QVBoxLayout(dialog)
        # --- UI 元素定义 (保持不变) ---
        search_layout = QHBoxLayout(); search_label = QLabel("搜索币种:"); search_input = QLineEdit(); search_input.setPlaceholderText("输入币种名称或代号..."); search_layout.addWidget(search_label); search_layout.addWidget(search_input)
        available_label = QLabel("可用代币: (双击添加)"); available_list = QListWidget(); available_list.setSelectionMode(QListWidget.SingleSelection)
        selected_label = QLabel("已选代币: (双击移除)"); selected_label.setToolTip("勾选代币名称前的复选框，可将其显示切换为与 BERA 的比率 (%)"); selected_list = QListWidget()
        button_layout = QHBoxLayout(); add_button = QPushButton("添加 ➡"); remove_button = QPushButton("⬅ 移除"); move_up_button = QPushButton("⬆ 上移"); move_down_button = QPushButton("⬇ 下移"); button_layout.addWidget(add_button); button_layout.addWidget(remove_button); button_layout.addWidget(move_up_button); button_layout.addWidget(move_down_button)
        dialog_buttons = QHBoxLayout(); ok_button = QPushButton("确定"); cancel_button = QPushButton("取消"); dialog_buttons.addStretch(); dialog_buttons.addWidget(ok_button); dialog_buttons.addWidget(cancel_button)
        layout.addLayout(search_layout); layout.addWidget(available_label); layout.addWidget(available_list); layout.addLayout(button_layout); layout.addWidget(selected_label); layout.addWidget(selected_list); layout.addLayout(dialog_buttons)


        # --- 1. 创建副本和本地字典 (保持不变) ---
        try:
             dialog_user_tokens = copy.deepcopy(self.user_tokens)
             logging.debug("创建 dialog_user_tokens 副本成功")
        except Exception as copy_err:
             logging.error(f"创建用户代币列表副本失败: {copy_err}")
             QMessageBox.critical(self, "错误", "无法打开代币管理器：创建数据副本失败。")
             return
        selected_tokens_dict = {token["id"]: token for token in dialog_user_tokens}


        # --- 2. 定义核心辅助函数 (调整顺序) ---
        search_timer = QTimer(); search_timer.setSingleShot(True); search_timer.setInterval(500)

        def fill_available_list(): # <--- 定义移到前面
            """填充可用代币列表 (使用 self.available_tokens)"""
            available_list.clear(); search_text = search_input.text().lower()
            logging.debug(f"fill_available_list: 搜索文本='{search_text}'")
            count = 0
            for token in self.available_tokens:
                if token["id"] in selected_tokens_dict: continue
                token_id_lower = token["id"].lower()
                token_symbol_lower = token["symbol"].lower()
                token_name_lower = token["name"].lower()
                if search_text and not (
                    search_text in token_id_lower or
                    search_text in token_symbol_lower or
                    search_text in token_name_lower):
                    continue
                item = QListWidgetItem(f"{token['name']} ({token['symbol'].upper()})")
                item.setData(Qt.UserRole, token)
                available_list.addItem(item)
                count += 1
            logging.debug(f"fill_available_list 完成，添加了 {count} 项")

        def fill_selected_list(): # <--- 定义移到前面
            """填充已选代币列表 (使用 dialog_user_tokens)"""
            selected_list.clear()
            logging.debug("fill_selected_list: 使用 dialog_user_tokens 填充列表")
            for token_data in dialog_user_tokens:
                item_text = f"{token_data['name']} ({token_data['symbol'].upper()})"
                item = QListWidgetItem(item_text)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                initial_state = token_data.get("display_as_bera_ratio", False)
                item.setCheckState(Qt.Checked if initial_state else Qt.Unchecked)
                item.setData(Qt.UserRole, token_data)
                selected_list.addItem(item)
            logging.debug(f"fill_selected_list 完成，添加了 {selected_list.count()} 项")

        def delayed_search(): # <--- 定义移到前面
            """延迟执行搜索"""
            logging.debug("delayed_search: 触发搜索计时器")
            search_timer.start()

        def update_model_from_list_state(): # <--- 定义移到前面
            """将列表状态同步到 dialog_user_tokens 副本"""
            logging.debug("同步列表复选框状态到 dialog_user_tokens 副本...")
            token_map = {token['id']: token for token in dialog_user_tokens}
            for i in range(selected_list.count()):
                item = selected_list.item(i)
                linked_token_data = item.data(Qt.UserRole)
                if linked_token_data and isinstance(linked_token_data, dict) and 'id' in linked_token_data:
                    token_id = linked_token_data['id']
                    if token_id in token_map:
                        if item.flags() & Qt.ItemIsUserCheckable:
                            current_check_state = (item.checkState() == Qt.Checked)
                            token_map[token_id]['display_as_bera_ratio'] = current_check_state
                    else: logging.warning(f"同步状态时在副本中找不到ID: {token_id}")
                else: logging.warning(f"列表项 {i} 没有有效数据")


        # --- 3. 定义动作/事件处理函数 (现在可以安全调用上面的辅助函数了) ---
        def available_double_clicked(item):
            token_data = item.data(Qt.UserRole)
            add_token_by_data(copy.deepcopy(token_data))

        def selected_double_clicked(item):
            token_data = item.data(Qt.UserRole)
            if token_data: remove_token_by_data(token_data)

        def add_token_by_data(token_data):
            nonlocal dialog_user_tokens # 声明要修改外部作用域变量
            if isinstance(token_data, dict) and token_data["id"] not in selected_tokens_dict:
                token_data["display_as_bera_ratio"] = False
                dialog_user_tokens.append(token_data)
                selected_tokens_dict[token_data["id"]] = token_data
                fill_selected_list() # 调用辅助函数
                fill_available_list() # 调用辅助函数

        def add_token():
            current_item = available_list.currentItem()
            if current_item: add_token_by_data(copy.deepcopy(current_item.data(Qt.UserRole)))

        def remove_token_by_data(token_data):
            nonlocal dialog_user_tokens
            token_id_to_remove = token_data["id"]
            dialog_user_tokens = [t for t in dialog_user_tokens if t["id"] != token_id_to_remove]
            selected_tokens_dict.pop(token_id_to_remove, None)
            fill_selected_list() # 调用辅助函数
            fill_available_list() # 调用辅助函数

        def remove_token():
            current_item = selected_list.currentItem()
            if current_item:
                token_data = current_item.data(Qt.UserRole)
                if token_data: remove_token_by_data(token_data)

        def move_up():
            nonlocal dialog_user_tokens
            current_row = selected_list.currentRow()
            if current_row > 0:
                update_model_from_list_state() # 调用辅助函数
                dialog_user_tokens[current_row], dialog_user_tokens[current_row-1] = \
                    dialog_user_tokens[current_row-1], dialog_user_tokens[current_row]
                fill_selected_list() # 调用辅助函数
                selected_list.setCurrentRow(current_row-1)

        def move_down():
            nonlocal dialog_user_tokens
            current_row = selected_list.currentRow()
            if current_row < len(dialog_user_tokens) - 1:
                update_model_from_list_state() # 调用辅助函数
                dialog_user_tokens[current_row], dialog_user_tokens[current_row+1] = \
                    dialog_user_tokens[current_row+1], dialog_user_tokens[current_row]
                fill_selected_list() # 调用辅助函数
                selected_list.setCurrentRow(current_row+1)

        def on_cancel():
            logging.debug("用户点击取消，丢弃更改")
            dialog.reject()

        def on_ok():
            logging.debug("用户点击确定")
            update_model_from_list_state() # 调用辅助函数
            self.user_tokens = dialog_user_tokens
            logging.debug("on_ok: 即将保存的 token 列表状态:")
            for tkn in self.user_tokens: logging.debug(f"  - {tkn.get('symbol', '?')}: display_as_bera_ratio = {tkn.get('display_as_bera_ratio', 'Not Set')}")
            self.save_user_tokens()
            self.create_token_widgets()
            self.set_dynamic_window_size()
            self.fetch_data()
            dialog.accept()

        # --- 4. 首次填充列表 ---
        fill_available_list(); fill_selected_list() # 调用现在肯定已定义的函数

        # --- 5. 连接信号 ---
        search_input.textChanged.connect(delayed_search)
        search_timer.timeout.connect(fill_available_list) # 连接到已定义的函数
        add_button.clicked.connect(add_token)
        remove_button.clicked.connect(remove_token)
        move_up_button.clicked.connect(move_up)
        move_down_button.clicked.connect(move_down)
        ok_button.clicked.connect(on_ok)
        cancel_button.clicked.connect(on_cancel)
        available_list.itemDoubleClicked.connect(available_double_clicked)
        selected_list.itemDoubleClicked.connect(selected_double_clicked)

        # --- 6. 显示对话框 ---
        dialog.exec()

    def check_token_list_updates(self):
        """检查CoinGecko代币列表是否有更新，并在需要时更新"""
        try:
            from datetime import datetime, timedelta
            import requests
            import json
            import os
            from PySide6.QtWidgets import QMessageBox
            
            # 获取代币列表文件路径
            tokens_path = resource_path('coingecko.list')
            logging.info(f'检查代币列表更新: {tokens_path}')
            
            # 显示进度对话框
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setText("正在检查代币列表更新...")
            msg.setWindowTitle("更新检查")
            msg.setStandardButtons(QMessageBox.NoButton)
            msg.show()
            QApplication.processEvents()  # 强制更新UI
            
            needs_update = True
            
            # 检查文件是否存在且是否需要更新
            if os.path.exists(tokens_path):
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(tokens_path))
                now = datetime.now()
                # 如果文件在24小时内更新过，则不需要再次更新
                if (now - file_mod_time) < timedelta(days=1):
                    logging.info(f'代币列表已于 {file_mod_time} 更新，无需更新')
                    msg.setText("代币列表已是最新的！\n最后更新时间: " + 
                               file_mod_time.strftime("%Y-%m-%d %H:%M:%S"))
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec()
                    return
            
            # 发送请求获取代币列表
            try:
                logging.info("从CoinGecko API获取代币列表...")
                response = requests.get("https://api.coingecko.com/api/v3/coins/list", 
                                       timeout=30)  # 增加超时时间
                
                if response.status_code == 200:
                    tokens_data = response.json()
                    
                    # 计算新旧列表的差异
                    old_tokens = []
                    if os.path.exists(tokens_path):
                        try:
                            with open(tokens_path, 'r', encoding='utf-8') as f:
                                old_tokens = json.load(f)
                        except Exception as e:
                            logging.error(f'读取旧代币列表失败: {e}')
                    
                    new_tokens_count = len(tokens_data)
                    old_tokens_count = len(old_tokens)
                    delta = new_tokens_count - old_tokens_count
                    
                    # 保存到文件
                    try:
                        with open(tokens_path, 'w', encoding='utf-8') as f:
                            json.dump(tokens_data, f, ensure_ascii=False)
                        logging.info(f'已下载并保存代币列表: {new_tokens_count}个代币')
                        
                        # 更新内存中的代币列表
                        self.available_tokens = tokens_data
                        
                        # 显示成功消息
                        delta_text = ""
                        if delta > 0:
                            delta_text = f"\n\n新增了 {delta} 个代币！"
                        elif delta < 0:
                            delta_text = f"\n\n减少了 {abs(delta)} 个代币。"
                        
                        msg.setText(f"已成功获取并更新代币列表！\n\n"
                                   f"共 {new_tokens_count} 个代币{delta_text}")
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec()
                    except Exception as save_err:
                        logging.error(f'保存代币列表失败: {save_err}')
                        msg.setText(f"保存代币列表时出错: {save_err}")
                        msg.setIcon(QMessageBox.Critical)
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec()
                else:
                    logging.error(f'从CoinGecko获取代币列表失败: HTTP {response.status_code}')
                    msg.setText(f"从CoinGecko获取代币列表失败\n错误代码: {response.status_code}")
                    msg.setIcon(QMessageBox.Warning)
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec()
                    
            except Exception as net_err:
                logging.error(f'网络请求错误: {net_err}')
                msg.setText(f"网络请求错误: {net_err}")
                msg.setIcon(QMessageBox.Critical)
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
                
        except Exception as e:
            logging.error(f'检查代币列表更新时出错: {e}')
            import traceback
            logging.error(traceback.format_exc())
            QMessageBox.critical(self, "错误", f"检查代币列表更新时出错: {e}")

def main():
    """主程序入口"""
    # 检测运行环境
    is_packaged = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
    logging.info(f"程序启动 - {'打包环境' if is_packaged else '开发环境'}")
    if is_packaged:
        logging.info(f"打包路径: {sys._MEIPASS}")
        logging.info(f"执行文件: {sys.executable}")
        logging.info(f"工作目录: {os.getcwd()}")
        logging.info(f"命令行参数: {sys.argv}")
    
    logging.info("启动PySide6版本应用")
    app = QApplication(sys.argv)
    
    # 设置应用图标
    icon_path = resource_path('bera.ico')
    if os.path.exists(icon_path):
        # 使用QIcon的fromTheme方法来确保图标在任务栏中正确显示
        icon = QIcon(icon_path)
        app.setWindowIcon(icon)
        # 设置任务栏图标
        if sys.platform == 'win32':
            try:
                myappid = 'BeraHelper.1.0'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                logging.error(f'设置任务栏图标ID失败: {e}')
        logging.info(f'应用图标已全局设置: {icon_path}')
    else:
        logging.warning(f'全局图标文件不存在: {icon_path}')
    
    window = BeraHelperApp()
    
    # 设置位置（右上角）
    screen = app.primaryScreen().geometry()
    window.move(screen.width() - window.width() - 60, 60)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    try:
        main()
    except Exception as main_err:
         print(f"CRITICAL ERROR in main execution: {main_err}")
         traceback.print_exc() # 打印详细的回溯信息到控制台
         # --- !! 确保这里没有写入 _EARLY_LOG_FILE 的代码 !! ---
         sys.exit(1)
  