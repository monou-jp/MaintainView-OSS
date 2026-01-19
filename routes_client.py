from bottle import Bottle, request, redirect, jinja2_view, abort
from models import Client, User, Site, MaintenanceLog, Notice, Request, RequestMessage, SharedFile
from auth import login_required, get_current_user, generate_csrf_token, check_csrf_token
from utils import get_alert_level, format_date, get_month_range, get_prev_next_month, get_display_labels, get_app_settings, generate_file_token, save_uploaded_file
import datetime

client_app = Bottle()

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
        'request': request,
        'read_only_mode': getattr(settings, 'READ_ONLY_MODE', False)
    }

def check_client_access(site_id=None, client_id=None):
    user = get_current_user()
    if not user or user.role != 'client':
        abort(403)
    if client_id and user.client.id != client_id:
        abort(403)
    if site_id:
        site = Site.get_by_id(site_id)
        if site.client.id != user.client.id:
            abort(403)
        return site
    return None

@client_app.route('/')
@login_required(role='client')
@jinja2_view('client/dashboard.html')
def client_dashboard():
    user = get_current_user()
    client = user.client
    
    # 今月の対応内容
    start_date, end_date = get_month_range()
    logs = MaintenanceLog.select().join(Site).where(
        (Site.client == client) &
        (MaintenanceLog.is_visible_to_client == True) &
        (MaintenanceLog.performed_at >= start_date) &
        (MaintenanceLog.performed_at <= end_date)
    ).order_by(MaintenanceLog.performed_at.desc())
    
    # アラート（自社サイトのみ）
    sites = Site.select().where((Site.client == client) & (Site.is_active == True))
    alerts = []
    for site in sites:
        domain_alert = get_alert_level(site.domain_expire_date)
        ssl_alert = get_alert_level(site.ssl_expire_date)
        if domain_alert in ['warning', 'danger'] or ssl_alert in ['warning', 'danger']:
            alerts.append({'site': site, 'domain_alert': domain_alert, 'ssl_alert': ssl_alert})
            
    # 直近の注意事項
    today = datetime.date.today()
    notices = Notice.select().join(Site).where(
        (Site.client == client) &
        (Notice.is_visible_to_client == True) &
        ((Notice.start_date.is_null()) | (Notice.start_date <= today)) &
        ((Notice.end_date.is_null()) | (Notice.end_date >= today))
    ).order_by(Notice.created_at.desc())

    ctx = get_common_context('client_dashboard')
    ctx.update({'logs': logs, 'alerts': alerts, 'notices': notices, 'client': client})
    return ctx

@client_app.route('/sites')
@login_required(role='client')
@jinja2_view('client/sites.html')
def client_sites():
    user = get_current_user()
    sites = Site.select().where(Site.client == user.client).order_by(Site.id.desc())
    ctx = get_common_context('client_sites')
    ctx.update({'sites': sites})
    return ctx

@client_app.route('/sites/<id:int>')
@login_required(role='client')
@jinja2_view('client/site_detail.html')
def client_site_detail(id):
    site = check_client_access(site_id=id)
    
    today = datetime.date.today()
    notices = Notice.select().where(
        (Notice.site == site) &
        (Notice.is_visible_to_client == True) &
        ((Notice.start_date.is_null()) | (Notice.start_date <= today)) &
        ((Notice.end_date.is_null()) | (Notice.end_date >= today))
    ).order_by(Notice.created_at.desc())
    
    # 共有ファイル（最新5件）
    files = SharedFile.select().where(
        (SharedFile.site == site) &
        (SharedFile.client_visible == True) &
        (SharedFile.is_deleted == False)
    ).order_by(SharedFile.id.desc()).limit(5)
    
    ctx = get_common_context('client_sites')
    ctx.update({
        'site': site, 
        'notices': notices, 
        'files': files,
        'generate_file_token': generate_file_token
    })
    return ctx

@client_app.route('/sites/<id:int>/files')
@login_required(role='client')
@jinja2_view('client/site_files.html')
def client_site_files(id):
    app_settings = get_app_settings()
    if not app_settings.get('show_files'):
        abort(404, "This feature is disabled.")
    site = check_client_access(site_id=id)
    
    files = SharedFile.select().where(
        (SharedFile.site == site) &
        (SharedFile.client_visible == True) &
        (SharedFile.is_deleted == False)
    ).order_by(SharedFile.id.desc())
    
    ctx = get_common_context('client_sites')
    ctx.update({
        'site': site, 
        'files': files,
        'generate_file_token': generate_file_token
    })
    return ctx

@client_app.route('/sites/<id:int>/logs')
@login_required(role='client')
@jinja2_view('client/site_logs.html')
def client_site_logs(id):
    app_settings = get_app_settings()
    if not app_settings.get('show_maintenance_log'):
        abort(404, "This feature is disabled.")
    site = check_client_access(site_id=id)
    month = request.query.decode().get('month') # YYYY-MM
    start_date, end_date = get_month_range(month)
    prev_month, next_month = get_prev_next_month(month)
    
    logs = MaintenanceLog.select().where(
        (MaintenanceLog.site == site) &
        (MaintenanceLog.is_visible_to_client == True) &
        (MaintenanceLog.performed_at >= start_date) &
        (MaintenanceLog.performed_at <= end_date)
    ).order_by(MaintenanceLog.performed_at.desc())
    
    ctx = get_common_context('client_sites')
    ctx.update({
        'request': request,
        'site': site, 
        'logs': logs, 
        'selected_month': month or datetime.date.today().strftime('%Y-%m'),
        'prev_month': prev_month,
        'next_month': next_month
    })
    return ctx

