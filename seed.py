from peewee import SqliteDatabase
from models import init_db, Client, User, Site, MaintenanceLog, Notice, set_db, LogTemplate, Request, RequestMessage
import settings
from auth import hash_password
import datetime

def seed_data():
    set_db(SqliteDatabase(settings.DB_PATH))
    init_db()
    
    # 既存データのクリア (デモ用なので、再実行時に重複しないように)
    # 外部キー制約を考慮して削除順序に注意
    RequestMessage.delete().execute()
    Request.delete().execute()
    Notice.delete().execute()
    MaintenanceLog.delete().execute()
    Site.delete().execute()
    User.delete().execute()
    Client.delete().execute()
    LogTemplate.delete().execute()

    # 管理者ユーザー
    admin_pw = hash_password("admin")
    User.create(email="admin@example.com", password_hash=admin_pw, role="admin")
    
    # クライアント1 (既存のサンプル)
    c1 = Client.create(name="株式会社サンプル", display_name="サンプル株式会社", client_memo="いつもお世話になっております。")
    client_pw = hash_password("client")
    u1 = User.create(email="client@example.com", password_hash=client_pw, role="client", client=c1)
    
    # クライアント2 (複数クライアントのデモ用)
    c2 = Client.create(name="合同会社テスト", display_name="テスト合同会社", client_memo="新規のお客様です。")
    User.create(email="test@example.com", password_hash=client_pw, role="client", client=c2)

    today = datetime.date.today()
    
    # サイト1 (c1: 株式会社サンプル)
    s1 = Site.create(
        client=c1,
        name="サンプルコーポレートサイト",
        url="https://example.com",
        contract_type="月次保守",
        contract_start_date=today - datetime.timedelta(days=365),
        renewal_date=today + datetime.timedelta(days=30),
        domain_expire_date=today + datetime.timedelta(days=15), # アラート対象
        ssl_expire_date=today + datetime.timedelta(days=5),    # 警告対象
        client_note="メインサイトです。"
    )

    # サイト2 (c1: 株式会社サンプル - 複数サイト所有)
    s2 = Site.create(
        client=c1,
        name="サンプル採用特設サイト",
        url="https://recruit.example.com",
        contract_type="スポット",
        contract_start_date=today - datetime.timedelta(days=100),
        renewal_date=today + datetime.timedelta(days=265),
        domain_expire_date=today + datetime.timedelta(days=200),
        ssl_expire_date=today + datetime.timedelta(days=180),
        client_note="採用向けのLPです。"
    )

    # サイト3 (c2: 合同会社テスト)
    s3 = Site.create(
        client=c2,
        name="テストECサイト",
        url="https://shop.test-example.jp",
        contract_type="月次保守(高負荷)",
        contract_start_date=today - datetime.timedelta(days=30),
        renewal_date=today + datetime.timedelta(days=335),
        domain_expire_date=today + datetime.timedelta(days=300),
        ssl_expire_date=today - datetime.timedelta(days=1),    # 期限切れ
        client_note="ECサイトなのでダウンタイム厳禁。"
    )
    
    # ログ (s1)
    MaintenanceLog.create(
        site=s1,
        performed_at=today - datetime.timedelta(days=30),
        category="アップデート",
        summary="WordPress本体の更新",
        details="WordPress 6.4.1から6.4.2へ更新しました。",
        is_visible_to_client=True
    )
    MaintenanceLog.create(
        site=s1,
        performed_at=today,
        category="アップデート",
        summary="WordPressプラグインの更新",
        details="セキュリティ向上のため、以下のプラグインを更新しました。\n- Contact Form 7\n- Yoast SEO",
        is_visible_to_client=True
    )
    
    # ログ (s3)
    MaintenanceLog.create(
        site=s3,
        performed_at=today - datetime.timedelta(days=1),
        category="不具合対応",
        summary="決済エラーの調査",
        details="特定の決済手段でエラーが出る不具合を修正しました。",
        is_visible_to_client=True,
        is_important=True
    )
    
    # 注意事項 (s1)
    Notice.create(
        site=s1,
        title="年末年始のサポートについて",
        body="12/29〜1/4は休業とさせていただきます。",
        is_visible_to_client=True
    )

    # 注意事項 (s3)
    Notice.create(
        site=s3,
        title="サーバーメンテナンスのお知らせ",
        body="来週月曜日、深夜2:00〜4:00にサーバーメンテナンスを実施します。",
        is_visible_to_client=True
    )

    # ログテンプレート
    LogTemplate.create(
        name="定期プラグイン更新",
        category="アップデート",
        summary="WordPressプラグインの定期更新",
        details="以下のプラグインを最新版に更新しました。\n\n- \n- \n\n更新後、サイトの表示および主要機能の動作に問題がないことを確認しました。"
    )
    LogTemplate.create(
        name="脆弱性対応",
        category="セキュリティ",
        summary="緊急セキュリティパッチの適用",
        details="緊急の脆弱性が報告されたため、パッチを適用しました。"
    )

    # リクエスト (c1)
    r1 = Request.create(
        client=c1,
        site=s1,
        subject="画像が表示されません",
        body="トップページのメインビジュアルが一部表示されていないようです。確認をお願いします。",
        priority="high",
        status="in_progress",
        created_by=u1
    )
    RequestMessage.create(
        request=r1,
        author_user=u1,
        author_role="client",
        body="昨日までは表示されていました。"
    )

    print("Sample data created.")

if __name__ == "__main__":
    seed_data()
