import hashlib
import os
import secrets
from itsdangerous import URLSafeSerializer, BadSignature
from bottle import request, response, redirect
from models import User
from settings import SECRET_KEY, READ_ONLY_MODE

serializer = URLSafeSerializer(SECRET_KEY)

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${pwd_hash}"

def verify_password(password, stored_password):
    try:
        salt, pwd_hash = stored_password.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
        return new_hash == pwd_hash
    except ValueError:
        return False

def get_session():
    import settings
    session_data = request.get_cookie("session", secret=settings.SECRET_KEY)
    
    if getattr(settings, 'IS_CGI', False):
        import sys
        print(f"DEBUG: get_session - cookie: {'present' if request.get_cookie('session') else 'absent'}, decoded: {'success' if session_data else 'failed'}", file=sys.stderr)
        
    if session_data:
        return session_data
    return {}

def set_session(data):
    # ロリポップのCGI環境では path='/' だとCookieが正しく送られない、
    # またはサブディレクトリ設置時に問題が起きる場合がある。
    import settings
    # IS_CGI かつ SCRIPT_NAME がある場合は、それをCookieのパスにする
    # (例: /index.cgi/admin へのアクセスなら /index.cgi をパスにする)
    # ただし、ロリポップで .htaccess 等を使って index.cgi を隠している場合は要注意
    script_name = request.environ.get('SCRIPT_NAME', '/')
    
    # SCRIPT_NAMEが空、または / の場合は / を使用
    if not script_name or script_name == '':
        cookie_path = '/'
    else:
        # SCRIPT_NAMEにファイル名（index.cgi）が含まれる場合、
        # ディレクトリパスまでにするか、ファイル名そのものにするか。
        # ロリポップで index.cgi/login のようなURLの場合、SCRIPT_NAMEは /index.cgi になる。
        # この場合、Path=/index.cgi とすれば /index.cgi/login で有効になる。
        cookie_path = script_name

    # 常にパスの末尾がスラッシュで終わらないように調整（ファイル名が含まれる場合があるため）
    if cookie_path.endswith('/') and len(cookie_path) > 1:
        cookie_path = cookie_path[:-1]

    # デバッグ用にパスを出力
    if getattr(settings, 'IS_CGI', False):
        import sys
        print(f"DEBUG: set_cookie path={cookie_path}, SCRIPT_NAME={script_name}, data_keys={list(data.keys())}", file=sys.stderr)

    # 確実に同一のSECRET_KEYを使用するため、グローバルな SECRET_KEY ではなく settings.SECRET_KEY を参照
    # （インポートタイミングによる不一致を防ぐ）
    response.set_cookie("session", data, secret=settings.SECRET_KEY, path=cookie_path, httponly=True)
    # ブラウザによっては、パスの最後が / でないとうまくいかない場合があるため、予備的に / も設定
    if cookie_path != '/':
        response.set_cookie("session", data, secret=settings.SECRET_KEY, path='/', httponly=True)

def get_current_user():
    session = get_session()
    user_id = session.get('user_id')
    if user_id:
        try:
            return User.get_by_id(user_id)
        except User.DoesNotExist:
            return None
    return None

def login_required(role=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user or not user.is_active:
                redirect('/login')
            if role and user.role != role:
                redirect('/login')
            return func(*args, **kwargs)
        return wrapper
    return decorator

def generate_csrf_token():
    session = get_session()
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
        set_session(session)
    return session['csrf_token']

def check_csrf_token():
    import settings
    if getattr(settings, 'READ_ONLY_MODE', False):
        from bottle import abort
        abort(403, "Read-only mode is enabled. Changes are not allowed.")
    
    token = request.forms.decode().get('csrf_token')
    session = get_session()
    
    if getattr(settings, 'IS_CGI', False):
        import sys
        print(f"DEBUG: check_csrf_token - form_token: {token}, session_token: {session.get('csrf_token')}", file=sys.stderr)

    if not token or token != session.get('csrf_token'):
        from bottle import abort
        # デバッグ情報をエラーメッセージに含める（開発・トラブルシューティング時のみ。本番では隠すべきだが現状解決優先）
        msg = "CSRF token missing or invalid."
        if getattr(settings, 'IS_CGI', False):
            msg += f" (form: {token[:8] if token else 'None'}..., session: {session.get('csrf_token')[:8] if session.get('csrf_token') else 'None'}...)"
        abort(403, msg)
