# converter.py
# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import threading
import queue
import json
import psutil
import shutil
from utils import get_hwaccel_priority, get_memory_strategy, format_file_size

class VideoConverter:
    def __init__(self, temp_dir):
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.task_queue = queue.Queue()
        self.current_tasks = {}
        self.task_lock = threading.Lock()
        self._start_worker()
    
    def _start_worker(self):
        def worker():
            while True:
                task_id, task_data = self.task_queue.get()
                if task_id is None:
                    break
                try:
                    self._process_task(task_id, task_data)
                except Exception as e:
                    with self.task_lock:
                        self.current_tasks[task_id]['status'] = 'error'
                        self.current_tasks[task_id]['error'] = str(e)
                finally:
                    self.task_queue.task_done()
        
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
    
    def _process_task(self, task_id, task_data):
        input_path = task_data['input_path']
        output_path = task_data['output_path']
        output_format = task_data['format']
        options = task_data['options']
        
        with self.task_lock:
            self.current_tasks[task_id]['status'] = 'processing'
        
        result_path = None
        try:
            if options.get('target_size'):
                result_path = self._target_size_mode(input_path, output_path, output_format, options)
            else:
                result_path = self._convert_direct(input_path, output_path, output_format, options)
        except Exception as e:
            with self.task_lock:
                self.current_tasks[task_id]['status'] = 'error'
                self.current_tasks[task_id]['error'] = str(e)
            return
        
        with self.task_lock:
            self.current_tasks[task_id]['status'] = 'completed'
            self.current_tasks[task_id]['result_path'] = result_path
            if result_path:
                self.current_tasks[task_id]['result_filename'] = os.path.basename(result_path)
            else:
                self.current_tasks[task_id]['result_filename'] = None
    
    def start_conversion(self, input_path, output_format, options):
        """WebUI使用的异步转换接口"""
        # 生成输出文件名（预计）
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_dir = os.path.join(self.temp_dir, 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        expected_filename = f"{base_name}.{output_format}"
        output_path = os.path.join(output_dir, expected_filename)
        
        # 添加到任务队列（add_conversion_task 会记录 expected_filename）
        task_id = self.add_conversion_task(input_path, output_path, output_format, options)
        return task_id

    def _get_ffmpeg_cmd(self, input_path, output_path, output_format, options):
        """
        生成适用于不同输出格式的 ffmpeg 命令（list）。
        注意：不对 scale/fps 做替代，直接通过 vf 处理。
        """
        scale = options.get('scale', 1.0)
        fps = options.get('fps', None)
        quality = options.get('quality', 80) or 80

        # 基础命令
        cmd = ['ffmpeg', '-hide_banner', '-y', '-nostdin', '-i', input_path]

        # 线程数根据内存策略调整
        memory_strategy = get_memory_strategy()
        if memory_strategy == 'low':
            threads = '2'
        elif memory_strategy == 'medium':
            threads = '4'
        else:
            threads = '0'
        # set threads later with -threads

        # 构建 vf（filter）部分
        vf_parts = []
        if fps:
            vf_parts.append(f'fps={fps}')
        if scale and scale != 1.0:
            vf_parts.append(f'scale=iw*{scale}:ih*{scale}:flags=lanczos')

        # Format/pix_fmt and codec specific handling
        if output_format == 'gif':
            # 使用 palettegen/paletteuse 流程
            palette_path = os.path.join(self.temp_dir, f'palette_{os.path.basename(input_path)}.png')
            # palette generation command
            palette_cmd = [
                'ffmpeg', '-hide_banner', '-y', '-nostdin', '-i', input_path,
                '-vf', ','.join(([f'fps={fps or 10}'] + ([f'scale=iw*{scale}:ih*{scale}:flags=lanczos'] if scale != 1.0 else [])) + ['palettegen=max_colors=%d' % max(16, min(256, int(quality))) ]),
                palette_path
            ]
            return_cmd = [
                'ffmpeg', '-hide_banner', '-y', '-nostdin', '-i', input_path, '-i', palette_path,
                '-lavfi', f'fps={fps or 10},scale=iw*{scale}:ih*{scale}:flags=lanczos [x]; [x][1:v] paletteuse=dither=sierra2_4a',
                '-loop', '0', output_path
            ]
            # Return a "composite" indicator: we will run palette_cmd first, then return_cmd.
            return {'composite': True, 'palette_cmd': palette_cmd, 'main_cmd': return_cmd, 'palette_path': palette_path}

        elif output_format == 'apng':
            # APNG: 固定 compression_level=6，质量控制通过颜色数 (quantization)
            # 将 quality(1-100) 映射为 max_colors（16..256）
            q = max(1, min(100, int(quality)))
            max_colors = int(16 + (q - 1) * (240 / 99))  # 16..256
            if max_colors < 16:
                max_colors = 16
            vf = ','.join(vf_parts) if vf_parts else None
            cmd = ['ffmpeg', '-hide_banner', '-y', '-nostdin', '-i', input_path]
            if vf:
                cmd += ['-vf', vf + (',format=rgba' if 'format=rgba' not in vf else '')]
            # use pngquant-style by using palettegen/paletteuse as well to reduce colors & size
            palette_path = os.path.join(self.temp_dir, f'apng_palette_{os.path.basename(input_path)}.png')
            palette_cmd = [
                'ffmpeg', '-hide_banner', '-y', '-nostdin', '-i', input_path,
                '-vf', (vf + (',' if vf else '') if vf else '') + f'palettegen=max_colors={max(16,min(256,max_colors))}',
                palette_path
            ]
            main_cmd = [
                'ffmpeg', '-hide_banner', '-y', '-nostdin', '-i', input_path, '-i', palette_path,
                '-lavfi', (f'{vf},format=rgba [x]; [x][1:v] paletteuse=dither=bayer') if vf else f'paletteuse=dither=bayer',
                '-plays', '0', '-f', 'apng', output_path
            ]
            return {'composite': True, 'palette_cmd': palette_cmd, 'main_cmd': main_cmd, 'palette_path': palette_path}

        elif output_format == 'webp':
            # WebP 的质量是：数字越大图像越好，文件越大
            # 用户 UI 需要：滑块越大 → 质量越高
            # 因此这里需要反转映射，使用户体验正确
            user_quality = options.get('quality', 80)

            # 反转质量：用户 0→100 映射为 WebP 100→0
            mapped_quality = 100 - user_quality
            if mapped_quality < 1:
                mapped_quality = 1
            elif mapped_quality > 100:
                mapped_quality = 100

            cmd.extend(['-c:v', 'libwebp'])
            cmd.extend(['-quality', str(mapped_quality)])  # 修正后使用 mapped_quality
            cmd.extend(['-preset', 'default'])
            cmd.extend(['-compression_level', '6'])
            cmd.extend(['-loop', '0'])
            cmd.extend(['-f', 'webp'])
            cmd.append(output_path)


        elif output_format == 'avif':
            # AVIF: use libsvtav1 if available, else libaom-av1
            q = max(1, min(100, int(quality)))
            # Map quality 1..100 -> crf 63..0 (lower CRF = better quality)
            crf = int(max(0, min(63, 63 - (q / 100.0) * 63)))
            vf = ','.join(vf_parts) if vf_parts else None
            cmd = ['ffmpeg', '-hide_banner', '-y', '-nostdin', '-i', input_path]
            if vf:
                # AVIF prefers 10bit
                cmd += ['-vf', vf + (',format=yuv420p10le' if 'format=' not in vf else '')]
            # Choose encoder
            try:
                check_cmd = ['ffmpeg', '-hide_banner', '-encoders']
                result = subprocess.run(check_cmd, capture_output=True, text=True, check=True)
                encs = result.stdout.lower()
                if 'libsvtav1' in encs:
                    cmd += ['-c:v', 'libsvtav1', '-crf', str(crf), '-preset', '6', '-pix_fmt', 'yuv420p10le']
                else:
                    cmd += ['-c:v', 'libaom-av1', '-crf', str(crf), '-cpu-used', '6', '-pix_fmt', 'yuv420p10le']
            except Exception:
                cmd += ['-c:v', 'libaom-av1', '-crf', str(crf), '-cpu-used', '6', '-pix_fmt', 'yuv420p10le']
            cmd += ['-f', 'avif', output_path]
            if threads != '0':
                cmd.insert(1, '-threads')
                cmd.insert(2, threads)
            return cmd

        # Fallback: direct mp4 -> named output (should not generally happen)
        if vf_parts:
            cmd += ['-vf', ','.join(vf_parts)]
        if threads != '0':
            cmd.insert(1, '-threads')
            cmd.insert(2, threads)
        cmd.append(output_path)
        return cmd

    def _get_unique_output_path(self, base_path):
        """生成唯一的输出文件路径"""
        if not os.path.exists(base_path):
            return base_path
        
        directory = os.path.dirname(base_path)
        filename = os.path.basename(base_path)
        name, ext = os.path.splitext(filename)
        
        counter = 1
        while True:
            new_filename = f"{name}-{counter}{ext}"
            new_path = os.path.join(directory, new_filename)
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    def _run_cmd(self, cmd):
        """执行命令（list 或 dict for composite），返回 (returncode, stdout, stderr)"""
        if isinstance(cmd, dict) and cmd.get('composite'):
            # 先运行 palette 命令再主命令
            palette_cmd = cmd['palette_cmd']
            main_cmd = cmd['main_cmd']
            try:
                p1 = subprocess.run(palette_cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                # palette generation 失败，尝试使用简单命令（主命令可能需要 palette）
                return e.returncode, e.stdout, e.stderr
            try:
                p2 = subprocess.run(main_cmd, capture_output=True, text=True, check=True)
                return p2.returncode, p2.stdout, p2.stderr
            except subprocess.CalledProcessError as e:
                return e.returncode, e.stdout, e.stderr
        else:
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return p.returncode, p.stdout, p.stderr
            except subprocess.CalledProcessError as e:
                return e.returncode, e.stdout, e.stderr

    def _convert_direct(self, input_path, output_path, output_format, options):
        # 确保输出路径唯一
        output_path = self._get_unique_output_path(output_path)
        
        cmd = self._get_ffmpeg_cmd(input_path, output_path, output_format, options)
        
        print(f"执行FFmpeg命令: {cmd if not isinstance(cmd, dict) else 'composite command (palette + main)'}")
        print(f"输入文件: {input_path} ({format_file_size(os.path.getsize(input_path))})")
        print(f"输出文件: {output_path}")
        print(f"格式: {output_format}, 缩放: {options.get('scale', 1.0)}, 帧率: {options.get('fps', '自动')}, 质量: {options.get('quality', 80)}")
        
        rc, out, err = self._run_cmd(cmd)
        if rc == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ 转换成功: {output_path} ({format_file_size(file_size)})")
            return output_path
        else:
            # 组装错误信息
            stderr = err or out or ''
            error_msg = f"FFmpeg转换失败 (返回码: {rc}). stderr: {stderr}"
            print(f"✗ {error_msg}")
            raise Exception(error_msg)

    def _target_size_mode(self, input_path, output_path, output_format, options):
        """
        将视频/动图转换到目标文件大小模式。
        搜索绝对最优的 quality 参数，并保留偏差最小的结果。
        """
        import glob

        output_path = self._get_unique_output_path(output_path)
        target_size = options['target_size']
        max_iterations = 12
        precision_threshold = 0.005  # 0.5% 偏差

        # WebP 质量映射
        def map_webp_quality(user_q):
            mapped = 100 - user_q
            return max(1, min(100, mapped))

        # 初始化搜索
        low_q, high_q = 0, 100
        best_path = None
        best_dev = float('inf')
        base_name = os.path.splitext(output_path)[0]
        temp_dir = os.path.dirname(output_path)

        print(f"目标大小模式: {format_file_size(target_size)}")

        for i in range(max_iterations):
            if low_q > high_q:
                break

            mid_q = (low_q + high_q) // 2
            test_options = options.copy()
            if output_format == "webp":
                test_options['quality'] = map_webp_quality(mid_q)
            else:
                test_options['quality'] = mid_q

            test_output = os.path.join(temp_dir, f"{os.path.basename(base_name)}_test_{i}.{output_format}")
            cmd = self._get_ffmpeg_cmd(input_path, test_output, output_format, test_options)

            try:
                subprocess.run(cmd, capture_output=True, check=True)
                size = os.path.getsize(test_output)
            except Exception:
                continue

            dev = abs(size - target_size) / target_size
            print(f"迭代 {i+1}: UI质量 {mid_q} → {format_file_size(size)} (偏差 {dev:.2%})")

            # 更新最佳结果
            if dev < best_dev:
                if best_path and os.path.exists(best_path):
                    os.remove(best_path)
                best_path = test_output
                best_dev = dev

            # 二分搜索调整
            if size > target_size:
                high_q = mid_q - 1
            else:
                low_q = mid_q + 1

            # 精度阈值检查：如果偏差已经足够小且无法进一步改进，退出循环
            if best_dev <= precision_threshold and high_q - low_q <= 1:
                print(f"达到目标精度 {best_dev:.2%}，提前结束")
                break

        # 最终保留最佳结果
        if best_path and best_path != output_path:
            os.rename(best_path, output_path)
            print(f"最终结果: {output_path} ({format_file_size(os.path.getsize(output_path))}, 偏差: {best_dev:.2%})")

        # 清理其他测试文件
        for f in glob.glob(os.path.join(temp_dir, f"{os.path.basename(base_name)}_test_*.{output_format}")):
            if f != output_path:
                os.remove(f)

        return output_path


    def _calculate_quality(self, iteration, max_iterations, base_quality):
        # 备用未使用的方法（保留）
        if iteration == 0:
            return base_quality
        quality_step = max(1, base_quality // (max_iterations * 2))
        if iteration % 2 == 0:
            return min(100, base_quality + (iteration // 2) * quality_step)
        else:
            return max(1, base_quality - (iteration // 2) * quality_step)
    
    def add_conversion_task(self, input_path, output_path, output_format, options):
        # 更可靠的 task id 生成（使用线程id + 自增计数）
        with self.task_lock:
            base_id = threading.current_thread().ident or 0
            counter = len(self.current_tasks) + 1
            task_id = base_id + counter
            # 预期输出文件名（未去重）
            expected_filename = os.path.basename(output_path)
            task_data = {
                'input_path': input_path,
                'output_path': output_path,
                'format': output_format,
                'options': options
            }
            self.current_tasks[task_id] = {
                'status': 'queued',
                'data': task_data,
                'output_filename': expected_filename,
                'result_filename': None,
                'result_path': None,
                'error': None
            }
        
        self.task_queue.put((task_id, task_data))
        return task_id
    
    def get_task_status(self, task_id):
        with self.task_lock:
            info = self.current_tasks.get(task_id)
            if not info:
                return {'status': 'not_found'}
            # 返回可序列化的信息
            return {
                'status': info.get('status'),
                'output_filename': info.get('output_filename'),
                'result_filename': info.get('result_filename'),
                'error': info.get('error')
            }
    
    def convert_video(self, input_path, output_path, output_format, options):
        """同步转换接口（用于无头模式）"""
        if options.get('target_size'):
            return self._target_size_mode(input_path, output_path, output_format, options)
        else:
            return self._convert_direct(input_path, output_path, output_format, options)
