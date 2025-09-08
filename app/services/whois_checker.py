import socket
import re
import os
from datetime import datetime
from app.models.notification import WhoisRecord
from app.models.domain import Domain
from app import db
from app.services.notifier import Notifier
from app.utils.timezone import get_current_beijing_time

class WhoisChecker:
    # 查询配置
    MAX_SERVERS_TO_TRY = 5  # 最多尝试5个服务器
    SOCKET_TIMEOUT = 15     # Socket超时时间（秒）
    QUERY_TIMEOUT = 60      # 整体查询超时时间（秒）- 最多1分钟
    
    # 自定义WHOIS服务器映射
    DIY_WHOIS_SERVERS = {
        ".com": ["whois.markmonitor.com", "grs-whois.hichina.com", "whois.namecheap.com", "whois.tucows.com", "whois.verisign-grs.com"],
        ".net": ["whois.markmonitor.com", "grs-whois.hichina.com", "whois.namecheap.com", "whois.tucows.com", "whois.verisign-grs.com"],
        ".org": ["whois.pir.org"],
        ".ng": ["whois.nic.net.ng"],
        ".info": ["whois.afilias.net"],
        ".biz": ["whois.biz"],
        ".name": ["whois.nic.name"],
        ".pro": ["whois.afilias.net"],
        ".coop": ["whois.nic.coop"],
        ".aero": ["whois.aero"],
        ".museum": ["whois.museum"],
        ".travel": ["whois.nic.travel"],
        ".jobs": ["whois.nic.jobs"],
        ".mobi": ["whois.dotmobiregistry.net"],
        ".cat": ["whois.cat"],
        ".tel": ["whois.nic.tel"],
        ".asia": ["whois.nic.asia"],
        ".post": ["whois.dotpostregistry.net"],
        ".xxx": ["whois.nic.xxx"],
        ".int": ["whois.iana.org"],
        ".edu": ["whois.educause.edu"],
        ".gov": ["whois.dotgov.gov"],
        ".mil": ["whois.nic.mil"],
        ".cn": ["whois.cnnic.cn", "whois.cnnic.net.cn"],
        ".jp": ["whois.jprs.jp"],
        ".kr": ["whois.krnic.kr"],
        ".uk": ["whois.nic.uk"],
        ".de": ["whois.denic.de"],
        ".fr": ["whois.nic.fr"],
        ".it": ["whois.nic.it"],
        ".es": ["whois.nic.es"],
        ".nl": ["whois.domain-registry.nl"],
        ".ru": ["whois.tcinet.ru"],
        ".br": ["whois.registro.br"],
        ".au": ["whois.auda.org.au"],
        ".ca": ["whois.cira.ca"],
        ".mx": ["whois.mx"],
        ".ar": ["whois.nic.ar"],
        ".cl": ["whois.nic.cl"],
        ".pe": ["whois.nic.pe"],
        ".co": ["whois.nic.co"],
        ".ve": ["whois.nic.ve"],
        ".uy": ["whois.nic.uy"],
        ".py": ["whois.nic.py"],
        ".bo": ["whois.nic.bo"],
        ".ec": ["whois.nic.ec"],
        ".gt": ["whois.nic.gt"],
        ".hn": ["whois.nic.hn"],
        ".ni": ["whois.nic.ni"],
        ".pa": ["whois.nic.pa"],
        ".cr": ["whois.nic.cr"],
        ".sv": ["whois.nic.sv"],
        ".bz": ["whois.nic.bz"],
        ".gy": ["whois.nic.gy"],
        ".sr": ["whois.nic.sr"],
        ".gf": ["whois.nic.gf"],
        ".pf": ["whois.nic.pf"],
        ".nc": ["whois.nic.nc"],
        ".re": ["whois.nic.re"],
        ".yt": ["whois.nic.yt"],
        ".pm": ["whois.nic.pm"],
        ".wf": ["whois.nic.wf"],
        ".tf": ["whois.nic.tf"],
        ".bl": ["whois.nic.bl"],
        ".mf": ["whois.nic.mf"],
        ".sx": ["whois.nic.sx"],
        ".cw": ["whois.nic.cw"],
        ".aw": ["whois.nic.aw"],
        ".bq": ["whois.nic.bq"],
    }
    
    # 通用备用服务器
    FALLBACK_SERVERS = [
        'whois.verisign-grs.com',
        'whois.crsnic.net',
        'whois.pir.org',
        'whois.afilias.net',
        'whois.nic.name',
        'whois.biz',
        'whois.nic.coop',
        'whois.aero',
        'whois.museum',
        'whois.nic.travel',
        'whois.nic.jobs',
        'whois.dotmobiregistry.net',
        'whois.cat',
        'whois.nic.tel',
        'whois.nic.asia',
        'whois.dotpostregistry.net',
        'whois.nic.xxx',
        'whois.iana.org',
        'whois.educause.edu',
        'whois.dotgov.gov',
        'whois.nic.mil',
    ]
    
    @staticmethod
    def get_suffix_list():
        """获取公共后缀列表"""
        # 这里可以扩展为从文件读取或在线获取
        # 暂时使用硬编码的常见后缀
        return [
            "com", "net", "org", "info", "biz", "name", "pro", "coop", "aero", 
            "museum", "travel", "jobs", "mobi", "cat", "tel", "asia", "post", 
            "xxx", "int", "edu", "gov", "mil", "cn", "jp", "kr", "uk", "de", 
            "fr", "it", "es", "nl", "ru", "br", "au", "ca", "mx", "ar", "cl", 
            "pe", "co", "ve", "uy", "py", "bo", "ec", "gt", "hn", "ni", "pa", 
            "cr", "sv", "bz", "gy", "sr", "gf", "pf", "nc", "re", "yt", "pm", 
            "wf", "tf", "bl", "mf", "sx", "cw", "aw", "bq"
        ]
    
    @staticmethod
    def get_domain_suffix(domain_name):
        """获取域名后缀（支持多级后缀）"""
        suffix_list = WhoisChecker.get_suffix_list()
        domain_parts = domain_name.lower().split('.')
        
        # 逐步组合域名部分以匹配最长的后缀
        for i in range(len(domain_parts)):
            possible_suffix = '.'.join(domain_parts[i:])
            if possible_suffix in suffix_list:
                return possible_suffix
        return None
    
    @staticmethod
    def query_iana_whois_server(domain_suffix, whois_register='whois.iana.org'):
        """查询IANA获取WHOIS服务器"""
        try:
            test_domain = f"example{domain_suffix}"
            response = WhoisChecker.query_whois_server(test_domain, whois_register)
            
            # 解析IANA响应
            if isinstance(response, dict) and 'raw_data' in response:
                whois_data = response['raw_data']
            else:
                whois_data = str(response)
            
            refer_match = re.search(r'refer:\s*(.*?)\s*(?=\w+:|$)', whois_data, re.IGNORECASE | re.MULTILINE)
            if refer_match:
                return refer_match.group(1).strip()
        except Exception as e:
            print(f"Query IANA Whois Server Exception: {e}")
        
        return None
    
    @staticmethod
    def get_whois_servers(domain_name):
        """获取域名对应的WHOIS服务器列表"""
        domain_suffix = WhoisChecker.get_domain_suffix(domain_name)
        if not domain_suffix:
            return WhoisChecker.FALLBACK_SERVERS[:WhoisChecker.MAX_SERVERS_TO_TRY]
        
        servers = []
        
        # 添加自定义服务器
        suffix_key = f".{domain_suffix}"
        if suffix_key in WhoisChecker.DIY_WHOIS_SERVERS:
            servers.extend(WhoisChecker.DIY_WHOIS_SERVERS[suffix_key])
        
        # 查询IANA获取官方服务器
        iana_server = WhoisChecker.query_iana_whois_server(suffix_key)
        if iana_server and iana_server not in servers:
            servers.append(iana_server)
        
        # 添加备用服务器
        remaining_slots = WhoisChecker.MAX_SERVERS_TO_TRY - len(servers)
        if remaining_slots > 0:
            for server in WhoisChecker.FALLBACK_SERVERS:
                if server not in servers:
                    servers.append(server)
                    remaining_slots -= 1
                    if remaining_slots <= 0:
                        break
        
        # 去重并限制总数
        unique_servers = list(dict.fromkeys(servers))
        return unique_servers[:WhoisChecker.MAX_SERVERS_TO_TRY]
    
    @staticmethod
    def query_whois_server(domain_name, server, port=43, timeout=None):
        """查询特定的WHOIS服务器"""
        if timeout is None:
            timeout = WhoisChecker.SOCKET_TIMEOUT
            
        try:
            # 创建socket连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((server, port))
            
            # 发送查询
            query = f"{domain_name}\r\n".encode('utf-8')
            sock.send(query)
            
            # 接收响应
            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
            
            sock.close()
            
            # 解码响应
            whois_data = response.decode('utf-8', errors='ignore')
            
            # 检查是否包含有效信息
            if not WhoisChecker.is_valid_whois_response(whois_data):
                return {
                    'error': f"查询失败",
                    'is_valid': False,
                    'server': server
                }
            
            # 解析WHOIS数据
            return WhoisChecker.parse_whois_response(whois_data, server)
            
        except socket.timeout:
            return {
                'error': f"查询失败",
                'is_valid': False,
                'server': server
            }
        except Exception as e:
            return {
                'error': f"查询失败",
                'is_valid': False,
                'server': server
            }
    
    @staticmethod
    def is_valid_whois_response(whois_data):
        """检查WHOIS响应是否包含有效信息"""
        if not whois_data or len(whois_data.strip()) < 10:
            return False
        
        # 检查是否包含错误信息
        error_indicators = [
            'no match',
            'not found',
            'domain not found',
            'no entries found',
            'no data found',
            'no information available',
            'no such domain',
            'domain does not exist',
            'no domain',
            'not registered',
            'free',
            'available',
            'not available',
            'reserved',
            'restricted'
        ]
        
        whois_lower = whois_data.lower()
        for indicator in error_indicators:
            if indicator in whois_lower:
                return False
        
        # 检查是否包含有效信息
        valid_indicators = [
            'registrar',
            'creation date',
            'expiration date',
            'updated date',
            'name server',
            'status',
            'domain name',
            'whois server',
            'referral server'
        ]
        
        for indicator in valid_indicators:
            if indicator in whois_lower:
                return True
        
        return False
    
    @staticmethod
    def parse_whois_response(whois_data, server):
        """解析WHOIS响应数据"""
        try:
            # 使用正则表达式解析WHOIS数据
            registrar = None
            creation_date = None
            expiration_date = None
            updated_date = None
            status = None
            name_servers = []
            
            # 解析注册商
            registrar_patterns = [
                r'Registrar:\s*(.+)',
                r'Sponsoring Registrar:\s*(.+)',
                r'Registration Service Provider:\s*(.+)'
            ]
            for pattern in registrar_patterns:
                match = re.search(pattern, whois_data, re.IGNORECASE)
                if match:
                    registrar = match.group(1).strip()
                    break
            
            # 解析创建日期
            creation_patterns = [
                r'Creation Date:\s*(.+)',
                r'Created:\s*(.+)',
                r'Registration Date:\s*(.+)'
            ]
            for pattern in creation_patterns:
                match = re.search(pattern, whois_data, re.IGNORECASE)
                if match:
                    creation_date_str = match.group(1).strip()
                    creation_date = WhoisChecker.parse_date(creation_date_str)
                    break
            
            # 解析到期日期
            expiration_patterns = [
                r'Registry Expiry Date:\s*(.+)',
                r'Expiration Date:\s*(.+)',
                r'Expires:\s*(.+)',
                r'Expiry Date:\s*(.+)'
            ]
            for pattern in expiration_patterns:
                match = re.search(pattern, whois_data, re.IGNORECASE)
                if match:
                    expiration_date_str = match.group(1).strip()
                    expiration_date = WhoisChecker.parse_date(expiration_date_str)
                    break
            
            # 解析更新日期
            updated_patterns = [
                r'Updated Date:\s*(.+)',
                r'Last Updated:\s*(.+)',
                r'Modified:\s*(.+)'
            ]
            for pattern in updated_patterns:
                match = re.search(pattern, whois_data, re.IGNORECASE)
                if match:
                    updated_date_str = match.group(1).strip()
                    updated_date = WhoisChecker.parse_date(updated_date_str)
                    break
            
            # 解析状态
            status_patterns = [
                r'Status:\s*(.+)',
                r'Domain Status:\s*(.+)'
            ]
            for pattern in status_patterns:
                matches = re.findall(pattern, whois_data, re.IGNORECASE)
                if matches:
                    status = [s.strip() for s in matches]
                    break
            
            # 解析域名服务器
            nameserver_patterns = [
                r'Name Server:\s*(.+)',
                r'Nameservers:\s*(.+)'
            ]
            for pattern in nameserver_patterns:
                matches = re.findall(pattern, whois_data, re.IGNORECASE)
                if matches:
                    name_servers = [ns.strip() for ns in matches]
                    break
            
            # 检查是否有有效的到期日期
            if not expiration_date:
                return {
                    'error': f"查询失败",
                    'is_valid': False,
                    'server': server,
                    'raw_data': whois_data
                }
            
            return {
                'registrar': registrar,
                'creation_date': creation_date,
                'expiration_date': expiration_date,
                'updated_date': updated_date,
                'status': status,
                'name_servers': name_servers,
                'is_valid': True,
                'server': server,
                'raw_data': whois_data
            }
            
        except Exception as e:
            return {
                'error': f"查询失败",
                'is_valid': False,
                'server': server,
                'raw_data': whois_data
            }
    
    @staticmethod
    def parse_date(date_str):
        """解析各种日期格式"""
        if not date_str:
            return None
        
        # 常见的日期格式
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%d-%b-%Y',
            '%d-%B-%Y',
            '%d-%m-%Y',
            '%d.%m.%Y',
            '%Y.%m.%d',
            '%Y/%m/%d',
            '%Y%m%d',
            '%d/%m/%Y',
            '%Y. %m. %d.',
            '%Y.%m.%d %H:%M:%S',
            '%d-%b-%Y %H:%M:%S %Z',
            '%a %b %d %H:%M:%S %Z %Y',
            '%Y-%m-%d %H:%M:%SZ',
            '%d %b %Y %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M:%S %Z',
            '%B %d %Y',
            '%d.%m.%Y %H:%M:%S',
        ]
        
        # 清理日期字符串
        date_str = date_str.strip()
        
        # 移除时区信息
        date_str = re.sub(r'\s*[+-]\d{4}\s*$', '', date_str)
        date_str = re.sub(r'\s*[A-Z]{3,4}\s*$', '', date_str)
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def get_whois_info(domain_name):
        """获取WHOIS信息，尝试多个服务器（带超时限制）"""
        import time
        
        servers = WhoisChecker.get_whois_servers(domain_name)
        start_time = time.time()
        
        for i, server in enumerate(servers):
            # 检查整体超时
            if time.time() - start_time > WhoisChecker.QUERY_TIMEOUT:
                return {
                    'error': f"查询失败",
                    'is_valid': False,
                    'servers_tried': i
                }
            
            try:
                result = WhoisChecker.query_whois_server(domain_name, server)
                if result.get('is_valid') and result.get('expiration_date'):
                    return result
            except Exception as e:
                print(f"查询服务器 {server} 失败: {str(e)}")
                continue
        
        return {
            'error': f"查询失败",
            'is_valid': False,
            'servers_tried': len(servers)
        }
    
    @staticmethod
    def update_whois_record(domain):
        """更新域名的WHOIS信息"""
        try:
            # 首先创建或更新记录，标记为查询中
            whois_record = WhoisRecord.query.filter_by(domain_id=domain.id).first()
            if not whois_record:
                whois_record = WhoisRecord(domain_id=domain.id)
            
            # 标记为查询中状态
            whois_record.last_checked = get_current_beijing_time()
            whois_record.is_valid = False  # 暂时标记为无效，表示正在查询
            whois_record.error_message = "查询中..."  # 临时错误信息表示查询中
            whois_record.whois_server = "querying"
            
            db.session.add(whois_record)
            db.session.commit()
            
            # 执行实际的WHOIS查询
            whois_info = WhoisChecker.get_whois_info(domain.name)
            
            if whois_info.get('is_valid'):
                # 计算剩余天数
                expiration_date = whois_info['expiration_date']
                if isinstance(expiration_date, list):
                    expiration_date = expiration_date[0]
                
                days_until_expiry = None
                if expiration_date:
                    # 确保两个时间都是naive datetime对象进行比较
                    if expiration_date.tzinfo is not None:
                        expiration_date = expiration_date.replace(tzinfo=None)
                    current_time = get_current_beijing_time()
                    if current_time.tzinfo is not None:
                        current_time = current_time.replace(tzinfo=None)
                    days_until_expiry = (expiration_date - current_time).days
                
                # 更新WHOIS信息
                whois_record.registrar = whois_info['registrar']
                whois_record.creation_date = whois_info['creation_date']
                whois_record.expiration_date = expiration_date
                whois_record.updated_date = whois_info['updated_date']
                whois_record.status = str(whois_info['status']) if whois_info['status'] else None
                whois_record.name_servers = str(whois_info['name_servers']) if whois_info['name_servers'] else None
                whois_record.days_until_expiry = days_until_expiry
                whois_record.last_checked = get_current_beijing_time()
                whois_record.is_valid = True  # 明确设置为True
                whois_record.error_message = None  # 清除错误信息
                
                # 保存使用的WHOIS服务器信息
                whois_record.whois_server = whois_info.get('server', 'unknown')
                
                db.session.add(whois_record)
                db.session.commit()
                
                # 检查是否需要发送通知
                if whois_record.is_expiring_soon:
                    # 重新获取domain对象以确保在正确的会话中
                    current_domain = Domain.query.get(domain.id)
                    if current_domain and current_domain.notification_config:
                        Notifier.send_whois_expiry_notification(current_domain, whois_record)
                
                return whois_record
            else:
                # 记录错误信息
                whois_record.last_checked = get_current_beijing_time()
                whois_record.error_message = whois_info.get('error', '查询失败')
                whois_record.is_valid = False  # 明确设置为False
                whois_record.whois_server = whois_info.get('server', 'unknown')
                
                db.session.add(whois_record)
                db.session.commit()
                
                return None
                
        except Exception as e:
            # 确保即使出现异常也能更新状态
            try:
                whois_record = WhoisRecord.query.filter_by(domain_id=domain.id).first()
                if whois_record:
                    whois_record.last_checked = get_current_beijing_time()
                    whois_record.error_message = f"查询异常: {str(e)}"
                    whois_record.is_valid = False
                    whois_record.whois_server = "error"
                    db.session.add(whois_record)
                    db.session.commit()
            except Exception as db_error:
                print(f"更新WHOIS记录状态失败: {str(db_error)}")
            
            print(f"WHOIS查询异常 {domain.name}: {str(e)}")
            return None

