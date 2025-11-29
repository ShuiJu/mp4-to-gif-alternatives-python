# build_simple.py
import os
import subprocess
import sys
import shutil

def build_simple():
    # 清理之前的构建
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # 使用最简单的构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=VideoConverter',
        '--onedir',
        '--console',
        '--add-data=templates;templates',
        '--add-data=static;static',
        '--clean',
        'main.py'
    ]
    
    print(f"运行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("编译成功！可执行文件在 dist/VideoConverter/VideoConverter.exe")
        
        # 手动复制必要的Python文件到构建目录
        dist_dir = 'dist/VideoConverter'
        for py_file in ['webui.py', 'converter.py', 'utils.py']:
            if os.path.exists(py_file):
                shutil.copy2(py_file, dist_dir)
                print(f"已复制: {py_file} -> {dist_dir}")
        
        # 测试运行
        print("测试运行可执行文件...")
        test_result = subprocess.run(
            [os.path.join(dist_dir, 'VideoConverter.exe'), '--help'], 
            capture_output=True, text=True, timeout=15
        )
        if test_result.returncode == 0:
            print("可执行文件测试成功！")
            print(f"输出: {test_result.stdout}")
        else:
            print(f"测试失败，返回码: {test_result.returncode}")
            print(f"错误输出: {test_result.stderr}")
            
    except subprocess.CalledProcessError as e:
        print(f"编译失败: {e}")
        print(f"错误详情: {e.stderr}")
    except subprocess.TimeoutExpired:
        print("测试超时，但可执行文件可能已启动")
    except Exception as e:
        print(f"其他错误: {e}")

if __name__ == '__main__':
    build_simple()
