import datetime
from settings import ALERT_THRESHOLD_WARNING, ALERT_THRESHOLD_DANGER

def get_alert_level(expire_date):
    if not expire_date:
        return None
    
    if isinstance(expire_date, str):
        expire_date = datetime.datetime.strptime(expire_date, '%Y-%m-%d').date()
    
    today = datetime.date.today()
    days_left = (expire_date - today).days
    
    if days_left <= ALERT_THRESHOLD_DANGER:
        return 'danger'
    elif days_left <= ALERT_THRESHOLD_WARNING:
        return 'warning'
    return 'success'

def format_date(date_val):
    if not date_val:
        return ""
    if isinstance(date_val, (datetime.date, datetime.datetime)):
        return date_val.strftime('%Y-%m-%d')
    return date_val

def get_month_range(year_month=None):
    if not year_month:
        today = datetime.date.today()
        year = today.year
        month = today.month
    else:
        year, month = map(int, year_month.split('-'))
    
    start_date = datetime.date(year, month, 1)
    if month == 12:
        end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    
    return start_date, end_date

def get_prev_next_month(year_month):
    if not year_month:
        today = datetime.date.today()
        year = today.year
        month = today.month
    else:
        year, month = map(int, year_month.split('-'))
    
    current_date = datetime.date(year, month, 1)
    
    # 前月
    prev_date = current_date - datetime.timedelta(days=1)
    prev_month = prev_date.strftime('%Y-%m')
    
    # 次月
    if month == 12:
        next_date = datetime.date(year + 1, 1, 1)
    else:
        next_date = datetime.date(year, month + 1, 1)
    next_month = next_date.strftime('%Y-%m')
    
    return prev_month, next_month

def get_display_labels():
    from models import DisplayLabel, AppSetting
    from settings import DEFAULT_LABELS
    
    labels = DEFAULT_LABELS.copy()
    
    # 旧 DisplayLabel から取得
    try:
        db_labels = DisplayLabel.select()
        for l in db_labels:
            labels[l.key] = l.value
    except:
        pass
        
    # AppSetting から取得（上書き）
    try:
        settings = AppSetting.select().where(AppSetting.key.startswith('label_') | AppSetting.key.startswith('status_'))
        for s in settings:
            labels[s.key] = s.value
    except:
        pass
        
    return labels

def get_app_settings():
    from models import AppSetting
    from settings import DEFAULT_SETTINGS
    
    config = DEFAULT_SETTINGS.copy()
    try:
        db_settings = AppSetting.select().where(AppSetting.key.startswith('show_'))
        for s in db_settings:
            val = s.value.lower()
            config[s.key] = (val == 'true')
    except:
        pass
    return config

def generate_file_token(file_id):
    from itsdangerous import URLSafeSerializer
    from settings import SECRET_KEY, FILE_TOKEN_SALT
    s = URLSafeSerializer(SECRET_KEY, salt=FILE_TOKEN_SALT)
    return s.dumps(file_id)

def verify_file_token(token):
    from itsdangerous import URLSafeSerializer
    from settings import SECRET_KEY, FILE_TOKEN_SALT
    s = URLSafeSerializer(SECRET_KEY, salt=FILE_TOKEN_SALT)
    try:
        file_id = s.loads(token)
        return file_id
    except:
        return None

def save_uploaded_file(upload, user, site=None, request_obj=None, title=None, description=None, category=None, client_visible=True):
    import os
    import uuid
    from models import SharedFile
    from settings import UPLOAD_DIR, MAX_UPLOAD_BYTES, ALLOWED_EXTENSIONS
    
    if not upload or not upload.filename:
        return None, "ファイルが選択されていません"

    name, ext = os.path.splitext(upload.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return None, f"許可されていない拡張子です: {ext}"
    
    # サイズチェック
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    if size > MAX_UPLOAD_BYTES:
        return None, f"ファイルサイズが大きすぎます (最大 {MAX_UPLOAD_BYTES/1024/1024}MB)"
    
    file_uuid = str(uuid.uuid4())
    save_dir = os.path.join(UPLOAD_DIR, file_uuid)
    os.makedirs(save_dir, exist_ok=True)
    
    save_path = os.path.join(save_dir, upload.filename)
    upload.save(save_path)
    
    shared_file = SharedFile.create(
        site=site,
        request=request_obj,
        uploaded_by=user,
        title=title or upload.filename,
        description=description,
        category=category,
        original_filename=upload.filename,
        stored_path=os.path.relpath(save_path, UPLOAD_DIR),
        size_bytes=size,
        content_type=upload.content_type,
        client_visible=client_visible
    )
    return shared_file, None
