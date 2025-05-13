from flask import Flask, request, send_from_directory, abort, Response
import os
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)

# Konfigurasi
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'mp4', 'mp3'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
CREDENTIALS = {'username': 'febryensz', 'password': 'rahasia123'}  # Ganti sesuai kebutuhan
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Pastikan folder upload ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# HTML Template
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Temp File by FebryEnsz</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .error { color: red; }
        .success { color: green; }
        code { background: #f4f4f4; padding: 2px 4px; }
    </style>
</head>
<body>
    <h1>Temp File Hosting</h1>
    <p>Upload file (max 100MB)</p>
    {% if error %}
        <p class="error">{{ error }}</p>
    {% endif %}
    {% if success %}
        <p class="success">{{ success }}</p>
    {% endif %}
    <form method="post" enctype="multipart/form-data" action="/">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <input type="file" name="file">
        <input type="submit" value="Upload">
    </form>
    <h2>Uploaded Files</h2>
    <ul>
        {% for file in files %}
        <li><a href="/static/uploads/{{ file }}">{{ file }}</a></li>
        {% endfor %}
    </ul>
    <p>Upload via curl: <code>curl -u username:password -F "file=@/path/to/file" {{ request.host_url }}</code></p>
    <p>Download via wget: <code>wget {{ request.host_url }}static/uploads/filename</code></p>
</body>
</html>
"""

# Fungsi untuk memeriksa ekstensi file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Fungsi untuk mendapatkan nama file unik
def get_unique_filename(filename):
    base, ext = os.path.splitext(filename)
    counter = 2
    new_filename = filename
    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)):
        new_filename = f"{base}-{counter}{ext}"
        counter += 1
    return new_filename

# Dekorator untuk autentikasi
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        form_username = request.form.get('username')
        form_password = request.form.get('password')
        
        # Cek autentikasi dari curl (HTTP Basic Auth) atau form
        if auth and auth.username == CREDENTIALS['username'] and auth.password == CREDENTIALS['password']:
            return f(*args, **kwargs)
        elif form_username == CREDENTIALS['username'] and form_password == CREDENTIALS['password']:
            return f(*args, **kwargs)
        else:
            return Response(
                'Unauthorized', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
    return decorated

# Route utama (handle upload dan tampilan)
@app.route('/', methods=['GET', 'POST'])
@require_auth
def index():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    error = None
    success = None

    if request.method == 'POST':
        if 'file' not in request.files:
            error = 'No file part'
        else:
            file = request.files['file']
            if file.filename == '':
                error = 'No selected file'
            elif file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Dapatkan nama file unik
                unique_filename = get_unique_filename(filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                file_url = f"{request.host_url}static/uploads/{unique_filename}"
                success = f'File uploaded: <a href="{file_url}">{unique_filename}</a>'
            else:
                error = 'File type not allowed'

    # Render template secara manual
    from jinja2 import Template
    template = Template(INDEX_HTML)
    return template.render(
        files=files,
        error=error,
        success=success,
        request=request
    )

# Download file
@app.route('/static/uploads/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    abort(404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
