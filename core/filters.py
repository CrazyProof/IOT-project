# -*- coding: utf-8 -*-
"""
测距结果滤波器
实现各种滤波算法来减少测距波动
"""

import numpy as np
from collections import deque


class DistanceFilter:
    """距离测量滤波器"""
    
    def __init__(self, window_size=5, outlier_threshold=2.0):
        """
        初始化滤波器
        
        Args:
            window_size: 滤波窗口大小
            outlier_threshold: 异常值阈值（以标准差倍数计算）
        """
        self.window_size = window_size
        self.outlier_threshold = outlier_threshold
        self.measurements = deque(maxlen=window_size)
        self.filtered_values = deque(maxlen=window_size)
        
    def add_measurement(self, value):
        """
        添加新测量值
        
        Args:
            value: 新的测量值
            
        Returns:
            float or None: 滤波后的值，如果是异常值则返回None
        """
        # 检查是否为异常值
        if len(self.measurements) >= 3:
            if self._is_outlier(value):
                print(f"⚠️ 检测到异常值: {value:.3f}m (被过滤)")
                return None
        
        # 添加到历史记录
        self.measurements.append(value)
        
        # 应用滤波
        filtered_value = self._apply_filter()
        self.filtered_values.append(filtered_value)
        
        return filtered_value
    
    def _is_outlier(self, value):
        """
        检测是否为异常值
        使用基于中位数的绝对偏差（MAD）方法
        
        Args:
            value: 待检测的值
            
        Returns:
            bool: 是否为异常值
        """
        if len(self.measurements) < 3:
            return False
        
        # 计算中位数
        median = np.median(list(self.measurements))
        
        # 计算绝对偏差
        mad = np.median(np.abs(np.array(list(self.measurements)) - median))
        
        # MAD为0时使用标准差方法
        if mad < 1e-6:
            std = np.std(list(self.measurements))
            if std < 1e-6:
                return False
            return abs(value - median) > self.outlier_threshold * std
        
        # 计算标准化绝对偏差
        threshold = self.outlier_threshold * 1.4826 * mad  # 1.4826是使MAD与标准差一致的系数
        
        return abs(value - median) > threshold
    
    def _apply_filter(self):
        """
        应用滤波算法
        优先使用中值滤波（对异常值鲁棒）
        
        Returns:
            float: 滤波后的值
        """
        if len(self.measurements) == 0:
            return 0.0
        
        if len(self.measurements) == 1:
            return self.measurements[0]
        
        # 中值滤波
        return float(np.median(list(self.measurements)))
    
    def get_statistics(self):
        """
        获取统计信息
        
        Returns:
            dict: 包含均值、标准差等统计信息
        """
        if len(self.filtered_values) == 0:
            return {
                'mean': 0.0,
                'std': 0.0,
                'count': 0
            }
        
        values = list(self.filtered_values)
        return {
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'median': float(np.median(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'count': len(values)
        }
    
    def reset(self):
        """重置滤波器"""
        self.measurements.clear()
        self.filtered_values.clear()


class KalmanFilter:
    """卡尔曼滤波器 - 用于更平滑的距离估计"""
    
    def __init__(self, process_variance=1e-5, measurement_variance=0.01):
        """
        初始化卡尔曼滤波器
        
        Args:
            process_variance: 过程噪声方差（系统模型不确定性）
            measurement_variance: 测量噪声方差（测量不确定性）
        """
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        
        # 状态
        self.estimate = 0.0  # 估计值
        self.estimate_error = 1.0  # 估计误差
        self.is_initialized = False
        
    def update(self, measurement):
        """
        更新滤波器状态
        
        Args:
            measurement: 新的测量值
            
        Returns:
            float: 滤波后的估计值
        """
        if not self.is_initialized:
            # 首次测量，直接使用
            self.estimate = measurement
            self.is_initialized = True
            return self.estimate
        
        # 预测步骤
        prediction = self.estimate
        prediction_error = self.estimate_error + self.process_variance
        
        # 更新步骤
        kalman_gain = prediction_error / (prediction_error + self.measurement_variance)
        self.estimate = prediction + kalman_gain * (measurement - prediction)
        self.estimate_error = (1 - kalman_gain) * prediction_error
        
        return self.estimate
    
    def reset(self):
        """重置滤波器"""
        self.estimate = 0.0
        self.estimate_error = 1.0
        self.is_initialized = False


class MovingAverageFilter:
    """移动平均滤波器"""
    
    def __init__(self, window_size=5, weighted=False):
        """
        初始化移动平均滤波器
        
        Args:
            window_size: 窗口大小
            weighted: 是否使用加权平均（越近的值权重越大）
        """
        self.window_size = window_size
        self.weighted = weighted
        self.values = deque(maxlen=window_size)
        
        # 生成权重
        if weighted:
            self.weights = np.arange(1, window_size + 1)
            self.weights = self.weights / np.sum(self.weights)
        else:
            self.weights = None
    
    def update(self, value):
        """
        添加新值并计算平均
        
        Args:
            value: 新值
            
        Returns:
            float: 平均后的值
        """
        self.values.append(value)
        
        if len(self.values) == 0:
            return 0.0
        
        values_array = np.array(list(self.values))
        
        if self.weighted and len(self.values) > 1:
            # 加权平均
            weights = self.weights[-len(self.values):]
            weights = weights / np.sum(weights)
            return float(np.sum(values_array * weights))
        else:
            # 简单平均
            return float(np.mean(values_array))
    
    def reset(self):
        """重置滤波器"""
        self.values.clear()
