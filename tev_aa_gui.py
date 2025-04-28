#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEV/AA二合一传感器GUI监测程序
基于PyQt5实现界面可视化，展示传感器数据
"""

import sys
import time
import threading
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QComboBox, 
                            QGroupBox, QGridLayout, QLineEdit, QStatusBar, 
                            QMessageBox, QTabWidget, QFrame, QSplitter)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor

import pyqtgraph as pg
from pymodbus.client.sync import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

# 导入传感器类
from tev_aa_combined import TEVAASensor, get_available_ports


class DataMonitorThread(QThread):
    """数据监测线程，避免界面卡顿"""
    data_updated = pyqtSignal(dict)  # 数据更新信号
    error_occurred = pyqtSignal(str)  # 错误信号
    
    def __init__(self, sensor, parent=None):
        super().__init__(parent)
        self.sensor = sensor
        self.running = False
    
    def run(self):
        self.running = True
        while self.running:
            try:
                values = self.sensor.get_all_sensor_values()
                if values:
                    self.data_updated.emit(values)
                else:
                    self.error_occurred.emit("读取传感器数据失败")
            except Exception as e:
                self.error_occurred.emit(f"监测错误: {str(e)}")
                break
            
            # 休眠一小段时间，避免过于频繁的请求
            time.sleep(0.5)
    
    def stop(self):
        self.running = False
        self.wait()


class WaveformThread(QThread):
    """波形数据读取线程"""
    tev_waveform_ready = pyqtSignal(list)  # TEV波形数据信号
    aa_waveform_ready = pyqtSignal(list)   # AA波形数据信号
    error_occurred = pyqtSignal(str)       # 错误信号
    
    def __init__(self, sensor, parent=None):
        super().__init__(parent)
        self.sensor = sensor
    
    def run(self):
        try:
            # 读取TEV波形数据
            tev_waveform = self.sensor.get_tev_waveform()
            self.tev_waveform_ready.emit(tev_waveform)
            
            # 读取AA波形数据
            aa_waveform = self.sensor.get_aa_waveform()
            self.aa_waveform_ready.emit(aa_waveform)
        except Exception as e:
            self.error_occurred.emit(f"波形数据读取错误: {str(e)}")


class SensorGUI(QMainWindow):
    """TEV/AA传感器GUI主窗口"""
    
    def __init__(self):
        super().__init__()
        self.sensor = None
        self.data_thread = None
        self.waveform_thread = None
        self.tev_waveform_data = []
        self.aa_waveform_data = []
        
        self.init_ui()
        self.refresh_ports()
        
        # 创建定时器，定期更新端口列表
        self.port_timer = QTimer(self)
        self.port_timer.timeout.connect(self.refresh_ports)
        self.port_timer.start(5000)  # 每5秒刷新一次
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("TEV/AA二合一传感器监测系统")
        self.setGeometry(100, 100, 1000, 700)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建水平分割器
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # 顶部控制区域
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        splitter.addWidget(top_widget)
        
        # 底部数据和波形显示区域
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        splitter.addWidget(bottom_widget)
        
        # 设置初始分割比例
        splitter.setSizes([200, 500])
        
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
        self.addr_spin = QLineEdit("1")
        self.addr_spin.setFixedWidth(80)
        addr_layout.addWidget(self.addr_spin)
        connection_layout.addLayout(addr_layout)
        
        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.toggle_connection)
        connection_layout.addWidget(self.connect_btn)
        
        top_layout.addWidget(connection_group)
        
        # =============== 设备参数区域 ===============
        params_group = QGroupBox("设备参数")
        params_layout = QGridLayout()
        params_group.setLayout(params_layout)
        
        # TEV阈值
        params_layout.addWidget(QLabel("TEV背景阈值:"), 0, 0)
        self.tev_threshold_edit = QLineEdit("50")
        self.tev_threshold_edit.setReadOnly(True)
        params_layout.addWidget(self.tev_threshold_edit, 0, 1)
        self.set_tev_threshold_btn = QPushButton("设置")
        self.set_tev_threshold_btn.clicked.connect(self.set_tev_threshold)
        self.set_tev_threshold_btn.setEnabled(False)
        params_layout.addWidget(self.set_tev_threshold_btn, 0, 2)
        
        # AA阈值
        params_layout.addWidget(QLabel("AA/AE背景阈值:"), 1, 0)
        self.aa_threshold_edit = QLineEdit("50")
        self.aa_threshold_edit.setReadOnly(True)
        params_layout.addWidget(self.aa_threshold_edit, 1, 1)
        self.set_aa_threshold_btn = QPushButton("设置")
        self.set_aa_threshold_btn.clicked.connect(self.set_aa_threshold)
        self.set_aa_threshold_btn.setEnabled(False)
        params_layout.addWidget(self.set_aa_threshold_btn, 1, 2)
        
        top_layout.addWidget(params_group)
        
        # =============== 实时数据显示区域 ===============
        data_group = QGroupBox("实时监测数据")
        data_layout = QGridLayout()
        data_group.setLayout(data_layout)
        
        # TEV值
        data_layout.addWidget(QLabel("TEV值 (dB):"), 0, 0)
        self.tev_value_label = QLabel("--")
        self.tev_value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: blue;")
        self.tev_value_label.setAlignment(Qt.AlignCenter)
        data_layout.addWidget(self.tev_value_label, 0, 1)
        
        # TEV放电次数
        data_layout.addWidget(QLabel("TEV放电次数:"), 1, 0)
        self.tev_count_label = QLabel("--")
        self.tev_count_label.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")
        self.tev_count_label.setAlignment(Qt.AlignCenter)
        data_layout.addWidget(self.tev_count_label, 1, 1)
        
        # AA/AE值
        data_layout.addWidget(QLabel("AA/AE值 (dB):"), 2, 0)
        self.aa_value_label = QLabel("--")
        self.aa_value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: green;")
        self.aa_value_label.setAlignment(Qt.AlignCenter)
        data_layout.addWidget(self.aa_value_label, 2, 1)
        
        top_layout.addWidget(data_group)
        
        # =============== 波形图显示 ===============
        # 创建选项卡组件
        tab_widget = QTabWidget()
        bottom_layout.addWidget(tab_widget)
        
        # TEV波形选项卡
        tev_tab = QWidget()
        tev_layout = QVBoxLayout(tev_tab)
        self.tev_plot = pg.PlotWidget()
        self.tev_plot.setBackground('w')
        self.tev_plot.setTitle("TEV波形图", color="b", size="14pt")
        self.tev_plot.setLabel('left', 'TEV幅值', units='dB')
        self.tev_plot.setLabel('bottom', '样本点', units='')
        self.tev_plot.showGrid(x=True, y=True)
        self.tev_curve = self.tev_plot.plot(pen=pg.mkPen(color='b', width=2))
        tev_layout.addWidget(self.tev_plot)
        
        # 添加波形控制按钮
        tev_btn_layout = QHBoxLayout()
        self.refresh_tev_btn = QPushButton("刷新TEV波形")
        self.refresh_tev_btn.clicked.connect(self.refresh_waveforms)
        self.refresh_tev_btn.setEnabled(False)
        tev_btn_layout.addWidget(self.refresh_tev_btn)
        tev_layout.addLayout(tev_btn_layout)
        
        tab_widget.addTab(tev_tab, "TEV波形")
        
        # AA波形选项卡
        aa_tab = QWidget()
        aa_layout = QVBoxLayout(aa_tab)
        self.aa_plot = pg.PlotWidget()
        self.aa_plot.setBackground('w')
        self.aa_plot.setTitle("AA/AE波形图", color="g", size="14pt")
        self.aa_plot.setLabel('left', 'AA/AE幅值', units='dB')
        self.aa_plot.setLabel('bottom', '样本点', units='')
        self.aa_plot.showGrid(x=True, y=True)
        self.aa_curve = self.aa_plot.plot(pen=pg.mkPen(color='g', width=2))
        aa_layout.addWidget(self.aa_plot)
        
        tab_widget.addTab(aa_tab, "AA/AE波形")
        
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
            device_addr = int(self.addr_spin.text())
            
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
            self.addr_spin.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            
            # 启用参数设置按钮
            self.set_tev_threshold_btn.setEnabled(True)
            self.set_aa_threshold_btn.setEnabled(True)
            self.refresh_tev_btn.setEnabled(True)
            
            # 获取设备参数
            self.read_device_params()
            
            # 启动数据监测线程
            self.start_data_monitoring()
            
            # 读取初始波形数据
            self.refresh_waveforms()
            
            self.statusBar.showMessage("已连接到传感器")
        
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接传感器时出错: {str(e)}")
            self.sensor = None
            self.statusBar.showMessage("连接失败")
    
    def disconnect_sensor(self):
        """断开与传感器的连接"""
        # 停止数据监测线程
        if self.data_thread:
            self.data_thread.stop()
            self.data_thread = None
        
        # 断开传感器连接
        if self.sensor:
            self.sensor.disconnect()
            self.sensor = None
        
        # 更新UI状态
        self.connect_btn.setText("连接")
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.addr_spin.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        
        # 禁用参数设置按钮
        self.set_tev_threshold_btn.setEnabled(False)
        self.set_aa_threshold_btn.setEnabled(False)
        self.refresh_tev_btn.setEnabled(False)
        
        # 清空数据显示
        self.tev_value_label.setText("--")
        self.tev_count_label.setText("--")
        self.aa_value_label.setText("--")
        self.tev_threshold_edit.setText("--")
        self.aa_threshold_edit.setText("--")
        
        self.statusBar.showMessage("已断开连接")
    
    def read_device_params(self):
        """读取设备参数"""
        try:
            # 读取阈值参数
            tev_threshold = self.sensor.get_tev_threshold()
            if tev_threshold is not None:
                self.tev_threshold_edit.setText(str(tev_threshold))
            
            aa_threshold = self.sensor.get_aa_threshold()
            if aa_threshold is not None:
                self.aa_threshold_edit.setText(str(aa_threshold))
        
        except Exception as e:
            QMessageBox.warning(self, "参数读取错误", f"读取设备参数时出错: {str(e)}")
    
    def start_data_monitoring(self):
        """启动数据监测线程"""
        if self.sensor and self.sensor.connected:
            self.data_thread = DataMonitorThread(self.sensor)
            self.data_thread.data_updated.connect(self.update_sensor_data)
            self.data_thread.error_occurred.connect(self.handle_error)
            self.data_thread.start()
    
    def refresh_waveforms(self):
        """刷新波形数据"""
        if not self.sensor or not self.sensor.connected:
            return
        
        # 禁用刷新按钮，避免重复点击
        self.refresh_tev_btn.setEnabled(False)
        self.statusBar.showMessage("正在读取波形数据...")
        
        # 启动波形读取线程
        self.waveform_thread = WaveformThread(self.sensor)
        self.waveform_thread.tev_waveform_ready.connect(self.update_tev_waveform)
        self.waveform_thread.aa_waveform_ready.connect(self.update_aa_waveform)
        self.waveform_thread.error_occurred.connect(self.handle_error)
        self.waveform_thread.finished.connect(lambda: self.refresh_tev_btn.setEnabled(True))
        self.waveform_thread.start()
    
    @pyqtSlot(dict)
    def update_sensor_data(self, values):
        """更新传感器数据显示"""
        self.tev_value_label.setText(str(values['tev_value']))
        self.tev_count_label.setText(str(values['tev_discharge_count']))
        self.aa_value_label.setText(str(values['aa_value']))
    
    @pyqtSlot(list)
    def update_tev_waveform(self, data):
        """更新TEV波形图"""
        self.tev_waveform_data = data
        self.tev_curve.setData(range(len(data)), data)
        self.statusBar.showMessage("TEV波形数据已更新")
    
    @pyqtSlot(list)
    def update_aa_waveform(self, data):
        """更新AA波形图"""
        self.aa_waveform_data = data
        self.aa_curve.setData(range(len(data)), data)
        self.statusBar.showMessage("AA/AE波形数据已更新")
    
    def set_tev_threshold(self):
        """设置TEV背景阈值"""
        if not self.sensor or not self.sensor.connected:
            return
        
        threshold, ok = QMessageBox.getInt(self, "设置TEV阈值", "请输入TEV背景阈值:", 
                                         int(self.tev_threshold_edit.text()), 0, 500)
        if ok:
            try:
                if self.sensor.set_tev_threshold(threshold):
                    self.tev_threshold_edit.setText(str(threshold))
                    self.statusBar.showMessage(f"TEV阈值已设置为 {threshold}")
                else:
                    QMessageBox.warning(self, "设置失败", "TEV阈值设置失败")
            except Exception as e:
                QMessageBox.critical(self, "设置错误", f"设置TEV阈值时出错: {str(e)}")
    
    def set_aa_threshold(self):
        """设置AA/AE背景阈值"""
        if not self.sensor or not self.sensor.connected:
            return
        
        threshold, ok = QMessageBox.getInt(self, "设置AA/AE阈值", "请输入AA/AE背景阈值:", 
                                         int(self.aa_threshold_edit.text()), 0, 500)
        if ok:
            try:
                if self.sensor.set_aa_threshold(threshold):
                    self.aa_threshold_edit.setText(str(threshold))
                    self.statusBar.showMessage(f"AA/AE阈值已设置为 {threshold}")
                else:
                    QMessageBox.warning(self, "设置失败", "AA/AE阈值设置失败")
            except Exception as e:
                QMessageBox.critical(self, "设置错误", f"设置AA/AE阈值时出错: {str(e)}")
    
    @pyqtSlot(str)
    def handle_error(self, message):
        """处理错误信息"""
        self.statusBar.showMessage(message)
        if "连接" in message or "通信" in message:
            # 连接类错误，尝试断开重连
            self.disconnect_sensor()
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 停止数据线程
        if self.data_thread:
            self.data_thread.stop()
        
        # 断开传感器
        if self.sensor and self.sensor.connected:
            self.sensor.disconnect()
        
        event.accept()


if __name__ == "__main__":
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格
    
    # 创建并显示GUI
    window = SensorGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_()) 