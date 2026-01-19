import pytest
from models import Site, MaintenanceLog, Request

def test_client_access_own_data(auth_client, client_factory, client_user_factory):
    """クライアントが自分のデータにアクセスでき、他人のデータにはアクセスできないことを確認"""
    client1 = client_factory(name="Client 1")
    client2 = client_factory(name="Client 2")
    user1 = client_user_factory(email="user1@test.com", client=client1)
    
    site1 = Site.create(client=client1, name="Site 1")
    site2 = Site.create(client=client2, name="Site 2")
    
    auth_client.login(user1.email, 'password')
    
    # 自分のサイトは見れる
    res = auth_client.app.get(f'/client/sites/{site1.id}')
    assert res.status_code == 200
    assert "Site 1" in res.text
    
    # 他人のサイトは見れない
    auth_client.app.get(f'/client/sites/{site2.id}', status=403)

def test_client_request_flow(auth_client, client_factory, client_user_factory):
    """クライアントが依頼を作成できることを確認"""
    client = client_factory()
    user = client_user_factory(email="user@test.com", client=client)
    site = Site.create(client=client, name="Test Site")
    
    auth_client.login(user.email, 'password')
    
    # 依頼作成
    auth_client.get_with_csrf('/client/requests/new')
    res = auth_client.post_with_csrf('/client/requests/new', {
        'site_id': site.id,
        'subject': 'Help Me',
        'body': 'I need help with my site',
        'priority': 'high'
    })
    assert res.status_code == 302
    assert Request.filter(subject='Help Me').exists()
    
    req = Request.get(subject='Help Me')
    
    # 依頼詳細とメッセージ
    auth_client.get_with_csrf(f'/client/requests/{req.id}')
    res = auth_client.post_with_csrf(f'/client/requests/{req.id}', {
        'body': 'Additional info'
    })
    assert res.status_code == 302
    assert req.messages.count() == 1

def test_client_log_visibility(auth_client, client_factory, client_user_factory):
    """クライアントが「クライアントに表示」設定されたログのみ見れることを確認"""
    client = client_factory()
    user = client_user_factory(email="user@test.com", client=client)
    site = Site.create(client=client, name="Test Site")
    
    MaintenanceLog.create(site=site, performed_at='2026-01-01', category='Update', summary='Visible Log', is_visible_to_client=True)
    MaintenanceLog.create(site=site, performed_at='2026-01-01', category='Update', summary='Hidden Log', is_visible_to_client=False)
    
    auth_client.login(user.email, 'password')
    
    res = auth_client.app.get(f'/client/sites/{site.id}/logs')
    assert "Visible Log" in res.text
    assert "Hidden Log" not in res.text
