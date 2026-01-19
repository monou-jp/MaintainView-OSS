import pytest
from models import Client, User, Site, MaintenanceLog, LogTemplate

def test_client_crud(auth_client, admin_user):
    """クライアントの作成・編集ができることを確認"""
    auth_client.login(admin_user.email, 'password')
    
    # 作成
    auth_client.get_with_csrf('/admin/clients')
    res = auth_client.post_with_csrf('/admin/clients/new', {
        'name': 'Test Client',
        'display_name': 'Display Name',
        'client_memo': 'Memo'
    })
    assert res.status_code == 302
    assert Client.filter(name='Test Client').exists()
    
    client = Client.get(name='Test Client')
    
    # 編集
    auth_client.get_with_csrf(f'/admin/clients/{client.id}')
    res = auth_client.post_with_csrf(f'/admin/clients/{client.id}', {
        'name': 'Updated Client',
        'display_name': 'Updated Display',
        'client_memo': 'Updated Memo'
    })
    assert res.status_code == 302
    assert Client.get_by_id(client.id).name == 'Updated Client'

def test_site_crud(auth_client, admin_user, client_factory):
    """サイトの作成・編集ができることを確認"""
    client = client_factory()
    auth_client.login(admin_user.email, 'password')
    
    # 作成
    auth_client.get_with_csrf('/admin/sites')
    res = auth_client.post_with_csrf('/admin/sites/new', {
        'client_id': client.id,
        'name': 'Test Site',
        'url': 'http://example.com',
        'contract_type': 'Standard'
    })
    assert res.status_code == 302
    assert Site.filter(name='Test Site').exists()
    
    site = Site.get(name='Test Site')
    
    # 編集
    auth_client.get_with_csrf(f'/admin/sites/{site.id}')
    res = auth_client.post_with_csrf(f'/admin/sites/{site.id}', {
        'client_id': client.id,
        'name': 'Updated Site',
        'url': 'http://updated.com'
    })
    assert res.status_code == 302
    assert Site.get_by_id(site.id).name == 'Updated Site'

def test_maintenance_log_crud(auth_client, admin_user, client_factory):
    """保守ログの作成・編集ができることを確認"""
    client = client_factory()
    site = Site.create(client=client, name="Test Site")
    auth_client.login(admin_user.email, 'password')
    
    # 作成
    auth_client.get_with_csrf(f'/admin/sites/{site.id}/logs')
    res = auth_client.post_with_csrf(f'/admin/sites/{site.id}/logs/new', {
        'performed_at': '2026-01-01',
        'category': 'Update',
        'summary': 'OS Update',
        'details': 'Applied security patches',
        'is_visible_to_client': 'on'
    })
    assert res.status_code == 302
    assert MaintenanceLog.filter(summary='OS Update').exists()
    
    log = MaintenanceLog.get(summary='OS Update')
    
    # 編集
    auth_client.get_with_csrf(f'/admin/logs/{log.id}/edit')
    res = auth_client.post_with_csrf(f'/admin/logs/{log.id}/edit', {
        'performed_at': '2026-01-01',
        'category': 'Update',
        'summary': 'Updated Summary',
        'details': 'Updated Details'
    })
    assert res.status_code == 302
    assert MaintenanceLog.get_by_id(log.id).summary == 'Updated Summary'

def test_log_template_crud(auth_client, admin_user):
    """ログテンプレートの作成・編集・削除ができることを確認"""
    auth_client.login(admin_user.email, 'password')
    
    # 一覧表示
    auth_client.app.get('/admin/log_templates')

    # 作成
    res = auth_client.post_with_csrf('/admin/log_templates/new', {
        'name': 'Template 1',
        'category': 'Cat',
        'summary': 'Sum',
        'details': 'Det',
        'is_active': 'on'
    })
    assert res.status_code == 302
    assert LogTemplate.filter(name='Template 1').exists()
    
    template = LogTemplate.get(name='Template 1')
    
    # 編集
    res = auth_client.post_with_csrf(f'/admin/log_templates/{template.id}', {
        'name': 'Updated Template',
        'category': 'Cat',
        'summary': 'Sum',
        'details': 'Det',
        'is_active': 'on'
    })
    assert res.status_code == 302
    assert LogTemplate.get_by_id(template.id).name == 'Updated Template'
    
    # 削除
    res = auth_client.post_with_csrf(f'/admin/log_templates/{template.id}/delete')
    assert res.status_code == 302
    assert not LogTemplate.filter(id=template.id).exists()

def test_settings_update(auth_client, admin_user):
    """設定の更新ができることを確認"""
    auth_client.login(admin_user.email, 'password')
    
    # URL末尾のスラッシュなしで試行
    auth_client.app.get('/admin/settings')
    # チェックボックスがOFFの場合はパラメータ自体を送信しない
    res = auth_client.post_with_csrf('/admin/settings', {
        'label_log': 'Custom Log Label',
        # 'show_contract_info' を含めないことで False にする
    })
    assert res.status_code == 302
    
    from utils import get_display_labels, get_app_settings
    assert get_display_labels()['label_log'] == 'Custom Log Label'
    assert get_app_settings()['show_contract_info'] is False
