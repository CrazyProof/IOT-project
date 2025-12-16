# -*- coding: utf-8 -*-
"""
目标设备GUI应用程序
实现声波测距的移动端（目标设备）应用
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


class TargetDeviceApp:
    """目标设备应用程序"""
    
    def __init__(self, root):
        """
        初始化应用程序
        
        Args:
            root: Tkinter根窗口
        """
        self.root = root
        self.root.title("声波测距 - 目标设备")
        self.root.geometry("600x700")
        self.root.resizable(True, True)
        
        # 测距引擎
        self.engine = RangingEngine(device_role='target')
        
        # 设置回调
        self.engine.on_distance_updated = self.on_distance_updated
        self.engine.on_state_changed = self.on_state_changed
        self.engine.on_connection_changed = self.on_connection_changed
        self.engine.on_error = self.on_error
        
        # 测量历史
        self.measurements = []
        self.is_recording = False
        self.actual_distance = 0  # 用于记录实际距离
        
        # 创建UI
        self._create_ui()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def _create_ui(self):
        """创建用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== 连接设置区域 =====
        connection_frame = ttk.LabelFrame(main_frame, text="连接设置", padding="10")
        connection_frame.pack(fill=tk.X, pady=(0, 10))
        
        # IP地址输入
        ip_frame = ttk.Frame(connection_frame)
        ip_frame.pack(fill=tk.X)
        
        ttk.Label(ip_frame, text="锚节点IP:").pack(side=tk.LEFT)
        self.ip_entry = ttk.Entry(ip_frame, width=20)
        self.ip_entry.pack(side=tk.LEFT, padx=(5, 10))
        self.ip_entry.insert(0, "192.168.1.100")
        
        self.connect_btn = ttk.Button(ip_frame, text="连接", command=self.connect_to_anchor)
        self.connect_btn.pack(side=tk.LEFT)
        
        self.disconnect_btn = ttk.Button(ip_frame, text="断开", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # 连接状态
        self.connection_status = ttk.Label(connection_frame, text="● 未连接", foreground="red")
        self.connection_status.pack(pady=(5, 0))
        
        # ===== 测距控制区域 =====
        control_frame = ttk.LabelFrame(main_frame, text="测距控制", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack()
        
        self.start_btn = ttk.Button(btn_frame, text="▶ 开始测距", command=self.start_ranging, 
                                    width=15, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="■ 停止测距", command=self.stop_ranging,
                                   width=15, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.single_btn = ttk.Button(btn_frame, text="单次测量", command=self.single_measurement,
                                     width=15, state=tk.DISABLED)
        self.single_btn.pack(side=tk.LEFT, padx=5)
        
        # 状态显示
        self.state_label = ttk.Label(control_frame, text="状态: 空闲")
        self.state_label.pack(pady=(5, 0))
        
        # ===== 测距结果区域 =====
        result_frame = ttk.LabelFrame(main_frame, text="测距结果", padding="10")
        result_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 当前距离（大字体显示）
        self.distance_label = ttk.Label(result_frame, text="-- m", font=('Arial', 48, 'bold'))
        self.distance_label.pack()
        
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
        
        # ===== 实验记录区域 =====
        record_frame = ttk.LabelFrame(main_frame, text="实验记录", padding="10")
        record_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 实际距离输入
        dist_frame = ttk.Frame(record_frame)
        dist_frame.pack(fill=tk.X)
        
        ttk.Label(dist_frame, text="实际距离(m):").pack(side=tk.LEFT)
        self.actual_dist_entry = ttk.Entry(dist_frame, width=10)
        self.actual_dist_entry.pack(side=tk.LEFT, padx=5)
        self.actual_dist_entry.insert(0, "1.0")
        
        self.record_btn = ttk.Button(dist_frame, text="开始记录", command=self.toggle_recording)
        self.record_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = ttk.Button(dist_frame, text="清除记录", command=self.clear_records)
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        self.export_btn = ttk.Button(dist_frame, text="导出数据", command=self.export_data)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        # 记录列表
        columns = ('时间', '实际距离', '测量距离', '误差')
        self.record_tree = ttk.Treeview(record_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            self.record_tree.heading(col, text=col)
            self.record_tree.column(col, width=100)
            
        self.record_tree.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 滚动条
        scrollbar = ttk.Scrollbar(record_frame, orient=tk.VERTICAL, command=self.record_tree.yview)
        self.record_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ===== 日志区域 =====
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def log(self, message):
        """添加日志"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def connect_to_anchor(self):
        """连接到锚节点"""
        host = self.ip_entry.get().strip()
        if not host:
            messagebox.showerror("错误", "请输入锚节点IP地址")
            return
            
        self.log(f"正在连接到 {host}...")
        self.connect_btn.config(state=tk.DISABLED)
        
        def connect_thread():
            success = self.engine.connect_to_anchor(host)
            self.root.after(0, lambda: self._on_connect_result(success))
            
        threading.Thread(target=connect_thread, daemon=True).start()
        
    def _on_connect_result(self, success):
        """连接结果处理"""
        if success:
            self.log("连接成功!")
        else:
            self.log("连接失败!")
            self.connect_btn.config(state=tk.NORMAL)
            
    def disconnect(self):
        """断开连接"""
        self.engine.network.close()
        self.log("已断开连接")
        
    def on_connection_changed(self, connected, address):
        """连接状态改变回调"""
        def update():
            if connected:
                self.connection_status.config(text="● 已连接", foreground="green")
                self.connect_btn.config(state=tk.DISABLED)
                self.disconnect_btn.config(state=tk.NORMAL)
                self.start_btn.config(state=tk.NORMAL)
                self.single_btn.config(state=tk.NORMAL)
            else:
                self.connection_status.config(text="● 未连接", foreground="red")
                self.connect_btn.config(state=tk.NORMAL)
                self.disconnect_btn.config(state=tk.DISABLED)
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.DISABLED)
                self.single_btn.config(state=tk.DISABLED)
                
        self.root.after(0, update)
        
    def start_ranging(self):
        """开始测距"""
        if self.engine.start_ranging():
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.single_btn.config(state=tk.DISABLED)
            self.log("开始连续测距")
        else:
            self.log("启动测距失败")
            
    def stop_ranging(self):
        """停止测距"""
        self.engine.stop_ranging()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.single_btn.config(state=tk.NORMAL)
        self.log("停止测距")
        
    def single_measurement(self):
        """单次测量"""
        self.log("执行单次测量...")
        
        def measure():
            distance = self.engine.do_single_measurement()
            if distance is not None:
                self.root.after(0, lambda: self.log(f"单次测量结果: {distance:.3f} m"))
            else:
                self.root.after(0, lambda: self.log("单次测量失败"))
                
        threading.Thread(target=measure, daemon=True).start()
        
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
                
            # 如果正在记录，添加到记录列表
            if self.is_recording:
                try:
                    actual = float(self.actual_dist_entry.get())
                    error = abs(distance - actual)
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    
                    self.measurements.append({
                        'time': timestamp,
                        'actual': actual,
                        'measured': distance,
                        'error': error
                    })
                    
                    self.record_tree.insert('', 0, values=(
                        timestamp, f"{actual:.2f}", f"{distance:.3f}", f"{error:.3f}"
                    ))
                except ValueError:
                    pass
                    
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
        
    def toggle_recording(self):
        """切换记录状态"""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.record_btn.config(text="停止记录")
            self.log("开始记录测量数据")
        else:
            self.record_btn.config(text="开始记录")
            self.log("停止记录测量数据")
            
    def clear_records(self):
        """清除记录"""
        self.measurements = []
        for item in self.record_tree.get_children():
            self.record_tree.delete(item)
        self.log("已清除记录")
        
    def export_data(self):
        """导出数据到CSV"""
        if not self.measurements:
            messagebox.showinfo("提示", "没有数据可导出")
            return
            
        filename = f"ranging_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("时间,实际距离(m),测量距离(m),误差(m)\n")
                for m in self.measurements:
                    f.write(f"{m['time']},{m['actual']},{m['measured']},{m['error']}\n")
                    
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
    app = TargetDeviceApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
