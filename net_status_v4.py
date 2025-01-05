import sys
import logging
import dash
from dash import dcc, html, Input, Output, State, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import webview 
import subprocess
import re
import time
from datetime import datetime
from collections import deque, defaultdict
from threading import Thread

# config 
# -----------------
disable_logging = True


# -----------------
if disable_logging == True:
    logging.disable(logging.CRITICAL)
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )

# 数据存储
stats_data = defaultdict(lambda: {
    'total_pings': 0,
    'total_lost': 0,
    'loss_rate': 0.0,
    'avg_latency': 0.0,
    'latencies': deque(maxlen=1000),
    'loss_data': deque(maxlen=1000),
    'events': deque(maxlen=100)
})

# 网络监测类
class NetworkMonitor:
    def __init__(self, interval=1):
        """
        初始化网络监测器。

        :param interval: 监测间隔（秒）
        """
        self.targets = set()
        self.interval = interval
        self.running = False
        self.threads = {}

    def add_target(self, target):
        if target not in self.targets:
            self.targets.add(target)
            thread = Thread(target=self.monitor_target, args=(target,))
            thread.daemon = True
            thread.start()
            self.threads[target] = thread
            logging.info(f"开始监测目标: {target}")

    def remove_target(self, target):
        if target in self.targets:
            self.targets.remove(target)
            # 线程会自动退出，因为监测循环检查 self.running 和 target 是否在 self.targets
            del self.threads[target]
            logging.info(f"停止监测目标: {target}")

    def start(self):
        self.running = True
        logging.info("网络监测器已启动")

    def stop(self):
        self.running = False
        for thread in self.threads.values():
            thread.join()
        logging.info("网络监测器已停止")

    def monitor_target(self, target):
        """
        监测单个目标的网络质量。
        """
        ping_count = 0
        loss_count = 0
        consecutive_loss = 0
        loss_threshold = 3
        latency_threshold = 200  # ms

        while self.running and target in self.targets:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            latency, lost = self.ping(target)
            ping_count += 1

            if lost:
                loss_count += 1
                consecutive_loss += 1
                loss_value = 2  # 丢包
                stats_data[target]['loss_data'].append({'time': timestamp, 'value': loss_value})
                if consecutive_loss >= loss_threshold:
                    event = f"{timestamp} - 连续丢包 {consecutive_loss} 次"
                    stats_data[target]['events'].append(event)
                    logging.info(event)
            elif latency is not None and latency > latency_threshold:
                loss_value = 1  # 高延迟
                stats_data[target]['loss_data'].append({'time': timestamp, 'value': loss_value})
                loss_count += 1  # 将高延迟视为丢包的一种类型
                consecutive_loss += 1
                if consecutive_loss >= loss_threshold:
                    event = f"{timestamp} - 连续高延迟 {consecutive_loss} 次"
                    stats_data[target]['events'].append(event)
                    logging.info(event)
            else:
                loss_value = 0  # 正常
                stats_data[target]['loss_data'].append({'time': timestamp, 'value': loss_value})
                consecutive_loss = 0

            # 记录延迟信息
            if latency is not None and latency > 0:
                stats_data[target]['latencies'].append({'time': timestamp, 'value': latency})

            # 计算统计数据
            avg_latency = (
                sum(item['value'] for item in stats_data[target]['latencies']) / len(stats_data[target]['latencies'])
                if stats_data[target]['latencies'] else 0
            )
            loss_rate = (loss_count / ping_count) * 100 if ping_count > 0 else 0

            stats_data[target]['total_pings'] = ping_count
            stats_data[target]['total_lost'] = loss_count
            stats_data[target]['loss_rate'] = round(loss_rate, 2)
            stats_data[target]['avg_latency'] = round(avg_latency, 2)

            logging.info(
                f"目标 {target} - 总发送: {ping_count}, 丢包: {loss_count}, "
                f"丢包率: {loss_rate:.2f}%, 平均延迟: {avg_latency:.2f} ms"
            )

            time.sleep(self.interval)

    def ping(self, target):
        """
        执行 ping 命令并解析结果。
        返回 (latency, lost)
        """
        try:
            # 判断操作系统
            system = sys.platform
            if system.startswith('win'):
                # Windows
                cmd = ["ping", "-n", "1", "-w", "2000", target]
                timeout_regex = r"时间[=<]\s*(\d+)ms"
            else:
                # Unix/Linux/macOS
                cmd = ["ping", "-c", "1", "-W", "2", target]
                timeout_regex = r"time[=<]\s*(\d+\.\d+) ms"

            output = subprocess.check_output(
                cmd,
                universal_newlines=True,
                stderr=subprocess.DEVNULL
            )
            # 解析输出中的延迟
            match = re.search(timeout_regex, output)
            if match:
                latency = float(match.group(1))
                return latency, False
            else:
                return None, True
        except subprocess.CalledProcessError:
            return None, True

