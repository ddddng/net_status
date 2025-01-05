# 多目标网络质量检测工具

本项目是一个基于 [Dash](https://plotly.com/dash/) + [Dash Bootstrap Components](https://dash-bootstrap-components.opensource.faculty.ai/) + [pywebview](https://github.com/r0x0r/pywebview) 的多目标网络质量监测工具，可实时监控多个目标（域名或 IP）在网络中的延迟与丢包情况，并可视化显示统计信息、事件日志等。

---

## 功能简介

1. **多目标监测**：支持同时监控多个目标（域名或 IP）。
2. **实时数据更新**：包括发送次数、丢包次数、丢包率、平均延迟等，页面每秒自动刷新。
3. **延迟图表**：使用折线图显示目标的实时延迟变化。
4. **丢包图表**：用柱状图显示各时刻的“正常”“高延迟”“丢包”状态。
5. **事件日志**：当连续发生丢包或高延迟达到阈值时，记录事件日志，方便排查网络故障。
6. **标签页管理**：每个目标以一个标签页（Tab）形式存在，可以随时添加或移除。
7. **本地 WebView**：通过 pywebview 提供一个本地的 GUI 窗口，无需浏览器即可访问。  
   （当然，你也可以直接在浏览器中访问 [http://localhost:8050](http://localhost:8050)。）

---

## 环境依赖

1. **Python 3.7+**（推荐使用 Python 3.9 及以上）
2. 需要安装以下 Python 库：
   - [dash](https://pypi.org/project/dash/)
   - [dash_bootstrap_components](https://pypi.org/project/dash-bootstrap-components/)
   - [plotly](https://pypi.org/project/plotly/)
   - [pywebview](https://pypi.org/project/pywebview/)
   - 以及其他内置依赖（如 `subprocess`, `threading`, `re` 等），这些通常是标准库自带。

安装方式示例（假设已安装 `pip` 或 `pip3`）：

```bash
pip install dash dash-bootstrap-components plotly pywebview
```

---

## 运行方式

1. **克隆或下载本项目**  
   将本项目源码下载到本地。
2. **进入项目目录**  

3. **安装依赖** 
   ```bash
   pip install -r requirements.txt
   ```

4. **运行脚本**  
   ```bash
   python net_status_v4.py
   ```
   运行后，程序会先启动一个 Dash 服务器（默认监听 `0.0.0.0:8050`），接着通过 pywebview 打开一个桌面窗口，展示该 Dash 应用页面。

   如果想直接在浏览器访问，可手动打开 [http://localhost:8050](http://localhost:8050)。

---

## 使用说明

1. **添加目标**  
   - 在文本框中输入目标（可以是 IP 地址或域名，如 `8.8.8.8` 或 `www.baidu.com`），然后点击「添加目标」按钮。
   - 如果目标已存在，不会重复添加。

2. **监测信息查看**  
   - 每个目标对应一个标签页，点击对应的标签即可查看。
   - 每个标签页包括：
     - **统计信息**：总发送次数、丢包次数、丢包率、平均延迟。
     - **延迟图**：折线图，显示最近一段时间的延迟（单位：ms）。
     - **丢包图**：柱状图，显示“正常”“高延迟”“丢包”三种状态。
     - **事件日志**：记录连续丢包或高延迟达到阈值后触发的事件。

3. **移除目标**  
   - 点击右上角的「移除」按钮，即可停止对该目标的监测，并删除对应的标签页。

4. **刷新周期**  
   - 前端通过 `dcc.Interval` 每秒（1 秒）更新一次图表与统计信息。  
   - 后端通过线程循环执行 `ping` 命令，每隔 `interval=1` 秒监测一次（可根据实际需求调整）。

5. **丢包与高延迟判定**  
   - 默认：  
     - **高延迟阈值**：200 ms  
     - **连续丢包/高延迟阈值**：3 次  
   - 当连续发生“丢包”或“高延迟”达到 3 次时，会在事件日志中显示相应提示。

6. **其他说明**  
   - Windows 系统下使用 `ping -n 1 -w 2000 <target>`，Linux/Unix/macOS 使用 `ping -c 1 -W 2 <target>`，并通过正则表达式解析延迟时间。  
   - 如果在某些操作系统上需要管理员权限或者防火墙导致 `ping` 命令失败，请根据自身系统情况做相应配置。


