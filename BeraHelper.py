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
                    logging.info(f"Log directory will use LOCALAPPDATA: {log_dir_base}") # Changed to English

            # --- 改动：如果获取 %LOCALAPPDATA% 失败或非 Windows，则回退 ---
            if not log_dir_base:
                # 回退到可执行文件/脚本文件所在的目录下的 logs 文件夹
                if getattr(sys, 'frozen', False): # 打包后的 .exe 环境
                    exe_dir = os.path.dirname(sys.executable)
                else: # 开发环境 (.py)
                    exe_dir = os.path.dirname(os.path.abspath(__file__))
                log_dir_base = os.path.join(exe_dir, 'logs')
                logging.warning(f"Cannot get LOCALAPPDATA or not Windows, log directory fallback to: {log_dir_base}") # Changed to English

            # 创建日志目录（如果不存在）
            if not os.path.exists(log_dir_base):
                os.makedirs(log_dir_base, exist_ok=True) # exist_ok=True 避免目录已存在时报错
                logging.info(f"Created log directory: {log_dir_base}") # Changed to English

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

            logging.info('Logging system initialized successfully') # Changed to English
            logging.info(f'Actual log file path: {log_file}') # Changed to English
            
            # --- 删除: 测试警告消息、强制刷新和 atexit 机制 ---

        except Exception as log_setup_error:
            # 如果文件日志配置失败，提供基本的控制台日志作为后备
            logging.basicConfig(level=logging.ERROR) # 重新配置，至少保证 ERROR 级别能输出
            logging.critical(f"!!! Unable to configure file-based logging system: {log_setup_error}") # Changed to English
            logging.critical("!!! Logs will only be output to console/stderr") # Changed to English

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
        logging.debug(f"Using PyInstaller path: {base_path}") # Changed to English
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
                
        logging.debug(f"Using non-packaged environment path: {base_path}") # Changed to English
    
    result_path = os.path.join(base_path, relative_path)
    logging.debug(f"Resource path resolved: {relative_path} -> {result_path}") # Changed to English
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
            if price in ["Loading...", "Fetch Failed", "$--.--"]: # Changed to English
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
                        logging.error(f'Error setting taskbar icon ID (even though skipped): {e}') # Changed to English
                logging.info(f"App icon setup logic completed (taskbar ID skipped). Path: {icon_path}") # <--- 修改日志
            except Exception as icon_load_err:
                 logging.error(f"ERROR loading or setting icon: {icon_load_err}")
                 logging.error(f"Error loading or setting icon: {icon_load_err}") # Changed to English
        else:
            logging.warning(f"Icon file does NOT exist: {icon_path}") # <--- 修改日志
            logging.warning(f'Icon file does not exist: {icon_path}') # Changed to English

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
        logging.info("UI initialized, preparing to fetch initial data in the background") # Changed to English
        for token_id, widget in self.token_widgets.items():
            widget.update_price("Loading...", "") # 立即显示加载状态

        # 启动后台线程执行首次数据获取
        # 使用 QTimer 稍微延迟启动线程，确保主窗口已显示
        QTimer.singleShot(500, self.start_initial_fetch_thread) # 延迟 500ms
    
    def start_initial_fetch_thread(self):
        """启动一个后台线程来执行首次数据获取"""
        logging.info("Starting initial data fetch thread...") # Changed to English
        initial_fetch_thread = Thread(target=self._initial_fetch_thread, daemon=True)
        initial_fetch_thread.start()

    def _initial_fetch_thread(self):
        """在后台线程中执行首次数据获取"""
        logging.info("Initial data fetch thread started execution...") # Changed to English
        price_data = None
        fear_greed_data = None
        current_time = datetime.now().strftime("%H:%M:%S")
        try:
            # 获取价格数据
            price_data = self.get_prices()

            # 获取恐惧贪婪指数
            fear_greed_data = self.get_fear_greed_index(force_update=True) # 强制更新

            logging.info("Initial data fetch thread completed") # Changed to English

        except Exception as e:
            logging.error(f"Initial data fetch thread failed: {e}") # Changed to English
            import traceback
            logging.error(traceback.format_exc())
            # 即使失败，也发送信号，让主线程知道
        finally:
            # 使用信号将结果传递回主线程
            self.initial_data_ready.emit(price_data, fear_greed_data, current_time)

    @Slot(object, object, str)
    def handle_initial_data(self, price_data, fear_greed_data, current_time):
        """处理后台线程返回的首次数据，更新UI并启动定时器"""
        logging.info("Received initial data, preparing to update UI and start timer") # Changed to English
        self.price_data = price_data
        self.fear_greed_data = fear_greed_data
        self.current_time = current_time

        # 检查获取的数据是否有效
        if self.price_data is None or not self.price_data:
             logging.warning("Initial price data is invalid or empty, some UI might show error status") # Changed to English
             # 可以选择在这里为所有 widget 设置错误状态
             for token_id, widget in self.token_widgets.items():
                 if not self.price_data or token_id not in self.price_data:
                      widget.update_price("Fetch Failed", "--.--%")

        if self.fear_greed_data is None:
             logging.warning("Initial Fear & Greed index data is invalid") # Changed to English
             # UI 更新时会自动处理 None 的情况

        # 更新 UI (会使用 self.price_data 和 self.fear_greed_data)
        self.update_ui()

        # --- 在首次数据获取完成后再启动定时器 ---
        self.timer.start(self.update_interval * 1000)
        logging.info(f"Initial data display complete, update timer started, interval: {self.update_interval} seconds") # Changed to English

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
            logging.info(f'Loading configuration file: {config_path}') # Changed to English
            config = {} # 初始化为空字典
            if not os.path.exists(config_path):
                 logging.warning(f"Configuration file not found: {config_path}. Will use and create default configuration.") # Changed to English
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
                     logging.info(f"Created basic configuration file: {config_path}") # Changed to English
                 except Exception as create_err:
                     logging.error(f"Failed to create default configuration file: {create_err}, will continue using default configuration in memory.") # Changed to English
            else:
                 # 文件存在，正常加载
                 try:
                     with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                 except json.JSONDecodeError as e:
                     logging.error(f"Configuration file {config_path} format error: {e}. Will use default configuration.") # Changed to English
                     # 保留上面定义的默认 config 结构
                 except Exception as load_err:
                     logging.error(f"Error loading configuration file: {load_err}. Will use default configuration.") # Changed to English
                     # 保留上面定义的默认 config 结构

            # --- 字体设置 ---
            styles_config = config.get('styles', {})
            font_config = styles_config.get('FONT_NORMAL', ['Arial', 11])
            self.app_font = QFont(font_config[0], font_config[1])
            logging.debug(f'Configured font: {font_config[0]}, size: {font_config[1]}') # Changed to English

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
                logging.info(f'Attempting to load user token settings: {user_tokens_path}')

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
                            else: logging.warning(f"Skipping invalid/duplicate token data: {token_data}") # Changed to English

                        if self.user_tokens:
                             logging.info(f'Loaded user token settings: {len(self.user_tokens)} tokens') # Changed to English
                             user_tokens_loaded = True
                             for token in self.user_tokens: logging.debug(f'  Loaded: {token.get("symbol", "?")} ({token.get("id", "?ID")}), Ratio: {token.get("display_as_bera_ratio")}') # Changed to English
                        else: logging.warning("User token list is empty after processing.") # Changed to English
                else:
                    logging.warning(f'User token configuration file not found: {user_tokens_path}. Will use default tokens for the first time.') # Changed to English

            except json.JSONDecodeError as e: logging.error(f'Failed to parse user_tokens.json: {e}.') # Changed to English
            except Exception as e:
                logging.error(f'Error loading user token settings: {e}.') # Changed to English
                import traceback; logging.error(traceback.format_exc())

            if not user_tokens_loaded:
                logging.info('Using default token list.') # Changed to English
                self.user_tokens = default_tokens_with_flags # 使用带 False 标志的默认列表
                if user_tokens_path and not os.path.exists(user_tokens_path):
                    try: self.save_user_tokens()
                    except Exception as save_e: logging.error(f"Failed to save default token list for the first time: {save_e}") # Changed to English

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

            logging.info('Configuration loading complete') # Changed to English

        except Exception as e:
            # --- 极端情况下的硬编码默认值 (保持不变) ---
            logging.error(f'!!! Critical error during configuration file loading/creation: {e}') # Changed to English
            import traceback; logging.error(traceback.format_exc())
            logging.warning("Will use hardcoded program defaults!") # Changed to English
            # ... (保持之前的硬编码默认值设置) ...
            self.app_font = QFont('Arial', 11); self.BERA_ID = "berachain-bera"; self.IBGT_ID = "infrafred-bgt"; self.BTC_ID = "bitcoin"; self.ETH_ID = "ethereum"; self.update_interval = 60; self.api_config = {"coinmarketcap": {"enabled": True, "base_url": "https://pro-api.coinmarketcap.com/v3", "endpoints": {"fear_greed": "/fear-and-greed/historical"}, "params": {"fear_greed": {"start": 1, "limit": 1}}, "update_interval": 3600}}; self.up_color = QColor("#00FF7F"); self.down_color = QColor("#FF4500"); self.text_color = QColor("#FFD700"); self.extreme_fear_color = QColor("#FF0000"); self.fear_color = QColor("#FF7F00"); self.neutral_color = QColor("#FFFF00"); self.greed_color = QColor("#7FFF00"); self.extreme_greed_color = QColor("#00FF00")
            # 极端默认列表，全都不显示比率
            self.user_tokens = [ {"id": self.BTC_ID, "symbol": "BTC", "name": "Bitcoin", "display_as_bera_ratio": False}, {"id": self.ETH_ID, "symbol": "ETH", "name": "Ethereum", "display_as_bera_ratio": False}, {"id": self.BERA_ID, "symbol": "BERA", "name": "Berachain", "display_as_bera_ratio": False}, {"id": self.IBGT_ID, "symbol": "IBGT", "name": "Infrafred", "display_as_bera_ratio": False}, ]
            self.available_tokens = []
            try: self.load_available_tokens()
            except Exception as load_list_e: logging.error(f"Failed to load available token list under emergency default settings: {load_list_e}") # Changed to English

    def load_available_tokens(self):
        """加载可用的代币列表，并检查是否需要更新"""
        try:
            # 获取代币列表文件路径
            tokens_path = resource_path('coingecko.list')
            logging.info(f'Attempting to load token list file: {tokens_path}') # Changed to English

            # 检查文件是否存在
            if os.path.exists(tokens_path):
                try:
                    # 检查文件修改时间，决定是否需要提示用户更新
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(tokens_path))
                    now = datetime.now()
                    days_since_update = (now - file_mod_time).days

                    with open(tokens_path, 'r', encoding='utf-8') as f:
                        self.available_tokens = json.load(f)

                    logging.info(f'Loaded available token list: {len(self.available_tokens)} tokens') # Changed to English

                    # 如果列表文件超过30天未更新，弹出提示
                    if days_since_update > 30:
                        from PySide6.QtWidgets import QMessageBox
                        update_msg = QMessageBox(self)
                        update_msg.setIcon(QMessageBox.Information)
                        update_msg.setText(f"Token list hasn't been updated for {days_since_update} days.\nUpdate now?") # Changed to English
                        update_msg.setWindowTitle("Token List Update") # Changed to English
                        update_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        if update_msg.exec() == QMessageBox.Yes:
                            QTimer.singleShot(1000, self.check_token_list_updates)

                except Exception as e:
                    logging.error(f'Error reading token list file: {e}') # Changed to English
                    self.available_tokens = self.user_tokens.copy()
            else:
                # 文件不存在，直接触发下载
                logging.warning(f'Token list file does not exist: {tokens_path}') # Changed to English
                QTimer.singleShot(1000, self.check_token_list_updates)
                self.available_tokens = self.user_tokens.copy()
        except Exception as e:
            logging.error(f'Failed to load token list: {e}') # Changed to English
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
            
            logging.info(f'Saved user token settings to: {user_tokens_path}') # Changed to English
            logging.debug(f'Number of tokens saved: {len(self.user_tokens)}') # Changed to English
            
            # 验证保存结果
            if os.path.exists(user_tokens_path):
                try:
                    with open(user_tokens_path, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)
                    logging.debug(f'Verification: Number of tokens in file {len(saved_data)}') # Changed to English
                except Exception as e:
                    logging.error(f'Verification failed: {e}') # Changed to English
            else:
                logging.error(f'Save failed: File does not exist {user_tokens_path}') # Changed to English
                
        except Exception as e:
            logging.error(f'Failed to save user token settings: {e}') # Changed to English
    
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
        self.pin_button.setToolTip("Pin window on top")  # 设置工具提示 # Changed to English
        self.pin_button.clicked.connect(self.toggle_topmost)  # 连接按钮点击信号到切换置顶状态的函数
        
        # 添加代币列表更新按钮
        self.update_tokens_button = QPushButton("🔄")  # 创建更新按钮，使用循环箭头emoji
        self.update_tokens_button.setFont(self.app_font)  # 设置按钮字体
        self.update_tokens_button.setToolTip("Update token list")  # 设置工具提示 # Changed to English
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
        self.autostart_button.setToolTip("Start on boot")  # 设置工具提示 # Changed to English
        self.autostart_button.clicked.connect(self.toggle_autostart)  # 连接按钮点击信号
        
        # 代币管理按钮
        self.token_button = QPushButton("💰")  # 创建代币管理按钮，使用钱袋emoji
        self.token_button.setFont(self.app_font)  # 设置按钮字体
        self.token_button.setToolTip("Token Management")  # 设置工具提示 # Changed to English
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
        
        logging.debug(f'Window size adjusted: Width=260, Height={total_height} (Token count: {len(self.user_tokens)})') # Changed to English
    
    def create_token_widgets(self):
        """创建代币价格显示组件，并根据设置调整标签"""
        logging.debug("Executing create_token_widgets") # Changed to English
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
            logging.debug(f"  Creating widget for {token_symbol}: display_as_bera_ratio = {display_ratio}") # Changed to English
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
        logging.debug(f'Updating pin button status: is_topmost={self.is_topmost}')  # Changed to English
        
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
        logging.debug(f'Button style updated: is_topmost={self.is_topmost}') # Changed to English
    
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
        logging.debug('Toggling topmost state')  # Changed to English
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
                    
                    logging.info("Set window topmost state using Win32 API") # Changed to English
                else:
                    logging.error("Could not get window handle") # Changed to English
                    self._toggle_topmost_qt()  # 回退到Qt方式
                    
            except Exception as e:
                logging.error(f"Failed to set window topmost state using Win32 API: {e}") # Changed to English
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
                            "Window pinned on top", self)
        else:
            QToolTip.showText(self.pin_button.mapToGlobal(self.pin_button.rect().bottomLeft()), 
                            "Window unpinned", self)
        
        logging.info(f'Topmost state toggled: is_topmost={self.is_topmost}') # Changed to English

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
                logging.warning("User token list is empty") # Changed to English
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
            
            logging.debug(f'Requesting price data: {url}') # Changed to English
            logging.debug(f'Request parameters: {params}') # Changed to English
            
            try:
                response = requests.get(url, params=params, timeout=10)  # 添加超时
                
                if response.status_code != 200:
                    logging.error(f'Price data request failed: HTTP {response.status_code}') # Changed to English
                    logging.debug(f'Error response: {response.text}')
                    return {}
                    
                data = response.json()
                logging.debug(f'Received price data: {json.dumps(data, indent=2)}') # Changed to English
                
                # 验证数据有效性
                if not isinstance(data, dict):
                    logging.error(f'Invalid price data format: {type(data)}') # Changed to English
                    return {}
                
                # 记录哪些代币获取到了数据，哪些没有
                for token in self.user_tokens:
                    token_id = token["id"]
                    if token_id in data:
                        logging.debug(f'Successfully fetched {token["symbol"]} price data') # Changed to English
                    else:
                        logging.warning(f'Failed to get {token["symbol"]} price data') # Changed to English
                        
                # 尝试单独获取缺失的代币
                missing_tokens = [token for token in self.user_tokens if token["id"] not in data]
                if missing_tokens:
                    logging.info(f'Attempting to fetch {len(missing_tokens)} missing tokens\' prices')
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
                                    logging.info(f'Successfully fetched {token["symbol"]} price')
                                else:
                                    logging.warning(f'Fetching {token["symbol"]} price returned empty data')
                            else:
                                logging.warning(f'Failed to fetch {token["symbol"]} price: HTTP {single_response.status_code}')
                        except Exception as e:
                            logging.error(f'Error fetching {token["symbol"]} price: {e}')
                
                return data
                
            except requests.RequestException as e:
                logging.error(f'Network error while requesting price data: {e}')
                return {}
                
        except Exception as e:
            logging.error(f'Error fetching price data: {e}')
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
                reason = "Force update requested" # Changed to English
            elif self.fear_greed_cache is None or self.fear_greed_last_update is None:
                should_fetch = True
                reason = "Cache is empty or no timestamp" # Changed to English
            else:
                # 计算下次应该更新的时间点：上次更新日期的第二天早上8点
                last_update_date = self.fear_greed_last_update.date()
                next_day_date = last_update_date + timedelta(days=1)
                # 使用 datetime.combine 确保时间是准确的 8:00:00
                target_update_datetime = datetime.combine(next_day_date, datetime.min.time().replace(hour=8))

                if now >= target_update_datetime:
                    should_fetch = True
                    reason = f"Current time {now.strftime('%Y-%m-%d %H:%M')} >= Target update time {target_update_datetime.strftime('%Y-%m-%d %H:%M')}" # Changed to English
                else:
                    reason = f"Current time {now.strftime('%Y-%m-%d %H:%M')} < Target update time {target_update_datetime.strftime('%Y-%m-%d %H:%M')}" # Changed to English

            logging.debug(f'Checking if new index is needed: {should_fetch}. Reason: {reason}')

            if not should_fetch:
                logging.debug('Using cached Fear & Greed index data')
                return self.fear_greed_cache

            # --- 如果需要获取，则执行以下代码 ---
            logging.info('Attempting to fetch new Fear & Greed index data...')
            try:
                if not self.api_config.get('coinmarketcap', {}).get('enabled', False): # 更安全的检查
                    logging.warning('CoinMarketCap API is not enabled') # Changed to English
                    return self.fear_greed_cache # 获取失败时返回旧缓存

                api_key = os.getenv('CMC_API_KEY')
                if not api_key:
                    logging.error('CoinMarketCap API key not found') # Changed to English
                    return self.fear_greed_cache # 获取失败时返回旧缓存

                # API 请求部分保持不变
                url = f"{self.api_config['coinmarketcap']['base_url']}{self.api_config['coinmarketcap']['endpoints']['fear_greed']}"
                headers = {'X-CMC_PRO_API_KEY': api_key}
                params = self.api_config['coinmarketcap']['params']['fear_greed']

                logging.debug(f'Requesting Fear & Greed index: {url}') # Changed to English
                response = requests.get(url, headers=headers, params=params, timeout=10) # 添加超时

                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and len(data['data']) > 0:
                        new_data = data['data'][0]
                        self.fear_greed_cache = new_data
                        self.fear_greed_last_update = now # 使用当前的获取时间作为下次判断的基准
                        logging.info(f'Fear & Greed index updated successfully: {self.fear_greed_cache["value"]} ({self.fear_greed_cache["value_classification"]})') # Changed to English
                        return self.fear_greed_cache
                    else:
                        logging.warning('Fear & Greed index API returned empty data') # Changed to English
                        return self.fear_greed_cache # 获取失败时返回旧缓存
                else:
                    logging.error(f'Failed to fetch Fear & Greed index: HTTP {response.status_code}')
                    logging.debug(f'Error response: {response.text}')
                    return self.fear_greed_cache # 获取失败时返回旧缓存

            except requests.RequestException as e:
                 logging.error(f'Network error while requesting Fear & Greed index: {e}')
                 return self.fear_greed_cache # 获取失败时返回旧缓存
            except Exception as e:
                logging.error(f'Error fetching Fear & Greed index: {e}')
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
            logging.debug('Starting data fetch...') # Changed to English

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
            logging.debug('Emitting UI update signal') # Changed to English
            self.data_updated.emit()

        except Exception as e:
            logging.error(f"Data fetch error: {e}") # Changed to English
            import traceback
            logging.error(traceback.format_exc())
    
    @Slot()
    def update_ui(self):
        """更新UI显示 (支持美元价格和BERA比率模式)"""
        try:
            self.time_label.setText(f"Last Updated: {self.current_time}")
            logging.debug("Executing update_ui") # Changed to English

            if hasattr(self, 'price_data') and self.price_data:
                bera_price_usd = None
                if self.BERA_ID in self.price_data and "usd" in self.price_data[self.BERA_ID]:
                    bera_price_usd = self.price_data[self.BERA_ID]["usd"]
                    if bera_price_usd is None or bera_price_usd <= 0:
                        logging.warning(f"BERA price is invalid ({bera_price_usd}), cannot calculate ratios.") # Changed to English
                        bera_price_usd = None

                for token in self.user_tokens:
                    try:
                        token_id = token["id"]
                        token_symbol = token["symbol"].upper()

                        if token_id not in self.token_widgets:
                            logging.warning(f"update_ui: Widget not found for {token_id}") # Changed to English
                            continue

                        widget = self.token_widgets[token_id]
                        display_ratio = token.get("display_as_bera_ratio", False)
                        # --- Add Logging Here ---
                        logging.debug(f"  Updating {token_symbol}: display_as_bera_ratio = {display_ratio}") # Changed to English
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
                            else: logging.debug(f"{token_symbol} change is null") # Changed to English

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
                                except ZeroDivisionError: widget.update_price("Error", "--.--%"); logging.error(f"Zero division error calculating {token_symbol}/BERA ratio.") # Changed to English
                                except Exception as e: widget.update_price("Error", "--.--%"); logging.error(f"Error calculating {token_symbol}/BERA ratio: {e}") # Changed to English
                            elif bera_price_usd is None: widget.update_price("No BERA", change_text); logging.debug(f"Cannot calculate {token_symbol}/BERA ratio, BERA price unavailable") # Changed to English
                            else: widget.update_price("N/A", "--.--%"); logging.debug(f"Cannot calculate {token_symbol}/BERA ratio, {token_symbol} price unavailable") # Changed to English
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
                                except Exception as e: widget.update_price("$--.--", "--.--%"); logging.error(f"Error formatting price for {token_symbol}: {e}") # Changed to English
                            else: widget.update_price("$--.--", "--.--%"); logging.debug(f"No price data found for {token_symbol}") # Changed to English

                    except Exception as token_error:
                        logging.error(f"Error handling token {token.get('symbol', 'Unknown')}: {token_error}")
                        try:
                            if token_id in self.token_widgets: self.token_widgets[token_id].update_price("$Error$", "--.--%")
                        except Exception: pass
            else:
                for token_id, widget in self.token_widgets.items(): widget.update_price("$--.--", "--.--%")
                logging.warning("update_ui: No price data available") # Changed to English

            self.update_fear_greed_display()

        except Exception as e:
            logging.error(f"Error updating UI: {e}")
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
            classification_raw = fear_greed_data['value_classification']

            # --- Translate Classification ---
            classification_map = {
                "Extreme fear": "Extreme Fear",
                "Fear": "Fear",
                "Neutral": "Neutral",
                "Greed": "Greed",
                "Extreme greed": "Extreme Greed"
            }
            classification = classification_map.get(classification_raw, "Unknown") # Default to Unknown if not found

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
                logging.error(f"Error handling timestamp: {e}") # Changed to English
                time_str = f"Date: {timestamp}"
                tz_display = ""

            # 根据分类设置颜色 (Using translated classification)
            if classification == "Extreme Fear":
                color = "#FF0000"
            elif classification == "Fear":
                color = "#FF7F00"
            elif classification == "Neutral":
                color = "#FFFF00"
            elif classification == "Greed":
                color = "#7FFF00"
            elif classification == "Extreme Greed":
                color = "#00FF00"
            else: # Unknown
                color = "#FFFFFF"

            # 更新UI显示 (Using translated classification)
            self.fear_greed_value.setText(f" {value}")
            self.fear_greed_class.setText(f"({classification})")
            self.fear_greed_class.setStyleSheet(f"color: {color};")

            # 显示时间和时区偏移
            if tz_display:
                self.fear_greed_time.setText(f"Last Updated: {time_str} {tz_display}")
            else:
                self.fear_greed_time.setText(f"Last Updated: {time_str}")

        except Exception as e:
            logging.error(f"Error updating Fear & Greed index display: {e}")
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
                logging.info(f"Writing registry: Enable autostart \'{app_name}\'") # Changed to English
                app_path_raw = os.path.abspath(sys.argv[0])
                if not os.path.exists(app_path_raw):
                    raise FileNotFoundError(f"Application path not found: {app_path_raw}") # Changed to English

                if app_path_raw.lower().endswith('.py'):
                    pythonw_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                    if not os.path.exists(pythonw_path):
                        logging.warning(f"pythonw.exe not found, will use python.exe") # Changed to English
                        pythonw_path = sys.executable
                    registry_value = f'"{pythonw_path}" "{app_path_raw}" --minimized --no-splash --no-log'
                else:
                    registry_value = f'"{app_path_raw}" --minimized --no-splash --no-log'

                logging.debug(f"写入注册表的值: {registry_value}")
                reg_key = reg.OpenKey(key, key_path, 0, reg.KEY_WRITE)
                try:
                    reg.SetValueEx(reg_key, app_name, 0, reg.REG_SZ, registry_value)
                    logging.info("Successfully wrote registry entry.") # Changed to English
                finally:
                    reg.CloseKey(reg_key)
            else:
                # --- Delete registry entry ---
                logging.info(f"Writing registry: Disable autostart \'{app_name}\'") # Changed to English
                try:
                    reg_key = reg.OpenKey(key, key_path, 0, reg.KEY_WRITE)
                    try:
                        reg.DeleteValue(reg_key, app_name)
                        logging.info("Successfully deleted registry entry.") # Changed to English
                    except FileNotFoundError:
                        logging.warning(f"Attempted to delete registry entry \'{app_name}\', but it was already non-existent.") # Changed to English
                    finally:
                        reg.CloseKey(reg_key)
                except FileNotFoundError:
                     logging.warning(f"Attempted to open registry key to delete \'{app_name}\', but the key path does not exist.") # Changed to English


            return True # Indicate success

        except PermissionError as e:
            logging.error(f"Registry operation permission error: {e}") # Changed to English
            QMessageBox.warning(self, "Permission Denied", f"Registry operation failed: {e}\n\nAdministrator privileges may be required.") # Changed to English
            return False
        except Exception as e:
            logging.error(f"An error occurred during registry operation: {e}") # Changed to English
            import traceback
            logging.error(traceback.format_exc())
            QMessageBox.warning(self, "Error", f"An error occurred during registry operation:\n{e}") # Changed to English
            return False

    def _apply_pending_autostart_setting(self):
        """Applies the pending autostart setting to the registry."""
        if self.pending_autostart_state is not None:
            logging.info(f"Delayed timer triggered, applying pending autostart setting: {self.pending_autostart_state}") # Changed to English
            success = self._write_autostart_registry(enable=self.pending_autostart_state)
            if success:
                self.pending_autostart_state = None # Reset pending state only if write succeeded
                # Optionally re-verify and update button based on actual state now
                # self.update_autostart_button_status()
            else:
                # If write failed, keep pending state so maybe exit save can try again? Or reset?
                # Let's reset for now to avoid potential loops if permission is always denied.
                logging.warning("Applying pending autostart setting failed, resetting pending state.") # Changed to English
                self.pending_autostart_state = None
                # Update button back to actual state
                self.update_autostart_button_status()


    def update_autostart_button_status(self):
        """更新自启动按钮状态 (反映挂起状态优先)"""
        try:
            # Determine the state to display
            actual_state = self.is_autostart_enabled() # Check actual registry state
            display_state = self.pending_autostart_state if self.pending_autostart_state is not None else actual_state
            logging.debug(f'Updating autostart button status: Actual={actual_state}, Pending={self.pending_autostart_state}, Display={display_state}') # Changed to English

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
                tooltip = "Start on boot (Enabled)" # Changed to English
                if self.pending_autostart_state is True:
                     tooltip = "Start on boot (Will be enabled in 1 min or on exit)" # Changed to English
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
                tooltip = "Start on boot (Disabled)" # Changed to English
                if self.pending_autostart_state is False:
                    tooltip = "Start on boot (Will be disabled in 1 min or on exit)" # Changed to English

            self.autostart_button.setStyleSheet(style)
            self.autostart_button.setToolTip(tooltip) # Update tooltip as well
            self.autostart_button.update()
        except Exception as e:
            logging.error(f"Failed to update autostart button status: {e}") # Changed to English

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
                logging.debug(f"Registry autostart entry \'{app_name}\' exists.") # Changed to English
                return True # 如果查询成功，说明已存在
            except FileNotFoundError:
                logging.debug(f"Registry autostart entry \'{app_name}\' does not exist.") # Changed to English
                return False # 如果查询时找不到值，说明不存在
            finally:
                reg.CloseKey(key) # 确保关闭注册表项
        except Exception as e:
            logging.error(f"Failed to check registry autostart status: {e}") # Changed to English
            return False # 发生任何其他错误，都认为未启用

    def toggle_autostart(self):
        """切换挂起的自启动状态，并启动延迟保存计时器"""
        if sys.platform != 'win32':
             QMessageBox.warning(self, "Not Supported", "This feature is only supported on Windows.") # Changed to English
             return

        if self.autostart_lock:
            logging.debug("Autostart operation in progress, ignoring duplicate clicks.") # Changed to English
            return

        self.autostart_lock = True
        try:
            # Determine the *next* state based on the *current displayed* state
            # This handles the case where a pending state exists
            actual_state = self.is_autostart_enabled()
            current_display_state = self.pending_autostart_state if self.pending_autostart_state is not None else actual_state
            next_state = not current_display_state

            self.pending_autostart_state = next_state
            logging.info(f"Toggling pending autostart state to: {self.pending_autostart_state}") # Changed to English

            # 1. 立即更新按钮外观和它存储的 ToolTip 内容 (反映挂起状态，用于鼠标悬停)
            self.update_autostart_button_status() # 这会设置正确的悬停提示

            # --- 2. 强制显示 *不同的* ToolTip 作为即时反馈 (反映切换动作) ---
            # 根据 next_state 决定即时反馈的文本
            if next_state:
                immediate_feedback_text = "Switched to enable autostart" # Changed to English
            else:
                immediate_feedback_text = "Switched to disable autostart" # Changed to English

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
            logging.debug("Starting/restarting autostart setting delayed save timer (60 seconds)") # Changed to English
            self.autostart_save_timer.start() # Default interval is 60000ms

        except Exception as e:
             # This part should ideally not fail, but just in case
             logging.error(f"Error toggling pending autostart state: {e}") # Changed to English
             QMessageBox.warning(self, "Error", f"Error toggling autostart state:\n{e}") # Changed to English
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
        logging.debug("Autostart operation lock released") # Changed to English

    def closeEvent(self, event: QCloseEvent):
        """Override close event to save pending autostart setting."""
        logging.info("Received close event, checking pending autostart setting...") # Changed to English
        # Stop the timer first to prevent race condition
        self.autostart_save_timer.stop()
        logging.debug("Delayed save timer stopped.") # Changed to English

        # Apply pending setting if exists
        self._apply_pending_autostart_setting()

        logging.info("Allowing window to close.") # Changed to English
        event.accept() # Allow the window to close

    def show_token_manager(self):
        """显示代币管理对话框 (所有代币都可切换显示模式，操作副本保证取消有效)"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                      QListWidget, QPushButton, QLineEdit,
                                      QLabel, QListWidgetItem)
        from PySide6.QtCore import QTimer, Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("Token Management") # Changed to English
        dialog.setMinimumSize(400, 500)

        layout = QVBoxLayout(dialog)
        # --- UI 元素定义 (保持不变) ---
        search_layout = QHBoxLayout(); search_label = QLabel("Search Coin:"); search_input = QLineEdit(); search_input.setPlaceholderText("Enter coin name or symbol..."); search_layout.addWidget(search_label); search_layout.addWidget(search_input) # Changed placeholder
        available_label = QLabel("Available Tokens: (Double-click to add)"); available_list = QListWidget(); available_list.setSelectionMode(QListWidget.SingleSelection) # Changed label
        selected_label = QLabel("Selected Tokens: (Double-click to remove)"); selected_label.setToolTip("Check the box next to a token name to display its value as a ratio (%) to BERA"); selected_list = QListWidget() # Changed label and tooltip
        button_layout = QHBoxLayout(); add_button = QPushButton("Add ➡"); remove_button = QPushButton("⬅ Remove"); move_up_button = QPushButton("⬆ Move Up"); move_down_button = QPushButton("⬇ Move Down"); button_layout.addWidget(add_button); button_layout.addWidget(remove_button); button_layout.addWidget(move_up_button); button_layout.addWidget(move_down_button) # Changed button text
        dialog_buttons = QHBoxLayout(); ok_button = QPushButton("OK"); cancel_button = QPushButton("Cancel"); dialog_buttons.addStretch(); dialog_buttons.addWidget(ok_button); dialog_buttons.addWidget(cancel_button) # Changed button text
        layout.addLayout(search_layout); layout.addWidget(available_label); layout.addWidget(available_list); layout.addLayout(button_layout); layout.addWidget(selected_label); layout.addWidget(selected_list); layout.addLayout(dialog_buttons)


        # --- 1. 创建副本和本地字典 (保持不变) ---
        try:
             dialog_user_tokens = copy.deepcopy(self.user_tokens)
             logging.debug("Successfully created dialog_user_tokens copy") # Changed log
        except Exception as copy_err:
             logging.error(f"Failed to create copy of user token list: {copy_err}") # Changed log
             QMessageBox.critical(self, "Error", "Cannot open token manager: Failed to create data copy.") # Changed message
             return
        selected_tokens_dict = {token["id"]: token for token in dialog_user_tokens}


        # --- 2. 定义核心辅助函数 (调整顺序) ---
        search_timer = QTimer(); search_timer.setSingleShot(True); search_timer.setInterval(500)

        def fill_available_list(): # <--- 定义移到前面
            """填充可用代币列表 (使用 self.available_tokens)"""
            available_list.clear(); search_text = search_input.text().lower()
            logging.debug(f"fill_available_list: Search text='{search_text}'") # Changed to English
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
            logging.debug(f"fill_available_list completed, added {count} items") # Changed to English

        def fill_selected_list(): # <--- 定义移到前面
            """填充已选代币列表 (使用 dialog_user_tokens)"""
            selected_list.clear()
            logging.debug("fill_selected_list: Populating list using dialog_user_tokens") # Changed to English
            for token_data in dialog_user_tokens:
                item_text = f"{token_data['name']} ({token_data['symbol'].upper()})"
                item = QListWidgetItem(item_text)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                initial_state = token_data.get("display_as_bera_ratio", False)
                item.setCheckState(Qt.Checked if initial_state else Qt.Unchecked)
                item.setData(Qt.UserRole, token_data)
                selected_list.addItem(item)
            logging.debug(f"fill_selected_list completed, added {selected_list.count()} items") # Changed to English

        def delayed_search(): # <--- 定义移到前面
            """延迟执行搜索"""
            logging.debug("delayed_search: Triggering search timer") # Changed to English
            search_timer.start()

        def update_model_from_list_state(): # <--- 定义移到前面
            """将列表状态同步到 dialog_user_tokens 副本"""
            logging.debug("Syncing list checkbox states to dialog_user_tokens copy...") # Changed to English
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
                    else: logging.warning(f"Could not find ID in copy when syncing state: {token_id}") # Changed to English
                else: logging.warning(f"List item {i} has no valid data") # Changed to English


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
            logging.debug("User clicked Cancel, discarding changes") # Changed log
            dialog.reject()

        def on_ok():
            logging.debug("User clicked OK") # Changed log
            update_model_from_list_state() # 调用辅助函数
            self.user_tokens = dialog_user_tokens
            logging.debug("on_ok: Token list state to be saved:") # Changed log
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
            logging.info(f'Checking for token list updates: {tokens_path}') # Changed log
            
            # 显示进度对话框
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setText("Checking for token list updates...") # Changed message
            msg.setWindowTitle("Update Check") # Changed title
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
                    logging.info(f'Token list updated at {file_mod_time}, no update needed') # Changed log
                    msg.setText("Token list is up to date!\nLast updated: " + 
                               file_mod_time.strftime("%Y-%m-%d %H:%M:%S"))
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec()
                    return
            
            # 发送请求获取代币列表
            try:
                logging.info("Fetching token list from CoinGecko API...") # Changed log
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
                            logging.error(f'Failed to read old token list: {e}') # Changed log

                    new_tokens_count = len(tokens_data)
                    old_tokens_count = len(old_tokens)
                    delta = new_tokens_count - old_tokens_count
                    
                    # 保存到文件
                    try:
                        with open(tokens_path, 'w', encoding='utf-8') as f:
                            json.dump(tokens_data, f, ensure_ascii=False)
                        logging.info(f'Downloaded and saved token list: {new_tokens_count} tokens') # Changed log

                        # 更新内存中的代币列表
                        self.available_tokens = tokens_data
                        
                        # 显示成功消息
                        delta_text = ""
                        if delta > 0:
                            delta_text = f"\n\nAdded {delta} new tokens!" # Changed message
                        elif delta < 0:
                            delta_text = f"\n\nRemoved {abs(delta)} tokens." # Changed message
                        
                        msg.setText(f"Successfully fetched and updated token list!\n\n" # Changed message
                                   f"Total {new_tokens_count} tokens{delta_text}")
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec()
                    except Exception as save_err:
                        logging.error(f'Failed to save token list: {save_err}') # Changed log
                        msg.setText(f"Error saving token list: {save_err}") # Changed message
                        msg.setIcon(QMessageBox.Critical)
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec()
                else:
                    logging.error(f'Failed to fetch token list from CoinGecko: HTTP {response.status_code}') # Changed log
                    msg.setText(f"Failed to fetch token list from CoinGecko\nError code: {response.status_code}") # Changed message
                    msg.setIcon(QMessageBox.Warning)
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec()

            except Exception as net_err:
                logging.error(f'Network request error: {net_err}') # Changed log
                msg.setText(f"Network request error: {net_err}") # Changed message
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
    logging.info(f"Application starting - {'Packaged environment' if is_packaged else 'Development environment'}") # Changed log
    if is_packaged:
        logging.info(f"Packaged path: {sys._MEIPASS}") # Changed log
        logging.info(f"Executable: {sys.executable}") # Changed log
        logging.info(f"Working directory: {os.getcwd()}") # Changed log
        logging.info(f"Command line arguments: {sys.argv}") # Changed log
    
    logging.info("Starting PySide6 version application") # Changed log
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
                logging.error(f'Failed to set taskbar icon ID: {e}') # Changed log
        logging.info(f'Application icon set globally: {icon_path}') # Changed log
    else:
        logging.warning(f'Global icon file does not exist: {icon_path}') # Changed log
    
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
  