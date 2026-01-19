from peewee import *
import datetime
from settings import DB_PATH, READ_ONLY_MODE

db = Proxy()

def set_db(database):
    db.initialize(database)

class BaseModel(Model):
    class Meta:
        database = db
    
    def save(self, *args, **kwargs):
        import settings
        if getattr(settings, 'READ_ONLY_MODE', False):
            raise Exception("Database is in read-only mode.")
        return super(BaseModel, self).save(*args, **kwargs)

    @classmethod
    def create(cls, **query):
        import settings
        if getattr(settings, 'READ_ONLY_MODE', False):
            raise Exception("Database is in read-only mode.")
        return super(BaseModel, cls).create(**query)

class Client(BaseModel):
    name = CharField()
    display_name = CharField()
    client_memo = TextField(null=True)
    internal_memo = TextField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(BaseModel, self).save(*args, **kwargs)

class User(BaseModel):
    email = CharField(unique=True)
    password_hash = CharField()
    role = CharField()  # 'admin' or 'client'
    client = ForeignKeyField(Client, backref='users', null=True)
    is_active = BooleanField(default=True)
    last_login_at = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

class Site(BaseModel):
    client = ForeignKeyField(Client, backref='sites')
    name = CharField()
    url = CharField(null=True)
    contract_type = CharField(null=True)
    contract_start_date = DateField(null=True)
    contract_end_date = DateField(null=True)
    renewal_date = DateField(null=True)
    domain_expire_date = DateField(null=True)
    ssl_expire_date = DateField(null=True)
    client_note = TextField(null=True)
    internal_note = TextField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(BaseModel, self).save(*args, **kwargs)

class MaintenanceLog(BaseModel):
    site = ForeignKeyField(Site, backref='logs')
    performed_at = DateField()
    category = CharField()
    summary = CharField()
    details = TextField(null=True)
    internal_note = TextField(null=True)
    is_visible_to_client = BooleanField(default=True)
    is_important = BooleanField(default=False)
    created_by = ForeignKeyField(User, backref='logs', null=True)
    related_request = DeferredForeignKey('Request', backref='maintenance_logs', null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(MaintenanceLog, self).save(*args, **kwargs)

class Request(BaseModel):
    client = ForeignKeyField(Client, backref='requests')
    site = ForeignKeyField(Site, backref='requests', null=True)  # null = 全体
    subject = CharField()
    body = TextField()
    priority = CharField(default='normal')  # normal, high
    status = CharField(default='new')  # new, in_progress, done
    internal_note = TextField(null=True)
    created_by = ForeignKeyField(User, backref='requests')
    assigned_to = ForeignKeyField(User, backref='assigned_requests', null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(Request, self).save(*args, **kwargs)

class RequestMessage(BaseModel):
    request = ForeignKeyField(Request, backref='messages')
    author_user = ForeignKeyField(User, backref='request_messages')
    author_role = CharField()  # admin, client
    body = TextField()
    shared_file = DeferredForeignKey('SharedFile', backref='request_messages', null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

class LogTemplate(BaseModel):
    name = CharField()
    category = CharField()
    summary = CharField()
    details = TextField(null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(LogTemplate, self).save(*args, **kwargs)

class DisplayLabel(BaseModel):
    key = CharField(unique=True)
    value = CharField()

class AppSetting(BaseModel):
    key = CharField(unique=True)
    value = TextField()
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(AppSetting, self).save(*args, **kwargs)

class Notice(BaseModel):
    site = ForeignKeyField(Site, backref='notices')
    title = CharField()
    body = TextField()
    start_date = DateField(null=True)
    end_date = DateField(null=True)
    is_visible_to_client = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(Notice, self).save(*args, **kwargs)

class SharedFile(BaseModel):
    site = ForeignKeyField(Site, backref='shared_files', null=True)
    request = ForeignKeyField(Request, backref='shared_files', null=True)
    uploaded_by = ForeignKeyField(User, backref='uploaded_files')
    title = CharField()
    description = TextField(null=True)
    category = CharField(null=True)
    original_filename = CharField()
    stored_path = CharField()
    size_bytes = IntegerField()
    content_type = CharField(null=True)
    client_visible = BooleanField(default=True)
    is_deleted = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super(SharedFile, self).save(*args, **kwargs)

def init_db():
    db.connect()
    db.create_tables([User, Client, Site, MaintenanceLog, Notice, LogTemplate, DisplayLabel, AppSetting, Request, RequestMessage, SharedFile])
