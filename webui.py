# webui.py
# -*- coding: utf-8 -*-

import os
import json
import urllib.parse
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import safe_join


def create_app(converter):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/api/convert', methods=['POST'])
    def api_convert():
        try:
            if 'file' not in request.files:
                return jsonify({'error': '没有选择文件'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': '没有选择文件'}), 400
            
            # 处理中文文件名
            filename = file.filename
            if isinstance(filename, bytes):
                filename = filename.decode('utf-8')
            
            # 保存上传文件
            upload_dir = os.path.join(converter.temp_dir, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            # 防止中文或特殊字符问题，直接把用户上传的文件名作为文件名保存（Flask 会处理）
            input_path = os.path.join(upload_dir, filename)
            file.save(input_path)
            
            print(f"文件已上传: {input_path}")
            
            # 获取转换参数
            data = request.form
            output_format = data.get('format', 'gif')
            scale = float(data.get('scale', 1.0))
            fps = int(data.get('fps', 10)) if data.get('fps') else None
            quality = int(data.get('quality', 80)) if data.get('quality') else None
            target_size = int(data.get('target_size')) if data.get('target_size') else None
            
            # 设置转换选项
            options = {
                'scale': scale,
                'fps': fps,
                'quality': quality,
                'target_size': target_size
            }
            
            # 检查转换器是否支持所需方法
            if not hasattr(converter, 'start_conversion'):
                return jsonify({'error': '转换器配置错误，缺少必要方法'}), 500
            
            # 开始转换
            task_id = converter.start_conversion(input_path, output_format, options)

            # 获取后端记录的 expected filename（如果有）
            task_status = converter.get_task_status(task_id)
            expected_filename = None
            if isinstance(task_status, dict):
                expected_filename = task_status.get('output_filename')
            
            return jsonify({
                'task_id': task_id,
                'status': 'started',
                'message': '转换任务已开始',
                'expected_filename': expected_filename
            })
            
        except Exception as e:
            print(f"转换错误: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'转换失败: {str(e)}'}), 500


    @app.route('/api/status/<int:task_id>')
    def api_status(task_id):
        status = converter.get_task_status(task_id)
        return jsonify(status)
    
    @app.route('/api/download/<path:filename>')
    def api_download(filename):
        # filename 可能包含中文或空格，进行解码
        filename = urllib.parse.unquote(filename)
        output_dir = os.path.join(converter.temp_dir, 'outputs')
        file_path = os.path.join(output_dir, filename)
        
        if os.path.exists(file_path):
            # 使用 send_file 返回
            try:
                return send_file(file_path, as_attachment=True)
            except Exception as e:
                print(f"下载文件时出错: {e}")
                return jsonify({'error': '下载失败'}), 500
        else:
            return jsonify({'error': '文件不存在'}), 404
    
    return app
