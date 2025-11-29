# utils.py
# -*- coding: utf-8 -*-

import os
import psutil
import subprocess
import platform

def get_available_memory():
    """获取可用内存（字节）"""
    return psutil.virtual_memory().available

def get_memory_strategy():
    """根据可用内存返回策略"""
    available_gb = get_available_memory() / (1024 ** 3)
    
    if available_gb < 4:
        return 'low'
    elif available_gb < 8:
        return 'medium'
    elif available_gb < 16:
        return 'high'
    elif available_gb < 24:
        return 'very_high'
    elif available_gb < 48:
        return 'ultra'
    else:
        return 'max'

def get_hwaccel_priority():
    """检测并返回优先的硬件加速器，考虑格式兼容性"""
    try:
        # 检查可用的硬件加速器
        result = subprocess.run(['ffmpeg', '-hwaccels'], capture_output=True, text=True, check=True)
        hwaccels = result.stdout.lower()
        
        # 按优先级检查，但考虑实际兼容性
        if 'qsv' in hwaccels:
            return 'qsv'  # Intel QuickSync
        elif 'cuda' in hwaccels:
            return 'cuda'  # NVIDIA NVENC
        elif 'dxva2' in hwaccels:
            return 'dxva2'  # DirectX
        elif 'd3d11va' in hwaccels:
            return 'd3d11va'
        else:
            return ''  # 无硬件加速
    except Exception as e:
        print(f"硬件加速检测失败: {e}")
        return ''

def format_file_size(size_bytes):
    """格式化文件大小显示"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

def is_supported_video(file_path):
    """检查文件是否为支持的视频格式"""
    supported_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.webm'}
    _, ext = os.path.splitext(file_path.lower())
    return ext in supported_extensions

def sanitize_filename(filename):
    """清理文件名，确保中文兼容"""
    return filename