# 创建网络监测器实例
monitor = NetworkMonitor()
monitor.start()

# 创建 Dash 应用
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "多目标网络质量检测工具"

# 创建 Dash 应用布局
app.layout = dbc.Container([
    # 添加顶部空白，避免与系统窗口边缘重叠
    dbc.Row([
        dbc.Col(html.Div(), width=12)
    ], style={'marginTop': '20px'}),
    
    # 添加目标输入
    dbc.Row([
        dbc.Col([
            dbc.Input(id='input-target', placeholder='输入目标IP地址或域名 (例如: 8.8.8.8 或 www.baidu.com)', type='text'),
        ], width=8),
        dbc.Col([
            dbc.Button("添加目标", id='button-add', color='primary', className='w-100'),
        ], width=4),
    ], className='mb-4'),

    # 标签页显示监测目标
    dbc.Tabs(id='tabs', active_tab='tab-0', children=[]),

    # 使用 dcc.Interval 进行定时更新
    dcc.Interval(id='interval-component', interval=1*1000, n_intervals=0)  # 每秒更新一次

], fluid=True)

# 合并添加和移除目标的回调函数
@app.callback(
    Output('tabs', 'children'),
    [Input('button-add', 'n_clicks'),
     Input({'type': 'remove-button', 'index': ALL}, 'n_clicks')],
    [State('input-target', 'value'),
     State('tabs', 'children')],
    prevent_initial_call=True
)
def update_tabs(add_clicks, remove_clicks, input_value, tabs):
    ctx = dash.callback_context

    if not ctx.triggered:
        return tabs

    triggered_id = ctx.triggered_id

    if triggered_id == 'button-add':
        # 处理添加目标
        logging.info(f"按钮点击次数: {add_clicks}, 输入的目标: {input_value}")
        if not input_value:
            logging.warning("输入的目标为空，无法添加")
            return tabs
        # 检查是否已存在
        for tab in tabs:
            if tab['props']['label'] == input_value:
                logging.info(f"目标 {input_value} 已存在，跳过添加")
                return tabs  # 已存在，不重复添加
        # 添加新的标签页
        new_tab = dbc.Tab(label=input_value, tab_id=f"tab-{len(tabs)}", children=[
            html.Div(id={'type': 'tab-content', 'index': input_value}, children=[
                dbc.Row([
                    dbc.Col([
                        html.H5(f"目标: {input_value}"),
                    ], width=10),
                    dbc.Col([
                        dbc.Button("移除", id={'type': 'remove-button', 'index': input_value}, color='danger', size='sm')
                    ], width=2)
                ]),
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("统计信息"),
                            dbc.CardBody([
                                html.P(id={'type': 'total-pings', 'index': input_value}, children="总发送: 0"),
                                html.P(id={'type': 'total-lost', 'index': input_value}, children="丢包: 0"),
                                html.P(id={'type': 'loss-rate', 'index': input_value}, children="丢包率: 0.00%"),
                                html.P(id={'type': 'avg-latency', 'index': input_value}, children="平均延迟: 0 ms"),
                            ])
                        ])
                    ], width=3),
                    dbc.Col([
                        dcc.Graph(id={'type': 'latency-graph', 'index': input_value}, figure={
                            'data': [],
                            'layout': go.Layout(
                                title='延迟 (ms)',
                                xaxis={'title': '时间'},
                                yaxis={'title': '延迟 (ms)'},
                                margin={'l': 40, 'r': 10, 't': 40, 'b': 40},
                                hovermode='closest'
                            )
                        })
                    ], width=6),
                    dbc.Col([
                        dcc.Graph(id={'type': 'loss-graph', 'index': input_value}, figure={
                            'data': [],
                            'layout': go.Layout(
                                title='丢包情况',
                                xaxis={'title': '时间'},
                                yaxis={
                                    'title': '状态',
                                    'tickvals': [0, 1, 2],
                                    'ticktext': ['正常', '高延迟', '丢包']
                                },
                                margin={'l': 40, 'r': 10, 't': 40, 'b': 40},
                                barmode='group'
                            )
                        })
                    ], width=3),
                ]),
                dbc.Row([
                    dbc.Col([
                        html.H5("事件日志:"),
                        html.Div(
                            [
                                html.Ul(id={'type': 'event-log', 'index': input_value}, children=[])
                            ],
                            style={
                                'height': '200px',
                                'overflowY': 'scroll',
                                'border': '1px solid #ccc',
                                'padding': '10px',
                                'borderRadius': '5px',
                                'backgroundColor': '#f9f9f9'
                            }
                        )
                    ], width=12)
                ])
            ])
        ])
        tabs.append(new_tab)
        # 向监测器添加新目标
        monitor.add_target(input_value)
        logging.info(f"目标 {input_value} 已添加到监测器")
    elif isinstance(triggered_id, dict) and triggered_id.get('type') == 'remove-button':
        # 处理移除目标
        target = triggered_id['index']
        logging.info(f"尝试移除目标: {target}")
        
        # 移除目标数据
        if target in stats_data:
            del stats_data[target]
            logging.info(f"目标 {target} 的数据已移除")
        
        # 从监测器移除目标
        monitor.remove_target(target)
        
        # 移除标签页
        new_tabs = []
        for tab in tabs:
            if tab['props']['label'] != target:
                new_tabs.append(tab)
        logging.info(f"目标 {target} 的标签页已移除")
        tabs = new_tabs

    return tabs

