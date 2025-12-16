# -*- coding: utf-8 -*-
"""
网络通信模块
实现设备间的Socket通信，用于同步和数据交换
"""

import socket
import json
import threading
import time
from typing import Callable, Optional
import struct


class NetworkManager:
    """网络通信管理器"""
    
    # 消息类型定义
    MSG_SYNC_REQUEST = 'sync_request'      # 同步请求
    MSG_SYNC_RESPONSE = 'sync_response'    # 同步响应
    MSG_START_RANGING = 'start_ranging'    # 开始测距
    MSG_CHIRP_SENT = 'chirp_sent'          # Chirp已发送
    MSG_DETECTION_RESULT = 'detection'     # 检测结果
    MSG_DISTANCE_RESULT = 'distance'       # 距离结果
    MSG_HEARTBEAT = 'heartbeat'            # 心跳
    MSG_DISCONNECT = 'disconnect'          # 断开连接
    
    def __init__(self, port=12345):
        """
        初始化网络管理器
        
        Args:
            port: 通信端口
        """
        self.port = port
        self.socket = None
        self.client_socket = None
        self.is_server = False
        self.is_connected = False
        
        # 接收线程
        self.receive_thread = None
        self.running = False
        
        # 消息回调
        self.message_handlers = {}
        
        # 连接状态回调
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        
        # 时间同步
        self.time_offset = 0  # 与对方的时间差
        
    def register_handler(self, msg_type: str, handler: Callable):
        """
        注册消息处理器
        
        Args:
            msg_type: 消息类型
            handler: 处理函数
        """
        self.message_handlers[msg_type] = handler
        
    def start_server(self, host='0.0.0.0'):
        """
        启动服务器（锚节点使用）
        
        Args:
            host: 监听地址
        """
        self.is_server = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, self.port))
        self.socket.listen(1)
        
        print(f"服务器启动，监听端口 {self.port}")
        
        # 启动接受连接线程
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()
        
    def _accept_connections(self):
        """接受客户端连接"""
        while True:
            try:
                self.client_socket, address = self.socket.accept()
                print(f"客户端连接: {address}")
                self.is_connected = True
                
                if self.on_connect:
                    self.on_connect(address)
                
                # 启动接收线程
                self.running = True
                self.receive_thread = threading.Thread(
                    target=self._receive_loop, 
                    args=(self.client_socket,),
                    daemon=True
                )
                self.receive_thread.start()
                
            except Exception as e:
                print(f"接受连接错误: {e}")
                break
                
    def connect_to_server(self, host, timeout=10):
        """
        连接到服务器（目标设备使用）
        
        Args:
            host: 服务器地址
            timeout: 连接超时（秒）
            
        Returns:
            bool: 连接是否成功
        """
        self.is_server = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)
        
        try:
            self.socket.connect((host, self.port))
            print(f"已连接到服务器 {host}:{self.port}")
            self.is_connected = True
            self.client_socket = self.socket
            
            if self.on_connect:
                self.on_connect((host, self.port))
            
            # 启动接收线程
            self.running = True
            self.receive_thread = threading.Thread(
                target=self._receive_loop,
                args=(self.socket,),
                daemon=True
            )
            self.receive_thread.start()
            
            return True
            
        except Exception as e:
            print(f"连接失败: {e}")
            return False
            
    def _receive_loop(self, sock):
        """接收消息循环"""
        buffer = b''
        
        while self.running:
            try:
                sock.settimeout(1.0)
                data = sock.recv(4096)
                
                if not data:
                    print("连接已关闭")
                    break
                    
                buffer += data
                
                # 处理完整的消息
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        message = json.loads(line.decode('utf-8'))
                        self._handle_message(message)
                    except json.JSONDecodeError:
                        print(f"JSON解析错误: {line}")
                        
            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收错误: {e}")
                break
                
        self.is_connected = False
        if self.on_disconnect:
            self.on_disconnect()
            
    def _handle_message(self, message):
        """处理接收到的消息"""
        msg_type = message.get('type')
        data = message.get('data', {})
        timestamp = message.get('timestamp', 0)
        
        # 调用注册的处理器
        if msg_type in self.message_handlers:
            try:
                self.message_handlers[msg_type](data, timestamp)
            except Exception as e:
                print(f"消息处理错误 [{msg_type}]: {e}")
        else:
            print(f"未知消息类型: {msg_type}")
            
    def send_message(self, msg_type: str, data: dict = None):
        """
        发送消息
        
        Args:
            msg_type: 消息类型
            data: 消息数据
            
        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected:
            print("未连接，无法发送消息")
            return False
            
        message = {
            'type': msg_type,
            'data': data or {},
            'timestamp': time.time()
        }
        
        try:
            sock = self.client_socket if self.is_server else self.socket
            msg_bytes = json.dumps(message).encode('utf-8') + b'\n'
            sock.sendall(msg_bytes)
            return True
        except Exception as e:
            print(f"发送消息错误: {e}")
            return False
            
    def sync_time(self):
        """
        与对方进行时间同步
        
        Returns:
            float: 时间偏移量
        """
        if not self.is_connected:
            return 0
            
        sync_times = []
        
        for _ in range(5):
            t1 = time.time()
            self.send_message(self.MSG_SYNC_REQUEST, {'t1': t1})
            
            # 等待响应（这里简化处理，实际应该用事件等待）
            time.sleep(0.1)
            
        return self.time_offset
        
    def close(self):
        """关闭连接"""
        self.running = False
        self.is_connected = False
        
        self.send_message(self.MSG_DISCONNECT)
        
        if self.client_socket and self.client_socket != self.socket:
            try:
                self.client_socket.close()
            except:
                pass
                
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
                
    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'


class UDPBroadcaster:
    """UDP广播器，用于设备发现"""
    
    def __init__(self, port=12346):
        """
        初始化UDP广播器
        
        Args:
            port: 广播端口
        """
        self.port = port
        self.socket = None
        self.is_listening = False
        self.on_device_found: Optional[Callable] = None
        
    def start_broadcasting(self, device_info: dict, interval=1.0):
        """
        开始广播设备信息
        
        Args:
            device_info: 设备信息
            interval: 广播间隔（秒）
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        def broadcast_loop():
            while self.is_listening:
                try:
                    message = json.dumps(device_info).encode('utf-8')
                    self.socket.sendto(message, ('<broadcast>', self.port))
                except Exception as e:
                    print(f"广播错误: {e}")
                time.sleep(interval)
                
        self.is_listening = True
        thread = threading.Thread(target=broadcast_loop, daemon=True)
        thread.start()
        
    def start_listening(self):
        """开始监听广播"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', self.port))
        
        def listen_loop():
            while self.is_listening:
                try:
                    self.socket.settimeout(1.0)
                    data, addr = self.socket.recvfrom(1024)
                    device_info = json.loads(data.decode('utf-8'))
                    device_info['ip'] = addr[0]
                    
                    if self.on_device_found:
                        self.on_device_found(device_info)
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"监听错误: {e}")
                    
        self.is_listening = True
        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()
        
    def stop(self):
        """停止广播/监听"""
        self.is_listening = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass


if __name__ == '__main__':
    # 测试网络模块
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'server':
        # 服务器模式
        nm = NetworkManager()
        nm.start_server()
        
        def on_msg(data, ts):
            print(f"收到消息: {data}")
            nm.send_message('response', {'status': 'ok'})
            
        nm.register_handler('test', on_msg)
        
        print("服务器运行中，按Ctrl+C退出")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            nm.close()
            
    else:
        # 客户端模式
        nm = NetworkManager()
        
        if nm.connect_to_server('127.0.0.1'):
            def on_response(data, ts):
                print(f"收到响应: {data}")
                
            nm.register_handler('response', on_response)
            
            # 发送测试消息
            nm.send_message('test', {'message': 'Hello from client'})
            
            time.sleep(2)
            nm.close()
