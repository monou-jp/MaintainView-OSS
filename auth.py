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
    session_data = request.get_cookie("session", secret=SECRET_KEY)
    if session_data:
        return session_data
    return {}

def set_session(data):
    response.set_cookie("session", data, secret=SECRET_KEY, path='/', httponly=True)

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
    if not token or token != session.get('csrf_token'):
        from bottle import abort
        abort(403, "CSRF token missing or invalid.")
