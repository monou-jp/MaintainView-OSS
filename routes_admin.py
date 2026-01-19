from bottle import Bottle, request, redirect, jinja2_view, response, abort
import urllib.parse
from models import Client, User, Site, MaintenanceLog, Notice, LogTemplate, DisplayLabel, AppSetting, Request, RequestMessage, SharedFile
from auth import login_required, get_current_user, check_csrf_token, generate_csrf_token, hash_password
from utils import get_alert_level, format_date, get_display_labels, get_app_settings, get_month_range, get_prev_next_month, generate_file_token, save_uploaded_file
import datetime
import os
import uuid
from settings import UPLOAD_DIR, MAX_UPLOAD_BYTES, ALLOWED_EXTENSIONS

admin_app = Bottle()

def get_common_context(active_page=None):
    from bottle import request
    import settings
    return {
        'current_user': get_current_user(),
        'active_page': active_page,
        'csrf_token': generate_csrf_token(),
        'get_alert_level': get_alert_level,
        'format_date': format_date,
        'labels': get_display_labels(),
        'app_settings': get_app_settings(),
        'messages': get_flash(),
        'request': request,
        'read_only_mode': getattr(settings, 'READ_ONLY_MODE', False)
    }

@admin_app.route('/')
@login_required(role='admin')
@jinja2_view('admin/dashboard.html')
def admin_dashboard():
    # 期限アラート一覧
    sites = Site.select().where(Site.is_active == True)
    alerts = []
    for site in sites:
        domain_alert = get_alert_level(site.domain_expire_date)
        ssl_alert = get_alert_level(site.ssl_expire_date)
        if domain_alert in ['warning', 'danger'] or ssl_alert in ['warning', 'danger']:
            # 優先度計算: danger(1) > warning(2)
            priority = 2
            days_to_expire = 9999
            
            today = datetime.date.today()
            if site.domain_expire_date:
                d_days = (site.domain_expire_date - today).days
                days_to_expire = min(days_to_expire, d_days)
            if site.ssl_expire_date:
                s_days = (site.ssl_expire_date - today).days
                days_to_expire = min(days_to_expire, s_days)
            
            if domain_alert == 'danger' or ssl_alert == 'danger':
                priority = 1
                
            alerts.append({
                'site': site, 
                'domain_alert': domain_alert, 
                'ssl_alert': ssl_alert,
                'priority': priority,
                'days_to_expire': days_to_expire
            })
    
    # 1. 警告(7日以内)を最優先, 2. 期限が近い順
    alerts.sort(key=lambda x: (x['priority'], x['days_to_expire']))
    
    # 直近の保守ログ
    recent_logs = MaintenanceLog.select().order_by(MaintenanceLog.performed_at.desc()).limit(10)
    
    ctx = get_common_context('admin_dashboard')
    ctx.update({'alerts': alerts, 'recent_logs': recent_logs})
    return ctx

@admin_app.route('/clients')
@login_required(role='admin')
@jinja2_view('admin/clients.html')
def admin_clients():
    q = request.query.decode().get('q', '').strip()
    query = Client.select()
    if q:
        query = query.where((Client.name.contains(q)) | (Client.display_name.contains(q)))
    clients = query.order_by(Client.id.desc())
    ctx = get_common_context('admin_clients')
    ctx.update({'clients': clients, 'q': q})
    return ctx

