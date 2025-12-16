# 声波测距系统 (Acoustic Ranging System)

## 项目简介

本项目实现了基于声波信号的双设备测距系统，采用 **BeepBeep** 算法原理。系统包含两个应用程序：
- **锚节点 (Anchor)**: 固定位置的设备，作为服务器端
- **目标设备 (Target)**: 移动设备，作为客户端

## 系统原理

### BeepBeep 测距算法

系统使用 Chirp（线性调频）信号进行测距，通过测量声波在两个设备之间的传播时间来计算距离。

核心公式：
$$D = \frac{c}{2}[(t_{A3} - t_{A1}) - (t_{B3} - t_{B1})] + \frac{d_{AA} + d_{BB}}{2}$$

其中：
- $c$ 为声速（约343 m/s）
- $t_{A3} - t_{A1}$ 为设备A上检测到的两个信号的时间差
- $t_{B3} - t_{B1}$ 为设备B上检测到的两个信号的时间差
- $d_{AA}$, $d_{BB}$ 为各设备扬声器到麦克风的距离

### 信号设计

- **信号类型**: 线性调频（Chirp）信号
- **频率范围**: 17kHz - 20kHz（超声波范围，减少环境干扰）
- **信号时长**: 10ms
- **采样率**: 44100 Hz

## 系统架构

```
acoustic_ranging/
├── core/                      # 核心模块
│   ├── __init__.py
│   ├── signal_processor.py    # 信号处理（Chirp生成、互相关检测）
│   ├── audio_io.py            # 音频输入输出
│   ├── network.py             # 网络通信（TCP Socket）
│   └── ranging_engine.py      # 测距引擎
├── target_app.py              # 目标设备GUI应用
├── anchor_app.py              # 锚节点GUI应用
├── requirements.txt           # 依赖包
└── README.md                  # 本文档
```

## 环境要求

- Python 3.8+
- Windows/macOS/Linux
- 带有麦克风和扬声器的设备
- 同一局域网（WiFi）

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：

```bash
pip install numpy scipy sounddevice
```

### 2. 验证音频设备

运行以下命令检查音频设备：

```bash
python -c "import sounddevice as sd; print(sd.query_devices())"
```

## 使用方法

### 步骤1：启动锚节点

在固定位置的设备上运行：

```bash
cd acoustic_ranging
python anchor_app.py
```

锚节点启动后会显示本机IP地址，记下这个地址。

### 步骤2：启动目标设备

在移动设备上运行：

```bash
cd acoustic_ranging
python target_app.py
```

### 步骤3：建立连接

1. 在目标设备应用中输入锚节点的IP地址
2. 点击"连接"按钮
3. 等待连接成功提示

### 步骤4：开始测距

1. 点击"开始测距"按钮
2. 观察实时距离显示
3. 可以点击"停止测距"暂停

### 步骤5：记录数据（可选）

1. 在"实际距离"输入框中输入真实距离
2. 点击"开始记录"
3. 测量完成后点击"导出数据"保存CSV文件

## 功能说明

### 目标设备应用

- **连接设置**: 输入锚节点IP，建立连接
- **测距控制**: 开始/停止测距，单次测量
- **实时显示**: 当前距离、FPS、均值、标准差
- **实验记录**: 记录测量数据，支持导出CSV

### 锚节点应用

- **服务器状态**: 显示本机IP，连接状态
- **测距结果**: 实时距离显示和统计
- **测量历史**: 查看历史记录，支持导出
- **设备配置**: 设置扬声器-麦克风距离

## 性能优化建议

### 提高测距精度

1. **环境控制**
   - 选择安静环境
   - 避免强烈回声的空间
   - 保持设备稳定

2. **设备设置**
   - 将设备音量调至适中
   - 确保麦克风灵敏度正常
   - 校准设备自身距离参数

### 提高测距速度（FPS）

1. **信号优化**
   - 缩短Chirp信号时长
   - 减少等待时间

2. **网络优化**
   - 使用5GHz WiFi
   - 减少网络延迟

## 实验指南

### 实验1：距离对性能影响

1. 在空旷环境中
2. 设置距离：0.5m、1m、2m、4m、7m
3. 每个距离测量5次以上
4. 记录误差均值和方差

### 实验2：环境噪声影响

1. 固定距离3m
2. 测试三种环境：
   - 安静环境
   - 人说话环境
   - 大音量音乐环境
3. 记录各环境下的测量结果

### 实验3：环境遮挡影响

1. 固定距离3m
2. 测试不同遮挡：
   - 无遮挡
   - 书籍遮挡
   - 人体遮挡
3. 记录遮挡对测距的影响

### 实验4：测距刷新率

1. 测试系统FPS
2. 目标：> 1 FPS，满分：20 FPS

## 数据分析

导出的CSV文件可以使用Python进行分析：

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取数据
data = pd.read_csv('ranging_data_xxx.csv')

# 计算统计量
mean_error = data['误差(m)'].mean()
std_error = data['误差(m)'].std()

# 绘制直方图
plt.hist(data['误差(m)'], bins=20)
plt.xlabel('误差 (m)')
plt.ylabel('频次')
plt.title('测距误差分布')
plt.savefig('error_histogram.png')
plt.show()
```

## 故障排除

### 连接失败

1. 检查两设备是否在同一局域网
2. 检查防火墙设置
3. 确认IP地址正确

### 测距结果异常

1. 检查音量设置
2. 检查麦克风权限
3. 减少环境噪声

### 检测不到信号

1. 增加信号音量
2. 降低检测阈值
3. 检查音频设备工作状态

## 技术细节

### 信号处理流程

1. **信号生成**: 生成17-20kHz线性调频Chirp信号
2. **带通滤波**: 滤除Chirp频率范围外的噪声
3. **互相关检测**: 使用互相关法检测Chirp位置
4. **峰值检测**: 找出相关结果中的峰值位置
5. **距离计算**: 根据BeepBeep公式计算距离

### 网络协议

- 使用TCP Socket进行可靠通信
- JSON格式的消息传输
- 消息类型：同步请求、测距开始、检测结果、距离结果等

## 许可证

本项目仅供学习和实验使用。

## 参考资料

- BeepBeep: A High Accuracy Acoustic Ranging System
- iot-book.github.io
