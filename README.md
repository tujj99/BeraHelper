# Bera Helper - Crypto Price Monitor

A simple desktop widget to display real-time prices, 24-hour change percentages, and the Fear & Greed Index for selected cryptocurrencies.

## Features

*   **Real-time Prices**: Fetches and displays USD prices for various cryptocurrencies (e.g., BTC, ETH, BERA, IBGT).
*   **24h Change**: Shows the corresponding 24-hour percentage change alongside the price.
*   **Fear & Greed Index**: Scrapes the current Fear & Greed index value from the CoinMarketCap website and classifies it based on common standards.
*   **Ratio Display Mode**: Option to display the price of certain tokens as a percentage ratio relative to the BERA token price.
*   **Custom Token List**: Manage the list of displayed tokens and their display mode (USD Price or BERA Ratio) via a GUI.
*   **Always on Top**: Toggle whether the window stays above all other windows using a button.
*   **Window Dragging**: Borderless window that can be moved by clicking and dragging.
*   **Independent Auto-Update**: Price data and Fear & Greed Index data now refresh independently based on intervals set in the configuration file.
*   **Run on Startup (Windows)**: Optional configuration to automatically start the application when Windows boots.
*   **Command-Line Log Level Control**: Control the verbosity of log output using the `--log-level` command-line argument.
*   **Flexible Configuration**: Configure update intervals, color themes, F&G source URL, etc., via JSON files.
*   **Logging**: Logs runtime information and errors to files for easier troubleshooting (log level is configurable).

## How to Run

### Dependencies

Ensure you have Python installed along with the following libraries:

*   `PySide6`: For the graphical user interface.
*   `requests`: For making HTTP requests.
*   `beautifulsoup4`: For parsing HTML (used for scraping the Fear & Greed Index).
*   `python-dotenv`: For loading environment variables from a `.env` file (Note: `.env` is no longer required by the current code, but loading logic remains for future use).
*   `python-dateutil`: For date/time parsing.
*   `pywin32` (Windows Only): For window pinning (always on top) and run-on-startup functionality.

Install them using pip:
```bash
pip install PySide6 requests beautifulsoup4 python-dotenv python-dateutil pywin32
```

### Running the Script

1.  Ensure your project structure is similar to this (`.env` file is optional):
    ```
    /your_project_directory/
    ├── BeraHelper/
    │   ├── BeraHelper.py           # Main application script
    │   ├── bera_helper_config.json # Main configuration file
    │   ├── coingecko.list          # CoinGecko token list (auto-downloaded if missing)
    │   ├── bera.ico                # Application icon
    │   └── ... (Other potential resources)
    ├── CHANGELOG.md                # (New) Changelog
    └── README.md                   # (This file)
    ```
2.  Run the Python script:
    ```bash
    # Run with default INFO log level
    python BeraHelper/BeraHelper.py

    # Run with DEBUG log level (more verbose)
    python BeraHelper/BeraHelper.py --log-level DEBUG

    # Run with WARNING log level (only warnings and above)
    python BeraHelper/BeraHelper.py --log-level WARNING
    ```
    Supported log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

### (Optional) Running the Packaged `.exe` (Windows)

If you have packaged the script into an `.exe` file using PyInstaller or similar tools:

1.  Ensure the necessary resource files (icon, config, token list) are included in the package or located correctly relative to the `.exe`.
2.  Run the `.exe` file. You can also run it from the command line and append the `--log-level` argument:
    ```bash
    .\BeraHelper.exe --log-level DEBUG
    ```

## Configuration

The application reads configuration files from the `BeraHelper` directory:

*   **`bera_helper_config.json`**:
    *   `styles`: Configure UI element colors and fonts.
    *   `window.update_interval`: Main update interval for **price data** (in seconds).
    *   `fear_greed_source.url`: Webpage URL to scrape for the Fear & Greed Index.
    *   `fear_greed_source.update_interval`: Update interval for the **Fear & Greed Index** (in seconds).
