#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEV/AA二合一传感器简易GUI监测程序
基于PyQt5实现波形可视化显示
"""

import sys
import time
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QComboBox, 
                            QGroupBox, QLineEdit, QStatusBar, 
                            QMessageBox, QTabWidget, QSplitter)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
import pyqtgraph as pg
from pymodbus.client.sync import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse


# 原tev_aa_combined.py的函数，获取可用串口列表
def get_available_ports():
    """
    获取系统中所有可用的串口列表
    
    返回:
        list: 可用串口列表，格式为(端口名, 描述)的元组列表
    """
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append((port.device, port.description))
    return ports


# 原tev_aa_combined.py的传感器类
class TEVAASensor:
    """TEV/AA二合一传感器通信类"""
    
    # 寄存器地址常量
    REG_TEV_VALUE = 5003        # TEV值(dB)
    REG_TEV_DISCHARGE_COUNT = 5004  # TEV放电次数
    REG_AA_VALUE = 5005         # AA/AE值(dB)
    
    # 波形图谱寄存器范围
    REG_TEV_WAVEFORM_START = 201
    REG_TEV_WAVEFORM_END = 300
    REG_AA_WAVEFORM_START = 301
    REG_AA_WAVEFORM_END = 400
    
    # 配置参数寄存器
    REG_DEVICE_ADDR = 401       # 设备地址
    REG_BAUD_RATE = 402         # 波特率
    REG_TEV_THRESHOLD = 404     # TEV背景阈值
    REG_AA_THRESHOLD = 405      # AA/AE背景阈值
    
    def __init__(self, port, device_addr=1, baudrate=9600, timeout=1):
        """
        初始化传感器通信
        
        参数:
            port (str): 串口名称，如'COM1'或'/dev/ttyUSB0'
            device_addr (int): 设备地址，默认为1
            baudrate (int): 波特率，默认为9600
            timeout (float): 通信超时时间(秒)，默认为1
        """
        self.device_addr = device_addr
        self.client = ModbusSerialClient(
            method='rtu',
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout
        )
        self.connected = False
    
    def connect(self):
        """连接到传感器"""
        if not self.connected:
            self.connected = self.client.connect()
        return self.connected
    
    def disconnect(self):
        """断开与传感器的连接"""
        if self.connected:
            self.client.close()
            self.connected = False
    
    def _read_register(self, address, count=1):
        """
        读取寄存器值
        
        参数:
            address (int): 寄存器地址
            count (int): 寄存器数量
            
        返回:
            list: 读取到的寄存器值列表，失败返回None
        """
        if not self.connected and not self.connect():
            raise ConnectionError("无法连接到传感器")
        
        try:
            # pymodbus 2.5.3版本中使用unit而不是slave
            result = self.client.read_holding_registers(
                address=address,  # Modbus地址从0开始，而文档地址从1开始
                count=count,
                unit=self.device_addr
            )
            
            if result is None:
                raise ModbusException("读取寄存器失败：接收到空响应")
                
            if hasattr(result, 'isError') and result.isError():
                raise ModbusException(f"读取寄存器失败: {result}")
            
            if not hasattr(result, 'registers'):
                raise ModbusException(f"读取寄存器失败: 响应缺少registers属性")
                
            return result.registers
        except Exception as e:
            # 不再传递异常，直接返回None
            print(f"读取寄存器错误: {e}")
            return None
    
    def _write_register(self, address, values):
        """
        写入寄存器值
        
        参数:
            address (int): 寄存器地址
            values (list): 要写入的值列表
            
        返回:
            bool: 写入成功返回True，否则返回False
        """
        if not self.connected and not self.connect():
            raise ConnectionError("无法连接到传感器")
        
        try:
            # pymodbus 2.5.3版本中使用unit而不是slave
            result = self.client.write_registers(
                address=address-1,  # Modbus地址从0开始，而文档地址从1开始
                values=values,
                unit=self.device_addr
            )
            
            if isinstance(result, ExceptionResponse):
                raise ModbusException(f"写入寄存器失败: {result}")
                
            return True
        except Exception as e:
            raise IOError(f"写入寄存器错误: {e}")
    
    def get_tev_value(self):
        """
        获取TEV值(dB)
        
        返回:
            int: TEV值，失败返回None
        """
        result = self._read_register(self.REG_TEV_VALUE, 1)
        return result[0] if result else None
    
    def get_tev_discharge_count(self):
        """
        获取TEV放电次数
        
        返回:
            int: TEV放电次数，失败返回None
        """
        result = self._read_register(self.REG_TEV_DISCHARGE_COUNT, 1)
        return result[0] if result else None
    
    def get_aa_value(self):
        """
        获取AA/AE值(dB)
        
        返回:
            int: AA/AE值，失败返回None
        """
        result = self._read_register(self.REG_AA_VALUE, 1)
        return result[0] if result else None
    
    def get_all_sensor_values(self):
        """
        获取所有传感器的主要参数值
        
        返回:
            dict: 包含TEV值、TEV放电次数和AA/AE值的字典，失败返回None
        """
        try:
            # 一次性读取3个寄存器
            result = self._read_register(self.REG_TEV_VALUE, 3)
            if result and len(result) == 3:
                return {
                    'tev_value': result[0],
                    'tev_discharge_count': result[1],
                    'aa_value': result[2]
                }
            return None
        except Exception as e:
            print(f"获取传感器值错误: {e}")
            return None
    
    def get_tev_waveform(self):
        """
        获取TEV波形数据
        
        返回:
            list: TEV波形数据列表
        """
        count = self.REG_TEV_WAVEFORM_END - self.REG_TEV_WAVEFORM_START + 1
        return self._read_register(self.REG_TEV_WAVEFORM_START, count)
    
    def get_aa_waveform(self):
        """
        获取AA/AE波形数据
        
        返回:
            list: AA/AE波形数据列表
        """
        count = self.REG_AA_WAVEFORM_END - self.REG_AA_WAVEFORM_START + 1
        return self._read_register(self.REG_AA_WAVEFORM_START, count)
    
    def get_device_address(self):
        """
        获取设备地址
        
        返回:
            int: 设备地址
        """
        result = self._read_register(self.REG_DEVICE_ADDR)
        return result[0] if result else None
    
    def set_device_address(self, address):
        """
        设置设备地址
        
        参数:
            address (int): 新设备地址(1-247)
            
        返回:
            bool: 设置成功返回True，否则返回False
        """
        if not 1 <= address <= 247:
            raise ValueError("设备地址必须在1-247范围内")
        
        if self._write_register(self.REG_DEVICE_ADDR, [address]):
            # 更新当前客户端使用的设备地址
            self.device_addr = address
            return True
        return False
    
    def get_baud_rate(self):
        """
        获取波特率
        
        返回:
            int: 波特率
        """
        result = self._read_register(self.REG_BAUD_RATE)
        return result[0] if result else None
    
    def set_baud_rate(self, baudrate):
        """
        设置波特率
        
        参数:
            baudrate (int): 波特率值
            
        返回:
            bool: 设置成功返回True，否则抛出异常
        """
        valid_baudrates = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
        if baudrate not in valid_baudrates:
            raise ValueError(f"波特率必须是标准Modbus波特率之一: {valid_baudrates}")
        
        return self._write_register(self.REG_BAUD_RATE, [baudrate])
    
    def get_tev_threshold(self):
        """
        获取TEV背景阈值
        
        返回:
            int: TEV背景阈值
        """
        result = self._read_register(self.REG_TEV_THRESHOLD)
        return result[0] if result else None
    
    def set_tev_threshold(self, threshold):
        """
        设置TEV背景阈值
        
        参数:
            threshold (int): 阈值
            
        返回:
            bool: 设置成功返回True，否则抛出异常
        """
        return self._write_register(self.REG_TEV_THRESHOLD, [threshold])
    
    def get_aa_threshold(self):
        """
        获取AA/AE背景阈值
        
        返回:
            int: AA/AE背景阈值
        """
        result = self._read_register(self.REG_AA_THRESHOLD)
        return result[0] if result else None
    
    def set_aa_threshold(self, threshold):
        """
        设置AA/AE背景阈值
        
        参数:
            threshold (int): 阈值
            
        返回:
            bool: 设置成功返回True，否则抛出异常
        """
        return self._write_register(self.REG_AA_THRESHOLD, [threshold])
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()


class WaveformThread(QThread):
    """波形数据读取线程"""
    tev_waveform_ready = pyqtSignal(list)  # TEV波形数据信号
    aa_waveform_ready = pyqtSignal(list)   # AA波形数据信号
    error_occurred = pyqtSignal(str)       # 错误信号
    
    def __init__(self, sensor, auto_refresh=False, parent=None):
        super().__init__(parent)
        self.sensor = sensor
        self.auto_refresh = auto_refresh
        self.running = False
    
    def run(self):
        self.running = True
        
        while self.running:
            try:
                # 读取TEV波形数据
                tev_waveform = self.sensor.get_tev_waveform()
                self.tev_waveform_ready.emit(tev_waveform)
                
                # 读取AA波形数据
                aa_waveform = self.sensor.get_aa_waveform()
                self.aa_waveform_ready.emit(aa_waveform)
                
                # 如果不是自动刷新模式，读取一次后退出
                if not self.auto_refresh:
                    break
                
                # 自动刷新模式下，每隔一段时间刷新一次
                time.sleep(1)
                
            except Exception as e:
                self.error_occurred.emit(f"波形数据读取错误: {str(e)}")
                break
    
    def stop(self):
        self.running = False
        self.wait()


class DataMonitorThread(QThread):
    """数据监测线程，周期性获取传感器数据"""
    data_updated = pyqtSignal(dict)  # 数据更新信号
    error_occurred = pyqtSignal(str)  # 错误信号
    
    def __init__(self, sensor, refresh_interval=1.0, parent=None):
        super().__init__(parent)
        self.sensor = sensor
        self.refresh_interval = refresh_interval  # 刷新间隔(秒)
        self.running = False
    
    def run(self):
        self.running = True
        
        while self.running:
            try:
                # 获取传感器数据
                values = self.sensor.get_all_sensor_values()
                if values:
                    self.data_updated.emit(values)
                else:
                    self.error_occurred.emit("获取传感器数据失败")
                
                # 等待刷新间隔
                time.sleep(self.refresh_interval)
                
            except Exception as e:
                self.error_occurred.emit(f"数据监测错误: {str(e)}")
                time.sleep(2)  # 出错后等待2秒再尝试
    
    def stop(self):
        self.running = False
        self.wait()


class SimpleSensorGUI(QMainWindow):
    """TEV/AA传感器简易GUI主窗口"""
    
    def __init__(self):
        super().__init__()
        self.sensor = None
        self.waveform_thread = None
        self.data_monitor_thread = None  # 添加数据监测线程属性
        
        self.init_ui()
        self.refresh_ports()
        
        # 创建定时器，定期更新端口列表
        self.port_timer = QTimer(self)
        self.port_timer.timeout.connect(self.refresh_ports)
        self.port_timer.start(5000)  # 每5秒刷新一次
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("TEV/AA二合一传感器波形监测 V2 ")
        self.setGeometry(100, 100, 900, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建垂直分割器
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # 顶部控制区域
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        splitter.addWidget(top_widget)
        
        # 底部波形显示区域
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        splitter.addWidget(bottom_widget)
        
        # 设置初始分割比例
        splitter.setSizes([150, 450])
        
        # =============== 连接控制区域 ===============
        connection_group = QGroupBox("连接控制")
        connection_layout = QHBoxLayout()
        connection_group.setLayout(connection_layout)
        
        # 串口选择
        port_layout = QVBoxLayout()
        port_layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        port_layout.addWidget(self.port_combo)
        
        # 串口刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(self.refresh_btn)
        connection_layout.addLayout(port_layout)
        
        # 波特率选择
        baud_layout = QVBoxLayout()
        baud_layout.addWidget(QLabel("波特率:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("9600")
        baud_layout.addWidget(self.baud_combo)
        connection_layout.addLayout(baud_layout)
        
        # 设备地址
        addr_layout = QVBoxLayout()
        addr_layout.addWidget(QLabel("设备地址:"))
        self.addr_edit = QLineEdit("1")
        self.addr_edit.setFixedWidth(80)
        addr_layout.addWidget(self.addr_edit)
        connection_layout.addLayout(addr_layout)
        
        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        connection_layout.addWidget(self.connect_btn)
        
        # 自动刷新控制
        auto_refresh_layout = QVBoxLayout()
        auto_refresh_layout.addWidget(QLabel("自动刷新:"))
        self.auto_refresh_combo = QComboBox()
        self.auto_refresh_combo.addItems(["关闭", "开启"])
        self.auto_refresh_combo.setCurrentText("关闭")
        self.auto_refresh_combo.currentTextChanged.connect(self.toggle_auto_refresh)
        auto_refresh_layout.addWidget(self.auto_refresh_combo)
        connection_layout.addLayout(auto_refresh_layout)
        
        top_layout.addWidget(connection_group)
        
        # =============== 传感器数据显示区域 ===============
        data_group = QGroupBox("传感器数据")
        data_layout = QHBoxLayout()
        data_group.setLayout(data_layout)
        
        # TEV值显示
        tev_value_layout = QVBoxLayout()
        tev_value_layout.addWidget(QLabel("TEV值(dB):"))
        self.tev_value_label = QLabel("--")
        self.tev_value_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: blue;")
        self.tev_value_label.setAlignment(Qt.AlignCenter)
        tev_value_layout.addWidget(self.tev_value_label)
        data_layout.addLayout(tev_value_layout)
        
        # TEV放电次数显示
        tev_count_layout = QVBoxLayout()
        tev_count_layout.addWidget(QLabel("TEV放电次数:"))
        self.tev_count_label = QLabel("--")
        self.tev_count_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: red;")
        self.tev_count_label.setAlignment(Qt.AlignCenter)
        tev_count_layout.addWidget(self.tev_count_label)
        data_layout.addLayout(tev_count_layout)
        
        # # AA/AE值显示
        # aa_value_layout = QVBoxLayout()
        # aa_value_layout.addWidget(QLabel("AA/AE值(dB):"))
        # self.aa_value_label = QLabel("--")
        # self.aa_value_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: green;")
        # self.aa_value_label.setAlignment(Qt.AlignCenter)
        # aa_value_layout.addWidget(self.aa_value_label)
        # data_layout.addLayout(aa_value_layout)
        
        # # 更新时间显示
        # update_time_layout = QVBoxLayout()
        # update_time_layout.addWidget(QLabel("更新时间:"))
        # self.update_time_label = QLabel("--")
        # self.update_time_label.setAlignment(Qt.AlignCenter)
        # update_time_layout.addWidget(self.update_time_label)
        # data_layout.addLayout(update_time_layout)
        
        top_layout.addWidget(data_group)
        
        # =============== 波形图显示 ===============
        # 创建选项卡组件
        tab_widget = QTabWidget()
        bottom_layout.addWidget(tab_widget)
        
        # TEV波形选项卡
        tev_tab = QWidget()
        tev_layout = QVBoxLayout(tev_tab)
        
        # 添加Y轴范围控制
        tev_range_layout = QHBoxLayout()
        tev_range_layout.addWidget(QLabel("Y轴范围:"))
        self.tev_min_edit = QLineEdit("0")
        self.tev_min_edit.setFixedWidth(50)
        tev_range_layout.addWidget(self.tev_min_edit)
        tev_range_layout.addWidget(QLabel("~"))
        self.tev_max_edit = QLineEdit("300")
        self.tev_max_edit.setFixedWidth(50)
        tev_range_layout.addWidget(self.tev_max_edit)
        self.tev_range_btn = QPushButton("设置范围")
        self.tev_range_btn.clicked.connect(lambda: self.set_y_range(self.tev_plot, self.tev_min_edit, self.tev_max_edit))
        tev_range_layout.addWidget(self.tev_range_btn)
        tev_range_layout.addStretch()
        tev_layout.addLayout(tev_range_layout)
        
        # TEV波形图
        self.tev_plot = pg.PlotWidget()
        self.tev_plot.setBackground('w')
        self.tev_plot.setTitle("TEV波形图", color="b", size="14pt")
        self.tev_plot.setLabel('left', 'TEV幅值', units='mV')
        self.tev_plot.setLabel('bottom', '样本点', units='')
        self.tev_plot.showGrid(x=True, y=True)
        # 设置默认Y轴范围
        self.tev_plot.setYRange(0, 300)
        self.tev_curve = self.tev_plot.plot(pen=pg.mkPen(color='b', width=2))
        tev_layout.addWidget(self.tev_plot)
        
        tab_widget.addTab(tev_tab, "TEV波形")
        
        # AA波形选项卡
        aa_tab = QWidget()
        aa_layout = QVBoxLayout(aa_tab)
        
        # 添加Y轴范围控制
        aa_range_layout = QHBoxLayout()
        aa_range_layout.addWidget(QLabel("Y轴范围:"))
        self.aa_min_edit = QLineEdit("0")
        self.aa_min_edit.setFixedWidth(50)
        aa_range_layout.addWidget(self.aa_min_edit)
        aa_range_layout.addWidget(QLabel("~"))
        self.aa_max_edit = QLineEdit("300")
        self.aa_max_edit.setFixedWidth(50)
        aa_range_layout.addWidget(self.aa_max_edit)
        self.aa_range_btn = QPushButton("设置范围")
        self.aa_range_btn.clicked.connect(lambda: self.set_y_range(self.aa_plot, self.aa_min_edit, self.aa_max_edit))
        aa_range_layout.addWidget(self.aa_range_btn)
        aa_range_layout.addStretch()
        aa_layout.addLayout(aa_range_layout)
        
        # AA波形图
        self.aa_plot = pg.PlotWidget()
        self.aa_plot.setBackground('w')
        self.aa_plot.setTitle("AA/AE波形图", color="g", size="14pt")
        self.aa_plot.setLabel('left', 'AA/AE幅值', units='mV')
        self.aa_plot.setLabel('bottom', '样本点', units='')
        self.aa_plot.showGrid(x=True, y=True)
        # 设置默认Y轴范围
        self.aa_plot.setYRange(0, 300)
        self.aa_curve = self.aa_plot.plot(pen=pg.mkPen(color='g', width=2))
        aa_layout.addWidget(self.aa_plot)
        
        tab_widget.addTab(aa_tab, "AA/AE波形")
        
        # 刷新波形按钮
        refresh_layout = QHBoxLayout()
        self.refresh_wave_btn = QPushButton("刷新波形")
        self.refresh_wave_btn.clicked.connect(self.refresh_waveforms)
        self.refresh_wave_btn.setEnabled(False)
        refresh_layout.addWidget(self.refresh_wave_btn)
        bottom_layout.addLayout(refresh_layout)
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")
    
    def refresh_ports(self):
        """刷新可用串口列表"""
        # 保存当前选择
        current_port = self.port_combo.currentText()
        
        # 清空列表
        self.port_combo.clear()
        
        # 获取可用串口
        available_ports = get_available_ports()
        for port, desc in available_ports:
            self.port_combo.addItem(f"{port} - {desc}", port)
        
        # 恢复之前的选择（如果存在）
        index = self.port_combo.findText(current_port, Qt.MatchStartsWith)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)
    
    def toggle_connection(self):
        """连接或断开传感器"""
        if self.sensor is None or not self.sensor.connected:
            self.connect_sensor()
        else:
            self.disconnect_sensor()
    
    def connect_sensor(self):
        """连接到传感器"""
        if not self.port_combo.currentText():
            QMessageBox.warning(self, "连接错误", "请选择串口")
            return
        
        try:
            # 提取端口名称
            port_data = self.port_combo.currentData()
            baudrate = int(self.baud_combo.currentText())
            device_addr = int(self.addr_edit.text())
            
            # 创建传感器对象
            self.statusBar.showMessage("正在连接传感器...")
            self.sensor = TEVAASensor(port_data, device_addr, baudrate)
            
            if not self.sensor.connect():
                QMessageBox.critical(self, "连接错误", "无法连接到传感器")
                self.sensor = None
                self.statusBar.showMessage("连接失败")
                return
            
            # 更新UI状态
            self.connect_btn.setText("断开")
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.addr_edit.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.refresh_wave_btn.setEnabled(True)
            
            # 启动数据监测线程
            self.start_data_monitor()
            
            # 判断是否自动刷新
            if self.auto_refresh_combo.currentText() == "开启":
                self.start_auto_refresh()
            
            self.statusBar.showMessage("已连接到传感器")
            
            # 连接后立即刷新波形
            self.refresh_waveforms()
        
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接传感器时出错: {str(e)}")
            self.sensor = None
            self.statusBar.showMessage("连接失败")
    
    def disconnect_sensor(self):
        """断开与传感器的连接"""
        # 停止数据监测线程
        if self.data_monitor_thread:
            self.data_monitor_thread.stop()
            self.data_monitor_thread = None
        
        # 停止波形线程
        if self.waveform_thread:
            self.waveform_thread.stop()
            self.waveform_thread = None
        
        # 断开传感器连接
        if self.sensor:
            self.sensor.disconnect()
            self.sensor = None
        
        # 更新UI状态
        self.connect_btn.setText("连接")
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.addr_edit.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.refresh_wave_btn.setEnabled(False)
        
        # 清空数据显示
        self.tev_value_label.setText("--")
        self.tev_count_label.setText("--")
        # self.aa_value_label.setText("--")
        # self.update_time_label.setText("--")
        
        self.statusBar.showMessage("已断开连接")
    
    def refresh_waveforms(self):
        """刷新波形数据"""
        if not self.sensor or not self.sensor.connected:
            return
        
        # 禁用刷新按钮，避免重复点击
        self.refresh_wave_btn.setEnabled(False)
        self.statusBar.showMessage("正在读取波形数据...")
        
        # 启动波形读取线程
        if self.waveform_thread and self.waveform_thread.isRunning():
            self.waveform_thread.stop()
        
        # 创建一个非自动刷新的线程
        self.waveform_thread = WaveformThread(self.sensor, False)
        self.waveform_thread.tev_waveform_ready.connect(self.update_tev_waveform)
        self.waveform_thread.aa_waveform_ready.connect(self.update_aa_waveform)
        self.waveform_thread.error_occurred.connect(self.handle_error)
        self.waveform_thread.finished.connect(lambda: self.refresh_wave_btn.setEnabled(True))
        self.waveform_thread.start()
    
    def start_auto_refresh(self):
        """启动自动刷新波形"""
        if not self.sensor or not self.sensor.connected:
            return
        
        if self.waveform_thread and self.waveform_thread.isRunning():
            self.waveform_thread.stop()
        
        # 创建一个自动刷新的线程
        self.waveform_thread = WaveformThread(self.sensor, True)
        self.waveform_thread.tev_waveform_ready.connect(self.update_tev_waveform)
        self.waveform_thread.aa_waveform_ready.connect(self.update_aa_waveform)
        self.waveform_thread.error_occurred.connect(self.handle_error)
        self.waveform_thread.start()
        
        self.statusBar.showMessage("自动刷新波形已启动")
    
    def stop_auto_refresh(self):
        """停止自动刷新波形"""
        if self.waveform_thread and self.waveform_thread.isRunning():
            self.waveform_thread.stop()
            self.waveform_thread = None
            self.statusBar.showMessage("自动刷新波形已停止")
    
    def toggle_auto_refresh(self, value):
        """切换自动刷新状态"""
        if value == "开启" and self.sensor and self.sensor.connected:
            self.start_auto_refresh()
        elif value == "关闭" and self.waveform_thread:
            self.stop_auto_refresh()
    
    @pyqtSlot(list)
    def update_tev_waveform(self, data):
        """更新TEV波形图"""
        self.tev_curve.setData(range(len(data)), data)
        self.statusBar.showMessage("TEV波形数据已更新")
    
    @pyqtSlot(list)
    def update_aa_waveform(self, data):
        """更新AA波形图"""
        self.aa_curve.setData(range(len(data)), data)
        self.statusBar.showMessage("AA/AE波形数据已更新")
    
    @pyqtSlot(str)
    def handle_error(self, message):
        """处理错误信息"""
        self.statusBar.showMessage(message)
        if "连接" in message or "通信" in message:
            # 连接类错误，尝试断开重连
            self.disconnect_sensor()
    
    def start_data_monitor(self):
        """启动数据监测线程"""
        if not self.sensor or not self.sensor.connected:
            return
        
        if self.data_monitor_thread and self.data_monitor_thread.isRunning():
            self.data_monitor_thread.stop()
        
        # 创建并启动数据监测线程
        self.data_monitor_thread = DataMonitorThread(self.sensor, 1.0)
        self.data_monitor_thread.data_updated.connect(self.update_sensor_data)
        self.data_monitor_thread.error_occurred.connect(self.handle_error)
        self.data_monitor_thread.start()
    
    @pyqtSlot(dict)
    def update_sensor_data(self, data):
        """更新传感器数据显示"""
        if 'tev_value' in data:
            self.tev_value_label.setText(f"{data['tev_value']}")
        
        if 'tev_discharge_count' in data:
            self.tev_count_label.setText(f"{data['tev_discharge_count']}")
        
        # if 'aa_value' in data:
        #     self.aa_value_label.setText(f"{data['aa_value']}")
        
        # # 更新时间
        # current_time = time.strftime("%H:%M:%S")
        # self.update_time_label.setText(current_time)
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 停止数据监测线程
        if self.data_monitor_thread:
            self.data_monitor_thread.stop()
        
        # 停止波形线程
        if self.waveform_thread:
            self.waveform_thread.stop()
        
        # 断开传感器
        if self.sensor and self.sensor.connected:
            self.sensor.disconnect()
        
        event.accept()

    def set_y_range(self, plot_widget, min_edit, max_edit):
        """设置绘图的Y轴范围"""
        try:
            y_min = float(min_edit.text())
            y_max = float(max_edit.text())
            
            if y_min >= y_max:
                QMessageBox.warning(self, "范围错误", "最小值必须小于最大值")
                return
            
            plot_widget.setYRange(y_min, y_max)
            self.statusBar.showMessage(f"Y轴范围已设置为 {y_min} ~ {y_max}")
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数值")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"设置范围时出错: {str(e)}")


if __name__ == "__main__":
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格
    
    # 创建并显示GUI
    window = SimpleSensorGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_()) 