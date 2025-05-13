from flask import Flask, request, send_from_directory, abort, Response, render_template_string
import os
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)

# Konfigurasi
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'mp4', 'mp3'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
CREDENTIALS = {'username': 'febryensz', 'password': 'rahasia123'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Pastikan folder upload ada
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Lebih baik

# HTML Template (disimpan dalam variabel agar mudah)
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Temp File by FebryEnsz</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }
        .container { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1, h2 { color: #333; }
        .error { color: #d9534f; background-color: #f2dede; border: 1px solid #ebccd1; padding: 10px; border-radius: 4px; margin-bottom: 15px;}
        .success { color: #5cb85c; background-color: #dff0d8; border: 1px solid #d6e9c6; padding: 10px; border-radius: 4px; margin-bottom: 15px;}
        code { background: #eee; padding: 2px 4px; border-radius: 4px; }
        input[type="text"], input[type="password"], input[type="file"], input[type="submit"] {
            margin-bottom: 10px;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #ccc;
        }
        input[type="submit"] { background-color: #5cb85c; color: white; cursor: pointer; }
        input[type="submit"]:hover { background-color: #4cae4c; }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 5px; }
        a { color: #0275d8; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Temp File Hosting</h1>
        <p>Upload file (max 100MB)</p>
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        {% if success %}
            <p class="success">{{ success }}</p>
        {% endif %}
        <form method="post" enctype="multipart/form-data" action="/">
            <input type="text" name="username" placeholder="Username" required><br>
            <input type="password" name="password" placeholder="Password" required><br>
            <input type="file" name="file"><br>
            <input type="submit" value="Upload">
        </form>
        <h2>Uploaded Files</h2>
        {% if files %}
        <ul>
            {% for file in files %}
            <li><a href="{{ url_for('download_file', filename=file) }}">{{ file }}</a></li>
            {% endfor %}
        </ul>
        {% else %}
        <p>No files uploaded yet.</p>
        {% endif %}
        <hr>
        <p>Upload via curl: <code>curl -u username:password -F "file=@/path/to/file" {{ request.host_url }}</code></p>
        <p>Download via wget: <code>wget {{ request.host_url.rstrip('/') }}{{ url_for('download_file', filename='your_filename_here') }}</code></p>
        <p><em>Note: On free tier hosting, files might be ephemeral and disappear on service restart/redeploy.</em></p>
    </div>
</body>
</html>
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_unique_filename(filename):
    base, ext = os.path.splitext(filename)
    counter = 1 # Start counter at 1 for consistency if original exists
    new_filename = filename
    # Check if original filename exists
    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)):
        new_filename = f"{base}-{counter}{ext}"
        # Increment counter until a unique name is found
        while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)):
            counter += 1
            new_filename = f"{base}-{counter}{ext}"
    return new_filename

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        form_username = request.form.get('username') if request.method == 'POST' else None
        form_password = request.form.get('password') if request.method == 'POST' else None

        # Check Basic Auth (curl)
        if auth and auth.username == CREDENTIALS['username'] and auth.password == CREDENTIALS['password']:
            return f(*args, **kwargs)
        # Check Form Auth (browser form submission)
        elif form_username == CREDENTIALS['username'] and form_password == CREDENTIALS['password']:
            return f(*args, **kwargs)
        else:
            # For GET requests or failed Basic Auth, prompt for Basic Auth
            if request.method == 'GET' or auth:
                 return Response(
                    'Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})
            # For failed form POST authentication, re-render the page with an error
            # This part is tricky as the decorator would need to re-render.
            # A common pattern is to let the route handler manage form auth failure display.
            # For simplicity here, we'll still send 401, or you can pass a flag.
            # However, if we reach here on POST it means form credentials were wrong.
            # The `index` route itself can show a specific error message if needed.
            # For now, the existing 401 is okay, but a 403 might be more appropriate for "bad form credentials"
            # to avoid the browser's Basic Auth popup on a failed form login.
            # Let's try to make the route handle the form error message for POST.
            # We'll set a flag in `g` or simply let the route re-check for POST.
            # For now, sticking to the original behavior which might show basic auth dialog.
            # A better way for form failure:
            if request.method == 'POST' and (form_username or form_password): # an attempt was made via form
                 # Signal to the route handler that form auth failed
                 request.form_auth_failed = True
                 return f(*args, **kwargs) # Let the route handler deal with it

            return Response(
                'Unauthorized', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
    return decorated

@app.route('/', methods=['GET', 'POST'])
@require_auth
def index():
    error = None
    success = None
    
    # Handle failed form authentication if decorator signaled it
    if request.method == 'POST' and getattr(request, 'form_auth_failed', False):
        error = "Invalid username or password submitted in form."
        # List files even on auth error so page renders correctly
        files = []
        try:
            files = sorted(os.listdir(app.config['UPLOAD_FOLDER']))
        except OSError:
            error = "Error accessing upload directory." # Should not happen if makedirs worked
        return render_template_string(INDEX_HTML, files=files, error=error, success=success, request=request), 401 # or 403

    files = []
    try:
        files = sorted(os.listdir(app.config['UPLOAD_FOLDER']))
    except OSError:
        error = "Error accessing upload directory."

    if request.method == 'POST':
        # Auth has already been checked by the decorator for POST if we reach here without form_auth_failed
        if 'file' not in request.files:
            error = 'No file part'
        else:
            file = request.files['file']
            if file.filename == '':
                error = 'No selected file'
            elif file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = get_unique_filename(filename)
                try:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(file_path)
                    file_url = f"{request.host_url.rstrip('/')}{url_for('download_file', filename=unique_filename)}"
                    success = f'File uploaded: <a href="{file_url}">{unique_filename}</a> (URL: {file_url})'
                    # Reload file list
                    files = sorted(os.listdir(app.config['UPLOAD_FOLDER']))
                except Exception as e:
                    error = f"Error saving file: {e}"
            else:
                error = f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

    return render_template_string(INDEX_HTML, files=files, error=error, success=success, request=request)


@app.route('/static/uploads/<filename>')
def download_file(filename):
    # No auth on download for simplicity, but you could add @require_auth here too if needed.
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path) and os.path.isfile(file_path): # check if it's a file
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    abort(404)

if __name__ == '__main__':
    # For local development:
    # Make sure 'static' folder exists at the same level as your app.py
    # and 'uploads' folder inside 'static'.
    if not os.path.exists('static'):
        os.makedirs('static')
    # UPLOAD_FOLDER is already created above.

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
