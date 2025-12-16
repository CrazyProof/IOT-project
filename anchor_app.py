# -*- coding: utf-8 -*-
"""
锚节点GUI应用程序
实现声波测距的固定端（锚节点）应用
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import numpy as np
from datetime import datetime

from core.ranging_engine import RangingEngine
from core.signal_processor import SignalProcessor
from core.audio_io import AudioIO


class AnchorDeviceApp:
    """锚节点应用程序"""
    
    def __init__(self, root):
        """
        初始化应用程序
        
        Args:
            root: Tkinter根窗口
        """
        self.root = root
        self.root.title("声波测距 - 锚节点")
        self.root.geometry("600x650")
        self.root.resizable(True, True)
        
        # 测距引擎
        self.engine = RangingEngine(device_role='anchor')
        
        # 设置回调
        self.engine.on_distance_updated = self.on_distance_updated
        self.engine.on_state_changed = self.on_state_changed
        self.engine.on_connection_changed = self.on_connection_changed
        self.engine.on_error = self.on_error
        
        # 测量历史
        self.measurements = []
        
        # 创建UI
        self._create_ui()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 自动启动服务器
        self.start_server()
        
    def _create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== 服务器状态区域 =====
        server_frame = ttk.LabelFrame(main_frame, text="服务器状态", padding="10")
        server_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 本机IP显示
        ip_frame = ttk.Frame(server_frame)
        ip_frame.pack(fill=tk.X)
        
        ttk.Label(ip_frame, text="本机IP:").pack(side=tk.LEFT)
        self.ip_label = ttk.Label(ip_frame, text="获取中...", font=('Arial', 12, 'bold'))
        self.ip_label.pack(side=tk.LEFT, padx=5)
        
        self.copy_ip_btn = ttk.Button(ip_frame, text="复制", command=self.copy_ip)
        self.copy_ip_btn.pack(side=tk.LEFT, padx=5)
        
        # 端口
        ttk.Label(ip_frame, text="端口: 12345").pack(side=tk.LEFT, padx=(20, 0))
        
        # 服务器状态
        status_frame = ttk.Frame(server_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.server_status = ttk.Label(status_frame, text="● 服务器未启动", foreground="gray")
        self.server_status.pack(side=tk.LEFT)
        
        self.connection_status = ttk.Label(status_frame, text="")
        self.connection_status.pack(side=tk.LEFT, padx=(20, 0))
        
        # ===== 测距结果区域 =====
        result_frame = ttk.LabelFrame(main_frame, text="测距结果", padding="10")
        result_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 当前距离（大字体显示）
        self.distance_label = ttk.Label(result_frame, text="-- m", font=('Arial', 48, 'bold'))
        self.distance_label.pack()
        
        # 状态显示
        self.state_label = ttk.Label(result_frame, text="状态: 等待连接")
        self.state_label.pack(pady=(5, 0))
        
        # 统计信息
        stats_frame = ttk.Frame(result_frame)
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.fps_label = ttk.Label(stats_frame, text="FPS: --")
        self.fps_label.pack(side=tk.LEFT, padx=10)
        
        self.mean_label = ttk.Label(stats_frame, text="均值: -- m")
        self.mean_label.pack(side=tk.LEFT, padx=10)
        
        self.std_label = ttk.Label(stats_frame, text="标准差: -- m")
        self.std_label.pack(side=tk.LEFT, padx=10)
        
        self.count_label = ttk.Label(stats_frame, text="测量次数: 0")
        self.count_label.pack(side=tk.LEFT, padx=10)
        
        # ===== 测量历史区域 =====
        history_frame = ttk.LabelFrame(main_frame, text="测量历史", padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 控制按钮
        btn_frame = ttk.Frame(history_frame)
        btn_frame.pack(fill=tk.X)
        
        self.clear_btn = ttk.Button(btn_frame, text="清除历史", command=self.clear_history)
        self.clear_btn.pack(side=tk.LEFT)
        
        self.export_btn = ttk.Button(btn_frame, text="导出数据", command=self.export_data)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        # 历史列表
        columns = ('序号', '时间', '距离', 'FPS')
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)
        
        self.history_tree.heading('序号', text='序号')
        self.history_tree.heading('时间', text='时间')
        self.history_tree.heading('距离', text='距离(m)')
        self.history_tree.heading('FPS', text='FPS')
        
        self.history_tree.column('序号', width=60)
        self.history_tree.column('时间', width=100)
        self.history_tree.column('距离', width=100)
        self.history_tree.column('FPS', width=80)
        
        self.history_tree.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 滚动条
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ===== 设备配置区域 =====
        config_frame = ttk.LabelFrame(main_frame, text="设备配置", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 设备自身距离设置
        dist_frame = ttk.Frame(config_frame)
        dist_frame.pack(fill=tk.X)
        
        ttk.Label(dist_frame, text="扬声器-麦克风距离(m):").pack(side=tk.LEFT)
        self.self_dist_entry = ttk.Entry(dist_frame, width=10)
        self.self_dist_entry.pack(side=tk.LEFT, padx=5)
        self.self_dist_entry.insert(0, "0.02")
        
        ttk.Button(dist_frame, text="应用", command=self.apply_config).pack(side=tk.LEFT, padx=5)
        
        # ===== 日志区域 =====
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 获取本机IP
        self.root.after(100, self.update_ip)
        
    def log(self, message):
        """添加日志"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def update_ip(self):
        """更新本机IP显示"""
        ip = self.engine.get_local_ip()
        self.ip_label.config(text=ip)
        
    def copy_ip(self):
        """复制IP到剪贴板"""
        ip = self.ip_label.cget("text")
        self.root.clipboard_clear()
        self.root.clipboard_append(ip)
        self.log(f"已复制IP: {ip}")
        
    def start_server(self):
        """启动服务器"""
        try:
            self.engine.start_server()
            self.server_status.config(text="● 服务器已启动", foreground="green")
            self.log("服务器已启动，等待目标设备连接...")
        except Exception as e:
            self.server_status.config(text="● 服务器启动失败", foreground="red")
            self.log(f"服务器启动失败: {e}")
            
    def on_connection_changed(self, connected, address):
        """连接状态改变回调"""
        def update():
            if connected:
                self.connection_status.config(
                    text=f"● 已连接: {address[0]}",
                    foreground="green"
                )
                self.state_label.config(text="状态: 已连接，等待测距")
                self.log(f"目标设备已连接: {address}")
            else:
                self.connection_status.config(text="", foreground="gray")
                self.state_label.config(text="状态: 等待连接")
                self.log("目标设备已断开")
                
        self.root.after(0, update)
        
    def on_distance_updated(self, distance):
        """距离更新回调"""
        def update():
            # 更新显示
            self.distance_label.config(text=f"{distance:.3f} m")
            
            # 更新统计
            stats = self.engine.get_statistics()
            if stats:
                self.fps_label.config(text=f"FPS: {stats['fps']:.1f}")
                self.mean_label.config(text=f"均值: {stats['mean']:.3f} m")
                self.std_label.config(text=f"标准差: {stats['std']:.3f} m")
                self.count_label.config(text=f"测量次数: {stats['count']}")
                
            # 添加到历史
            self.measurements.append({
                'time': datetime.now().strftime("%H:%M:%S.%f")[:-3],
                'distance': distance,
                'fps': stats['fps'] if stats else 0
            })
            
            self.history_tree.insert('', 0, values=(
                len(self.measurements),
                self.measurements[-1]['time'],
                f"{distance:.3f}",
                f"{self.measurements[-1]['fps']:.1f}"
            ))
            
        self.root.after(0, update)
        
    def on_state_changed(self, state):
        """状态改变回调"""
        state_texts = {
            'idle': '空闲',
            'waiting': '等待中',
            'sending': '发送信号',
            'receiving': '接收信号',
            'processing': '处理中'
        }
        
        def update():
            text = state_texts.get(state, state)
            self.state_label.config(text=f"状态: {text}")
            
        self.root.after(0, update)
        
    def on_error(self, error_msg):
        """错误回调"""
        self.root.after(0, lambda: self.log(f"错误: {error_msg}"))
        
    def apply_config(self):
        """应用配置"""
        try:
            d_self = float(self.self_dist_entry.get())
            self.engine.signal_processor.d_self = d_self
            self.log(f"设备自身距离已设置为: {d_self} m")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值")
            
    def clear_history(self):
        """清除历史"""
        self.measurements = []
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        self.log("已清除历史记录")
        
    def export_data(self):
        """导出数据"""
        if not self.measurements:
            messagebox.showinfo("提示", "没有数据可导出")
            return
            
        filename = f"anchor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("序号,时间,距离(m),FPS\n")
                for i, m in enumerate(self.measurements, 1):
                    f.write(f"{i},{m['time']},{m['distance']},{m['fps']}\n")
                    
            self.log(f"数据已导出到 {filename}")
            messagebox.showinfo("成功", f"数据已导出到 {filename}")
        except Exception as e:
            self.log(f"导出失败: {e}")
            messagebox.showerror("错误", f"导出失败: {e}")
            
    def on_closing(self):
        """关闭窗口"""
        self.engine.close()
        self.root.destroy()


def main():
    """主函数"""
    root = tk.Tk()
    app = AnchorDeviceApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
