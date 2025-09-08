from app import db
from datetime import datetime
from app.utils.timezone import get_current_beijing_time

class URLCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=False)
    
    # 基本检查结果
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)
    is_available = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)
    checked_at = db.Column(db.DateTime, default=get_current_beijing_time)
    
    # 详细检查结果
    response_size = db.Column(db.Integer)  # 响应大小（字节）
    response_headers = db.Column(db.Text)  # 响应头（JSON格式）
    response_content = db.Column(db.Text)  # 响应内容（截取前1000字符）
    
    # 验证结果
    status_code_valid = db.Column(db.Boolean)  # 状态码是否有效
    response_time_valid = db.Column(db.Boolean)  # 响应时间是否在阈值内
    content_valid = db.Column(db.Boolean)  # 内容验证是否通过
    ssl_valid = db.Column(db.Boolean)  # SSL证书是否有效
    
    # 重试信息
    retry_count = db.Column(db.Integer, default=0)  # 实际重试次数
    final_url = db.Column(db.String(500))  # 最终URL（考虑重定向）
    
    # 性能指标
    dns_time = db.Column(db.Float)  # DNS解析时间
    connect_time = db.Column(db.Float)  # 连接时间
    transfer_time = db.Column(db.Float)  # 传输时间
    
    def __repr__(self):
        return f'<URLCheck {self.url_id} at {self.checked_at}>'

class DomainAccessCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), nullable=False)
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)
    is_accessible = db.Column(db.Boolean, nullable=True)
    error_message = db.Column(db.Text)
    checked_at = db.Column(db.DateTime, default=get_current_beijing_time)
    
    def __repr__(self):
        return f'<DomainAccessCheck {self.domain_id}>'

class WhoisRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), nullable=False)
    registrar = db.Column(db.String(255))
    creation_date = db.Column(db.DateTime)
    expiration_date = db.Column(db.DateTime)
    updated_date = db.Column(db.DateTime)
    status = db.Column(db.String(255))
    name_servers = db.Column(db.Text)
    days_until_expiry = db.Column(db.Integer)
    last_checked = db.Column(db.DateTime, default=get_current_beijing_time)
    
    # 新增字段
    whois_server = db.Column(db.String(255))  # 使用的WHOIS服务器
    error_message = db.Column(db.Text)  # 错误信息
    is_valid = db.Column(db.Boolean, default=True)  # 查询是否成功
    raw_data = db.Column(db.Text)  # 原始WHOIS数据
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expiration_date if self.expiration_date else True
    
    @property
    def is_expiring_soon(self):
        if not self.expiration_date:
            return True
        days_left = (self.expiration_date - datetime.utcnow()).days
        return days_left <= 30

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))  # 'cert_expiry', 'url_down', 'whois_expiry', 'domain_inaccessible'
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), nullable=True)
    url_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=True)
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    domain = db.relationship('Domain', backref='notifications')
    url = db.relationship('URL', backref='notifications')

class NotificationConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50))  # 'webhook', 'wechat_bot'
    webhook_url = db.Column(db.String(500))
    wechat_bot_key = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<NotificationConfig {self.name}>'
