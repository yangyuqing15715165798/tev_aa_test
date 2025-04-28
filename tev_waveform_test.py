#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TEV波形图谱读取测试程序
直接使用串口发送Modbus RTU指令读取波形数据
"""

import sys
import time
import struct
import serial
import serial.tools.list_ports
import binascii


def get_available_ports():
    """获取可用串口列表"""
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append((port.device, port.description))
    return ports


def calculate_crc(data):
    """
    计算Modbus CRC16校验码
    
    参数:
        data (bytes): 要计算校验码的数据
        
    返回:
        bytes: 两字节的CRC校验码，低字节在前，高字节在后
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    # 返回低字节在前，高字节在后的CRC
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_read_registers_request(device_addr, start_address, count):
    """
    构建读取保持寄存器的请求
    
    参数:
        device_addr (int): 设备地址
        start_address (int): 起始寄存器地址
        count (int): 寄存器数量
        
    返回:
        bytes: 完整的Modbus RTU请求报文
    """
    # Modbus地址从0开始，文档从1开始，所以需要减1
    modbus_address = start_address
    
    # 构造帧：设备地址(1) + 功能码(1) + 起始地址(2) + 数量(2)
    request = struct.pack('>BBHH', device_addr, 0x03, modbus_address, count)
    
    # 添加CRC
    request += calculate_crc(request)
    
    return request


def parse_read_registers_response(response, register_count):
    """
    解析读取保持寄存器的响应
    
    参数:
        response (bytes): 完整的Modbus RTU响应报文
        register_count (int): 预期的寄存器数量
        
    返回:
        list 或 None: 解析出的寄存器值列表，失败返回None
    """
    # 检查响应长度 = 设备地址(1) + 功能码(1) + 字节数(1) + 数据(2*寄存器数) + CRC(2)
    expected_length = 5 + register_count * 2
    
    if len(response) != expected_length:
        print(f"响应长度错误: 预期{expected_length}字节，实际{len(response)}字节")
        return None
    
    # 检查功能码（是否有异常）
    if response[1] == 0x83:
        exception_code = response[2]
        print(f"Modbus异常: 代码={exception_code}")
        return None
    
    # 检查功能码是否为0x03
    if response[1] != 0x03:
        print(f"功能码错误: 预期0x03，实际接收{hex(response[1])}")
        return None
    
    # 检查字节数是否匹配
    byte_count = response[2]
    if byte_count != register_count * 2:
        print(f"字节数不匹配: 预期{register_count*2}，实际{byte_count}")
        return None
    
    # 验证CRC
    received_data = response[:-2]
    received_crc = response[-2:]
    calculated_crc = calculate_crc(received_data)
    
    if received_crc != calculated_crc:
        print(f"CRC校验失败: 计算值={calculated_crc.hex()}，接收值={received_crc.hex()}")
        return None
    
    # 解析数据
    registers = []
    for i in range(3, 3 + byte_count, 2):
        register_value = (response[i] << 8) + response[i+1]
        registers.append(register_value)
    
    return registers


def select_port():
    """选择串口"""
    ports = get_available_ports()
    
    if not ports:
        print("未检测到串口设备")
        return None
    
    print("\n可用串口:")
    for i, (port, desc) in enumerate(ports):
        print(f"{i+1}. {port} - {desc}")
    
    choice = input("\n请选择串口编号 (q退出): ")
    if choice.lower() == 'q':
        return None
    
    try:
        index = int(choice) - 1
        if 0 <= index < len(ports):
            return ports[index][0]
        else:
            print("无效的选择")
            return select_port()
    except ValueError:
        print("请输入数字")
        return select_port()


def main():
    """主函数"""
    print("=" * 50)
    print("TEV波形图谱读取测试程序")
    print("=" * 50)
    
    # 选择串口
    port = select_port()
    if not port:
        print("未选择串口，程序退出")
        return 1
    
    # 串口参数配置
    device_addr = 1 # 默认设备地址为1
    baudrate = 9600 # 默认波特率9600
    
    try:
        device_addr = int(input("请输入设备地址 [1]: ") or "1")
        baudrate = int(input("请输入波特率 [9600]: ") or "9600")
    except ValueError:
        print("输入无效，使用默认值")
    
    # 读取寄存器参数
    tev_start_address = 201  # TEV波形图谱起始地址
    tev_register_count = 100  # 读取100个寄存器 (201-300)
    
    # 构建请求
    request = build_read_registers_request(device_addr, tev_start_address, tev_register_count)
    
    # 打印请求报文
    print("\n发送请求:")
    print(f"原始报文: {binascii.hexlify(request).decode().upper()}")
    print(f"报文分析: 设备地址={device_addr}, 功能码=03, 起始地址={tev_start_address-1}(0x{(tev_start_address-1):04X}), 寄存器数量={tev_register_count}(0x{tev_register_count:04X})")
    
    # 打开串口
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=2  # 2秒超时
        )
        
        # 发送请求
        print("\n正在发送请求并等待响应...")
        
        # 清空缓冲区
        ser.reset_input_buffer()
        
        # 发送请求
        ser.write(request)
        
        # 读取响应 (预期: 设备地址1 + 功能码1 + 字节数1 + 数据2*count + CRC2)
        expected_response_length = 5 + tev_register_count * 2
        response = ser.read(expected_response_length)
        
        # 打印原始响应
        print(f"\n接收响应: {len(response)}字节")
        if response:
            print(f"原始响应: {binascii.hexlify(response).decode().upper()}")
        else:
            print("未收到响应或响应超时")
            ser.close()
            return 1
        
        # 解析响应
        registers = parse_read_registers_response(response, tev_register_count)
        
        if registers:
            print(f"\n成功读取TEV波形数据，共{len(registers)}个点")
            
            # 显示前10个点（如果有）
            preview_count = min(10, len(registers))
            print(f"\n前{preview_count}个数据点:")
            for i in range(preview_count):
                print(f"点{i+1}: {registers[i]}")
            
            # 显示基本统计信息
            if registers:
                print(f"\n数据统计:")
                print(f"最小值: {min(registers)}")
                print(f"最大值: {max(registers)}")
                print(f"平均值: {sum(registers)/len(registers):.2f}")
            
            # 保存数据
            save_option = input("\n是否保存波形数据到文件? (y/n): ").lower()
            if save_option == 'y':
                filename = "tev_waveform_data.txt"
                with open(filename, 'w') as f:
                    for i, value in enumerate(registers):
                        f.write(f"{i+1}, {value}\n")
                print(f"波形数据已保存到 {filename}")
        else:
            print("解析波形数据失败")
        
        # 关闭串口
        ser.close()
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        return 1
    
    print("\n测试完成")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 