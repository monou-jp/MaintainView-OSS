import pytest
import settings
from models import Client

def test_read_only_mode_blocks_post(auth_client, admin_user):
    """READ_ONLY_MODEが有効なとき、POSTリクエストがブロックされることを確認"""
    # ログインは通常通り行える（セッション作成のため）
    # ただし、セッション作成時にREAD_ONLY_MODEチェックがあるとログインできなくなるので注意が必要。
    # 現在のチェックは check_csrf_token に入っており、ログイン(POST)でも呼ばれる。
    
    # READ_ONLY_MODEを有効にする
    settings.READ_ONLY_MODE = True
    
    try:
        # ログイン試行。check_csrf_tokenでブロックされるはず。
        # ログイン画面のPOSTでも check_csrf_token が呼ばれるか確認が必要。
        # index.py の login ルートを見ると check_csrf_token を呼んでいない。
        # 代わりに auth.set_session を呼んでいる。
        
        # ログイン自体は許可したい場合が多い（デモサイトの閲覧のため）
        # 管理者ログインを試みる
        auth_client.login(admin_user.email, 'password')
        
        # クライアント作成を試みる。これは check_csrf_token を呼ぶのでブロックされるはず。
        auth_client.get_with_csrf('/admin/clients')
        
        # 403が返ることを期待する（webtestのAppErrorを回避するため直接app.postを呼ぶか、期待値を設定する）
        # auth_client.post_with_csrf は内部で form.submit() を呼ぶため、status引数がうまく伝わらない場合がある
        # ここでは直接 app.post を使用して検証する
        params = {
            'name': 'Should Fail',
            'display_name': 'Fail',
            'csrf_token': auth_client.csrf_token
        }
        res = auth_client.app.post('/admin/clients/new', params, status=403)
        
        assert res.status_code == 403
        assert "Read-only mode" in res.body.decode()
        assert "アクセスが拒否されました" in res.body.decode()
        assert "読み取り専用（デモモード）" in res.body.decode()
        assert not Client.filter(name='Should Fail').exists()
        
    finally:
        # 他のテストに影響を与えないよう元に戻す
        settings.READ_ONLY_MODE = False

def test_read_only_mode_blocks_model_save(admin_user):
    """READ_ONLY_MODEが有効なとき、コードからのsave()が例外を投げることを確認"""
    settings.READ_ONLY_MODE = True
    try:
        admin_user.email = "new@example.com"
        with pytest.raises(Exception) as excinfo:
            admin_user.save()
        assert "Database is in read-only mode" in str(excinfo.value)
    finally:
        settings.READ_ONLY_MODE = False

def test_read_only_mode_blocks_model_create():
    """READ_ONLY_MODEが有効なとき、コードからのcreate()が例外を投げることを確認"""
    settings.READ_ONLY_MODE = True
    try:
        with pytest.raises(Exception) as excinfo:
            Client.create(name="Fail", display_name="Fail")
        assert "Database is in read-only mode" in str(excinfo.value)
    finally:
        settings.READ_ONLY_MODE = False