def check_all_whois():
    """检查所有域名的WHOIS信息"""
    domains = Domain.query.filter_by(is_active=True, check_whois=True).all()
    
    for domain in domains:
        try:
            WhoisChecker.update_whois_record(domain)
        except Exception as e:
            print(f"检查WHOIS失败 {domain.name}: {str(e)}")

def check_single_whois(domain_id):
    """检查单个域名的WHOIS信息"""
    try:
        # 重新获取domain对象，确保在正确的会话中
        domain = Domain.query.get(domain_id)
        if domain and domain.is_active and domain.check_whois:
            # 直接在这里执行WHOIS检查，避免传递domain对象
            # 首先创建或更新记录，标记为查询中
            whois_record = WhoisRecord.query.filter_by(domain_id=domain.id).first()
            if not whois_record:
                whois_record = WhoisRecord(domain_id=domain.id)
            
            # 标记为查询中状态
            whois_record.last_checked = get_current_beijing_time()
            whois_record.is_valid = False  # 暂时标记为无效，表示正在查询
            whois_record.error_message = "查询中..."  # 临时错误信息表示查询中
            whois_record.whois_server = "querying"
            
            db.session.add(whois_record)
            db.session.commit()
            
            # 执行实际的WHOIS查询
            whois_info = WhoisChecker.get_whois_info(domain.name)
            
            if whois_info.get('is_valid'):
                # 计算剩余天数
                expiration_date = whois_info['expiration_date']
                if isinstance(expiration_date, list):
                    expiration_date = expiration_date[0]
                
                days_until_expiry = None
                if expiration_date:
                    # 确保两个时间都是naive datetime对象进行比较
                    if expiration_date.tzinfo is not None:
                        expiration_date = expiration_date.replace(tzinfo=None)
                    current_time = get_current_beijing_time()
                    if current_time.tzinfo is not None:
                        current_time = current_time.replace(tzinfo=None)
                    days_until_expiry = (expiration_date - current_time).days
                
                # 更新WHOIS信息
                whois_record.registrar = whois_info['registrar']
                whois_record.creation_date = whois_info['creation_date']
                whois_record.expiration_date = expiration_date
                whois_record.updated_date = whois_info['updated_date']
                whois_record.status = str(whois_info['status']) if whois_info['status'] else None
                whois_record.name_servers = str(whois_info['name_servers']) if whois_info['name_servers'] else None
                whois_record.days_until_expiry = days_until_expiry
                whois_record.last_checked = get_current_beijing_time()
                whois_record.is_valid = True  # 明确设置为True
                whois_record.error_message = None  # 清除错误信息
                
                # 保存使用的WHOIS服务器信息
                whois_record.whois_server = whois_info.get('server', 'unknown')
                
                db.session.add(whois_record)
                db.session.commit()
                
                # 检查是否需要发送通知
                if whois_record.is_expiring_soon:
                    # 重新获取domain对象以确保在正确的会话中
                    current_domain = Domain.query.get(domain_id)
                    if current_domain and current_domain.notification_config:
                        Notifier.send_whois_expiry_notification(current_domain, whois_record)
                
                return whois_record
            else:
                # 记录错误信息
                whois_record.last_checked = get_current_beijing_time()
                whois_record.error_message = whois_info.get('error', '查询失败')
                whois_record.is_valid = False  # 明确设置为False
                whois_record.whois_server = whois_info.get('server', 'unknown')
                
                db.session.add(whois_record)
                db.session.commit()
                
                return None
    except Exception as e:
        # 确保即使出现异常也能更新状态
        try:
            whois_record = WhoisRecord.query.filter_by(domain_id=domain_id).first()
            if whois_record:
                whois_record.last_checked = get_current_beijing_time()
                whois_record.error_message = f"查询异常: {str(e)}"
                whois_record.is_valid = False
                whois_record.whois_server = "error"
                db.session.add(whois_record)
                db.session.commit()
        except Exception as db_error:
            print(f"更新WHOIS记录状态失败: {str(db_error)}")
        
        print(f"检查WHOIS失败 {domain_id}: {str(e)}")
        return None
