# -*- coding: utf-8 -*-
"""
声波信号处理核心模块
实现Chirp信号生成、互相关检测、距离计算等核心算法
"""

import numpy as np
from scipy import signal
from scipy.io import wavfile
import time


class SignalProcessor:
    """声波信号处理器"""
    
    def __init__(self, sample_rate=44100, speed_of_sound=343.0):
        """
        初始化信号处理器
        
        Args:
            sample_rate: 采样率 (Hz)
            speed_of_sound: 声速 (m/s)，标准条件下约343m/s
        """
        self.sample_rate = sample_rate
        self.speed_of_sound = speed_of_sound
        
        # Chirp信号参数
        self.chirp_duration = 0.01  # Chirp信号持续时间 (秒)
        self.chirp_f0 = 17000       # 起始频率 (Hz) - 使用超声波范围减少干扰
        self.chirp_f1 = 20000       # 结束频率 (Hz)
        
        # 设备自身距离（扬声器到麦克风的距离）
        self.d_self = 0.15  # 默认15cm，可根据实际设备调整
        
        # 生成参考Chirp信号
        self.reference_chirp = self._generate_chirp()
        
    def _generate_chirp(self):
        """
        生成Chirp信号（线性调频信号）
        
        Returns:
            numpy.ndarray: Chirp信号数组
        """
        t = np.linspace(0, self.chirp_duration, 
                       int(self.sample_rate * self.chirp_duration), 
                       endpoint=False)
        
        # 生成线性调频信号
        chirp_signal = signal.chirp(t, f0=self.chirp_f0, f1=self.chirp_f1, 
                                    t1=self.chirp_duration, method='linear')
        
        # 应用汉宁窗减少频谱泄漏
        window = np.hanning(len(chirp_signal))
        chirp_signal = chirp_signal * window
        
        # 归一化
        chirp_signal = chirp_signal / np.max(np.abs(chirp_signal))
        
        return chirp_signal.astype(np.float32)
    
    def generate_ranging_signal(self):
        """
        生成用于测距的完整信号
        包含静音段 + Chirp信号 + 静音段
        
        Returns:
            numpy.ndarray: 测距信号
        """
        # 前后添加静音段
        silence_before = np.zeros(int(self.sample_rate * 0.05))  # 50ms静音
        silence_after = np.zeros(int(self.sample_rate * 0.3))    # 300ms等待响应
        
        # 组合信号
        ranging_signal = np.concatenate([
            silence_before,
            self.reference_chirp,
            silence_after
        ])
        
        return ranging_signal.astype(np.float32)
    
    def detect_chirp(self, recorded_signal, threshold_ratio=0.08, expected_peaks=2):
        """
        在录制的信号中检测Chirp信号位置
        使用互相关方法，增强鲁棒性
        
        Args:
            recorded_signal: 录制的音频信号
            threshold_ratio: 峰值检测阈值比例（降低以提高检测灵敏度）
            expected_peaks: 期望检测到的峰值数量
            
        Returns:
            list: 检测到的Chirp信号位置（采样点索引）列表
        """
        # 确保信号是一维的
        if len(recorded_signal.shape) > 1:
            recorded_signal = recorded_signal[:, 0]
        
        # 带通滤波，只保留Chirp频率范围
        nyquist = self.sample_rate / 2
        low = (self.chirp_f0 - 1000) / nyquist
        high = min((self.chirp_f1 + 1000) / nyquist, 0.99)
        
        b, a = signal.butter(4, [low, high], btype='band')
        filtered_signal = signal.filtfilt(b, a, recorded_signal)
        
        # 计算互相关
        correlation = signal.correlate(filtered_signal, self.reference_chirp, mode='valid')
        correlation = np.abs(correlation)
        
        # 归一化
        max_corr = np.max(correlation)
        if max_corr > 0:
            correlation_norm = correlation / max_corr
        else:
            return [], correlation
        
        # 检测峰值 - 使用更宽松的条件
        # 最小间隔：根据录音时长动态调整，至少15ms，避免漏掉对方较弱的峰
        min_distance = int(self.sample_rate * 0.015)
        
        peaks, properties = signal.find_peaks(
            correlation_norm, 
            height=threshold_ratio,
            distance=min_distance,
            prominence=0.1  # 添加显著性要求，过滤噪声峰值
        )
        
        # 如果检测到的峰值数量不足，尝试降低阈值重新检测
        if len(peaks) < expected_peaks:
            peaks, properties = signal.find_peaks(
                correlation_norm, 
                height=threshold_ratio * 0.5,
                distance=min_distance,
                prominence=0.05
            )
        
        # 返回所有检测到的峰值，由上层逻辑决定如何筛选
        # 排序以确保时间顺序
        peaks = np.sort(peaks)
        
        return peaks.tolist(), correlation
    
    def calculate_distance_beepbeep(self, t_a1, t_a3, t_b1, t_b3, d_aa=None, d_bb=None):
        """
        使用BeepBeep算法计算距离
        
        公式: D = c/2 * [(t_A3 - t_A1) - (t_B3 - t_B1)] + (d_AA + d_BB)/2
        
        Args:
            t_a1: 设备A收到自己信号的时间（采样点）
            t_a3: 设备A收到设备B信号的时间（采样点）
            t_b1: 设备B收到设备A信号的时间（采样点）
            t_b3: 设备B收到自己信号的时间（采样点）
            d_aa: 设备A自身距离（扬声器到麦克风）
            d_bb: 设备B自身距离（扬声器到麦克风）
            
        Returns:
            float: 计算得到的距离（米）
        """
        if d_aa is None:
            d_aa = self.d_self
        if d_bb is None:
            d_bb = self.d_self
            
        # 将采样点转换为时间（秒）
        delta_a = (t_a3 - t_a1) / self.sample_rate
        delta_b = (t_b3 - t_b1) / self.sample_rate
        
        # 计算距离
        distance = (self.speed_of_sound / 2) * (delta_a - delta_b) + (d_aa + d_bb) / 2
        
        return max(0, distance)  # 距离不能为负
    
    def calculate_distance_simple(self, time_diff_samples):
        """
        简化的距离计算（单向测量）
        
        Args:
            time_diff_samples: 时间差（采样点数）
            
        Returns:
            float: 距离（米）
        """
        time_diff = time_diff_samples / self.sample_rate
        distance = self.speed_of_sound * time_diff
        return max(0, distance)
    
    def calculate_distance_tof(self, send_time, receive_time, is_roundtrip=True):
        """
        基于飞行时间(ToF)计算距离
        
        Args:
            send_time: 发送时间戳
            receive_time: 接收时间戳
            is_roundtrip: 是否为往返时间
            
        Returns:
            float: 距离（米）
        """
        tof = receive_time - send_time
        if is_roundtrip:
            tof = tof / 2
        distance = self.speed_of_sound * tof
        return max(0, distance - self.d_self)


