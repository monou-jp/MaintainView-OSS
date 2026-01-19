import pytest

def test_login_success(auth_client, admin_user):
    """管理者ログインが成功することを確認"""
    res = auth_client.login(admin_user.email, 'password')
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/admin')

def test_login_failure(auth_client, admin_user):
    """パスワード間違いでログイン失敗することを確認"""
    res = auth_client.login(admin_user.email, 'wrongpassword')
    assert res.status_code == 200
    # res.text の中身を柔軟にチェック
    assert "ログイン" in res.text

def test_login_inactive_user(auth_client, admin_user):
    """無効なユーザーがログインできないことを確認"""
    admin_user.is_active = False
    admin_user.save()
    
    res = auth_client.login(admin_user.email, 'password')
    assert res.status_code == 200
    assert "ログイン" in res.text

def test_logout(auth_client, admin_user):
    """ログアウトができることを確認"""
    auth_client.login(admin_user.email, 'password')
    res = auth_client.app.get('/logout')
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/login')
    
    # ログアウト後に管理画面にアクセスするとリダイレクトされる
    res = auth_client.app.get('/admin', status=302)
    assert res.headers['Location'].endswith('/login')

def test_csrf_protection(test_app, admin_user):
    """CSRFトークンがない場合にPOSTが拒否されることを確認"""
    # ログイン自体はCSRFが必要なので、まずはログイン
    res = test_app.get('/login')
    csrf_token = res.html.find('input', {'name': 'csrf_token'})['value']
    test_app.post('/login', {'email': admin_user.email, 'password': 'password', 'csrf_token': csrf_token})
    
    # トークンなしでPOST
    res = test_app.post('/admin/clients/new', {'name': 'New Client'}, status=403)
    assert "CSRF token missing or invalid." in res.text
