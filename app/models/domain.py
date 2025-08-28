from app import db
from datetime import datetime

class Domain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    check_ssl = db.Column(db.Boolean, default=True)
    check_whois = db.Column(db.Boolean, default=True)
    check_access = db.Column(db.Boolean, default=False)  # 新增：访问检查
    notification_config_id = db.Column(db.Integer, db.ForeignKey('notification_config.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    certificates = db.relationship('Certificate', backref='domain', lazy=True, cascade='all, delete-orphan')
    whois_records = db.relationship('WhoisRecord', backref='domain', lazy=True, cascade='all, delete-orphan')
    access_checks = db.relationship('DomainAccessCheck', backref='domain', lazy=True, cascade='all, delete-orphan')  # 新增：访问检查记录
    notification_config = db.relationship('NotificationConfig', backref='domains')
    
    @property
    def status(self):
        """根据WHOIS信息确定域名状态"""
        if not self.whois_records:
            return "unknown"  # 未知状态
        
        whois_record = self.whois_records[0]
        if not whois_record.is_valid:
            return "unknown"  # WHOIS查询失败，状态未知
        
        if whois_record.expiration_date:
            if whois_record.is_expired:
                return "expired"  # 已过期
            elif whois_record.is_expiring_soon:
                return "expiring_soon"  # 即将到期
            else:
                return "active"  # 活跃
        else:
            return "unknown"  # 无法获取到期时间，状态未知
    
    @property
    def status_display(self):
        """状态显示文本"""
        status_map = {
            "active": "活跃",
            "expiring_soon": "即将到期",
            "expired": "已过期",
            "unknown": "未知"
        }
        return status_map.get(self.status, "未知")
    
    @property
    def status_badge_class(self):
        """状态徽章样式类"""
        status_map = {
            "active": "bg-success",
            "expiring_soon": "bg-warning",
            "expired": "bg-danger",
            "unknown": "bg-secondary"
        }
        return status_map.get(self.status, "bg-secondary")
    
    @property
    def access_status(self):
        """获取最新的访问状态"""
        if not self.access_checks:
            return "unknown"
        
        latest_check = max(self.access_checks, key=lambda x: x.checked_at)
        if latest_check.is_accessible:
            return "accessible"
        else:
            return "inaccessible"
    
    @property
    def access_status_display(self):
        """访问状态显示文本"""
        status_map = {
            "accessible": "可访问",
            "inaccessible": "不可访问",
            "unknown": "未检查"
        }
        return status_map.get(self.access_status, "未知")
    
    @property
    def access_status_badge_class(self):
        """访问状态徽章样式类"""
        status_map = {
            "accessible": "bg-success",
            "inaccessible": "bg-danger",
            "unknown": "bg-secondary"
        }
        return status_map.get(self.access_status, "bg-secondary")
    
    @property
    def latest_access_status_code(self):
        """获取最新的访问检查状态码"""
        if not self.access_checks:
            return None
        
        latest_check = max(self.access_checks, key=lambda x: x.checked_at)
        return latest_check.status_code
    
    def __repr__(self):
        return f'<Domain {self.name}>'