*   **`user_tokens.json`** (Located in the user data directory): Stores the user-managed token list and display modes.
*   **`.env`**: (No longer required) If present, `python-dotenv` will still attempt to load it, but the current code doesn't use variables from it.

## Packaging (Using PyInstaller)

To package the script into a standalone executable (`.exe`):

1.  Install PyInstaller: `pip install pyinstaller`
2.  Ensure your working directory is the one **above** `BeraHelper/`.
3.  Run the PyInstaller command (example for Windows, adjust path separators and continuation characters for Linux/macOS):

    ```bash
    pyinstaller --noconfirm --onedir --windowed --icon "BeraHelper/bera.ico" ^
    --add-data "BeraHelper/bera.ico;BeraHelper/" ^
    --add-data "BeraHelper/bera_helper_config.json;BeraHelper/" ^
    --add-data "BeraHelper/coingecko.list;BeraHelper/" ^
    --hidden-import "PySide6.QtSvg" ^
    --hidden-import "PySide6.QtNetwork" ^
    "BeraHelper/BeraHelper.py"
    ```
    *   You might want to create a shortcut to the executable in the `dist/BeraHelper` folder and add `--log-level INFO` (or another level) to the shortcut target to control the default log level when launched via the shortcut.

4.  The packaged application will be in the `dist/BeraHelper` directory.

## Notes

*   **Fear & Greed Index Scraping**: Relies on scraping the CoinMarketCap webpage and manual classification based on the value. Changes to the website's HTML structure may break the scraping.
*   **CoinGecko API**: Price data depends on CoinGecko's free API, which may have rate limits.
*   **User Data Directory**: `user_tokens.json` and log files are stored in a user-specific data directory or the application directory.
*   **Log Files**: Log files are generated in a `logs` subdirectory within the user data directory. The level of detail is controlled by the `--log-level` argument.

---

# Bera Helper - 加密货币价格监控器 (中文)

一个简单的桌面小部件，用于实时显示选定的加密货币价格、24 小时变化率以及恐惧与贪婪指数。

## 主要功能

*   **实时价格显示**: 获取并展示多种加密货币（如 BTC, ETH, BERA, IBGT 等）的美元价格。
*   **24小时变化率**: 同时显示价格对应的 24 小时涨跌幅百分比。
*   **恐惧与贪婪指数**: 通过抓取 CoinMarketCap 网页获取当前的恐惧与贪婪指数值，并根据常见标准进行手动分类。
*   **比率显示模式**: 支持将某些代币的价格显示为其与 BERA 代币的价格比率（百分比）。
*   **自定义代币列表**: 用户可以通过图形界面管理要显示的代币列表，并设置特定代币的显示模式（美元价格或 BERA 比率）。
*   **窗口置顶**: 可以通过按钮切换窗口是否保持在所有其他窗口之上。
*   **窗口拖动**: 无边框窗口，但可以通过按住鼠标左键拖动。
*   **独立自动更新**: 价格数据和恐惧贪婪指数数据现在根据配置文件中的不同间隔独立自动刷新。
*   **开机自启动 (Windows)**: 可选配置，使程序在 Windows 启动时自动运行。
*   **命令行日志级别控制**: 可以通过命令行参数 `--log-level` 控制日志输出的详细程度。
*   **配置灵活**: 通过 JSON 文件配置更新间隔、颜色主题、F&G 指数来源 URL 等。
*   **日志记录**: 将运行信息和错误记录到日志文件，便于排查问题（日志级别可配置）。

## 运行说明

### 依赖项

确保你安装了 Python 和以下库：

*   `PySide6`: 用于图形用户界面。
*   `requests`: 用于发送 HTTP 请求。
*   `beautifulsoup4`: 用于解析 HTML (抓取恐惧贪婪指数)。
*   `python-dotenv`: 用于加载 `.env` 文件中的环境变量（注意：当前代码不再需要 `.env` 文件，但保留了加载逻辑以备将来使用）。
*   `python-dateutil`: 用于日期时间解析。
*   `pywin32` (仅限 Windows): 用于窗口置顶和开机自启动功能。

你可以使用 pip 安装它们：
```bash
pip install PySide6 requests beautifulsoup4 python-dotenv python-dateutil pywin32
```

