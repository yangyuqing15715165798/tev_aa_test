# TEV/AA二合一传感器监测软件

## 项目概述
这是一个用于监测TEV/AA（瞬态地电压/声学发射）二合一传感器的软件。该软件提供了与传感器通信的功能，并通过图形界面显示传感器数据和波形。

### 主要功能
- 直接通过串口与传感器通信（Modbus RTU协议）
- 实时显示传感器数据
- 可视化TEV和AA波形数据
- 自动检测可用串口
- 用户友好的图形界面
- 支持数据分析

## 系统要求
- 操作系统：Windows 7/8/10/11
- Python 3.6或更高版本（如使用打包版本则不需要）
- RS-485/USB转换器（用于连接传感器）

## 软件使用

### 打包版本
1. 从发布页面下载最新的软件包
2. 解压缩文件
3. 运行`tev_aa_gui.exe`或`tev_aa_simple_gui.exe`（简化版界面）

### 开发版本
1. 克隆或下载此代码库
2. 安装所需依赖：
   ```
   pip install -r requirements.txt
   ```
3. 运行主程序：
   ```
   python tev_aa_gui.py
   ```
   或运行简化版界面：
   ```
   python tev_aa_simple_gui.py
   ```

## 软件打包
使用PyInstaller可以将软件打包为独立的可执行文件：

### 安装PyInstaller
```
pip install pyinstaller
```

### 打包完整版GUI
```
pyinstaller --noconsole --onefile --icon=sensor_icon.ico --name=tev_aa_gui tev_aa_gui.py
```

### 打包简化版GUI
```
pyinstaller --noconsole --onefile --icon=sensor_icon.ico --name=tev_aa_simple_gui tev_aa_simple_gui.py

```
不加图标
```
pyinstaller --noconsole --onefile --name=tev_aa_simple_gui tev_aa_simple_gui.py
```

### 打包选项说明
- `--noconsole`: 启动程序时不显示命令行窗口
- `--onefile`: 将所有依赖打包到单个可执行文件中
- `--icon`: 设置可执行文件图标（需要提供图标文件）
- `--name`: 指定输出的可执行文件名称

打包后的文件将位于`dist`目录中。

## 常见问题

### 无法检测到串行设备
- 确保RS-485/USB转换器已正确连接到计算机
- 检查设备管理器中是否识别了串行设备
- 尝试重新插拔转换器
- 安装或更新设备驱动程序

### 无法连接到传感器
- 确保选择了正确的串口
- 验证波特率设置（默认为9600）
- 检查传感器电源是否接通
- 确认传感器地址设置（默认为1）

### 波形显示异常
- 检查传感器是否正常工作
- 尝试调整波形显示范围
- 重新连接传感器
- 重启软件

## 目录结构
- `tev_aa_combined.py`: 传感器通信核心模块
- `tev_aa_gui.py`: 完整版图形界面程序
- `tev_aa_simple_gui.py`: 简化版图形界面程序（仅波形显示）
- `requirements.txt`: 项目依赖列表
- `README.md`: 项目说明文档

## 开发者信息
本软件使用Python语言开发，基于PyQt5图形界面框架，使用pymodbus库进行Modbus RTU通信。 