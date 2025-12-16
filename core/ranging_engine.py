# -*- coding: utf-8 -*-
"""
测距引擎
整合信号处理、音频IO和网络通信，实现完整的测距功能
"""

import time
import threading
import numpy as np
from typing import Callable, Optional
from .signal_processor import SignalProcessor
from .audio_io import AudioIO
from .network import NetworkManager


class RangingEngine:
    """测距引擎 - 核心测距逻辑"""
    
    # 测距状态
    STATE_IDLE = 'idle'
    STATE_WAITING = 'waiting'
    STATE_SENDING = 'sending'
    STATE_RECEIVING = 'receiving'
    STATE_PROCESSING = 'processing'
    
    def __init__(self, device_role='target', sample_rate=44100):
        """
        初始化测距引擎
        
        Args:
            device_role: 设备角色 ('target' 目标设备 或 'anchor' 锚节点)
            sample_rate: 采样率
        """
        self.device_role = device_role
        self.sample_rate = sample_rate
        
        # 核心组件
        self.signal_processor = SignalProcessor(sample_rate=sample_rate)
        self.audio = AudioIO(sample_rate=sample_rate)
        self.network = NetworkManager()
        
        # 状态
        self.state = self.STATE_IDLE
        self.is_ranging = False
        self.is_connected = False
        
        # 测距参数
        self.ranging_interval = 0.1  # 测距间隔（秒）
        self.record_duration = 1.0   # 录音时长（秒），进一步延长以确保收到对方Chirp
        
        # 测量数据
        self.local_detections = []   # 本地检测结果
        self.remote_detections = []  # 远程检测结果
        self.current_distance = None
        self.distance_history = []
        
        # 滑动窗口滤波器参数
        self.filter_window_size = 5  # 滤波窗口大小
        self.recent_distances = []   # 最近的测量值，用于滤波
        self.use_median_filter = True  # 使用中值滤波去除异常值
        
        # 统计数据
        self.measurement_count = 0
        self.successful_count = 0
        self.fps = 0
        self.last_fps_time = time.time()
        self.fps_count = 0
        
        # 回调函数
        self.on_distance_updated: Optional[Callable] = None
        self.on_state_changed: Optional[Callable] = None
        self.on_connection_changed: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # 测距线程
        self.ranging_thread = None
        
        # 注册网络消息处理器
        self._setup_network_handlers()
        
    def _setup_network_handlers(self):
        """设置网络消息处理器"""
        self.network.register_handler(
            NetworkManager.MSG_START_RANGING, 
            self._on_start_ranging
        )
        self.network.register_handler(
            NetworkManager.MSG_CHIRP_SENT, 
            self._on_chirp_sent
        )
        self.network.register_handler(
            NetworkManager.MSG_DETECTION_RESULT, 
            self._on_detection_result
        )
        self.network.register_handler(
            NetworkManager.MSG_DISTANCE_RESULT, 
            self._on_distance_result
        )
        
        # 连接回调
        self.network.on_connect = self._on_connected
        self.network.on_disconnect = self._on_disconnected
        
    def _on_connected(self, address):
        """连接成功回调"""
        self.is_connected = True
        if self.on_connection_changed:
            self.on_connection_changed(True, address)
            
    def _on_disconnected(self):
        """断开连接回调"""
        self.is_connected = False
        self.stop_ranging()
        if self.on_connection_changed:
            self.on_connection_changed(False, None)
            
    def _on_start_ranging(self, data, timestamp):
        """收到开始测距消息"""
        if self.device_role == 'anchor':
            # 锚节点收到目标设备的测距请求
            self._do_anchor_ranging()
            
    def _on_chirp_sent(self, data, timestamp):
        """收到对方已发送Chirp的通知"""
        pass  # 用于同步
        
    def _on_detection_result(self, data, timestamp):
        """收到对方的检测结果"""
        self.remote_detections = data.get('detections', [])
        self._calculate_distance()
        
    def _on_distance_result(self, data, timestamp):
        """收到距离计算结果"""
        distance = data.get('distance')
        if distance is not None:
            self.current_distance = distance
            self._update_distance(distance)
            
    def _set_state(self, new_state):
        """更新状态"""
        self.state = new_state
        if self.on_state_changed:
            self.on_state_changed(new_state)
            
    def start_server(self, host='0.0.0.0'):
        """
        以服务器模式启动（锚节点）
        
        Args:
            host: 监听地址
        """
        self.network.start_server(host)
        
    def connect_to_anchor(self, host, timeout=10):
        """
        连接到锚节点（目标设备）
        
        Args:
            host: 锚节点IP地址
            timeout: 连接超时
            
        Returns:
            bool: 连接是否成功
        """
        return self.network.connect_to_server(host, timeout)
        
    def start_ranging(self):
        """开始连续测距"""
        if not self.is_connected:
            if self.on_error:
                self.on_error("未连接到对方设备")
            return False
            
        if self.is_ranging:
            return True
            
        self.is_ranging = True
        self.last_fps_time = time.time()
        self.fps_count = 0
        
        # 启动测距线程
        self.ranging_thread = threading.Thread(target=self._ranging_loop, daemon=True)
        self.ranging_thread.start()
        
        return True
        
    def stop_ranging(self):
        """停止测距"""
        self.is_ranging = False
        self._set_state(self.STATE_IDLE)
        
    def _ranging_loop(self):
        """测距主循环"""
        while self.is_ranging and self.is_connected:
            try:
                if self.device_role == 'target':
                    self._do_target_ranging()
                else:
                    # 锚节点等待目标设备发起
                    time.sleep(0.1)
                    
                # 控制测距频率
                time.sleep(self.ranging_interval)
                
            except Exception as e:
                print(f"测距错误: {e}")
                if self.on_error:
                    self.on_error(str(e))
                    
    def _do_target_ranging(self):
        """目标设备执行测距"""
        self._set_state(self.STATE_SENDING)
        self.measurement_count += 1
        
        # 生成测距信号
        signal = self.signal_processor.generate_ranging_signal()
        
        # 通知锚节点准备
        self.network.send_message(NetworkManager.MSG_START_RANGING, {
            'measurement_id': self.measurement_count
        })
        
        # 等待锚节点准备好录音（增加等待时间确保同步）
        time.sleep(0.15)
        
        # 播放并录音
        self._set_state(self.STATE_RECEIVING)
        recorded = self.audio.play_and_record(signal, extra_duration=self.record_duration)
        
        # 处理信号
        self._set_state(self.STATE_PROCESSING)
        detections, correlation = self.signal_processor.detect_chirp(recorded)
        
        # 调试输出
        print(f"[Target] 检测到 {len(detections)} 个峰值: {detections}")
        
        self.local_detections = detections
        
        # 发送检测结果给锚节点
        self.network.send_message(NetworkManager.MSG_DETECTION_RESULT, {
            'detections': detections,
            'measurement_id': self.measurement_count
        })
        
    def _do_anchor_ranging(self):
        """锚节点执行测距响应"""
        self._set_state(self.STATE_RECEIVING)
        
        # 立即开始录音，准备接收目标设备的信号
        # 生成并发送响应信号
        self._set_state(self.STATE_SENDING)
        signal = self.signal_processor.generate_ranging_signal()
        
        # 播放并录音（不需要额外等待，直接开始）
        recorded = self.audio.play_and_record(signal, extra_duration=self.record_duration)
        
        # 处理信号
        self._set_state(self.STATE_PROCESSING)
        detections, correlation = self.signal_processor.detect_chirp(recorded)
        
        # 调试输出
        print(f"[Anchor] 检测到 {len(detections)} 个峰值: {detections}")
        
        self.local_detections = detections
        
        # 发送检测结果
        self.network.send_message(NetworkManager.MSG_DETECTION_RESULT, {
            'detections': detections
        })
        
    def _calculate_distance(self):
        """计算距离 - 增强版本，加入有效性验证"""
        # 检查检测结果是否有效
        if len(self.local_detections) < 2 or len(self.remote_detections) < 2:
            print(f"检测点不足: local={len(self.local_detections)}, remote={len(self.remote_detections)}")
            return
        
        # 使用BeepBeep算法
        t_a1 = self.local_detections[0]   # 本地收到自己的信号
        t_a3 = self.local_detections[1]   # 本地收到对方的信号
        t_b1 = self.remote_detections[0]  # 对方收到本地的信号
        t_b3 = self.remote_detections[1]  # 对方收到自己的信号
        
        # 验证时间差是否合理
        delta_a = t_a3 - t_a1
        delta_b = t_b3 - t_b1
        
        # 时间差应该为正数，且不应该太大（对应最大测距范围）
        max_time_diff = int(self.sample_rate * 0.5)  # 最大约85米
        min_time_diff = int(self.sample_rate * 0.001)  # 最小约0.3米
        
        if delta_a < min_time_diff or delta_b < min_time_diff:
            print(f"时间差过小，可能是检测错误: delta_a={delta_a}, delta_b={delta_b}")
            return
        
        if delta_a > max_time_diff or delta_b > max_time_diff:
            print(f"时间差过大，可能是检测错误: delta_a={delta_a}, delta_b={delta_b}")
            return
        
        distance = self.signal_processor.calculate_distance_beepbeep(
            t_a1, t_a3, t_b1, t_b3
        )
        
        # 验证距离是否在合理范围内
        if distance < 0 or distance > 50:  # 最大50米
            print(f"计算距离异常: {distance:.3f}m，丢弃此次测量")
            return
        
        self._update_distance(distance)
        
        # 发送结果给对方
        self.network.send_message(NetworkManager.MSG_DISTANCE_RESULT, {
            'distance': distance
        })
        
        self.successful_count += 1
            
    def _update_distance(self, distance):
        """更新距离结果，加入滤波处理"""
        # 将原始测量值加入滤波窗口
        self.recent_distances.append(distance)
        if len(self.recent_distances) > self.filter_window_size:
            self.recent_distances.pop(0)
        
        # 应用滤波
        if self.use_median_filter and len(self.recent_distances) >= 3:
            # 中值滤波：去除异常值的效果更好
            filtered_distance = np.median(self.recent_distances)
        elif len(self.recent_distances) >= 2:
            # 简单移动平均
            filtered_distance = np.mean(self.recent_distances)
        else:
            filtered_distance = distance
        
        self.current_distance = filtered_distance
        self.distance_history.append({
            'distance': filtered_distance,
            'raw_distance': distance,
            'timestamp': time.time()
        })
        
        # 只保留最近100条记录
        if len(self.distance_history) > 100:
            self.distance_history = self.distance_history[-100:]
            
        # 更新FPS
        self.fps_count += 1
        current_time = time.time()
        elapsed = current_time - self.last_fps_time
        if elapsed >= 1.0:
            self.fps = self.fps_count / elapsed
            self.fps_count = 0
            self.last_fps_time = current_time
            
        # 回调
        if self.on_distance_updated:
            self.on_distance_updated(distance)
            
        self._set_state(self.STATE_IDLE)
        
    def do_single_measurement(self):
        """
        执行单次测量（简化版，用于测试）
        
        Returns:
            float: 测量的距离，失败返回None
        """
        if not self.is_connected:
            return None
            
        # 生成信号
        signal = self.signal_processor.generate_ranging_signal()
        
        # 播放并录音
        recorded = self.audio.play_and_record(signal, extra_duration=0.5)
        
        # 检测
        detections, _ = self.signal_processor.detect_chirp(recorded)
        
        if len(detections) >= 2:
            # 简化计算：使用时间差
            time_diff = detections[1] - detections[0]
            distance = self.signal_processor.calculate_distance_simple(time_diff)
            return distance
            
        return None
        
    def get_statistics(self):
        """
        获取测距统计数据
        
        Returns:
            dict: 统计数据
        """
        if not self.distance_history:
            return None
            
        distances = [d['distance'] for d in self.distance_history]
        
        return {
            'count': len(distances),
            'mean': np.mean(distances),
            'std': np.std(distances),
            'min': np.min(distances),
            'max': np.max(distances),
            'fps': self.fps,
            'success_rate': self.successful_count / max(1, self.measurement_count)
        }
        
    def get_local_ip(self):
        """获取本机IP"""
        return self.network.get_local_ip()
        
    def close(self):
        """关闭引擎"""
        self.stop_ranging()
        self.network.close()