@client_app.route('/logs')
@login_required(role='client')
@jinja2_view('client/logs.html')
def client_all_logs():
    app_settings = get_app_settings()
    if not app_settings.get('show_maintenance_log'):
        abort(404, "This feature is disabled.")
    user = get_current_user()
    month = request.query.decode().get('month')
    start_date, end_date = get_month_range(month)
    prev_month, next_month = get_prev_next_month(month)
    
    logs = MaintenanceLog.select().join(Site).where(
        (Site.client == user.client) &
        (MaintenanceLog.is_visible_to_client == True) &
        (MaintenanceLog.performed_at >= start_date) &
        (MaintenanceLog.performed_at <= end_date)
    ).order_by(MaintenanceLog.performed_at.desc())
    
    ctx = get_common_context('client_logs')
    ctx.update({
        'logs': logs, 
        'selected_month': month or datetime.date.today().strftime('%Y-%m'),
        'prev_month': prev_month,
        'next_month': next_month
    })
    return ctx

@client_app.route('/reports/monthly')
@client_app.route('/reports/monthly/print')
@login_required(role='client')
@jinja2_view('client/report_monthly.html')
def client_report_monthly():
    app_settings = get_app_settings()
    if not app_settings.get('show_monthly_report'):
        abort(404, "This feature is disabled.")
    
    user = get_current_user()
    client = user.client
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
    # レポート期間内に有効なものを抽出
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

    base_path = '/client/reports/monthly'
    ctx = get_common_context('client_reports')
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
        'is_admin_view': False,
        'base_path': base_path,
        'today': datetime.date.today()
    })
    return ctx

@client_app.route('/requests')
@login_required(role='client')
@jinja2_view('client/requests_list.html')
def client_requests():
    app_settings = get_app_settings()
    if not app_settings.get('show_requests'):
        abort(404, "This feature is disabled.")
    
    user = get_current_user()
    requests = Request.select().where(Request.client == user.client).order_by(Request.updated_at.desc())
    ctx = get_common_context('client_requests')
    ctx.update({'requests': requests})
    return ctx

@client_app.route('/requests/new', method=['GET', 'POST'])
@login_required(role='client')
@jinja2_view('client/requests_form.html')
def client_request_new():
    app_settings = get_app_settings()
    if not app_settings.get('show_requests'):
        abort(404, "This feature is disabled.")
    
    user = get_current_user()
    sites = Site.select().where((Site.client == user.client) & (Site.is_active == True))
    
    if request.method == 'POST':
        check_csrf_token()
        site_id = request.forms.decode().get('site_id')
        subject = request.forms.decode().get('subject')
        body = request.forms.decode().get('body')
        priority = request.forms.decode().get('priority', 'normal')
        
        site = None
        if site_id and site_id != 'all':
            site = Site.get_by_id(site_id)
            if site.client.id != user.client.id:
                abort(403)
        
        new_request = Request.create(
            client=user.client,
            site=site,
            subject=subject,
            body=body,
            priority=priority,
            created_by=user,
            status='new'
        )
        
        # 添付ファイル
        upload = request.files.get('file')
        if upload and upload.filename and upload.filename != 'empty':
            save_uploaded_file(upload, user, request_obj=new_request)

        redirect(f'/client/requests/{new_request.id}')
        
    ctx = get_common_context('client_requests')
    ctx.update({'sites': sites})
    return ctx

@client_app.route('/requests/<id:int>', method=['GET', 'POST'])
@login_required(role='client')
@jinja2_view('client/requests_detail.html')
def client_request_detail(id):
    user = get_current_user()
    try:
        req = Request.get_by_id(id)
    except Request.DoesNotExist:
        abort(404)
        
    if req.client.id != user.client.id:
        abort(403)
        
    if request.method == 'POST':
        check_csrf_token()
        body = request.forms.decode().get('body')
        if body:
            shared_file = None
            upload = request.files.get('file')
            if upload and upload.filename and upload.filename != 'empty':
                # クライアントからの添付は常に可視
                shared_file, error = save_uploaded_file(upload, user, request_obj=req)

            RequestMessage.create(
                request=req,
                author_user=user,
                author_role='client',
                body=body,
                shared_file=shared_file
            )
            req.updated_at = datetime.datetime.now()
            req.save()
        redirect(f'/client/requests/{id}')
            
    initial_files = SharedFile.select().where(
        SharedFile.request == req,
        SharedFile.id.not_in(
            RequestMessage.select(RequestMessage.shared_file).where(RequestMessage.shared_file.is_null(False))
        )
    )
    
    ctx = get_common_context('client_requests')
    ctx.update({
        'request': req, 
        'initial_files': initial_files,
        'generate_file_token': generate_file_token, 
        'SharedFile': SharedFile, 
        'RequestMessage': RequestMessage
    })
    return ctx
