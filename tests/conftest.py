import pytest
import os
import sys
from peewee import SqliteDatabase
from webtest import TestApp

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, set_db, init_db, User, Client, Site, MaintenanceLog, Notice, LogTemplate, AppSetting, Request
from auth import hash_password
from index import app, set_apps_catchall

@pytest.fixture(scope='session', autouse=True)
def disable_readonly_mode():
    import settings
    original = settings.READ_ONLY_MODE
    settings.READ_ONLY_MODE = False
    yield
    settings.READ_ONLY_MODE = original

@pytest.fixture(scope='session')
def test_db():
    # テスト用の一時データベース
    test_db = SqliteDatabase(':memory:')
    set_db(test_db)
    init_db()
    yield test_db
    test_db.close()

@pytest.fixture(autouse=True)
def clean_db(test_db):
    # 各テスト前にデータをクリア（またはトランザクション）
    # 今回は単純にテーブルのデータを削除
    models = [User, Client, Site, MaintenanceLog, Notice, LogTemplate, AppSetting, Request]
    for model in models:
        model.delete().execute()
    yield

@pytest.fixture
def test_app():
    # Bottleの catchall を False にすると、テスト中に発生した例外のスタックトレースが見やすくなる
    set_apps_catchall(False)
    return TestApp(app)

@pytest.fixture
def admin_user(test_db):
    return User.create(
        email='admin@test.com',
        password_hash=hash_password('password'),
        role='admin'
    )

@pytest.fixture
def client_factory(test_db):
    def _create_client(name="Test Client"):
        return Client.create(name=name, display_name=name)
    return _create_client

@pytest.fixture
def client_user_factory(test_db):
    def _create_client_user(email, client, password='password'):
        return User.create(
            email=email,
            password_hash=hash_password(password),
            role='client',
            client=client
        )
    return _create_client_user

class AuthClient:
    def __init__(self, test_app):
        self.app = test_app
        self.csrf_token = None

    def login(self, email, password='password'):
        # ログインページからCSRFトークンを取得
        res = self.app.get('/login')
        form = res.forms[0]
        form['email'] = email
        form['password'] = password
        res = form.submit()
        # ログイン後のトークン更新
        res2 = self.app.get('/')
        try:
            self.csrf_token = res2.html.find('input', {'name': 'csrf_token'})['value']
        except:
            self.csrf_token = None
        return res

    def get_with_csrf(self, url, **kwargs):
        url = url.replace('//', '/')
        res = self.app.get(url, **kwargs)
        # フォームがある場合はCSRFトークンを更新
        try:
            csrf_input = res.html.find('input', {'name': 'csrf_token'})
            if csrf_input:
                self.csrf_token = csrf_input['value']
        except:
            pass
        return res

    def post_with_csrf(self, url, params=None, **kwargs):
        url = url.replace('//', '/')
        
        # GET /admin/log_templates/1/delete は許可されていないので、
        # 直接POSTする
        if url.endswith('/delete') or url.endswith('/settings'):
            # 削除や設定保存の場合は直接POST（フォーム取得をスキップ）
            # ただし、トークンを確実に持っている必要があるため、親ページを一度GETしておく
            parent_url = url.rsplit('/', 1)[0]
            if url.endswith('/settings'): parent_url = url
            self.get_with_csrf(parent_url)
            
            if params is None: params = {}
            if isinstance(params, dict): params = params.copy()
            if self.csrf_token: params['csrf_token'] = self.csrf_token
            return self.app.post(url, params, **kwargs)

        # まず対象URLにGETしてフォームを取得する
        res_get = self.app.get(url)
        if res_get.forms:
            form = res_get.forms[0]
            if params:
                for k, v in params.items():
                    try:
                        form[k] = v
                    except:
                        # フォームにないフィールドは無視（または動的に追加）
                        pass
            # action が空（現在のURLへのPOST）の場合は、明示的にURLを指定する
            action = form.action or url
            # actionが相対パスの場合は結合、絶対パス（スラッシュ開始）の場合はそのまま、
            # ただし mount の影響で // になるのを防ぐ
            if not action.startswith('/') and not action.startswith('http'):
                # 簡易的な結合
                action = url.rsplit('/', 1)[0] + '/' + action
            
            action = action.replace('//', '/')
            # form.submit() に action 引数はないので、form.action を直接書き換える
            form.action = action
            res = form.submit()
        else:
            # フォームがない場合は直接POST（ただしトークンを手動付与）
            if params is None: params = {}
            if isinstance(params, dict): params = params.copy()
            if self.csrf_token: params['csrf_token'] = self.csrf_token
            res = self.app.post(url, params, **kwargs)
        
        # レスポンスに新しいフォームがあればトークン更新
        try:
            if hasattr(res, 'html') and res.html:
                csrf_input = res.html.find('input', {'name': 'csrf_token'})
                if csrf_input:
                    self.csrf_token = csrf_input['value']
        except:
            pass
        return res

@pytest.fixture
def auth_client(test_app):
    return AuthClient(test_app)
