import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.models.notification import Notification, NotificationConfig
from app import db
from flask import current_app

class Notifier:
    @staticmethod
    def send_webhook_notification(message, webhook_url):
        """发送Webhook通知"""
        try:
            payload = {
                "text": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"发送Webhook通知失败: {str(e)}")
            return False
    
    @staticmethod
    def send_wechat_bot_notification(message, bot_key):
        """发送企业微信机器人通知"""
        try:
            webhook_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={bot_key}"
            
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"发送企业微信机器人通知失败: {str(e)}")
            return False
    
    @staticmethod
    def send_notification_to_config(message, config):
        """发送通知到指定的配置"""
        if config.type == 'webhook' and config.webhook_url:
            return Notifier.send_webhook_notification(message, config.webhook_url)
        elif config.type == 'wechat_bot' and config.wechat_bot_key:
            return Notifier.send_wechat_bot_notification(message, config.wechat_bot_key)
        return False
    
    @staticmethod
    def send_notification_to_all_channels(message):
        """发送通知到所有配置的渠道"""
        configs = NotificationConfig.query.filter_by(is_active=True).all()
        
        for config in configs:
            Notifier.send_notification_to_config(message, config)
    
    @staticmethod
    def send_certificate_expiry_notification(domain, certificate):
        """发送证书到期通知"""
        days_left = certificate.days_until_expiry
        
        message = f"""
SSL证书到期提醒
域名: {domain.name}
证书主题: {certificate.subject}
到期时间: {certificate.not_after}
剩余天数: {days_left}天

请及时更新SSL证书以避免服务中断。
        """
        
        # 保存通知记录
        notification = Notification(
            type='cert_expiry',
            domain_id=domain.id,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
        
        # 如果域名配置了特定通知方式，使用该配置；否则发送到所有渠道
        if domain.notification_config:
            Notifier.send_notification_to_config(message, domain.notification_config)
        else:
            Notifier.send_notification_to_all_channels(message)
    
    @staticmethod
    def send_whois_expiry_notification(domain, whois_record):
        """发送WHOIS到期通知"""
        days_left = whois_record.days_until_expiry
        
        message = f"""
域名到期提醒
域名: {domain.name}
注册商: {whois_record.registrar}
到期时间: {whois_record.expiration_date}
剩余天数: {days_left}天

请及时续费域名以避免域名失效。
        """
        
        # 保存通知记录
        notification = Notification(
            type='whois_expiry',
            domain_id=domain.id,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
        
        # 如果域名配置了特定通知方式，使用该配置；否则发送到所有渠道
        if domain.notification_config:
            Notifier.send_notification_to_config(message, domain.notification_config)
        else:
            Notifier.send_notification_to_all_channels(message)
    
    @staticmethod
    def send_domain_access_notification(domain, access_check):
        """发送域名访问检查通知"""
        message = f"""
域名访问异常提醒
域名: {domain.name}
检查时间: {access_check.checked_at}
错误信息: {access_check.error_message}

域名HTTPS访问出现异常，请检查域名解析和服务器状态。
        """
        
        # 保存通知记录
        notification = Notification(
            type='domain_inaccessible',
            domain_id=domain.id,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
        
        # 如果域名配置了特定通知方式，使用该配置；否则发送到所有渠道
        if domain.notification_config:
            Notifier.send_notification_to_config(message, domain.notification_config)
        else:
            Notifier.send_notification_to_all_channels(message)
    
    @staticmethod
    def send_url_check_notification(url_obj, check_result):
        """发送URL检查通知（支持新的监控功能）"""
        # 构建详细的通知消息
        status_text = "正常" if check_result['is_available'] else "异常"
        
        message = f"""
URL监控异常提醒
监控名称: {url_obj.name}
URL: {url_obj.url}
检查时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
监控状态: {status_text}

请求信息:
- 请求方法: {url_obj.method}
- 超时设置: {url_obj.timeout}秒
- 重试次数: {check_result['retry_count']}

响应信息:
- 状态码: {check_result['status_code']}
- 响应时间: {check_result['response_time']:.2f}秒
- 响应大小: {check_result['response_size']}字节
- 最终URL: {check_result['final_url']}

验证结果:
- 状态码验证: {'通过' if check_result['status_code_valid'] else '失败'}
- 响应时间验证: {'通过' if check_result['response_time_valid'] else '失败'}
- 内容验证: {'通过' if check_result['content_valid'] else '失败'}
- SSL验证: {'通过' if check_result['ssl_valid'] else '失败'}

配置要求:
- 期望状态码: {url_obj.expected_status_codes}
- 响应时间阈值: {url_obj.response_time_threshold}秒
- 期望包含内容: {url_obj.expected_response_contains or '无'}
- 期望不包含内容: {url_obj.expected_response_not_contains or '无'}
"""
        
        if check_result['error_message']:
            message += f"\n错误信息: {check_result['error_message']}"
        
        # 保存通知记录
        notification = Notification(
            type='url_monitor_down',
            url_id=url_obj.id,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
        
        # 如果URL配置了特定通知方式，使用该配置；否则发送到所有渠道
        if url_obj.notification_config:
            Notifier.send_notification_to_config(message, url_obj.notification_config)
        else:
            Notifier.send_notification_to_all_channels(message)
