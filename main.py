#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

# ----------------------------------------------------------------------
# 动态导入（修复 PyInstaller + 修复 safe_join ImportError）
# ----------------------------------------------------------------------
def import_custom_modules():
    """动态导入自定义模块，兼容打包和开发环境"""
    try:
        # 开发环境直接导入
        from webui import create_app
        from converter import VideoConverter
        print("正常导入模块成功")
        return create_app, VideoConverter

    except Exception as e:
        print("正常导入失败，尝试动态导入…")
        print(f"开发环境错误: {e}")

        # -------------------------------
        # PyInstaller 打包路径
        # -------------------------------
        if getattr(sys, 'frozen', False):
            root = sys._MEIPASS       # PyInstaller 解包目录
            internal = os.path.join(root, "_internal")
        else:
            # 开发环境（不会触发这里）
            root = os.path.dirname(os.path.abspath(__file__))
            internal = root

        # ========== 加载 webui.py ==========
        webui_path = os.path.join(internal, "webui.py")
        if not os.path.exists(webui_path):
            raise ImportError(f"找不到 webui.py，检查是否正确打包路径: {webui_path}")

        import importlib.util

        spec = importlib.util.spec_from_file_location("webui", webui_path)
        webui_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(webui_module)
        create_app = webui_module.create_app

        # ========== 加载 converter.py ==========
        converter_path = os.path.join(internal, "converter.py")
        if not os.path.exists(converter_path):
            raise ImportError(f"找不到 converter.py，检查是否正确打包路径: {converter_path}")

        spec2 = importlib.util.spec_from_file_location("converter", converter_path)
        converter_module = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(converter_module)
        VideoConverter = converter_module.VideoConverter

        print("动态导入模块成功（PyInstaller 模式）")
        return create_app, VideoConverter


create_app, VideoConverter = import_custom_modules()


# ----------------------------------------------------------------------
# 标准库和第三方库
# ----------------------------------------------------------------------
import argparse

import flask
import waitress


def main():
    parser = argparse.ArgumentParser(description='视频格式转换器')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    parser.add_argument('--host', default='0.0.0.0', help='WebUI主机地址')
    parser.add_argument('--port', type=int, default=5000, help='WebUI端口')
    parser.add_argument('--input', help='输入文件路径（无头模式使用）')
    parser.add_argument('--output', help='输出文件路径（无头模式使用）')
    parser.add_argument('--format', choices=['gif', 'apng', 'webp', 'avif'], help='输出格式')
    parser.add_argument('--scale', type=float, default=1.0, help='分辨率缩放比例')
    parser.add_argument('--fps', type=int, help='输出帧率')
    parser.add_argument('--quality', type=int, help='质量设置')
    parser.add_argument('--target-size', type=int, help='目标文件大小（字节）')

    args = parser.parse_args()

    # 创建临时目录
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    temp_dir = os.path.join(base_dir, '0Animated-Convertor-Temp')
    os.makedirs(temp_dir, exist_ok=True)

    converter = VideoConverter(temp_dir)

    # --------------------------
    # 无头模式
    # --------------------------
    if args.headless:
        if not all([args.input, args.output, args.format]):
            print("错误：无头模式需要指定 --input, --output, --format")
            sys.exit(1)

        opts = {
            "scale": args.scale,
            "fps": args.fps,
            "quality": args.quality,
            "target_size": args.target_size
        }

        result = converter.convert_video(args.input, args.output, args.format, opts)
        print("转换完成:", result)
        return

    # --------------------------
    # WebUI 模式
    # --------------------------
    app = create_app(converter)
    print(f"启动 Web 服务: http://{args.host}:{args.port}")
    waitress.serve(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
