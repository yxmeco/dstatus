import ssl
import socket
from OpenSSL import SSL
from datetime import datetime
from app.models.certificate import Certificate
from app.models.domain import Domain
from app import db
from app.services.notifier import Notifier
from flask import current_app

class SSLChecker:
    @staticmethod
    def get_certificate_info(domain_name, port=443):
        """获取SSL证书信息"""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain_name, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain_name) as ssock:
                    cert = ssock.getpeercert()
                    
                    return {
                        'issuer': dict(x[0] for x in cert['issuer']),
                        'subject': dict(x[0] for x in cert['subject']),
                        'serial_number': cert['serialNumber'],
                        'not_before': datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z'),
                        'not_after': datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z'),
                        'is_valid': True
                    }
        except Exception as e:
            return {
                'error': str(e),
                'is_valid': False
            }
    
    @staticmethod
    def update_certificate_info(domain):
        """更新域名的SSL证书信息"""
        # 首先创建或更新证书记录，标记为查询中
        certificate = Certificate.query.filter_by(domain_id=domain.id).first()
        if not certificate:
            certificate = Certificate(domain_id=domain.id)
        
        # 标记为查询中状态
        certificate.last_checked = datetime.utcnow()
        certificate.is_valid = False  # 暂时标记为无效，表示正在查询
        
        db.session.add(certificate)
        db.session.commit()
        
        # 执行实际的SSL证书查询
        cert_info = SSLChecker.get_certificate_info(domain.name)
        
        if cert_info.get('is_valid'):
            # 计算剩余天数 - 修复时区问题
            not_after = cert_info['not_after']
            current_time = datetime.utcnow()
            
            # 如果not_after是naive，将其转换为aware（假设为UTC）
            if not_after.tzinfo is None:
                import pytz
                not_after = pytz.UTC.localize(not_after)
                current_time = pytz.UTC.localize(current_time)
            
            days_until_expiry = (not_after - current_time).days
            
            # 更新证书信息
            certificate.issuer = str(cert_info['issuer'])
            certificate.subject = str(cert_info['subject'])
            certificate.serial_number = cert_info['serial_number']
            certificate.not_before = cert_info['not_before']
            certificate.not_after = cert_info['not_after']
            certificate.days_until_expiry = days_until_expiry
            certificate.is_valid = True
            certificate.last_checked = datetime.utcnow()
            
            db.session.add(certificate)
            db.session.commit()
            
            # 检查是否需要发送通知
            if certificate.is_expiring_soon:
                Notifier.send_certificate_expiry_notification(domain, certificate)
            
            return certificate
        else:
            # 记录错误信息
            certificate.last_checked = datetime.utcnow()
            certificate.is_valid = False
            
            db.session.add(certificate)
            db.session.commit()
            
            return None

def check_all_certificates():
    """检查所有域名的SSL证书"""
    from app import create_app
    app = create_app()
    with app.app_context():
        domains = Domain.query.filter_by(is_active=True, check_ssl=True).all()
        
        for domain in domains:
            try:
                SSLChecker.update_certificate_info(domain)
            except Exception as e:
                print(f"检查SSL证书失败 {domain.name}: {str(e)}")

def check_single_certificate(domain_id):
    """检查单个域名的SSL证书"""
    from app import create_app
    app = create_app()
    with app.app_context():
        domain = Domain.query.get(domain_id)
        if domain and domain.is_active and domain.check_ssl:
            try:
                SSLChecker.update_certificate_info(domain)
            except Exception as e:
                print(f"检查SSL证书失败 {domain.name}: {str(e)}")