# 更新前端图表和统计信息
@app.callback(
    [
        Output({'type': 'total-pings', 'index': ALL}, 'children'),
        Output({'type': 'total-lost', 'index': ALL}, 'children'),
        Output({'type': 'loss-rate', 'index': ALL}, 'children'),
        Output({'type': 'avg-latency', 'index': ALL}, 'children'),
        Output({'type': 'latency-graph', 'index': ALL}, 'figure'),
        Output({'type': 'loss-graph', 'index': ALL}, 'figure'),
        Output({'type': 'event-log', 'index': ALL}, 'children'),
    ],
    Input('interval-component', 'n_intervals'),
    prevent_initial_call=True
)
def update_graphs(n):
    total_pings = []
    total_lost = []
    loss_rate = []
    avg_latency = []
    latency_figures = []
    loss_figures = []
    event_logs = []

    for target, stats in stats_data.items():
        # 更新统计信息
        total_pings.append(f"总发送: {stats['total_pings']}")
        total_lost.append(f"丢包: {stats['total_lost']}")
        loss_rate.append(f"丢包率: {stats['loss_rate']}%")
        avg_latency.append(f"平均延迟: {stats['avg_latency']} ms")
        
        # 更新延迟图
        lat_times = [item['time'] for item in stats['latencies']]
        lat_values = [item['value'] for item in stats['latencies']]
        latency_trace = go.Scatter(
            x=lat_times,
            y=lat_values,
            mode='lines+markers',
            name='延迟',
            line=dict(color='blue'),
            marker=dict(
                size=8,
                color='blue',
                line=dict(color='white', width=2)
            )
        )
        latency_fig = {
            'data': [latency_trace],
            'layout': go.Layout(
                title='延迟 (ms)',
                xaxis={'title': '时间'},
                yaxis={'title': '延迟 (ms)'},
                margin={'l': 40, 'r': 10, 't': 40, 'b': 40},
                hovermode='closest'
            )
        }
        latency_figures.append(latency_fig)
        
        # 更新丢包图
        loss_times = [item['time'] for item in stats['loss_data']]
        loss_values = []
        colors = []

        for item in stats['loss_data']:
            loss_value = item['value']
            loss_values.append(loss_value)
            if loss_value == 0:
                colors.append('green')  # 正常
            elif loss_value == 1:
                colors.append('yellow')  # 高延迟
            elif loss_value == 2:
                colors.append('red')  # 丢包

        loss_trace = go.Bar(
            x=loss_times,
            y=loss_values,
            name='丢包情况',
            marker_color=colors,
            opacity=0.7,
            width=0.8
        )
        loss_fig = {
            'data': [loss_trace],
            'layout': go.Layout(
                title='丢包情况',
                xaxis={'title': '时间'},
                yaxis={
                    'title': '状态',
                    'tickvals': [0, 1, 2],
                    'ticktext': ['正常', '高延迟', '丢包']
                },
                margin={'l': 40, 'r': 10, 't': 40, 'b': 40},
                barmode='group'
            )
        }
        loss_figures.append(loss_fig)
        
        # 更新事件日志
        events = list(stats['events'])[-10:]  # 只显示最近10条
        event_items = [html.Li(event) for event in events]
        event_logs.append(event_items)

    return total_pings, total_lost, loss_rate, avg_latency, latency_figures, loss_figures, event_logs

# 创建并打开 WebView 窗口
def open_window():
    # 打开 WebView 窗口，指向 Dash 应用
    window = webview.create_window("网络质量检测工具", "http://localhost:8050", width=1600, height=900, resizable=True)
    webview.start()

if __name__ == '__main__':
    try:
        # 创建并启动 Dash 服务器线程
        dash_thread = Thread(target=lambda: app.run_server(debug=False, host='0.0.0.0', port=8050))
        dash_thread.daemon = True
        dash_thread.start()

        # 等待 Dash 服务器启动
        time.sleep(2)  # 等待 2 秒，确保服务器已启动

        # 打开 WebView 窗口
        open_window()
    except KeyboardInterrupt:
        logging.info("应用正在退出...")
    finally:
        # 当窗口关闭时，停止监测器
        monitor.stop()
