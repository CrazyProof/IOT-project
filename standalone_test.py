# -*- coding: utf-8 -*-
"""
单机测试应用
用于单设备测试声波信号处理功能，不需要网络连接
可以通过回声测距或者模拟数据进行测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import numpy as np
from datetime import datetime
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from core.signal_processor import SignalProcessor
from core.audio_io import AudioIO


class StandaloneTestApp:
    """单机测试应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("声波测距 - 单机测试")
        self.root.geometry("900x700")
        
        # 初始化组件
        self.signal_processor = SignalProcessor()
        self.audio = AudioIO()
        
        # 测量数据
        self.measurements = []
        self.is_continuous = False
        
        self._create_ui()
        
    def _create_ui(self):
        """创建UI"""
        # 使用Notebook创建标签页
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 测试页面
        test_frame = ttk.Frame(notebook, padding="10")
        notebook.add(test_frame, text="信号测试")
        
        # 信号可视化页面
        visual_frame = ttk.Frame(notebook, padding="10")
        notebook.add(visual_frame, text="信号可视化")
        
        # 设备检测页面
        device_frame = ttk.Frame(notebook, padding="10")
        notebook.add(device_frame, text="设备检测")
        
        self._create_test_tab(test_frame)
        self._create_visual_tab(visual_frame)
        self._create_device_tab(device_frame)
        
    def _create_test_tab(self, parent):
        """创建测试标签页"""
        # 控制区域
        control_frame = ttk.LabelFrame(parent, text="测试控制", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack()
        
        ttk.Button(btn_frame, text="播放测试信号", command=self.play_test_signal).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="录音测试", command=self.record_test).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="播放+录音", command=self.play_and_record).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="单次测距", command=self.single_ranging).pack(side=tk.LEFT, padx=5)
        
        # 连续测距控制
        continuous_frame = ttk.Frame(control_frame)
        continuous_frame.pack(pady=(10, 0))
        
        self.continuous_btn = ttk.Button(continuous_frame, text="开始连续测距", 
                                         command=self.toggle_continuous)
        self.continuous_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(continuous_frame, text="间隔(秒):").pack(side=tk.LEFT)
        self.interval_entry = ttk.Entry(continuous_frame, width=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5)
        self.interval_entry.insert(0, "0.5")
        
        # 结果显示
        result_frame = ttk.LabelFrame(parent, text="测距结果", padding="10")
        result_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.distance_label = ttk.Label(result_frame, text="-- m", font=('Arial', 36, 'bold'))
        self.distance_label.pack()
        
        stats_frame = ttk.Frame(result_frame)
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.count_label = ttk.Label(stats_frame, text="测量次数: 0")
        self.count_label.pack(side=tk.LEFT, padx=10)
        
        self.mean_label = ttk.Label(stats_frame, text="均值: -- m")
        self.mean_label.pack(side=tk.LEFT, padx=10)
        
        self.std_label = ttk.Label(stats_frame, text="标准差: -- m")
        self.std_label.pack(side=tk.LEFT, padx=10)
        
        # 日志
        log_frame = ttk.LabelFrame(parent, text="日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def _create_visual_tab(self, parent):
        """创建信号可视化标签页"""
        # 控制
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill=tk.X)
        
        ttk.Button(ctrl_frame, text="显示Chirp信号", command=self.show_chirp).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="录音并分析", command=self.record_and_analyze).pack(side=tk.LEFT, padx=5)
        
        # 图表
        self.fig = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=10)
        
    def _create_device_tab(self, parent):
        """创建设备检测标签页"""
        # 设备列表
        device_frame = ttk.LabelFrame(parent, text="音频设备", padding="10")
        device_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(device_frame, text="刷新设备列表", command=self.refresh_devices).pack()
        
        # 输入设备
        ttk.Label(device_frame, text="输入设备（麦克风）:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        
        self.input_list = tk.Listbox(device_frame, height=5)
        self.input_list.pack(fill=tk.X)
        
        # 输出设备
        ttk.Label(device_frame, text="输出设备（扬声器）:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        
        self.output_list = tk.Listbox(device_frame, height=5)
        self.output_list.pack(fill=tk.X)
        
        # 初始加载设备
        self.root.after(100, self.refresh_devices)
        
    def log(self, message):
        """添加日志"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def play_test_signal(self):
        """播放测试信号"""
        self.log("播放Chirp信号...")
        signal = self.signal_processor.generate_ranging_signal()
        
        def play():
            self.audio.play_sound(signal, blocking=True)
            self.root.after(0, lambda: self.log("播放完成"))
            
        threading.Thread(target=play, daemon=True).start()
        
    def record_test(self):
        """录音测试"""
        self.log("开始录音（2秒）...")
        
        def record():
            recorded = self.audio.record_for_duration(2.0)
            self.root.after(0, lambda: self.log(f"录音完成，采样点数: {len(recorded)}"))
            
        threading.Thread(target=record, daemon=True).start()
        
    def play_and_record(self):
        """播放并录音"""
        self.log("播放并录音...")
        signal = self.signal_processor.generate_ranging_signal()
        
        def do_play_record():
            recorded = self.audio.play_and_record(signal, extra_duration=0.5)
            
            # 检测Chirp
            detections, correlation = self.signal_processor.detect_chirp(recorded)
            
            self.root.after(0, lambda: self._show_play_record_result(recorded, detections, correlation))
            
        threading.Thread(target=do_play_record, daemon=True).start()
        
    def _show_play_record_result(self, recorded, detections, correlation):
        """显示播放录音结果"""
        self.log(f"录音完成，检测到 {len(detections)} 个Chirp信号")
        
        if detections:
            for i, pos in enumerate(detections):
                time_ms = pos / self.signal_processor.sample_rate * 1000
                self.log(f"  Chirp {i+1}: 位置 {pos} ({time_ms:.1f}ms)")
                
        # 更新图表
        self.fig.clear()
        
        ax1 = self.fig.add_subplot(211)
        t = np.arange(len(recorded)) / self.signal_processor.sample_rate * 1000
        ax1.plot(t, recorded)
        ax1.set_xlabel('时间 (ms)')
        ax1.set_ylabel('幅度')
        ax1.set_title('录制的信号')
        
        # 标记检测位置
        for pos in detections:
            time_ms = pos / self.signal_processor.sample_rate * 1000
            ax1.axvline(time_ms, color='r', linestyle='--', alpha=0.7)
            
        ax2 = self.fig.add_subplot(212)
        t_corr = np.arange(len(correlation)) / self.signal_processor.sample_rate * 1000
        ax2.plot(t_corr, correlation)
        ax2.set_xlabel('时间 (ms)')
        ax2.set_ylabel('相关值')
        ax2.set_title('互相关结果')
        
        self.fig.tight_layout()
        self.canvas.draw()
        
    def single_ranging(self):
        """单次测距"""
        self.log("执行单次测距...")
        
        def do_ranging():
            signal = self.signal_processor.generate_ranging_signal()
            recorded = self.audio.play_and_record(signal, extra_duration=1.0)
            detections, _ = self.signal_processor.detect_chirp(recorded, threshold_ratio=0.2)
            
            if len(detections) >= 2:
                # 计算时间差
                time_diff = (detections[1] - detections[0]) / self.signal_processor.sample_rate
                # 距离 = 声速 * 时间 / 2 (往返)
                distance = self.signal_processor.speed_of_sound * time_diff / 2
                
                self.measurements.append(distance)
                self.root.after(0, lambda: self._update_distance(distance))
            else:
                self.root.after(0, lambda: self.log("未检测到足够的信号"))
                
        threading.Thread(target=do_ranging, daemon=True).start()
        
    def _update_distance(self, distance):
        """更新距离显示"""
        self.distance_label.config(text=f"{distance:.3f} m")
        self.count_label.config(text=f"测量次数: {len(self.measurements)}")
        
        if self.measurements:
            mean = np.mean(self.measurements)
            std = np.std(self.measurements)
            self.mean_label.config(text=f"均值: {mean:.3f} m")
            self.std_label.config(text=f"标准差: {std:.3f} m")
            
        self.log(f"测距结果: {distance:.3f} m")
        
    def toggle_continuous(self):
        """切换连续测距"""
        self.is_continuous = not self.is_continuous
        
        if self.is_continuous:
            self.continuous_btn.config(text="停止连续测距")
            self.log("开始连续测距")
            
            def continuous_loop():
                while self.is_continuous:
                    try:
                        interval = float(self.interval_entry.get())
                    except:
                        interval = 0.5
                        
                    signal = self.signal_processor.generate_ranging_signal()
                    recorded = self.audio.play_and_record(signal, extra_duration=0.5)
                    detections, _ = self.signal_processor.detect_chirp(recorded, threshold_ratio=0.2)
                    
                    if len(detections) >= 2:
                        time_diff = (detections[1] - detections[0]) / self.signal_processor.sample_rate
                        distance = self.signal_processor.speed_of_sound * time_diff / 2
                        self.measurements.append(distance)
                        self.root.after(0, lambda d=distance: self._update_distance(d))
                        
                    time.sleep(interval)
                    
            threading.Thread(target=continuous_loop, daemon=True).start()
        else:
            self.continuous_btn.config(text="开始连续测距")
            self.log("停止连续测距")
            
    def show_chirp(self):
        """显示Chirp信号"""
        chirp = self.signal_processor.reference_chirp
        
        self.fig.clear()
        
        # 时域
        ax1 = self.fig.add_subplot(211)
        t = np.arange(len(chirp)) / self.signal_processor.sample_rate * 1000
        ax1.plot(t, chirp)
        ax1.set_xlabel('时间 (ms)')
        ax1.set_ylabel('幅度')
        ax1.set_title('Chirp信号 - 时域')
        ax1.grid(True, alpha=0.3)
        
        # 频谱
        ax2 = self.fig.add_subplot(212)
        freqs = np.fft.rfftfreq(len(chirp), 1/self.signal_processor.sample_rate)
        spectrum = np.abs(np.fft.rfft(chirp))
        ax2.plot(freqs/1000, spectrum)
        ax2.set_xlabel('频率 (kHz)')
        ax2.set_ylabel('幅度')
        ax2.set_title('Chirp信号 - 频谱')
        ax2.set_xlim(0, 25)
        ax2.grid(True, alpha=0.3)
        
        self.fig.tight_layout()
        self.canvas.draw()
        
        self.log(f"Chirp信号: {self.signal_processor.chirp_f0/1000:.1f}kHz - {self.signal_processor.chirp_f1/1000:.1f}kHz, "
                f"时长: {self.signal_processor.chirp_duration*1000:.1f}ms")
        
    def record_and_analyze(self):
        """录音并分析"""
        self.log("录音2秒并分析...")
        
        def do_record():
            recorded = self.audio.record_for_duration(2.0)
            detections, correlation = self.signal_processor.detect_chirp(recorded)
            
            self.root.after(0, lambda: self._show_analysis(recorded, detections, correlation))
            
        threading.Thread(target=do_record, daemon=True).start()
        
    def _show_analysis(self, recorded, detections, correlation):
        """显示分析结果"""
        self.log(f"分析完成，检测到 {len(detections)} 个Chirp")
        
        self.fig.clear()
        
        # 原始信号
        ax1 = self.fig.add_subplot(311)
        t = np.arange(len(recorded)) / self.signal_processor.sample_rate
        ax1.plot(t, recorded)
        ax1.set_xlabel('时间 (s)')
        ax1.set_ylabel('幅度')
        ax1.set_title('录制的信号')
        
        # 频谱图
        ax2 = self.fig.add_subplot(312)
        freqs = np.fft.rfftfreq(len(recorded), 1/self.signal_processor.sample_rate)
        spectrum = np.abs(np.fft.rfft(recorded))
        ax2.plot(freqs/1000, spectrum)
        ax2.set_xlabel('频率 (kHz)')
        ax2.set_ylabel('幅度')
        ax2.set_title('频谱')
        ax2.set_xlim(0, 25)
        
        # 互相关
        ax3 = self.fig.add_subplot(313)
        t_corr = np.arange(len(correlation)) / self.signal_processor.sample_rate
        ax3.plot(t_corr, correlation)
        ax3.set_xlabel('时间 (s)')
        ax3.set_ylabel('相关值')
        ax3.set_title('互相关结果')
        
        # 标记检测位置
        for pos in detections:
            t_pos = pos / self.signal_processor.sample_rate
            ax3.axvline(t_pos, color='r', linestyle='--', alpha=0.7)
            
        self.fig.tight_layout()
        self.canvas.draw()
        
    def refresh_devices(self):
        """刷新设备列表"""
        devices = self.audio.get_devices()
        
        self.input_list.delete(0, tk.END)
        for d in devices['input']:
            self.input_list.insert(tk.END, f"[{d['id']}] {d['name']}")
            
        self.output_list.delete(0, tk.END)
        for d in devices['output']:
            self.output_list.insert(tk.END, f"[{d['id']}] {d['name']}")
            
        self.log(f"检测到 {len(devices['input'])} 个输入设备, {len(devices['output'])} 个输出设备")


def main():
    root = tk.Tk()
    app = StandaloneTestApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
