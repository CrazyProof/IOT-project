# -*- coding: utf-8 -*-
"""
音频输入输出模块
处理麦克风录音和扬声器播放
"""

import numpy as np
import sounddevice as sd
import threading
import queue
import time
from typing import Callable, Optional


class AudioIO:
    """音频输入输出管理器"""
    
    def __init__(self, sample_rate=44100, channels=1, blocksize=1024):
        """
        初始化音频IO
        
        Args:
            sample_rate: 采样率
            channels: 通道数
            blocksize: 音频块大小
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        
        # 录音缓冲
        self.recording_buffer = []
        self.is_recording = False
        self.recording_lock = threading.Lock()
        
        # 播放状态
        self.is_playing = False
        
        # 同时录音播放的流
        self.stream = None
        self.play_buffer = None
        self.play_index = 0
        
        # 回调函数
        self.on_audio_data: Optional[Callable] = None
        
    def get_devices(self):
        """
        获取可用的音频设备列表
        
        Returns:
            dict: 输入和输出设备列表
        """
        devices = sd.query_devices()
        input_devices = []
        output_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })
            if device['max_output_channels'] > 0:
                output_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_output_channels'],
                    'sample_rate': device['default_samplerate']
                })
                
        return {
            'input': input_devices,
            'output': output_devices
        }
    
    def _audio_callback(self, indata, outdata, frames, time_info, status):
        """
        音频流回调函数
        同时处理录音和播放
        """
        if status:
            print(f'音频状态: {status}')
        
        # 录音部分
        if self.is_recording:
            with self.recording_lock:
                self.recording_buffer.append(indata.copy())
            
            # 实时回调
            if self.on_audio_data:
                self.on_audio_data(indata.copy())
        
        # 播放部分
        if self.play_buffer is not None and self.play_index < len(self.play_buffer):
            end_index = min(self.play_index + frames, len(self.play_buffer))
            chunk = self.play_buffer[self.play_index:end_index]
            
            if len(chunk) < frames:
                # 不足的部分填充零
                outdata[:len(chunk), 0] = chunk
                outdata[len(chunk):] = 0
                self.play_index = len(self.play_buffer)
            else:
                outdata[:, 0] = chunk
                self.play_index += frames
        else:
            outdata.fill(0)
            
    def start_stream(self, input_device=None, output_device=None):
        """
        启动音频流（同时录音和播放）
        
        Args:
            input_device: 输入设备ID
            output_device: 输出设备ID
        """
        if self.stream is not None:
            self.stop_stream()
            
        self.stream = sd.Stream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            device=(input_device, output_device),
            channels=self.channels,
            dtype=np.float32,
            callback=self._audio_callback
        )
        self.stream.start()
        self.is_recording = True
        
    def stop_stream(self):
        """停止音频流"""
        self.is_recording = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
    def play_sound(self, signal, blocking=False):
        """
        播放声音信号
        
        Args:
            signal: 要播放的信号数组
            blocking: 是否阻塞等待播放完成
        """
        if self.stream is not None:
            # 使用流播放
            self.play_buffer = signal.astype(np.float32)
            self.play_index = 0
            
            if blocking:
                # 等待播放完成
                duration = len(signal) / self.sample_rate
                time.sleep(duration + 0.1)
        else:
            # 直接播放
            sd.play(signal, self.sample_rate)
            if blocking:
                sd.wait()
                
    def start_recording(self):
        """开始录音"""
        with self.recording_lock:
            self.recording_buffer = []
        self.is_recording = True
        
    def stop_recording(self):
        """
        停止录音并返回录制的数据
        
        Returns:
            numpy.ndarray: 录制的音频数据
        """
        self.is_recording = False
        
        with self.recording_lock:
            if self.recording_buffer:
                recorded = np.concatenate(self.recording_buffer, axis=0)
                self.recording_buffer = []
                return recorded.flatten()
            return np.array([])
    
    def record_for_duration(self, duration, start_callback=None):
        """
        录制指定时长的音频
        
        Args:
            duration: 录制时长（秒）
            start_callback: 开始录音时的回调
            
        Returns:
            numpy.ndarray: 录制的音频数据
        """
        frames = int(duration * self.sample_rate)
        
        if start_callback:
            start_callback()
            
        recording = sd.rec(frames, samplerate=self.sample_rate, 
                          channels=self.channels, dtype=np.float32)
        sd.wait()
        
        return recording.flatten()
    
    def play_and_record(self, signal, extra_duration=0.5):
        """
        同时播放和录音
        
        Args:
            signal: 要播放的信号
            extra_duration: 额外录制时间（秒）
            
        Returns:
            numpy.ndarray: 录制的音频数据
        """
        signal = signal.astype(np.float32)
        record_duration = len(signal) / self.sample_rate + extra_duration
        frames = int(record_duration * self.sample_rate)
        
        # 同时播放和录音
        recording = sd.playrec(signal, self.sample_rate, 
                               channels=self.channels, dtype=np.float32)
        sd.wait()
        
        return recording.flatten()


class ContinuousRecorder:
    """持续录音器，用于实时处理"""
    
    def __init__(self, sample_rate=44100, buffer_duration=2.0):
        """
        初始化持续录音器
        
        Args:
            sample_rate: 采样率
            buffer_duration: 缓冲区时长（秒）
        """
        self.sample_rate = sample_rate
        self.buffer_size = int(sample_rate * buffer_duration)
        
        # 环形缓冲区
        self.buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.write_index = 0
        self.lock = threading.Lock()
        
        # 录音流
        self.stream = None
        self.is_running = False
        
        # 数据队列（用于外部处理）
        self.data_queue = queue.Queue(maxsize=100)
        
    def _callback(self, indata, frames, time_info, status):
        """录音回调"""
        if status:
            print(f'录音状态: {status}')
            
        data = indata[:, 0] if len(indata.shape) > 1 else indata.flatten()
        
        with self.lock:
            # 写入环形缓冲区
            end_index = self.write_index + len(data)
            if end_index <= self.buffer_size:
                self.buffer[self.write_index:end_index] = data
            else:
                # 回绕
                first_part = self.buffer_size - self.write_index
                self.buffer[self.write_index:] = data[:first_part]
                self.buffer[:end_index - self.buffer_size] = data[first_part:]
            
            self.write_index = end_index % self.buffer_size
        
        # 放入队列
        try:
            self.data_queue.put_nowait(data.copy())
        except queue.Full:
            pass
            
    def start(self, device=None):
        """开始持续录音"""
        if self.is_running:
            return
            
        self.is_running = True
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=self._callback,
            device=device
        )
        self.stream.start()
        
    def stop(self):
        """停止录音"""
        self.is_running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
    def get_recent_data(self, duration):
        """
        获取最近一段时间的数据
        
        Args:
            duration: 时长（秒）
            
        Returns:
            numpy.ndarray: 音频数据
        """
        samples = int(duration * self.sample_rate)
        samples = min(samples, self.buffer_size)
        
        with self.lock:
            start_index = (self.write_index - samples) % self.buffer_size
            
            if start_index < self.write_index:
                return self.buffer[start_index:self.write_index].copy()
            else:
                return np.concatenate([
                    self.buffer[start_index:],
                    self.buffer[:self.write_index]
                ])


if __name__ == '__main__':
    # 测试音频IO
    audio = AudioIO()
    
    # 列出设备
    devices = audio.get_devices()
    print("输入设备:")
    for d in devices['input']:
        print(f"  [{d['id']}] {d['name']}")
    print("\n输出设备:")
    for d in devices['output']:
        print(f"  [{d['id']}] {d['name']}")
    
    # 测试录音和播放
    print("\n测试播放和录音...")
    
    # 生成测试信号（1kHz正弦波）
    duration = 0.5
    t = np.linspace(0, duration, int(44100 * duration))
    test_signal = 0.3 * np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    
    # 播放并录音
    recorded = audio.play_and_record(test_signal, extra_duration=0.2)
    print(f"录制了 {len(recorded)} 采样点")
