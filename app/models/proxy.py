from app import db
from datetime import datetime

class Proxy(db.Model):
    __tablename__ = 'proxies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='代理名称')
    type = db.Column(db.String(20), nullable=False, comment='代理类型：http, https, socks4, socks5')
    host = db.Column(db.String(255), nullable=False, comment='代理主机地址')
    port = db.Column(db.Integer, nullable=False, comment='代理端口')
    username = db.Column(db.String(100), comment='代理用户名')
    password = db.Column(db.String(100), comment='代理密码')
    description = db.Column(db.Text, comment='代理描述')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    is_default = db.Column(db.Boolean, default=False, comment='是否默认代理')
    last_checked = db.Column(db.DateTime, comment='最后检查时间')
    is_working = db.Column(db.Boolean, default=None, comment='代理是否正常工作，None表示未测试')
    response_time = db.Column(db.Float, comment='响应时间（毫秒）')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联URL监控
    url_checks = db.relationship('URL', back_populates='proxy', lazy='dynamic')
    
    def __repr__(self):
        return f'<Proxy {self.name} ({self.type}://{self.host}:{self.port})>'
    
    @property
    def proxy_url(self):
        """获取代理URL"""
        if self.username and self.password:
            return f"{self.type}://{self.username}:{self.password}@{self.host}:{self.port}"
        else:
            return f"{self.type}://{self.host}:{self.port}"
    
    @property
    def proxy_dict(self):
        """获取代理字典格式（用于requests库）"""
        proxy_dict = {}
        if self.type in ['http', 'https']:
            proxy_dict[self.type] = self.proxy_url
        elif self.type in ['socks4', 'socks5']:
            # SOCKS代理需要特殊处理
            if self.username and self.password:
                proxy_dict['http'] = f"socks{self.type[-1]}://{self.username}:{self.password}@{self.host}:{self.port}"
                proxy_dict['https'] = f"socks{self.type[-1]}://{self.username}:{self.password}@{self.host}:{self.port}"
            else:
                proxy_dict['http'] = f"socks{self.type[-1]}://{self.host}:{self.port}"
                proxy_dict['https'] = f"socks{self.type[-1]}://{self.host}:{self.port}"
        return proxy_dict
    
    @property
    def status_display(self):
        """获取状态显示文本"""
        if not self.is_active:
            return "已禁用"
        elif self.is_working is None:
            return "未知"
        elif not self.is_working:
            return "异常"
        else:
            return "正常"
    
    @property
    def status_badge_class(self):
        """获取状态徽章样式类"""
        if not self.is_active:
            return "bg-secondary"
        elif self.is_working is None:
            return "bg-warning"
        elif not self.is_working:
            return "bg-danger"
        else:
            return "bg-success"
    
    @property
    def type_display(self):
        """获取代理类型显示文本"""
        type_map = {
            'http': 'HTTP',
            'https': 'HTTPS',
            'socks4': 'SOCKS4',
            'socks5': 'SOCKS5'
        }
        return type_map.get(self.type, self.type.upper())
