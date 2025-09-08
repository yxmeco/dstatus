from app import db
from app.models.domain import Domain
from app.models.url import URL
from app.services.ssl_checker import check_all_certificates
from app.services.url_checker import check_all_urls
from app.services.whois_checker import check_all_whois
from app.services.domain_access_checker import check_all_domain_access
from app.services.notifier import Notifier
from datetime import datetime, timedelta
from flask import current_app

def check_all_certificates_job():
    """检查所有域名的SSL证书"""
    with current_app.app_context():
        try:
            check_all_certificates()
            print(f"[{datetime.utcnow()}] SSL证书检查完成")
        except Exception as e:
            print(f"[{datetime.utcnow()}] SSL证书检查失败: {str(e)}")

def check_all_urls_job():
    """检查所有URL的可用性"""
    with current_app.app_context():
        try:
            check_all_urls()
            print(f"[{datetime.utcnow()}] URL可用性检查完成")
        except Exception as e:
            print(f"[{datetime.utcnow()}] URL可用性检查失败: {str(e)}")

def check_all_whois_job():
    """检查所有域名的WHOIS信息"""
    with current_app.app_context():
        try:
            check_all_whois()
            print(f"[{datetime.utcnow()}] WHOIS检查完成")
        except Exception as e:
            print(f"[{datetime.utcnow()}] WHOIS检查失败: {str(e)}")

def check_all_domain_access_job():
    """检查所有域名的访问状态（备用功能）"""
    with current_app.app_context():
        try:
            check_all_domain_access()
            print(f"[{datetime.utcnow()}] 域名访问检查完成")
        except Exception as e:
            print(f"[{datetime.utcnow()}] 域名访问检查失败: {str(e)}")

def send_daily_notifications_job():
    """发送每日通知汇总"""
    with current_app.app_context():
        try:
            # 获取今日统计信息
            today = datetime.utcnow().date()
            start_time = datetime.combine(today, datetime.min.time())
            end_time = datetime.combine(today, datetime.max.time())
            
            # 统计今日检查的域名数量
            domains_checked = Domain.query.filter(
                Domain.updated_at >= start_time,
                Domain.updated_at <= end_time
            ).count()
            
            # 统计今日检查的URL数量
            from app.models.notification import URLCheck
            urls_checked = URLCheck.query.filter(
                URLCheck.checked_at >= start_time,
                URLCheck.checked_at <= end_time
            ).count()
            
            # 统计今日异常数量
            from app.models.notification import Notification
            today_notifications = Notification.query.filter(
                Notification.sent_at >= start_time,
                Notification.sent_at <= end_time
            ).count()
            
            # 发送每日汇总通知
            if domains_checked > 0 or urls_checked > 0:
                summary_message = f"""
每日监控汇总报告
时间: {today.strftime('%Y-%m-%d')}

检查统计:
- 域名检查: {domains_checked} 个
- URL检查: {urls_checked} 个
- 异常通知: {today_notifications} 条

系统运行正常，请关注异常通知。
                """
                
                Notifier.send_notification_to_all_channels(summary_message)
                print(f"[{datetime.utcnow()}] 每日通知汇总发送完成")
            
        except Exception as e:
            print(f"[{datetime.utcnow()}] 每日通知汇总发送失败: {str(e)}")