class SimplifiedRangingEngine:
    """
    简化版测距引擎
    不需要网络通信，适合单机测试或特殊场景
    """
    
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.signal_processor = SignalProcessor(sample_rate=sample_rate)
        self.audio = AudioIO(sample_rate=sample_rate)
        
        self.is_ranging = False
        self.current_distance = None
        self.distance_history = []
        
        self.on_distance_updated: Optional[Callable] = None
        
    def measure_once(self):
        """
        执行一次测量
        发送Chirp信号，通过回声计算距离（需要反射面）
        
        Returns:
            float: 距离（米）
        """
        # 生成信号
        signal = self.signal_processor.generate_ranging_signal()
        
        # 播放并录音
        recorded = self.audio.play_and_record(signal, extra_duration=1.0)
        
        # 检测Chirp
        detections, correlation = self.signal_processor.detect_chirp(recorded, threshold_ratio=0.2)
        
        if len(detections) >= 2:
            # 计算时间差
            time_diff_samples = detections[1] - detections[0]
            time_diff = time_diff_samples / self.sample_rate
            
            # 距离 = 声速 * 时间 / 2 (往返)
            distance = self.signal_processor.speed_of_sound * time_diff / 2
            
            self.current_distance = distance
            self.distance_history.append(distance)
            
            if self.on_distance_updated:
                self.on_distance_updated(distance)
                
            return distance
            
        return None
