import os
import re
import time
import threading
from datetime import datetime
from pathlib import Path

class LogCapture:
    def __init__(self, logger):
        self.logger = logger
        self.is_capturing = False
        self.capture_thread = None
        self.callbacks = []
        self.server_address = None
        self.stream_code = None

    def add_callback(self, callback):
        """添加回调函数"""
        self.callbacks.append(callback)

    def start(self):
        """启动日志模式抓取推流"""
        self.server_address = None
        self.stream_code = None
        if self.is_capturing:
            self.logger.info("日志抓取已经在运行中")
            return False
            
        # 获取日志文件夹路径
        log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "webcast_mate", "logs" )
        
        if not os.path.exists(log_dir):
            self.logger.info("日志文件夹不存在，请确认直播伴侣正确安装")
            return False
            
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_log, args=(log_dir,), daemon=True)
        self.capture_thread.start()
        self.logger.info("启动日志模式抓取推流系统")
        return True
    
    def stop(self):
        """停止日志模式抓取推流"""
        self.is_capturing = False
        if self.capture_thread:
            self.capture_thread.join()
            self.capture_thread = None
        self.logger.info("停止日志模式抓取推流系统")
        
    def _get_latest_log_file(self, log_dir):
        """获取最新的日志文件"""
        try:
            # 获取当前时间
            current_time = time.time()
            
            # 筛选出符合条件的文件
            files = [
                os.path.join(log_dir, f) 
                for f in os.listdir(log_dir) 
                if os.path.isfile(os.path.join(log_dir, f)) 
                and "client" in f 
                and (current_time - os.path.getmtime(os.path.join(log_dir, f))) <= 180  # 180秒 = 3分钟
            ]
            if not files:
                return None
            # 返回修改时间最新的文件
            return max(files, key=os.path.getmtime)
        except Exception as e:
            self.logger.info(f"获取最新日志文件失败: {e}")
            return None
    
    def format_text(self, input_text):
        input_text = input_text.replace('\n', '')
        input_text = ' '.join(input_text.split())
        input_text = input_text.replace('\\', '')
        input_text = input_text.replace('\t', '')
        input_text = input_text.replace('\r', '')
        input_text = input_text.replace('\b', '')
        input_text = input_text.replace('\f', '')
        return input_text

    def _parse_stream_info(self, line):
        """解析推流地址和推流码"""
        try:
            start_pattern = re.compile(r'\[startStream\]success.*?\n', re.DOTALL)
            matches = start_pattern.findall(line)
            
            if matches:
                matched_line = matches[-1]
                matched_line = self.format_text(matched_line)
                # 第二步：从匹配到的字符串中提取url、key、timestamp
                url_pattern = re.compile(r'"url":"([^"]+)"')
                key_pattern = re.compile(r'"key":"([^"]+)"')
                timestamp_pattern = re.compile(r'"timestamp":"([^"]+)"')
    
                # 提取 url 和 key
                url_match = url_pattern.search(matched_line)
                key_match = key_pattern.search(matched_line)
                timestamp_match = timestamp_pattern.search(matched_line)
                    
                if url_match and key_match and timestamp_match:
                    url = url_match.group(1)
                    key = key_match.group(1)
                    timestamp = timestamp_match.group(1)
                    current_time = int(time.time())
                    # 判断 timestamp 是否在 1 分钟内
                    if timestamp and current_time - int(timestamp) <= 30:
                        # 更新推流地址
                        if url != self.server_address:
                            self.server_address = url
                            self.logger.info(f"找到推流地址: {self.server_address}")
                        
                        # 更新推流码
                        if key != self.stream_code:
                            self.stream_code = key
                            self.logger.info(f"找到推流码: {self.stream_code}")

                # 触发回调
                if self.server_address and self.stream_code:
                    for callback in self.callbacks:
                        try:
                            self.is_capturing = False
                            callback(self.server_address, self.stream_code)
                        except Exception as e:
                            self.logger.info(f"回调执行失败: {e}")
        except Exception as e:
            self.logger.info(f"解析推流信息失败: {e}")
            
    def _capture_log(self, log_dir):
        """监控日志文件并解析推流信息"""
        while self.is_capturing:
            try:
                # 获取最新日志文件
                current_file = self._get_latest_log_file(log_dir)
                if not current_file:
                    time.sleep(2)
                    continue
                
                # 读取整个文件内容
                try:
                    with open(current_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception as e:
                    self.logger.info(f"文件读取失败: {e}")
                    time.sleep(2)
                    continue
                
                self.logger.info(f"正在通过日志模式获取推流信息，请在直播伴侣开始直播...")
                
                # 解析全部内容
                self._parse_stream_info(content)
                    
            except Exception as e:
                self.logger.info(f"日志监控异常: {e}")
            
            time.sleep(2)  # 每次检查间隔2秒
            
    