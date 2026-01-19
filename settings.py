import os
import secrets

# 基本設定
SECRET_KEY = os.environ.get('SECRET_KEY', "change_strong_strings")
DB_PATH = 'maintenance.db'
DEBUG = True

# 動作モード (True: CGI, False: Bottle development server)
if os.path.exists('dev.flag'):
    IS_CGI = False
else:
    IS_CGI = True

# デモ用読み取り専用モード (True: 書き込み禁止, False: 通常)
READ_ONLY_MODE = False

# アラート閾値（日数）
ALERT_THRESHOLD_WARNING = 30  # 注意
ALERT_THRESHOLD_DANGER = 7    # 警告

# 初期管理者設定
DEFAULT_ADMIN_EMAIL = 'admin@example.com'
DEFAULT_ADMIN_PASSWORD = 'admin'

# 表示ラベル初期値
DEFAULT_LABELS = {
    'label_log': '保守ログ',
    'label_report': '作業報告',
    'label_next_plan': '次回予定',
    'label_caution': '注意事項',
    # v1.5 拡張
    'label_contract_info': '契約情報',
    'label_renewal_date': '更新予定日',
    'label_domain_expire': 'ドメイン期限',
    'label_ssl_expire': '安全証明書の期限（SSL）',
    'label_monthly_report': '月次レポート',
    'label_request': '依頼',
    'label_files': '資料・ファイル',
    'status_new': '受付済み',
    'status_in_progress': '対応中',
    'status_done': '完了'
}

# 表示項目設定（True: 表示, False: 非表示）
DEFAULT_SETTINGS = {
    'show_contract_info': True,
    'show_renewal_date': True,
    'show_domain_expire': True,
    'show_ssl_expire': True,
    'show_notice': True,
    'show_maintenance_log': True,
    'show_monthly_report': True,
    'show_requests': True,
    'show_files': True,
    'show_top_cards': True
}

# アップロード設定
UPLOAD_DIR = os.path.join('data', 'uploads')
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.txt', '.csv', '.xlsx'}
FILE_TOKEN_SALT = os.environ.get('FILE_TOKEN_SALT', 'maintainview-file-salt')
