import requests
import time
from datetime import datetime
from app.models.notification import DomainAccessCheck
from app.models.domain import Domain
from app import db
from app.services.notifier import Notifier
from app.utils.timezone import get_current_beijing_time

class DomainAccessChecker:
    @staticmethod
    def check_domain_access(domain_name, timeout=30):
        """检查域名HTTPS可访问性"""
        url = f"https://{domain_name}"
        
        try:
            start_time = time.time()
            response = requests.get(
                url, 
                timeout=timeout, 
                allow_redirects=True,
                verify=True
            )
            response_time = time.time() - start_time
            
            return {
                'is_accessible': True,
                'status_code': response.status_code,
                'response_time': round(response_time, 3),
                'error_message': None
            }
            
        except requests.exceptions.SSLError as e:
            return {
                'is_accessible': False,
                'status_code': None,
                'response_time': None,
                'error_message': f"SSL错误: {str(e)}"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                'is_accessible': False,
                'status_code': None,
                'response_time': None,
                'error_message': f"连接错误: {str(e)}"
            }
        except requests.exceptions.Timeout as e:
            return {
                'is_accessible': False,
                'status_code': None,
                'response_time': None,
                'error_message': "超时"
            }
        except requests.exceptions.RequestException as e:
            return {
                'is_accessible': False,
                'status_code': None,
                'response_time': None,
                'error_message': f"请求错误: {str(e)}"
            }
        except Exception as e:
            return {
                'is_accessible': False,
                'status_code': None,
                'response_time': None,
                'error_message': f"未知错误: {str(e)}"
            }
    
    @staticmethod
    def update_domain_access_record(domain):
        """更新域名的访问检查记录"""
        access_info = DomainAccessChecker.check_domain_access(domain.name)
        
        # 查找现有的访问检查记录，如果没有则创建新的
        access_check = DomainAccessCheck.query.filter_by(domain_id=domain.id).first()
        if not access_check:
            access_check = DomainAccessCheck(domain_id=domain.id)
        
        # 更新访问检查记录
        access_check.status_code = access_info['status_code']
        access_check.response_time = access_info['response_time']
        access_check.is_accessible = access_info['is_accessible']
        access_check.error_message = access_info['error_message']
        access_check.checked_at = get_current_beijing_time()
        
        db.session.add(access_check)
        db.session.commit()
        
        # 如果不可访问且配置了通知，发送通知
        if not access_info['is_accessible']:
            # 重新获取domain对象以确保在正确的会话中
            current_domain = Domain.query.get(domain.id)
            if current_domain and current_domain.notification_config:
                Notifier.send_domain_access_notification(current_domain, access_check)
        
        return access_check

def check_all_domain_access():
    """检查所有启用访问检查的域名"""
    domains = Domain.query.filter_by(is_active=True, check_access=True).all()
    
    for domain in domains:
        try:
            DomainAccessChecker.update_domain_access_record(domain)
        except Exception as e:
            print(f"检查域名访问失败 {domain.name}: {str(e)}")

def check_single_domain_access(domain_id):
    """检查单个域名的访问状态"""
    try:
        # 重新获取domain对象，确保在正确的会话中
        domain = Domain.query.get(domain_id)
        if domain and domain.is_active and domain.check_access:
            # 直接在这里执行访问检查，避免传递domain对象
            access_info = DomainAccessChecker.check_domain_access(domain.name)
            
            # 查找现有的访问检查记录，如果没有则创建新的
            access_check = DomainAccessCheck.query.filter_by(domain_id=domain.id).first()
            if not access_check:
                access_check = DomainAccessCheck(domain_id=domain.id)
            
            # 更新访问检查记录
            access_check.status_code = access_info['status_code']
            access_check.response_time = access_info['response_time']
            access_check.is_accessible = access_info['is_accessible']
            access_check.error_message = access_info['error_message']
            access_check.checked_at = get_current_beijing_time()
            
            db.session.add(access_check)
            db.session.commit()
            
            # 如果不可访问且配置了通知，发送通知
            if not access_info['is_accessible']:
                # 重新获取domain对象以确保在正确的会话中
                current_domain = Domain.query.get(domain_id)
                if current_domain and current_domain.notification_config:
                    Notifier.send_domain_access_notification(current_domain, access_check)
            
            return access_check
    except Exception as e:
        print(f"检查域名访问失败 {domain_id}: {str(e)}")
