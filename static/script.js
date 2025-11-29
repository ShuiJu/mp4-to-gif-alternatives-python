// static/script.js
let currentFileName = null;
let activeTasks = new Map();

// 通知系统
class NotificationSystem {
    constructor() {
        this.container = document.getElementById('notificationsContainer');
        this.maxNotifications = 50; // 保留最多50条通知
    }

    addNotification(message, type = 'info') {
        const time = new Date().toLocaleTimeString();
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="time">${time}</div>
            <div class="message">${message}</div>
        `;

        // 移除空状态提示
        const emptyNote = this.container.querySelector('.notification.empty');
        if (emptyNote) {
            emptyNote.remove();
        }

        // 添加新通知到顶部
        this.container.insertBefore(notification, this.container.firstChild);

        // 限制通知数量
        const notifications = this.container.querySelectorAll('.notification:not(.empty)');
        if (notifications.length > this.maxNotifications) {
            notifications[notifications.length - 1].remove();
        }

        // 自动滚动到顶部
        this.container.scrollTop = 0;
    }
}

const notifications = new NotificationSystem();

// 拖放功能
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const conversionSettings = document.getElementById('conversionSettings');
const formatSelect = document.getElementById('formatSelect');

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

function handleFileSelect(file) {
    if (!file.type.match('video.*')) {
        notifications.addNotification('请选择视频文件！', 'error');
        return;
    }
    
    // 更新文件输入元素
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;
    
    currentFileName = file.name;
    uploadArea.style.display = 'none';
    conversionSettings.style.display = 'block';
    
    notifications.addNotification(`已选择文件: ${file.name}`, 'success');
    console.log('文件已选择:', file.name, '大小:', formatFileSize(file.size));
    
    // 根据格式更新UI
    updateQualitySettings();
}

function resetFileSelection() {
    fileInput.value = '';
    currentFileName = null;
    uploadArea.style.display = 'block';
    conversionSettings.style.display = 'none';
    notifications.addNotification('已重置文件选择', 'info');
}

// 根据输出格式更新质量设置（不再隐藏 GIF 的质量）
function updateQualitySettings() {
    const format = formatSelect.value;
    const qualityGroup = document.getElementById('qualityGroup');

    // 全部格式都显示 quality（后端会对不同格式做映射）
    qualityGroup.style.display = 'block';
    // 可根据格式调整 quality 的文本说明（可扩展）
    const qualityValue = document.getElementById('qualityValue');
    const qualitySlider = document.getElementById('qualitySlider');
    if (format === 'apng') {
        // APNG 用 quality 映射到颜色数量，UI 不必改变滑块范围
        qualityValue.textContent = qualitySlider.value;
    } else {
        qualityValue.textContent = qualitySlider.value;
    }
}

formatSelect.addEventListener('change', updateQualitySettings);

// 设置面板交互
const scaleSlider = document.getElementById('scaleSlider');
const scaleValue = document.getElementById('scaleValue');
const qualitySlider = document.getElementById('qualitySlider');
const qualityValue = document.getElementById('qualityValue');
const targetSizeCheckbox = document.getElementById('targetSizeCheckbox');
const targetSizeInput = document.getElementById('targetSizeInput');
const targetSizeUnit = document.getElementById('targetSizeUnit');

scaleSlider.addEventListener('input', () => {
    scaleValue.textContent = scaleSlider.value + '%';
});

qualitySlider.addEventListener('input', () => {
    qualityValue.textContent = qualitySlider.value;
});

targetSizeCheckbox.addEventListener('change', () => {
    const enabled = targetSizeCheckbox.checked;
    targetSizeInput.disabled = !enabled;
    targetSizeUnit.disabled = !enabled;
});

// 文件大小格式化函数
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 开始转换
async function startConversion() {
    if (!fileInput.files.length) {
        notifications.addNotification('请先选择文件！', 'error');
        return;
    }

    const format = document.getElementById('formatSelect').value;
    const scale = parseInt(document.getElementById('scaleSlider').value) / 100;
    const fps = document.getElementById('fpsInput').value || '';
    const quality = document.getElementById('qualitySlider').value;
    
    // 构建选项
    const options = {
        scale: scale,
        fps: fps ? parseInt(fps) : null,
        quality: quality ? parseInt(quality) : null
    };
    
    if (targetSizeCheckbox.checked) {
        const size = parseInt(targetSizeInput.value) * parseInt(targetSizeUnit.value);
        options.target_size = size;
    }

    const taskInfo = {
        fileName: currentFileName,
        format: format,
        options: options,
        startTime: new Date(),
        lastStatus: null,
        expectedFilename: null
    };

    notifications.addNotification(`开始转换: ${currentFileName} → ${format.toUpperCase()}`, 'info');

    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('format', format);
        formData.append('scale', options.scale);
        formData.append('fps', options.fps || '');
        formData.append('quality', options.quality || '');
        
        if (options.target_size) {
            formData.append('target_size', options.target_size);
        }

        const response = await fetch('/api/convert', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        
        if (response.ok) {
            const taskId = result.task_id;
            // 如果后端返回预期文件名，保存以便生成下载链接
            if (result.expected_filename) {
                taskInfo.expectedFilename = result.expected_filename;
            } else {
                taskInfo.expectedFilename = `${currentFileName.split('.')[0]}.${format}`;
            }

            activeTasks.set(taskId, taskInfo);
            notifications.addNotification(`任务已开始 (ID: ${taskId})`, 'success');
            checkTaskProgress(taskId);
        } else {
            notifications.addNotification('转换失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        notifications.addNotification('请求失败: ' + error.message, 'error');
    }
}

// 检查任务进度（仅在状态变化时通知）
async function checkTaskProgress(taskId) {
    if (!activeTasks.has(taskId)) return;

    try {
        const response = await fetch(`/api/status/${taskId}`);
        const status = await response.json();

        const taskInfo = activeTasks.get(taskId);
        if (!taskInfo) return;

        // 仅当状态变化时才生成通知
        if (taskInfo.lastStatus === status.status) {
            // 继续轮询
            setTimeout(() => checkTaskProgress(taskId), 1000);
            return;
        }
        taskInfo.lastStatus = status.status;

        switch (status.status) {
            case 'queued':
                notifications.addNotification(`任务排队中: ${taskInfo.fileName}`, 'info');
                break;
            case 'processing':
                notifications.addNotification(`正在转换: ${taskInfo.fileName}`, 'info');
                break;
            case 'completed':
                notifications.addNotification(`转换完成: ${taskInfo.fileName} → ${taskInfo.format.toUpperCase()}`, 'success');
                
                // 使用后端返回的 result_filename 优先
                const resultFilename = status.result_filename || taskInfo.expectedFilename || `${taskInfo.fileName.split('.')[0]}.${taskInfo.format}`;
                const downloadUrl = `/api/download/${encodeURIComponent(resultFilename)}`;
                notifications.addNotification(
                    `<a href="${downloadUrl}" download>点击下载 ${taskInfo.format.toUpperCase()} 文件</a>`,
                    'success'
                );
                
                activeTasks.delete(taskId);
                return;
            case 'error':
                notifications.addNotification(`转换错误: ${status.error || '未知错误'}`, 'error');
                activeTasks.delete(taskId);
                return;
            default:
                notifications.addNotification(`未知状态: ${status.status}`, 'warning');
        }

        // 继续轮询
        setTimeout(() => checkTaskProgress(taskId), 1000);
    } catch (error) {
        console.error('检查进度失败:', error);
        setTimeout(() => checkTaskProgress(taskId), 2000);
    }
}

// 初始化
updateQualitySettings();
