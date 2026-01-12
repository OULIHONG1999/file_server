import os
import mimetypes
from flask import Flask, request, Response, send_file, abort, redirect, url_for, flash
from werkzeug.exceptions import NotFound
import urllib.parse
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # 添加密钥用于flash消息

# 指定要共享的文件夹路径
SHARE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_storage')
print(f"共享文件夹路径: {SHARE_FOLDER}")

# 确保共享文件夹存在
if not os.path.exists(SHARE_FOLDER):
    os.makedirs(SHARE_FOLDER)

# 允许的文件扩展名（如果需要限制上传文件类型）
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar', 'doc', 'docx', 'avi'}


def get_file_size(file_path):
    """获取文件大小"""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0

def human_readable_size(size_bytes):
    """将字节大小转换为人类可读格式"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def allowed_file(filename):
    """检查文件扩展名是否被允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_directory_listing(directory_path, relative_path):
    """生成目录列表页面"""
    # 获取目录中的所有项目
    try:
        items = os.listdir(directory_path)
    except PermissionError:
        abort(403)
        return
    
    # 分离文件和文件夹
    directories = []
    files = []
    
    for item in items:
        item_path = os.path.join(directory_path, item)
        if os.path.isdir(item_path):
            directories.append(item)
        else:
            files.append(item)
    
    # 排序
    directories.sort()
    files.sort()
    
    # 构造HTML页面
    html = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>文件列表</title>',
        '<style>',
        'body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }',
        'h1 { color: #333; }',
        'ul { list-style-type: none; padding: 0; }',
        'li { margin: 8px 0; padding: 10px; background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
        'a { text-decoration: none; color: #0066cc; margin-right: 10px; }',
        'a:hover { text-decoration: underline; }',
        '.dir::before { content: "📁 "; }',
        '.file::before { content: "📄 "; }',
        '.size { color: #666; font-size: 0.9em; margin-left: 10px; }',
        '.actions { float: right; }',
        '.btn { padding: 5px 10px; margin-left: 5px; border: none; border-radius: 3px; cursor: pointer; font-size: 0.8em; }',
        '.btn-delete { background-color: #ff4444; color: white; }',
        '.btn-rename { background-color: #ff9800; color: white; }',
        '.btn-upload { background-color: #4CAF50; color: white; padding: 10px 15px; margin-bottom: 20px; }',
        '.upload-form { margin-bottom: 20px; padding: 15px; background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
        '.rename-form { display: inline; }',
        '.flash-message { padding: 10px; margin: 10px 0; border-radius: 5px; }',
        '.flash-success { background-color: #d4edda; color: #155724; }',
        '.flash-error { background-color: #f8d7da; color: #721c24; }',
        '</style>',
        '</head>',
        '<body>',
        '<h1>文件管理系统</h1>'
    ]
    
    # 添加消息闪现区域
    html.append('{% with messages = get_flashed_messages(with_categories=true) %}')
    html.append('  {% if messages %}')
    html.append('    {% for category, message in messages %}')
    html.append('      <div class="flash-message flash-{{ category }}">{{ message }}</div>')
    html.append('    {% endfor %}')
    html.append('  {% endif %}')
    html.append('{% endwith %}')
    
    # 添加上传文件表单
    if relative_path == '':
        upload_url = '/files/upload'
    else:
        upload_url = f'/files/{urllib.parse.quote(relative_path)}upload'
    html.append(f'<div class="upload-form">')
    html.append(f'<form method="post" action="{upload_url}" enctype="multipart/form-data">')
    html.append(f'    <input type="file" name="file" multiple>')
    html.append(f'    <button type="submit" class="btn btn-upload">上传文件</button>')
    html.append(f'</form>')
    html.append(f'</div>')
    
    # 添加返回上级目录链接（如果不是根目录）
    if relative_path != '':
        parent_path = os.path.dirname(relative_path.rstrip('/'))
        if parent_path == '':
            parent_url = '/'
        else:
            parent_url = f'/files/{urllib.parse.quote(parent_path)}/'
        html.append(f'<p><a href="{parent_url}">📁 ..</a></p>')
    
    html.append('<ul>')
    
    # 列出目录
    for directory in directories:
        encoded_dir = urllib.parse.quote(directory)
        dir_url = f'/files/{urllib.parse.quote(relative_path)}{encoded_dir}/'
        html.append(f'<li><a class="dir" href="{dir_url}">{directory}/</a></li>')
    
    # 列出文件
    for i, file in enumerate(files):
        encoded_file = urllib.parse.quote(file)
        file_url = f'/files/{urllib.parse.quote(relative_path)}{"/" if relative_path else ""}{encoded_file}'
        file_path = os.path.join(directory_path, file)
        file_size = get_file_size(file_path)
        readable_size = human_readable_size(file_size)
        
        # 删除表单
        delete_url = f'/files/{urllib.parse.quote(relative_path)}{"/" if relative_path else ""}{encoded_file}/delete'
        
        # 重命名表单
        rename_url = f'/files/{urllib.parse.quote(relative_path)}{"/" if relative_path else ""}{encoded_file}/rename'
        
        # 使用索引作为ID的一部分，避免文件名特殊字符问题
        rename_form_id = f'rename-form-{i}'
        
        html.append(f'<li>')
        html.append(f'    <a class="file" href="{file_url}" target="_blank">{file}</a><span class="size">({readable_size})</span>')
        html.append(f'    <div class="actions">')
        html.append(f'        <form method="post" action="{delete_url}" style="display: inline;">')
        html.append(f'            <button type="submit" class="btn btn-delete" onclick="return confirm(\'确定要删除文件 {file} 吗？\')">删除</button>')
        html.append(f'        </form>')
        html.append(f'        <button class="btn btn-rename" onclick="showRenameForm(\'{rename_form_id}\')">重命名</button>')
        html.append(f'        <form method="post" action="{rename_url}" class="rename-form" id="{rename_form_id}" style="display: none;">')
        html.append(f'            <input type="text" name="new_name" value="{file}" style="width: 200px; padding: 5px; margin-right: 5px;">')
        html.append(f'            <button type="submit" class="btn btn-rename">确认</button>')
        html.append(f'            <button type="button" class="btn" onclick="hideRenameForm(\'{rename_form_id}\')">取消</button>')
        html.append(f'        </form>')
        html.append(f'    </div>')
        html.append(f'</li>')
    
    html.extend([
        '</ul>',
        '<script>',
        'function showRenameForm(formId) {',
        '    document.getElementById(formId).style.display = "inline";',
        '}',
        'function hideRenameForm(formId) {',
        '    document.getElementById(formId).style.display = "none";',
        '}',
        '</script>',
        '</body>',
        '</html>'
    ])
    
    # 使用Flask的render_template_string来渲染模板，支持flash消息
    from flask import render_template_string
    return render_template_string('\n'.join(html))