@admin_app.route('/clients/new', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/client_form.html')
def admin_client_new():
    if request.method == 'POST':
        check_csrf_token()
        Client.create(
            name=request.forms.decode().get('name'),
            display_name=request.forms.decode().get('display_name'),
            client_memo=request.forms.decode().get('client_memo'),
            internal_memo=request.forms.decode().get('internal_memo'),
            is_active=request.forms.decode().get('is_active') == 'on'
        )
        set_flash("クライアントを登録しました。", "success")
        redirect('/admin/clients')
    
    ctx = get_common_context('admin_clients')
    ctx.update({'client': None})
    return ctx

@admin_app.route('/clients/<id:int>', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/client_form.html')
def admin_client_edit(id):
    client = Client.get_by_id(id)
    if request.method == 'POST':
        check_csrf_token()
        client.name = request.forms.decode().get('name')
        client.display_name = request.forms.decode().get('display_name')
        client.client_memo = request.forms.decode().get('client_memo')
        client.internal_memo = request.forms.decode().get('internal_memo')
        client.is_active = request.forms.decode().get('is_active') == 'on'
        client.save()
        set_flash("クライアントを更新しました。", "success")
        redirect('/admin/clients')
    
    ctx = get_common_context('admin_clients')
    ctx.update({'client': client})
    return ctx

@admin_app.route('/clients/<id:int>/users')
@login_required(role='admin')
@jinja2_view('admin/client_users.html')
def admin_client_users(id):
    client = Client.get_by_id(id)
    if request.method == 'POST':
        check_csrf_token()
        action = request.forms.decode().get('action')
        user_id = request.forms.decode().get('user_id')
        user = User.get_by_id(user_id)
        
        if action == 'update_status':
            user.is_active = request.forms.decode().get('is_active') == 'on'
            user.save()
            set_flash("ユーザー状態を更新しました。", "success")
        elif action == 'change_password':
            new_password = request.forms.decode().get('new_password')
            if new_password:
                user.password_hash = hash_password(new_password)
                user.save()
                set_flash("パスワードを変更しました。", "success")
        redirect(f'/admin/clients/{id}/users')

    users = User.select().where(User.client == client)
    ctx = get_common_context('admin_clients')
    ctx.update({'client': client, 'users': users})
    return ctx

@admin_app.route('/clients/<id:int>/users/new', method='POST')
@login_required(role='admin')
def admin_client_user_new(id):
    check_csrf_token()
    client = Client.get_by_id(id)
    email = request.forms.decode().get('email')
    password = request.forms.decode().get('password')
    User.create(
        email=email,
        password_hash=hash_password(password),
        role='client',
        client=client
    )
    redirect(f'/admin/clients/{id}/users')

@admin_app.route('/sites')
@login_required(role='admin')
@jinja2_view('admin/sites.html')
def admin_sites():
    client_id = request.query.decode().get('client_id')
    q = request.query.decode().get('q', '').strip()
    query = Site.select()
    if client_id:
        query = query.where(Site.client == client_id)
    if q:
        query = query.where(Site.name.contains(q))
    sites = query.order_by(Site.id.desc())
    clients = Client.select()
    ctx = get_common_context('admin_sites')
    ctx.update({'sites': sites, 'clients': clients, 'selected_client_id': client_id, 'q': q})
    return ctx

@admin_app.route('/sites/new', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/site_form.html')
def admin_site_new():
    if request.method == 'POST':
        check_csrf_token()
        Site.create(
            client=request.forms.decode().get('client_id'),
            name=request.forms.decode().get('name'),
            url=request.forms.decode().get('url'),
            contract_type=request.forms.decode().get('contract_type'),
            contract_start_date=request.forms.decode().get('contract_start_date') or None,
            contract_end_date=request.forms.decode().get('contract_end_date') or None,
            renewal_date=request.forms.decode().get('renewal_date') or None,
            domain_expire_date=request.forms.decode().get('domain_expire_date') or None,
            ssl_expire_date=request.forms.decode().get('ssl_expire_date') or None,
            client_note=request.forms.decode().get('client_note'),
            internal_note=request.forms.decode().get('internal_note'),
            is_active=request.forms.decode().get('is_active') == 'on'
        )
        set_flash("サイトを登録しました。", "success")
        redirect('/admin/sites')
    
    ctx = get_common_context('admin_sites')
    ctx.update({'site': None, 'clients': Client.select()})
    return ctx

@admin_app.route('/sites/<id:int>', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/site_form.html')
def admin_site_edit(id):
    site = Site.get_by_id(id)
    if request.method == 'POST':
        check_csrf_token()
        site.name = request.forms.decode().get('name')
        site.url = request.forms.decode().get('url')
        site.contract_type = request.forms.decode().get('contract_type')
        site.contract_start_date = request.forms.decode().get('contract_start_date') or None
        site.contract_end_date = request.forms.decode().get('contract_end_date') or None
        site.renewal_date = request.forms.decode().get('renewal_date') or None
        site.domain_expire_date = request.forms.decode().get('domain_expire_date') or None
        site.ssl_expire_date = request.forms.decode().get('ssl_expire_date') or None
        site.client_note = request.forms.decode().get('client_note')
        site.internal_note = request.forms.decode().get('internal_note')
        site.is_active = request.forms.decode().get('is_active') == 'on'
        site.save()
        set_flash("サイトを更新しました。", "success")
        redirect('/admin/sites')
    
    ctx = get_common_context('admin_sites')
    ctx.update({'site': site, 'clients': Client.select()})
    return ctx

@admin_app.route('/sites/<id:int>/logs')
@login_required(role='admin')
@jinja2_view('admin/site_logs.html')
def admin_site_logs(id):
    site = Site.get_by_id(id)
    q = request.query.decode().get('q', '').strip()
    query = MaintenanceLog.select().where(MaintenanceLog.site == site)
    if q:
        query = query.where(MaintenanceLog.summary.contains(q))
    logs = query.order_by(MaintenanceLog.performed_at.desc())
    ctx = get_common_context('admin_sites')
    ctx.update({'site': site, 'logs': logs, 'q': q})
    return ctx

@admin_app.route('/sites/<id:int>/logs/new', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/log_form.html')
def admin_log_new(id):
    site = Site.get_by_id(id)
    if request.method == 'POST':
        check_csrf_token()
        MaintenanceLog.create(
            site=site,
            performed_at=request.forms.decode().get('performed_at'),
            category=request.forms.decode().get('category'),
            summary=request.forms.decode().get('summary'),
            details=request.forms.decode().get('details'),
            internal_note=request.forms.decode().get('internal_note'),
            is_visible_to_client=request.forms.decode().get('is_visible_to_client') == 'on',
            is_important=request.forms.decode().get('is_important') == 'on',
            created_by=get_current_user(),
            related_request=request.forms.decode().get('related_request_id') or None
        )
        redirect(f'/admin/sites/{id}/logs')
    
    templates = LogTemplate.select().where(LogTemplate.is_active == True).order_by(LogTemplate.name)
    ctx = get_common_context('admin_sites')
    ctx.update({'site': site, 'log': None, 'templates': templates})
    return ctx

@admin_app.route('/logs/<log_id:int>/edit', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/log_form.html')
def admin_log_edit(log_id):
    log = MaintenanceLog.get_by_id(log_id)
    if request.method == 'POST':
        check_csrf_token()
        log.performed_at = request.forms.decode().get('performed_at')
        log.category = request.forms.decode().get('category')
        log.summary = request.forms.decode().get('summary')
        log.details = request.forms.decode().get('details')
        log.internal_note = request.forms.decode().get('internal_note')
        log.is_visible_to_client = request.forms.decode().get('is_visible_to_client') == 'on'
        log.is_important = request.forms.decode().get('is_important') == 'on'
        log.save()
        redirect(f'/admin/sites/{log.site.id}/logs')
    
    templates = LogTemplate.select().where(LogTemplate.is_active == True).order_by(LogTemplate.name)
    ctx = get_common_context('admin_sites')
    ctx.update({'site': log.site, 'log': log, 'templates': templates})
    return ctx

# テンプレート管理
@admin_app.route('/log_templates')
@login_required(role='admin')
@jinja2_view('admin/log_templates.html')
def admin_log_templates():
    templates = LogTemplate.select().order_by(LogTemplate.id.desc())
    ctx = get_common_context('admin_log_templates')
    ctx.update({'templates': templates})
    return ctx

@admin_app.route('/log_templates/new', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/log_template_form.html')
def admin_log_template_new():
    if request.method == 'POST':
        check_csrf_token()
        LogTemplate.create(
            name=request.forms.decode().get('name'),
            category=request.forms.decode().get('category'),
            summary=request.forms.decode().get('summary'),
            details=request.forms.decode().get('details'),
            is_active=request.forms.decode().get('is_active') == 'on'
        )
        set_flash("テンプレートを作成しました。", "success")
        redirect('/admin/log_templates')
    
    ctx = get_common_context('admin_log_templates')
    ctx.update({'template': None})
    return ctx

@admin_app.route('/log_templates/<id:int>', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/log_template_form.html')
def admin_log_template_edit(id):
    template = LogTemplate.get_by_id(id)
    if request.method == 'POST':
        check_csrf_token()
        template.name = request.forms.decode().get('name')
        template.category = request.forms.decode().get('category')
        template.summary = request.forms.decode().get('summary')
        template.details = request.forms.decode().get('details')
        template.is_active = request.forms.decode().get('is_active') == 'on'
        template.save()
        set_flash("テンプレートを更新しました。", "success")
        redirect('/admin/log_templates')
    
    ctx = get_common_context('admin_log_templates')
    ctx.update({'template': template})
    return ctx

@admin_app.route('/log_templates/<id:int>/delete', method='POST')
@login_required(role='admin')
def admin_log_template_delete(id):
    check_csrf_token()
    template = LogTemplate.get_by_id(id)
    template.delete_instance()
    set_flash("テンプレートを削除しました。", "success")
    redirect('/admin/log_templates')

# 月次レポート
@admin_app.route('/reports/monthly/<client_id:int>')
@admin_app.route('/reports/monthly/<client_id:int>/print')
@login_required(role='admin')
@jinja2_view('client/report_monthly.html')
def admin_report_monthly(client_id):
    client = Client.get_by_id(client_id)
    month = request.query.decode().get('month')
    is_print = request.url.endswith('/print')
    
    start_date, end_date = get_month_range(month)
    prev_month, next_month = get_prev_next_month(month)
    
    # ログ
    logs = MaintenanceLog.select().join(Site).where(
        (Site.client == client) &
        (MaintenanceLog.is_visible_to_client == True) &
        (MaintenanceLog.performed_at >= start_date) &
        (MaintenanceLog.performed_at <= end_date)
    ).order_by(MaintenanceLog.performed_at.desc())
    
    # 重要対応 (最大5件)
    important_logs = [log for log in logs if log.is_important][:5]
    
    # カテゴリ集計
    category_counts = {}
    for log in logs:
        cat = log.category or "その他"
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # 注意事項
    notices = Notice.select().join(Site).where(
        (Site.client == client) &
        (Notice.is_visible_to_client == True) &
        (
            ((Notice.start_date.is_null()) | (Notice.start_date <= end_date)) &
            ((Notice.end_date.is_null()) | (Notice.end_date >= start_date))
        )
    ).order_by(Notice.created_at.desc())
    
    # サイト情報（契約・期限）
    sites = Site.select().where((Site.client == client) & (Site.is_active == True))
    
    # アラート集計 (v1.5: 期限切れ間近の通知)
    alerts = []
    for site in sites:
        d_alert = get_alert_level(site.domain_expire_date)
        s_alert = get_alert_level(site.ssl_expire_date)
        if d_alert in ['warning', 'danger']:
            alerts.append({'site': site.name, 'type': 'ドメイン期限', 'date': site.domain_expire_date, 'level': d_alert})
        if s_alert in ['warning', 'danger']:
            alerts.append({'site': site.name, 'type': 'SSL証明書期限', 'date': site.ssl_expire_date, 'level': s_alert})

    base_path = '/admin/reports/monthly/{}'.format(client_id)
    ctx = get_common_context('admin_clients')
    ctx.update({
        'client': client,
        'logs': logs,
        'important_logs': important_logs,
        'category_counts': category_counts,
        'notices': notices,
        'sites': sites,
        'alerts': alerts,
        'selected_month': month or datetime.date.today().strftime('%Y-%m'),
        'prev_month': prev_month,
        'next_month': next_month,
        'is_print': is_print,
        'is_admin_view': True,
        'base_path': base_path,
        'today': datetime.date.today()
    })
    return ctx

# 設定
@admin_app.route('/settings', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/settings.html')
def admin_settings():
    from settings import DEFAULT_LABELS, DEFAULT_SETTINGS
    if request.method == 'POST':
        check_csrf_token()
        
        action = request.forms.decode().get('action')
        if action == 'change_password':
            new_password = request.forms.decode().get('new_password')
            if new_password:
                user = get_current_user()
                user.password_hash = hash_password(new_password)
                user.save()
                set_flash("管理者パスワードを変更しました。", "success")
            redirect('/admin/settings')

        # ON/OFF設定の保存
        for key in DEFAULT_SETTINGS.keys():
            val = 'true' if request.forms.decode().get(key) == 'on' else 'false'
            setting, created = AppSetting.get_or_create(key=key, defaults={'value': val})
            if not created:
                setting.value = val
                setting.save()
        
        # ラベル設定の保存
        for key in DEFAULT_LABELS.keys():
            val = request.forms.decode().get(key)
            if val:
                setting, created = AppSetting.get_or_create(key=key, defaults={'value': val})
                if not created:
                    setting.value = val
                    setting.save()

        set_flash("設定を保存しました。", "success")
        redirect('/admin/settings')
    
    ctx = get_common_context('admin_settings')
    ctx.update({
        'app_settings': get_app_settings(),
        'display_labels': get_display_labels(),
        'default_settings': DEFAULT_SETTINGS,
        'default_labels': DEFAULT_LABELS
    })
    return ctx

def set_flash(message, category='info'):
    # クッキーを使用した簡易フラッシュメッセージ（CGI対応のため）
    # 本来はsessionを使うのが望ましいが、既存のlayout.htmlが messages を参照している
    # ここでは既存の実装に合わせて routes_admin.py 内で完結させる
    # 日本語の文字化けを防ぐためURLエンコードを行う
    safe_message = urllib.parse.quote(message)
    response.set_cookie('flash_msg', safe_message, path='/', max_age=5)
    response.set_cookie('flash_cat', category, path='/', max_age=5)

def get_flash():
    msg = request.get_cookie('flash_msg')
    cat = request.get_cookie('flash_cat')
    if msg:
        # クッキーを消去
        response.delete_cookie('flash_msg', path='/')
        response.delete_cookie('flash_cat', path='/')
        try:
            # URLデコードを行う
            decoded_msg = urllib.parse.unquote(msg)
            return [(cat or 'info', decoded_msg)]
        except Exception:
            return [(cat or 'info', msg)]
    return []

@admin_app.route('/sites/<id:int>/notices')
@login_required(role='admin')
@jinja2_view('admin/site_notices.html')
def admin_site_notices(id):
    site = Site.get_by_id(id)
    notices = Notice.select().where(Notice.site == site).order_by(Notice.created_at.desc())
    ctx = get_common_context('admin_sites')
    ctx.update({'site': site, 'notices': notices})
    return ctx

@admin_app.route('/sites/<id:int>/files', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/site_files.html')
def admin_site_files(id):
    site = Site.get_by_id(id)
    if request.method == 'POST':
        check_csrf_token()
        
        # アップロード処理
        upload = request.files.get('file')
        if not (upload and upload.filename and upload.filename != 'empty'):
            set_flash("ファイルを選択してください。", "danger")
        else:
            shared_file, error = save_uploaded_file(
                upload, 
                get_current_user(), 
                site=site,
                title=request.forms.decode().get('title'),
                description=request.forms.decode().get('description'),
                category=request.forms.decode().get('category'),
                client_visible=request.forms.decode().get('client_visible') == 'on'
            )
            if error:
                set_flash(error, "danger")
            else:
                set_flash("ファイルをアップロードしました。", "success")
        redirect(f'/admin/sites/{id}/files')

    show_deleted = request.query.decode().get('show_deleted') == '1'
    query = SharedFile.select().where(SharedFile.site == site)
    if not show_deleted:
        query = query.where(SharedFile.is_deleted == False)
    
    files = query.order_by(SharedFile.id.desc())
    
    ctx = get_common_context('admin_sites')
    ctx.update({
        'site': site, 
        'files': files, 
        'show_deleted': show_deleted,
        'generate_file_token': generate_file_token
    })
    return ctx

@admin_app.route('/files/<file_id:int>/edit', method=['POST'])
@login_required(role='admin')
def admin_file_edit(file_id):
    check_csrf_token()
    f = SharedFile.get_by_id(file_id)
    f.title = request.forms.decode().get('title')
    f.description = request.forms.decode().get('description')
    f.category = request.forms.decode().get('category')
    f.client_visible = request.forms.decode().get('client_visible') == 'on'
    f.save()
    set_flash("ファイル情報を更新しました。", "success")
    redirect(f'/admin/sites/{f.site.id}/files')

@admin_app.route('/files/<file_id:int>/delete', method=['POST'])
@login_required(role='admin')
def admin_file_delete(file_id):
    check_csrf_token()
    f = SharedFile.get_by_id(file_id)
    f.is_deleted = True
    f.save()
    set_flash("ファイルを非表示にしました。", "success")
    redirect(f'/admin/sites/{f.site.id}/files')

@admin_app.route('/files/<file_id:int>/restore', method=['POST'])
@login_required(role='admin')
def admin_file_restore(file_id):
    check_csrf_token()
    f = SharedFile.get_by_id(file_id)
    f.is_deleted = False
    f.save()
    set_flash("ファイルを再表示しました。", "success")
    redirect(f'/admin/sites/{f.site.id}/files')

@admin_app.route('/sites/<id:int>/notices/new', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/notice_form.html')
def admin_notice_new(id):
    site = Site.get_by_id(id)
    if request.method == 'POST':
        check_csrf_token()
        Notice.create(
            site=site,
            title=request.forms.decode().get('title'),
            body=request.forms.decode().get('body'),
            start_date=request.forms.decode().get('start_date') or None,
            end_date=request.forms.decode().get('end_date') or None,
            is_visible_to_client=request.forms.decode().get('is_visible_to_client') == 'on'
        )
        redirect(f'/admin/sites/{id}/notices')
    
    ctx = get_common_context('admin_sites')
    ctx.update({'site': site, 'notice': None})
    return ctx

@admin_app.route('/notices/<notice_id:int>/edit', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/notice_form.html')
def admin_notice_edit(notice_id):
    notice = Notice.get_by_id(notice_id)
    if request.method == 'POST':
        check_csrf_token()
        notice.title = request.forms.decode().get('title')
        notice.body = request.forms.decode().get('body')
        notice.start_date = request.forms.decode().get('start_date') or None
        notice.end_date = request.forms.decode().get('end_date') or None
        notice.is_visible_to_client = request.forms.decode().get('is_visible_to_client') == 'on'
        notice.save()
        redirect(f'/admin/sites/{notice.site.id}/notices')
    
    ctx = get_common_context('admin_sites')
    ctx.update({'site': notice.site, 'notice': notice})
    return ctx

@admin_app.route('/requests')
@login_required(role='admin')
@jinja2_view('admin/requests_list.html')
def admin_requests():
    status = request.query.decode().get('status')
    client_id = request.query.decode().get('client_id')
    q = request.query.decode().get('q', '').strip()
    
    query = Request.select()
    if status:
        query = query.where(Request.status == status)
    if client_id:
        query = query.where(Request.client == client_id)
    if q:
        query = query.where((Request.subject.contains(q)) | (Request.body.contains(q)))
        
    requests = query.order_by(Request.updated_at.desc())
    clients = Client.select()
    
    ctx = get_common_context('admin_requests')
    ctx.update({
        'requests': requests,
        'clients': clients,
        'selected_status': status,
        'selected_client_id': client_id,
        'q': q
    })
    return ctx

@admin_app.route('/requests/<id:int>', method=['GET', 'POST'])
@login_required(role='admin')
@jinja2_view('admin/requests_detail.html')
def admin_request_detail(id):
    try:
        req = Request.get_by_id(id)
    except Request.DoesNotExist:
        abort(404)
        
    if request.method == 'POST':
        check_csrf_token()
        action = request.forms.decode().get('action')
        
        do_redirect = True
        if action == 'update_status':
            req.status = request.forms.decode().get('status')
            req.internal_note = request.forms.decode().get('internal_note')
            req.save()
            set_flash("状態を更新しました。", "success")
        elif action == 'add_message':
            body = request.forms.decode().get('body')
            if body:
                shared_file = None
                # request.files から全ての 'file' を取得
                uploads = request.files.getall('file')
                for upload in uploads:
                    if upload and upload.filename and upload.filename != 'empty':
                        shared_file, error = save_uploaded_file(upload, get_current_user(), request_obj=req)
                        if error:
                            set_flash(error, "danger")
                            do_redirect = False 
                        break # 最初の有効なファイルを処理

                if do_redirect:
                    RequestMessage.create(
                        request=req,
                        author_user=get_current_user(),
                        author_role='admin',
                        body=body,
                        shared_file=shared_file
                    )
                    req.updated_at = datetime.datetime.now()
                    req.save()
                    set_flash("返信を投稿しました。", "success")
        
        if do_redirect:
            redirect(f'/admin/requests/{id}')
        else:
            redirect(f'/admin/requests/{id}')
            
    initial_files = SharedFile.select().where(
        SharedFile.request == req,
        SharedFile.id.not_in(
            RequestMessage.select(RequestMessage.shared_file).where(RequestMessage.shared_file.is_null(False))
        )
    )
    
    ctx = get_common_context('admin_requests')
    ctx.update({
        'request': req, 
        'initial_files': initial_files,
        'generate_file_token': generate_file_token, 
        'SharedFile': SharedFile,
        'RequestMessage': RequestMessage
    })
    return ctx

@admin_app.route('/requests/<id:int>/create_log')
@login_required(role='admin')
@jinja2_view('admin/log_form.html')
def admin_request_to_log(id):
    req = Request.get_by_id(id)
    
    # 依頼内容をベースにした初期値
    log_data = {
        'site': req.site,
        'summary': f"【依頼対応】{req.subject}",
        'performed_at': datetime.date.today().strftime('%Y-%m-%d'),
        'category': 'その他',
        'details': f"依頼内容:\n{req.body}\n\n---",
        'related_request': req
    }
    
    # スレッドの内容も少し含める（任意）
    messages = list(req.messages.order_by(RequestMessage.created_at))
    if messages:
        log_data['details'] += "\n対応経緯:\n"
        for msg in messages:
            role_name = "お客様" if msg.author_role == 'client' else "制作会社"
            log_data['details'] += f"[{msg.created_at.strftime('%m/%d')}] {role_name}: {msg.body[:50]}...\n"

    templates = LogTemplate.select().where(LogTemplate.is_active == True).order_by(LogTemplate.name)
    ctx = get_common_context('admin_sites') # サイト管理のコンテキストを流用
    ctx.update({
        'site': req.site or Site.select().where(Site.client == req.client).first(), 
        'log': None, 
        'templates': templates,
        'prefill': log_data
    })
    return ctx
