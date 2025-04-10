# 更新日志

所有重要的项目变更将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased] - YYYY-MM-DD

### 新增

*   添加了命令行参数 `--log-level` 以控制日志输出级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)，默认为 INFO。
*   为恐惧贪婪指数的获取添加了独立的配置项 (`fear_greed_source.url`, `fear_greed_source.update_interval`) 和独立的更新定时器。
*   创建了 `CHANGELOG.md` 文件。

### 更改

*   将恐惧与贪婪指数的获取方式从依赖 CoinMarketCap API 改为通过网页抓取 (`beautifulsoup4`)，并根据数值范围手动进行分类。
*   价格数据和恐惧贪婪指数数据现在通过不同的定时器独立更新。
*   分离了价格数据和恐惧贪婪指数数据的后台获取线程。
*   更新了 `README.md` 以反映最新功能和配置。
*   更新了打包脚本 (`build_exe.bat`)，移除了不再需要的 `.env` 文件处理逻辑。

### 移除

*   移除了恐惧与贪婪指数获取的缓存机制。
*   移除了配置文件 (`bera_helper_config.json`) 中不再使用的 `api.coinmarketcap` 部分。
*   代码不再依赖 `.env` 文件中的 `CMC_API_KEY`。 