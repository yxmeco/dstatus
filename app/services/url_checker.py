import requests
import json
import time
from datetime import datetime
from app.models.url import URL
from app.models.notification import URLCheck, Notification, NotificationConfig
from app import db
from app.utils.timezone import get_current_beijing_time

class URLChecker:
    """URL监控检查器，参考Uptime Kuma功能"""
    
    @staticmethod
    def check_single_url(url_id):
        """检查单个URL"""
        url_obj = URL.query.get(url_id)
        if not url_obj or not url_obj.is_active:
            return
        
        # 执行检查
        result = URLChecker._perform_check(url_obj)
        
        # 保存检查结果
        URLChecker._save_check_result(url_obj, result)
        
        # 发送通知（如果需要）
        if result['is_available'] == False and url_obj.notification_config:
            URLChecker._send_notification(url_obj, result)
    
    @staticmethod
    def check_all_urls():
        """检查所有活跃的URL"""
        urls = URL.query.filter_by(is_active=True).all()
        for url_obj in urls:
            try:
                URLChecker.check_single_url(url_obj.id)
            except Exception as e:
                print(f"检查URL失败 {url_obj.name}: {str(e)}")
    
    @staticmethod
    def _perform_check(url_obj):
        """执行URL检查"""
        result = {
            'status_code': None,
            'response_time': None,
            'is_available': False,
            'error_message': None,
            'response_size': 0,
            'response_headers': {},
            'response_content': '',
            'status_code_valid': False,
            'response_time_valid': False,
            'content_valid': False,
            'ssl_valid': False,
            'retry_count': 0,
            'final_url': url_obj.url,
            'dns_time': None,
            'connect_time': None,
            'transfer_time': None
        }
        
        # 准备请求参数
        headers = url_obj.headers_dict.copy()
        if url_obj.method.upper() in ['POST', 'PUT', 'PATCH'] and url_obj.body:
            headers['Content-Type'] = url_obj.content_type
        
        # 准备请求数据
        data = None
        json_data = None
        if url_obj.method.upper() in ['POST', 'PUT', 'PATCH'] and url_obj.body:
            if url_obj.content_type == 'application/json':
                try:
                    json_data = json.loads(url_obj.body)
                except json.JSONDecodeError:
                    data = url_obj.body
            else:
                data = url_obj.body
        
        # 准备代理配置
        proxies = {}
        if url_obj.proxy and url_obj.proxy.is_active and url_obj.proxy.is_working:
            proxies = url_obj.proxy.proxy_dict
        
        # 执行请求（支持重试）
        for attempt in range(url_obj.retry_count + 1):
            try:
                start_time = time.time()
                
                response = requests.request(
                    method=url_obj.method.upper(),
                    url=url_obj.url,
                    headers=headers,
                    data=data,
                    json=json_data,
                    proxies=proxies,
                    timeout=url_obj.timeout,
                    allow_redirects=url_obj.follow_redirects,
                    verify=url_obj.verify_ssl,
                    stream=True  # 流式传输以获取性能指标
                )
                
                # 获取响应时间
                end_time = time.time()
                response_time = end_time - start_time
                
                # 读取响应内容
                response_content = ''
                response_size = 0
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        response_size += len(chunk)
                        if len(response_content) < 1000:  # 只保存前1000字符
                            response_content += chunk.decode('utf-8', errors='ignore')
                
                # 更新结果
                result.update({
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'response_size': response_size,
                    'response_headers': dict(response.headers),
                    'response_content': response_content,
                    'final_url': response.url,
                    'retry_count': attempt
                })
                
                # 验证结果
                result.update(URLChecker._validate_response(url_obj, result))
                
                # 如果验证通过，标记为可用
                if result['status_code_valid'] and result['response_time_valid'] and result['content_valid']:
                    result['is_available'] = True
                    break
                else:
                    result['is_available'] = False
                    if attempt < url_obj.retry_count:
                        time.sleep(1)  # 重试前等待1秒
                        continue
                    else:
                        break
                        
            except requests.exceptions.SSLError as e:
                result['error_message'] = f"SSL证书错误: {str(e)}"
                result['ssl_valid'] = False
                if attempt < url_obj.retry_count:
                    time.sleep(1)
                    continue
                break
                
            except requests.exceptions.Timeout as e:
                result['error_message'] = f"请求超时: {str(e)}"
                if attempt < url_obj.retry_count:
                    time.sleep(1)
                    continue
                break
                
            except requests.exceptions.ConnectionError as e:
                result['error_message'] = f"连接错误: {str(e)}"
                if attempt < url_obj.retry_count:
                    time.sleep(1)
                    continue
                break
                
            except Exception as e:
                result['error_message'] = f"请求失败: {str(e)}"
                if attempt < url_obj.retry_count:
                    time.sleep(1)
                    continue
                break
        
        return result
    
    @staticmethod
    def _validate_response(url_obj, result):
        """验证响应结果"""
        validation_result = {
            'status_code_valid': False,
            'response_time_valid': False,
            'content_valid': False,
            'ssl_valid': True
        }
        
        # 验证状态码
        if result['status_code'] in url_obj.expected_status_codes_list:
            validation_result['status_code_valid'] = True
        
        # 验证响应时间
        if result['response_time'] and result['response_time'] <= url_obj.response_time_threshold:
            validation_result['response_time_valid'] = True
        
        # 验证响应内容
        if url_obj.expected_response_contains or url_obj.expected_response_not_contains:
            content = result['response_content'].lower()
            
            # 检查必须包含的内容
            if url_obj.expected_response_contains:
                expected_contains = url_obj.expected_response_contains.lower()
                if expected_contains in content:
                    validation_result['content_valid'] = True
                else:
                    validation_result['content_valid'] = False
                    return validation_result
            
            # 检查不能包含的内容
            if url_obj.expected_response_not_contains:
                not_contains = url_obj.expected_response_not_contains.lower()
                if not_contains not in content:
                    validation_result['content_valid'] = True
                else:
                    validation_result['content_valid'] = False
                    return validation_result
            
            # 如果只有内容验证，默认通过
            if not url_obj.expected_response_contains and not url_obj.expected_response_not_contains:
                validation_result['content_valid'] = True
        else:
            # 没有内容验证要求，默认通过
            validation_result['content_valid'] = True
        
        return validation_result
    
    @staticmethod
    def _save_check_result(url_obj, result):
        """保存检查结果到数据库"""
        url_check = URLCheck(
            url_id=url_obj.id,
            status_code=result['status_code'],
            response_time=result['response_time'],
            is_available=result['is_available'],
            error_message=result['error_message'],
            response_size=result['response_size'],
            response_headers=json.dumps(result['response_headers']) if result['response_headers'] else None,
            response_content=result['response_content'],
            status_code_valid=result['status_code_valid'],
            response_time_valid=result['response_time_valid'],
            content_valid=result['content_valid'],
            ssl_valid=result['ssl_valid'],
            retry_count=result['retry_count'],
            final_url=result['final_url'],
            dns_time=result['dns_time'],
            connect_time=result['connect_time'],
            transfer_time=result['transfer_time']
        )
        
        db.session.add(url_check)
        db.session.commit()

    @staticmethod
    def _send_notification(url_obj, check_result):
        """发送URL监控通知"""
        # 构建详细的通知消息
        status_text = "正常" if check_result['is_available'] else "异常"
        
        message = f"""
URL监控异常提醒
监控名称: {url_obj.name}
URL: {url_obj.url}
检查时间: {get_current_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}
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
        
        # 发送通知到配置的渠道
        if url_obj.notification_config:
            URLChecker._send_notification_to_config(message, url_obj.notification_config)
    
    @staticmethod
    def _send_notification_to_config(message, config):
        """发送通知到指定配置"""
        try:
            if config.type == 'webhook' and config.webhook_url:
                payload = {
                    "text": message,
                    "timestamp": get_current_beijing_time().isoformat()
                }
                requests.post(
                    config.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
            elif config.type == 'wechat_bot' and config.wechat_bot_key:
                webhook_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={config.wechat_bot_key}"
                payload = {
                    "msgtype": "text",
                    "text": {"content": message}
                }
                requests.post(
                    webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
        except Exception as e:
            print(f"发送通知失败: {str(e)}")

# 保持向后兼容的函数
def check_single_url(url_id):
    """检查单个URL（向后兼容）"""
    URLChecker.check_single_url(url_id)

def check_all_urls():
    """检查所有URL（向后兼容）"""
    URLChecker.check_all_urls()