class RangingSession:
    """测距会话管理"""
    
    def __init__(self, device_role='target'):
        """
        初始化测距会话
        
        Args:
            device_role: 设备角色 ('target' 或 'anchor')
        """
        self.device_role = device_role
        self.processor = SignalProcessor()
        
        # 测量记录
        self.measurements = []
        self.current_measurement = None
        
        # 时间戳记录
        self.t_send = None      # 发送时间
        self.t_self = None      # 收到自己信号的时间
        self.t_other = None     # 收到对方信号的时间
        
    def start_measurement(self):
        """开始一次测量"""
        self.current_measurement = {
            'start_time': time.time(),
            'role': self.device_role,
            'local_times': {},
            'remote_times': {},
            'distance': None
        }
        
    def record_local_detection(self, chirp_positions):
        """
        记录本地检测到的Chirp信号位置
        
        Args:
            chirp_positions: 检测到的位置列表
        """
        if self.current_measurement and len(chirp_positions) >= 2:
            self.current_measurement['local_times']['t_self'] = chirp_positions[0]
            self.current_measurement['local_times']['t_other'] = chirp_positions[1]
            
    def record_remote_detection(self, remote_data):
        """
        记录远程设备的检测数据
        
        Args:
            remote_data: 远程设备发送的时间数据
        """
        if self.current_measurement:
            self.current_measurement['remote_times'] = remote_data
            
    def calculate_final_distance(self):
        """
        计算最终距离
        
        Returns:
            float: 计算得到的距离，失败返回None
        """
        if not self.current_measurement:
            return None
            
        local = self.current_measurement.get('local_times', {})
        remote = self.current_measurement.get('remote_times', {})
        
        t_self = local.get('t_self')
        t_other = local.get('t_other')
        r_self = remote.get('t_self')
        r_other = remote.get('t_other')
        
        if all(v is not None for v in [t_self, t_other, r_self, r_other]):
            # 使用BeepBeep算法
            distance = self.processor.calculate_distance_beepbeep(
                t_self, t_other, r_other, r_self
            )
            self.current_measurement['distance'] = distance
            self.current_measurement['end_time'] = time.time()
            self.measurements.append(self.current_measurement)
            return distance
            
        return None
    
    def get_statistics(self):
        """
        获取测量统计数据
        
        Returns:
            dict: 统计数据
        """
        if not self.measurements:
            return None
            
        distances = [m['distance'] for m in self.measurements if m['distance'] is not None]
        
        if not distances:
            return None
            
        return {
            'count': len(distances),
            'mean': np.mean(distances),
            'std': np.std(distances),
            'min': np.min(distances),
            'max': np.max(distances),
            'measurements': distances
        }


if __name__ == '__main__':
    # 测试信号处理器
    processor = SignalProcessor()
    
    # 生成测距信号
    ranging_signal = processor.generate_ranging_signal()
    print(f"测距信号长度: {len(ranging_signal)} 采样点")
    print(f"信号持续时间: {len(ranging_signal)/processor.sample_rate:.3f} 秒")
    
    # 模拟检测
    # 创建一个包含两个Chirp的模拟信号
    test_signal = np.zeros(int(processor.sample_rate * 0.5))
    chirp = processor.reference_chirp
    
    # 在不同位置插入Chirp
    pos1 = int(processor.sample_rate * 0.1)  # 100ms处
    pos2 = int(processor.sample_rate * 0.3)  # 300ms处
    
    test_signal[pos1:pos1+len(chirp)] = chirp
    test_signal[pos2:pos2+len(chirp)] = chirp * 0.8
    
    # 添加噪声
    test_signal += np.random.randn(len(test_signal)) * 0.1
    
    # 检测
    peaks, correlation = processor.detect_chirp(test_signal)
    print(f"检测到的Chirp位置: {peaks}")
    print(f"预期位置: [{pos1}, {pos2}]")
