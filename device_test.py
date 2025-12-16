# -*- coding: utf-8 -*-
"""
设备音频能力测试
测试扬声器和麦克风在不同频率下的性能
"""

import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from scipy import signal as sig
import time


def test_speaker_frequency_response():
    """测试扬声器频率响应"""
    print("=" * 50)
    print("设备音频能力测试")
    print("=" * 50)
    
    sample_rate = 44100
    duration = 0.5  # 每个频率播放0.5秒
    
    # 测试频率列表
    test_frequencies = [1000, 2000, 4000, 8000, 10000, 12000, 15000, 17000, 18000, 19000, 20000]
    
    print("\n1. 扬声器频率响应测试")
    print("   请仔细听，记录每个频率是否能清晰听到")
    print("-" * 50)
    
    for freq in test_frequencies:
        # 生成正弦波
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = 0.3 * np.sin(2 * np.pi * freq * t)
        
        print(f"   播放 {freq:5d} Hz...", end=" ", flush=True)
        sd.play(tone, sample_rate)
        sd.wait()
        
        if freq >= 15000:
            print("(可能听不到，这是正常的)")
        else:
            print("(应该能听到)")
        
        time.sleep(0.3)
    
    print("\n" + "=" * 50)


def test_record_frequency_response():
    """测试麦克风频率响应 - 播放并录制"""
    print("\n2. 麦克风频率响应测试")
    print("   将播放音频并同时录制，分析录制信号的频谱")
    print("-" * 50)
    
    sample_rate = 44100
    duration = 1.0
    
    # 生成扫频信号 (Chirp)
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # 测试两个频率范围
    test_ranges = [
        ("可听范围 8-12kHz", 8000, 12000),
        ("超声波范围 17-20kHz", 17000, 20000),
    ]
    
    results = {}
    
    for name, f0, f1 in test_ranges:
        print(f"\n   测试: {name}")
        
        # 生成 Chirp 信号
        chirp = sig.chirp(t, f0, duration, f1, method='linear')
        chirp = 0.5 * chirp.astype(np.float32)
        
        # 播放并录制
        print("   播放并录制中...")
        recorded = sd.playrec(chirp, sample_rate, channels=1)
        sd.wait()
        recorded = recorded.flatten()
        
        # 分析录制信号的频谱
        freqs, psd = sig.welch(recorded, sample_rate, nperseg=4096)
        
        # 计算目标频率范围内的能量
        mask = (freqs >= f0) & (freqs <= f1)
        target_energy = np.mean(psd[mask]) if np.any(mask) else 0
        
        # 计算总能量
        total_energy = np.mean(psd)
        
        # 信噪比
        snr = 10 * np.log10(target_energy / (total_energy - target_energy + 1e-10))
        
        results[name] = {
            'target_energy': target_energy,
            'total_energy': total_energy,
            'snr': snr
        }
        
        print(f"   目标频带能量: {target_energy:.6f}")
        print(f"   信噪比 (SNR): {snr:.1f} dB")
        
        if snr > 10:
            print(f"   ✅ 该频率范围工作良好！")
        elif snr > 5:
            print(f"   ⚠️ 该频率范围勉强可用")
        else:
            print(f"   ❌ 该频率范围可能无法正常工作")
    
    return results


def test_chirp_detection():
    """测试Chirp信号检测能力"""
    print("\n3. Chirp信号检测测试")
    print("   测试不同频率范围的Chirp信号检测能力")
    print("-" * 50)
    
    sample_rate = 44100
    chirp_duration = 0.01  # 10ms
    record_duration = 0.5  # 500ms 录制时长
    
    test_ranges = [
        ("可听范围 8-12kHz", 8000, 12000),
        ("超声波范围 17-20kHz", 17000, 20000),
    ]
    
    for name, f0, f1 in test_ranges:
        print(f"\n   测试: {name}")
        
        # 生成 Chirp 信号
        t = np.linspace(0, chirp_duration, int(sample_rate * chirp_duration), False)
        chirp = sig.chirp(t, f0, chirp_duration, f1, method='linear')
        chirp = 0.5 * chirp.astype(np.float32)
        
        # 创建带静音的信号
        silence_before = np.zeros(int(sample_rate * 0.1))  # 100ms 静音
        silence_after = np.zeros(int(sample_rate * (record_duration - 0.1 - chirp_duration)))
        full_signal = np.concatenate([silence_before, chirp, silence_after])
        
        # 播放并录制
        print("   播放并录制中...")
        recorded = sd.playrec(full_signal, sample_rate, channels=1)
        sd.wait()
        recorded = recorded.flatten()
        
        # 带通滤波
        nyquist = sample_rate / 2
        low = max((f0 - 1000) / nyquist, 0.01)
        high = min((f1 + 1000) / nyquist, 0.99)
        b, a = sig.butter(4, [low, high], btype='band')
        filtered = sig.filtfilt(b, a, recorded)
        
        # 互相关检测
        correlation = sig.correlate(filtered, chirp, mode='valid')
        correlation = np.abs(correlation)
        
        # 检测峰值
        peak_idx = np.argmax(correlation)
        peak_value = correlation[peak_idx]
        noise_level = np.median(correlation)
        snr = peak_value / (noise_level + 1e-10)
        
        print(f"   检测到峰值位置: {peak_idx} (预期约 {int(sample_rate * 0.1)})")
        print(f"   峰值强度: {peak_value:.4f}")
        print(f"   噪声水平: {noise_level:.4f}")
        print(f"   峰噪比: {snr:.1f}")
        
        if snr > 10:
            print(f"   ✅ 检测能力良好！推荐使用此频率范围")
        elif snr > 5:
            print(f"   ⚠️ 检测能力一般，可能有误检")
        else:
            print(f"   ❌ 检测能力差，建议使用其他频率范围")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("     声波测距系统 - 设备音频能力测试")
    print("=" * 60)
    print("\n请确保：")
    print("  1. 音量调到适中（约50-70%）")
    print("  2. 周围环境安静")
    print("  3. 麦克风和扬声器都正常工作")
    print("\n按 Enter 开始测试...")
    input()
    
    # 测试扬声器
    test_speaker_frequency_response()
    
    print("\n按 Enter 继续麦克风测试...")
    input()
    
    # 测试麦克风
    test_record_frequency_response()
    
    print("\n按 Enter 继续Chirp检测测试...")
    input()
    
    # 测试Chirp检测
    test_chirp_detection()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n建议：")
    print("  - 如果超声波范围(17-20kHz)检测能力差，请使用可听范围(8-12kHz)")
    print("  - 修改 core/signal_processor.py 中的 use_audible_frequency = True")
    print("  - 如果两个范围都工作良好，推荐使用超声波范围以减少环境噪声干扰")


if __name__ == "__main__":
    main()
