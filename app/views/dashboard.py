from flask import Blueprint, render_template
from app.models.domain import Domain
from app.models.url import URL
from app.models.certificate import Certificate
from app.models.notification import URLCheck, WhoisRecord, Notification
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def index():
    # 域名统计
    total_domains = Domain.query.count()
    
    # 根据WHOIS状态统计域名
    known_domains = 0
    unknown_domains = 0
    expiring_domains = 0
    
    domains = Domain.query.all()
    for domain in domains:
        if domain.status == "unknown":
            unknown_domains += 1
        else:
            known_domains += 1
            if domain.status in ["expiring_soon", "expired"]:
                expiring_domains += 1
    
    # URL统计
    total_urls = URL.query.count()
    
    # 证书统计
    expiring_certs = Certificate.query.filter(
        Certificate.not_after <= datetime.utcnow() + timedelta(days=30),
        Certificate.is_valid == True
    ).count()
    
    # WHOIS统计
    expiring_whois = WhoisRecord.query.filter(
        WhoisRecord.expiration_date <= datetime.utcnow() + timedelta(days=30),
        WhoisRecord.is_valid == True
    ).count()
    
    # URL监控统计 - 修复异常URL监控统计逻辑
    # 统计当前状态为异常的URL监控数量
    unavailable_urls = 0
    urls = URL.query.filter_by(is_active=True).all()
    for url in urls:
        if url.url_checks and not url.url_checks[-1].is_available:
            unavailable_urls += 1
    
    # 最近通知
    recent_notifications = Notification.query.order_by(
        Notification.sent_at.desc()
    ).limit(10).all()
    
    # 即将到期的证书
    expiring_certificates = Certificate.query.filter(
        Certificate.not_after <= datetime.utcnow() + timedelta(days=30),
        Certificate.is_valid == True
    ).order_by(Certificate.not_after).limit(5).all()
    
    # 即将到期的WHOIS
    expiring_whois_records = WhoisRecord.query.filter(
        WhoisRecord.expiration_date <= datetime.utcnow() + timedelta(days=30),
        WhoisRecord.is_valid == True
    ).order_by(WhoisRecord.expiration_date).limit(5).all()
    
    # 状态统计
    status_stats = {
        'active': 0,
        'expiring_soon': 0,
        'expired': 0,
        'unknown': 0
    }
    
    for domain in domains:
        status_stats[domain.status] += 1
    
    return render_template('dashboard/index.html',
                         total_domains=total_domains,
                         known_domains=known_domains,
                         unknown_domains=unknown_domains,
                         expiring_domains=expiring_domains,
                         total_urls=total_urls,
                         expiring_certs=expiring_certs,
                         expiring_whois=expiring_whois,
                         unavailable_urls=unavailable_urls,
                         recent_notifications=recent_notifications,
                         expiring_certificates=expiring_certificates,
                         expiring_whois_records=expiring_whois_records,
                         status_stats=status_stats)