### 运行脚本

1.  确保你的项目结构如下（`.env` 文件不再是必需的）：
    ```
    /你的项目目录/
    ├── BeraHelper/
    │   ├── BeraHelper.py       # 主程序脚本
    │   ├── bera_helper_config.json # 主配置文件
    │   ├── coingecko.list      # CoinGecko 代币列表 (可自动下载)
    │   ├── bera.ico            # 应用图标
    │   └── ... (其他可能的资源)
    ├── CHANGELOG.md            # (新增) 变更日志
    └── README.md               # (本文件)
    ```
2.  运行 Python 脚本：
    ```bash
    # 默认以 INFO 日志级别运行
    python BeraHelper/BeraHelper.py

    # 以 DEBUG 日志级别运行 (输出更详细)
    python BeraHelper/BeraHelper.py --log-level DEBUG

    # 以 WARNING 日志级别运行 (只输出警告及以上)
    python BeraHelper/BeraHelper.py --log-level WARNING
    ```
    支持的日志级别：`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`。

### (可选) 运行打包后的 `.exe` (Windows)

如果你已经使用 PyInstaller 等工具将脚本打包成了 `.exe` 文件：

1.  确保 `.exe` 文件所在的目录包含必要的资源文件（如图标、配置文件、代币列表等），或者打包时已正确包含它们。
2.  运行 `.exe` 文件。你也可以在命令行中运行并附加 `--log-level` 参数：
    ```bash
    .\BeraHelper.exe --log-level DEBUG
    ```

## 配置说明

程序运行时会读取 `BeraHelper` 目录下的配置文件：

*   **`bera_helper_config.json`**:
    *   `styles`: 配置 UI 元素的颜色和字体。
    *   `window.update_interval`: **价格信息**的主要更新间隔（秒）。
    *   `fear_greed_source.url`: 获取恐惧贪婪指数的网页 URL。
    *   `fear_greed_source.update_interval`: **恐惧贪婪指数**的更新间隔（秒）。
*   **`user_tokens.json`** (位于用户数据目录): 存储用户管理的代币列表和显示模式。
*   **`.env`**: (不再必需) 如果存在，`python-dotenv` 仍会尝试加载，但当前代码不使用其中的变量。

## 打包说明 (使用 PyInstaller)

如果你想将脚本打包成单个可执行文件（`.exe`），可以使用 PyInstaller。

1.  安装 PyInstaller: `pip install pyinstaller`
2.  确保你的工作目录是包含 `BeraHelper.py` 的 **上一级** 目录。
3.  运行 PyInstaller 命令（示例适用于 Windows，注意移除 `.env` 相关部分）：

    ```bash
    pyinstaller --noconfirm --onedir --windowed --icon "BeraHelper/bera.ico" ^
    --add-data "BeraHelper/bera.ico;BeraHelper/" ^
    --add-data "BeraHelper/bera_helper_config.json;BeraHelper/" ^
    --add-data "BeraHelper/coingecko.list;BeraHelper/" ^
    --hidden-import "PySide6.QtSvg" ^
    --hidden-import "PySide6.QtNetwork" ^
    "BeraHelper/BeraHelper.py"
    ```
    *   **注意:** Linux/macOS 请调整路径分隔符和续行符。
    *   可以在 `dist/BeraHelper` 目录中创建快捷方式，并在目标后添加 `--log-level INFO` 等参数控制默认日志级别。

4.  打包完成后，生成的文件会在 `dist/BeraHelper` 目录下。

## 注意事项

*   **恐惧与贪婪指数获取**: 当前实现依赖于抓取 CoinMarketCap 网页，并根据数值手动分类。如果网站更改 HTML 结构，抓取可能失败。
*   **CoinGecko API**: 价格数据依赖 CoinGecko 的免费 API。
*   **用户数据目录**: `user_tokens.json` 和日志文件存储在用户特定的数据目录或程序所在目录。
*   **日志文件**: 程序会在日志目录下生成日志文件，级别可通过 `--log-level` 控制。 