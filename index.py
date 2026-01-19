#!/usr/local/bin/python3

import os
import sys
import urllib.parse
from bottle import Bottle, run, request, redirect, jinja2_view, static_file, abort, TEMPLATE_PATH, jinja2_template
from models import init_db, User, Client, SharedFile, Site, set_db

# テンプレートのパスを追加
TEMPLATE_PATH.insert(0, os.path.join(os.path.dirname(__file__), 'templates'))
from peewee import SqliteDatabase
from auth import verify_password, set_session, get_current_user, generate_csrf_token, hash_password, login_required
from routes_admin import admin_app
from routes_client import client_app
from utils import verify_file_token
import settings

# Proxyを初期化
if not settings.DB_PATH.startswith('test_'): # テスト時は conftest.py で初期化される
    set_db(SqliteDatabase(settings.DB_PATH))

app = Bottle()

# データベース初期化 (モジュール読み込み時には実行せず、明示的に呼び出す)
def init_app_db():
    init_db()

if __name__ == '__main__':
    init_app_db()

# ファイル配信（権限チェック付き）
@app.route('/files/<token>')
@login_required()
def download_file(token):
    file_id = verify_file_token(token)
    if not file_id:
        abort(404, "Invalid or expired token")
    
    try:
        f = SharedFile.get_by_id(file_id)
    except SharedFile.DoesNotExist:
        abort(404, "File not found")
    
    if f.is_deleted:
        abort(404, "File is deleted")
        
    user = get_current_user()
    
    # 権限チェック
    if user.role == 'admin':
        # 管理者は全アクセス可（ただし削除済みはURL直接でも上記で弾いている）
        pass
    else:
        # クライアントの場合
        if not f.client_visible:
            abort(403, "Access denied")
        # サイト所属チェック
        if f.site and f.site.client.id != user.client.id:
            abort(403, "Access denied")
        # 依頼所属チェック (Request実装時用)
        if f.request and f.request.client.id != user.client.id:
            abort(403, "Access denied")

    return static_file(f.stored_path, root=settings.UPLOAD_DIR, download=f.original_filename)

# 初期管理者作成
def create_default_admin():
    if User.select().where(User.role == 'admin').count() == 0:
        User.create(
            email=settings.DEFAULT_ADMIN_EMAIL,
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            role='admin'
        )

if __name__ == '__main__':
    create_default_admin()

@app.route('/login', method=['GET', 'POST'])
@jinja2_view('login.html')
def login():
    from auth import check_csrf_token
    user = get_current_user()
    if user:
        if user.role == 'admin': redirect('/admin')
        else: redirect('/client')

    error = None
    if request.method == 'POST':
        # CGI環境でのデバッグ用ログ出力
        if settings.IS_CGI:
            print(f"DEBUG: login POST - path: {request.path}, script_name: {request.environ.get('SCRIPT_NAME')}", file=sys.stderr)

        # CSRFチェックの追加
        try:
            check_csrf_token()
        except Exception as e:
            if settings.IS_CGI:
                print(f"DEBUG: CSRF failure: {str(e)}", file=sys.stderr)
            abort(403, str(e))

        email = request.forms.decode().get('email')
        password = request.forms.decode().get('password')
        try:
            user = User.get(User.email == email, User.is_active == True)
            if not verify_password(password, user.password_hash):
                user = None
                error = "ログインに失敗しました。"
        except User.DoesNotExist:
            user = None
            error = "ログインに失敗しました。"
        
        # エラーメッセージをエンコード（テンプレート側で直接表示されるが、一応安全のため）
        # ただしこの error はリダイレクトせずに render されるので文字化けの問題は起きにくいはず

        if user:
            if settings.IS_CGI:
                print(f"DEBUG: login success - user: {user.email}", file=sys.stderr)
            set_session({'user_id': user.id})
            if user.role == 'admin': redirect('/admin')
            else: redirect('/client')
    
    if settings.IS_CGI:
        print(f"DEBUG: rendering login page - cookie: {request.get_cookie('session')}", file=sys.stderr)
    return {
        'error': error, 
        'csrf_token': generate_csrf_token(), 
        'current_user': None,
        'read_only_mode': getattr(settings, 'READ_ONLY_MODE', False)
    }

@app.route('/logout')
def logout():
    set_session({})
    redirect('/login')

@app.route('/')
def index():
    user = get_current_user()
    if not user:
        redirect('/login')
    if user.role == 'admin':
        redirect('/admin')
    else:
        redirect('/client')

@app.route('/api/version')
def api_version():
    return {
        "version": "1.5",
        "system": "MaintainView-OSS",
        "status": "OK"
    }

# アプリケーションのマウント
app.mount('/admin', admin_app)
app.mount('/client', client_app)

@app.error(403)
@admin_app.error(403)
@client_app.error(403)
def error403(error):
    from utils import get_display_labels, get_app_settings
    return jinja2_template('error_403.html', {
        'current_user': get_current_user(),
        'read_only_mode': getattr(settings, 'READ_ONLY_MODE', False),
        'error_message': error.body,
        'labels': get_display_labels(),
        'app_settings': get_app_settings(),
        'csrf_token': generate_csrf_token()
    })

# マウント後に各アプリの catchall も設定（テスト用）
def set_apps_catchall(value):
    app.catchall = value
    admin_app.catchall = value
    client_app.catchall = value

if __name__ == '__main__':
    if settings.IS_CGI:
        run(app, server='cgi')
    else:
        run(app, host='localhost', port=8080, debug=settings.DEBUG, reloader=True)