@app.route('/')
def index():
    """根路径重定向到文件列表"""
    return redirect(url_for('list_files'))



@app.route('/files/')
@app.route('/files/<path:filepath>')
def list_files(filepath=''):
    """列出文件或提供文件下载"""
    # 构造实际文件系统路径
    safe_filepath = filepath.lstrip('/')
    full_path = os.path.join(SHARE_FOLDER, safe_filepath)
    
    # 防止目录遍历攻击
    if not os.path.abspath(full_path).startswith(os.path.abspath(SHARE_FOLDER)):
        abort(403)
    
    # 检查路径是否存在
    if not os.path.exists(full_path):
        abort(404)
    
    # 如果是目录，则显示目录列表
    if os.path.isdir(full_path):
        return generate_directory_listing(full_path, filepath)
    
    # 如果是文件，则提供下载
    if os.path.isfile(full_path):
        # 获取文件大小
        file_size = get_file_size(full_path)
        
        # 处理范围请求
        range_header = request.headers.get('Range', None)
        if range_header:
            # 解析范围请求
            byte_range = range_header.replace('bytes=', '').split('-')
            start = int(byte_range[0]) if byte_range[0] else 0
            end = int(byte_range[1]) if byte_range[1] else file_size - 1
            
            # 限制结束位置不超过文件大小
            end = min(end, file_size - 1)
            
            # 计算长度
            length = end - start + 1
            
            # 打开文件并定位到起始位置
            def generate():
                with open(full_path, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk_size = min(4096, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        yield data
                        remaining -= len(data)
            
            # 创建范围响应
            response = Response(
                generate(),
                206,  # Partial Content
                mimetype=mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
            )
            
            # 设置响应头
            response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
            response.headers.add('Accept-Ranges', 'bytes')
            response.headers.add('Content-Length', str(length))
            
            return response
        else:
            # 处理普通下载请求
            def generate():
                with open(full_path, 'rb') as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        yield chunk
            
            # 获取文件MIME类型
            mime_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
            
            # 创建响应
            response = Response(
                generate(),
                200,
                mimetype=mime_type
            )
            
            # 设置响应头
            filename = os.path.basename(full_path)
            response.headers.add('Content-Length', str(file_size))
            response.headers.add('Accept-Ranges', 'bytes')
            response.headers.add('Content-Disposition', f'inline; filename="{filename}"')
            
            return response

@app.route('/files/upload', methods=['POST'])
@app.route('/files/<path:filepath>/upload', methods=['POST'])
def upload_file(filepath=''):
    """上传文件"""
    # 构造实际目录路径
    safe_filepath = filepath.lstrip('/')
    upload_dir = os.path.join(SHARE_FOLDER, safe_filepath)
    
    # 防止目录遍历攻击
    if not os.path.abspath(upload_dir).startswith(os.path.abspath(SHARE_FOLDER)):
        abort(403)
    
    # 检查目录是否存在
    if not os.path.exists(upload_dir) or not os.path.isdir(upload_dir):
        abort(404)
    
    # 检查是否有文件被上传
    if 'file' not in request.files:
        flash('没有选择文件', 'error')
        return redirect(request.referrer)
    
    files = request.files.getlist('file')
    
    for file in files:
        if file.filename == '':
            continue
        
        # 保留原始文件名的扩展名
        original_filename = file.filename
        filename, ext = os.path.splitext(original_filename)
        ext = ext.lower()  # 统一扩展名大小写
        
        # 使用自定义逻辑保留中文和安全字符，不依赖secure_filename过滤中文
        import re
        # 只保留字母、数字、下划线、中文和常见的文件名符号（如空格、点、括号等）
        # 过滤掉绝对不安全的字符，如斜杠、反斜杠、冒号、星号、问号、引号、尖括号、竖线
        safe_filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        if not safe_filename:
            # 如果过滤后文件名为空，使用时间戳
            import time
            safe_filename = f"file_{int(time.time())}"
        final_filename = f"{safe_filename}{ext}"
        
        # 保存文件
        file_path = os.path.join(upload_dir, final_filename)
        file.save(file_path)
        flash(f'文件 "{final_filename}" 上传成功', 'success')
    
    return redirect(request.referrer)

@app.route('/files/<path:filepath>/delete', methods=['POST'])
def delete_file(filepath):
    """删除文件"""
    # 构造实际文件路径
    safe_filepath = filepath.lstrip('/')
    file_path = os.path.join(SHARE_FOLDER, safe_filepath)
    
    # 防止目录遍历攻击
    if not os.path.abspath(file_path).startswith(os.path.abspath(SHARE_FOLDER)):
        abort(403)
    
    # 检查文件是否存在
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        abort(404)
    
    # 删除文件
    try:
        os.remove(file_path)
        flash(f'文件 "{os.path.basename(file_path)}" 删除成功', 'success')
    except Exception as e:
        flash(f'删除文件失败: {str(e)}', 'error')
    
    # 重定向回上一页
    return redirect(request.referrer)

@app.route('/files/<path:filepath>/rename', methods=['POST'])
def rename_file(filepath):
    """重命名文件"""
    # 构造实际文件路径
    safe_filepath = filepath.lstrip('/')
    file_path = os.path.join(SHARE_FOLDER, safe_filepath)
    
    # 防止目录遍历攻击
    if not os.path.abspath(file_path).startswith(os.path.abspath(SHARE_FOLDER)):
        abort(403)
    
    # 检查文件是否存在
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        abort(404)
    
    # 获取新文件名
    new_name = request.form.get('new_name')
    if not new_name:
        flash('新文件名不能为空', 'error')
        return redirect(request.referrer)
    
    # 确保文件名安全
    new_name = secure_filename(new_name)
    if new_name == '':
        flash('新文件名无效', 'error')
        return redirect(request.referrer)
    
    # 构造新文件路径
    new_file_path = os.path.join(os.path.dirname(file_path), new_name)
    
    # 检查新文件名是否已存在
    if os.path.exists(new_file_path):
        flash('文件已存在', 'error')
        return redirect(request.referrer)
    
    # 重命名文件
    try:
        os.rename(file_path, new_file_path)
        flash(f'文件已重命名为 "{new_name}"', 'success')
    except Exception as e:
        flash(f'重命名文件失败: {str(e)}', 'error')
    
    # 重定向回上一页
    return redirect(request.referrer)

if __name__ == '__main__':
    # 获取本机IP地址
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print(f"服务器启动中...")
    print(f"本地访问地址: http://localhost:12345")
    print(f"局域网访问地址: http://{local_ip}:12345")
    
    app.run(host='0.0.0.0', port=12345, debug=True)