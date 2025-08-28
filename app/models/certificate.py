from app import db
from datetime import datetime, timedelta
from flask import current_app

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.id'), nullable=False)
    issuer = db.Column(db.String(255))
    subject = db.Column(db.String(255))
    serial_number = db.Column(db.String(255))
    not_before = db.Column(db.DateTime)
    not_after = db.Column(db.DateTime)
    days_until_expiry = db.Column(db.Integer)
    is_valid = db.Column(db.Boolean, default=True)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 证书文件存储
    cert_file_path = db.Column(db.String(500))  # 证书文件路径
    key_file_path = db.Column(db.String(500))   # 私钥文件路径
    cert_file_name = db.Column(db.String(255))  # 证书文件名
    key_file_name = db.Column(db.String(255))   # 私钥文件名
    
    # 证书域名信息
    cert_domains = db.Column(db.Text)  # 证书中包含的域名列表，JSON格式存储
    common_name = db.Column(db.String(255))  # 证书的通用名称
    san_domains = db.Column(db.Text)  # 主题备用名称(SAN)域名列表，JSON格式存储
    
    def __repr__(self):
        return f'<Certificate {self.subject}>'
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.not_after if self.not_after else True
    
    @property
    def is_expiring_soon(self):
        if self.not_after:
            return datetime.utcnow() + timedelta(days=current_app.config['NOTIFICATION_DAYS_BEFORE']) > self.not_after
        return False
    
    @property
    def domain_list(self):
        """获取证书中的域名列表"""
        import json
        domains = []
        
        # 添加通用名称
        if self.common_name:
            domains.append(self.common_name)
        
        # 添加SAN域名
        if self.san_domains:
            try:
                san_list = json.loads(self.san_domains)
                if isinstance(san_list, list):
                    domains.extend(san_list)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # 如果没有解析出域名，尝试从cert_domains字段获取
        if not domains and self.cert_domains:
            try:
                cert_domains_list = json.loads(self.cert_domains)
                if isinstance(cert_domains_list, list):
                    domains.extend(cert_domains_list)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return list(set(domains))  # 去重
    
    @property
    def domain_match_status(self):
        """检查证书域名是否与关联的域名匹配"""
        if not self.domain_list:
            return "unknown"
        
        domain_obj = self.domain
        if not domain_obj:
            return "unknown"
        
        # 检查域名是否在证书域名列表中
        domain_name = domain_obj.name.lower()
        cert_domains = [d.lower() for d in self.domain_list]
        
        # 精确匹配
        if domain_name in cert_domains:
            return "exact"
        
        # 通配符匹配
        for cert_domain in cert_domains:
            if cert_domain.startswith('*.'):
                wildcard_domain = cert_domain[2:]  # 去掉 *.
                if domain_name.endswith('.' + wildcard_domain):
                    return "wildcard"
        
        return "mismatch"
