import os
import mimetypes
from flask import Flask, request, Response, send_file, abort, redirect, url_for
from werkzeug.exceptions import NotFound
import urllib.parse

app = Flask(__name__)

# 指定要共享的文件夹路径
SHARE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_storage')
print(f"共享文件夹路径: {SHARE_FOLDER}")

# 确保共享文件夹存在
if not os.path.exists(SHARE_FOLDER):
    os.makedirs(SHARE_FOLDER)


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
        'body { font-family: Arial, sans-serif; margin: 20px; }',
        'ul { list-style-type: none; padding: 0; }',
        'li { margin: 5px 0; }',
        'a { text-decoration: none; color: #0066cc; }',
        'a:hover { text-decoration: underline; }',
        '.dir::before { content: "📁 "; }',
        '.file::before { content: "📄 "; }',
        '</style>',
        '</head>',
        '<body>',
        '<h1>文件列表</h1>'
    ]
    
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
    for file in files:
        encoded_file = urllib.parse.quote(file)
        file_url = f'/files/{urllib.parse.quote(relative_path)}{encoded_file}'
        file_path = os.path.join(directory_path, file)
        file_size = get_file_size(file_path)
        readable_size = human_readable_size(file_size)
        html.append(f'<li><a class="file" href="{file_url}" target="_blank">{file}</a> ({readable_size})</li>')
    
    html.extend([
        '</ul>',
        '</body>',
        '</html>'
    ])
    
    return '\n'.join(html)

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

if __name__ == '__main__':
    # 获取本机IP地址
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print(f"服务器启动中...")
    print(f"本地访问地址: http://localhost:5000")
    print(f"局域网访问地址: http://{local_ip}:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)