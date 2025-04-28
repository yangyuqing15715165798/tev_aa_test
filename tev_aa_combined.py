#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEV/AA二合一传感器通信模块和示例程序
基于Modbus RTU协议实现与传感器的通信
适用于pymodbus 2.5.3版本
"""

import time
import sys
import serial.tools.list_ports
from pymodbus.client.sync import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse


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


def select_port():
    """
    显示所有可用串口并让用户选择
    
    返回:
        str: 选择的串口名称，如果没有可用串口或用户取消，则返回None
    """
    ports = get_available_ports()
    
    if not ports:
        print("没有检测到任何可用的串口设备")
        return None
    
    print("\n可用串口列表:")
    for i, (port, desc) in enumerate(ports):
        print(f"{i+1}. {port} - {desc}")
    
    try:
        choice = input("\n请输入要使用的串口编号 (输入q退出): ")
        if choice.lower() == 'q':
            return None
        
        index = int(choice) - 1
        if 0 <= index < len(ports):
            return ports[index][0]
        else:
            print("无效的选择")
            return select_port()  # 递归调用，重新选择
    except ValueError:
        print("请输入有效的编号")
        return select_port()  # 递归调用，重新选择


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
            # pymodbus 2.5.3版本中，地址直接使用，无需address参数
            result = self.client.read_holding_registers(
                address=address-1,  # Modbus地址从0开始，而文档地址从1开始
                count=count,
                unit=self.device_addr  # pymodbus 2.5.3中使用unit而不是slave
            )
            
            if isinstance(result, ExceptionResponse):
                raise ModbusException(f"读取寄存器失败: {result}")
                
            return result.registers
        except Exception as e:
            raise IOError(f"读取寄存器错误: {e}")
    
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
            int: TEV值
        """
        result = self._read_register(self.REG_TEV_VALUE)
        return result[0] if result else None
    
    def get_tev_discharge_count(self):
        """
        获取TEV放电次数
        
        返回:
            int: TEV放电次数
        """
        result = self._read_register(self.REG_TEV_DISCHARGE_COUNT)
        return result[0] if result else None
    
    def get_aa_value(self):
        """
        获取AA/AE值(dB)
        
        返回:
            int: AA/AE值
        """
        result = self._read_register(self.REG_AA_VALUE)
        return result[0] if result else None
    
    def get_all_sensor_values(self):
        """
        获取所有传感器值
        
        返回:
            dict: 包含所有传感器值的字典
        """
        try:
            # 一次性读取3个寄存器（从TEV值开始）
            results = self._read_register(self.REG_TEV_VALUE, 3)
            
            if results and len(results) == 3:
                return {
                    'tev_value': results[0],
                    'tev_discharge_count': results[1],
                    'aa_value': results[2]
                }
            else:
                return None
        except Exception as e:
            raise IOError(f"获取传感器值错误: {e}")
    
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


def main():
    """传感器通信示例主函数"""
    # 显示欢迎信息
    print("=" * 50)
    print("TEV/AA二合一传感器测试程序")
    print("=" * 50)
    
    # 检测并选择串口
    port = select_port()
    if not port:
        print("未选择串口，程序退出")
        return 1
    
    # 设置通信参数
    device_addr = 1
    baudrate = 9600
    
    try:
        # 使用上下文管理器自动处理连接和断开
        with TEVAASensor(port, device_addr, baudrate) as sensor:
            print(f"已连接到串口: {port}, 波特率: {baudrate}, 设备地址: {device_addr}")
            
            # 读取基本配置信息
            device_addr = sensor.get_device_address()
            baudrate = sensor.get_baud_rate()
            tev_threshold = sensor.get_tev_threshold()
            aa_threshold = sensor.get_aa_threshold()
            
            print("\n设备配置信息:")
            print(f"设备地址: {device_addr}")
            print(f"波特率: {baudrate}")
            print(f"TEV背景阈值: {tev_threshold}")
            print(f"AA/AE背景阈值: {aa_threshold}")
            
            # 实时数据监测循环
            print("\n开始实时数据监测 (按Ctrl+C退出)...")
            print("-" * 50)
            print("时间\t\tTEV值(dB)\tTEV放电次数\tAA/AE值(dB)")
            print("-" * 50)
            
            try:
                while True:
                    # 获取所有传感器值
                    values = sensor.get_all_sensor_values()
                    
                    if values:
                        current_time = time.strftime("%H:%M:%S")
                        print(f"{current_time}\t{values['tev_value']}\t\t{values['tev_discharge_count']}\t\t{values['aa_value']}")
                    else:
                        print("无法读取传感器数据")
                    
                    # 每秒更新一次
                    time.sleep(1)
            
            except KeyboardInterrupt:
                print("\n监测已停止")
            
            # 读取波形数据示例
            print("\n读取波形数据示例:")
            try:
                print("正在读取TEV波形数据...")
                tev_waveform = sensor.get_tev_waveform()
                print(f"TEV波形数据点数: {len(tev_waveform)}")
                print(f"TEV波形前10个点: {tev_waveform[:10]}")
                
                print("\n正在读取AA/AE波形数据...")
                aa_waveform = sensor.get_aa_waveform()
                print(f"AA/AE波形数据点数: {len(aa_waveform)}")
                print(f"AA/AE波形前10个点: {aa_waveform[:10]}")
            except Exception as e:
                print(f"读取波形数据失败: {e}")
            
            # 参数设置示例
            print("\n参数设置示例:")
            try:
                # 读取原始阈值
                old_tev_threshold = sensor.get_tev_threshold()
                print(f"当前TEV阈值: {old_tev_threshold}")
                
                # 设置新阈值
                new_tev_threshold = 55
                print(f"设置新TEV阈值: {new_tev_threshold}")
                if sensor.set_tev_threshold(new_tev_threshold):
                    print("设置成功")
                
                # 读取设置后的阈值确认
                current_tev_threshold = sensor.get_tev_threshold()
                print(f"设置后的TEV阈值: {current_tev_threshold}")
                
                # 恢复原始阈值
                print("恢复原始阈值...")
                if sensor.set_tev_threshold(old_tev_threshold):
                    print("恢复成功")
            except Exception as e:
                print(f"参数设置失败: {e}")
    
    except ConnectionError as e:
        print(f"连接错误: {e}")
        return 1
    except Exception as e:
        print(f"程序错误: {e}")
        return 1
    
    print("\n程序已正常退出")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 