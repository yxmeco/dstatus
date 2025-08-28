import os
import tempfile
import json
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

class CertParser:
    @staticmethod
    def parse_certificate_file(cert_file):
        """解析证书文件，提取证书信息"""
        try:
            # 读取证书文件内容
            cert_data = cert_file.read()
            cert_file.seek(0)  # 重置文件指针
            
            # 解析证书
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            
            # 提取证书信息
            cert_info = {
                'issuer': CertParser._format_name(cert.issuer),
                'subject': CertParser._format_name(cert.subject),
                'serial_number': str(cert.serial_number),
                'not_before': cert.not_valid_before,
                'not_after': cert.not_valid_after,
                'is_valid': True
            }
            
            # 提取域名信息
            domain_info = CertParser._extract_domain_info(cert)
            cert_info.update(domain_info)
            
            return cert_info
            
        except Exception as e:
            return {
                'error': str(e),
                'is_valid': False
            }
    
    @staticmethod
    def _extract_domain_info(cert):
        """从证书中提取域名信息"""
        domains = []
        common_name = None
        san_domains = []
        
        try:
            # 提取通用名称 (CN)
            for name in cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME):
                common_name = name.value
                if common_name not in domains:
                    domains.append(common_name)
            
            # 提取主题备用名称 (SAN)
            try:
                san_extension = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                if san_extension:
                    san_names = san_extension.value
                    for name in san_names:
                        if isinstance(name, x509.DNSName):
                            san_domains.append(name.value)
                            if name.value not in domains:
                                domains.append(name.value)
            except x509.extensions.ExtensionNotFound:
                pass
            
            return {
                'common_name': common_name,
                'san_domains': json.dumps(san_domains) if san_domains else None,
                'cert_domains': json.dumps(domains) if domains else None
            }
            
        except Exception as e:
            return {
                'common_name': None,
                'san_domains': None,
                'cert_domains': None
            }
    
    @staticmethod
    def parse_private_key_file(key_file):
        """解析私钥文件"""
        try:
            # 读取私钥文件内容
            key_data = key_file.read()
            key_file.seek(0)  # 重置文件指针
            
            # 尝试解析私钥
            private_key = serialization.load_pem_private_key(
                key_data,
                password=None,  # 假设私钥没有密码保护
                backend=default_backend()
            )
            
            return {
                'is_valid': True,
                'key_type': type(private_key).__name__
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'is_valid': False
            }
    
    @staticmethod
    def save_certificate_file(cert_file, domain_name):
        """保存证书文件到服务器"""
        try:
            # 创建证书存储目录
            cert_dir = os.path.join('uploads', 'certificates', domain_name)
            os.makedirs(cert_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            cert_filename = f"cert_{timestamp}.crt"
            cert_path = os.path.join(cert_dir, cert_filename)
            
            # 保存文件
            cert_file.save(cert_path)
            
            return {
                'file_path': cert_path,
                'file_name': cert_filename,
                'is_saved': True
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'is_saved': False
            }
    
    @staticmethod
    def save_private_key_file(key_file, domain_name):
        """保存私钥文件到服务器"""
        try:
            # 创建私钥存储目录
            key_dir = os.path.join('uploads', 'private_keys', domain_name)
            os.makedirs(key_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            key_filename = f"key_{timestamp}.key"
            key_path = os.path.join(key_dir, key_filename)
            
            # 保存文件
            key_file.save(key_path)
            
            return {
                'file_path': key_path,
                'file_name': key_filename,
                'is_saved': True
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'is_saved': False
            }
    
    @staticmethod
    def _format_name(name):
        """格式化证书名称"""
        parts = []
        for attr in name:
            parts.append(f"{attr.oid._name}={attr.value}")
        return ", ".join(parts)
    
    @staticmethod
    def validate_certificate_files(cert_file, key_file=None):
        """验证证书文件的有效性"""
        errors = []
        
        # 验证证书文件
        if cert_file:
            cert_info = CertParser.parse_certificate_file(cert_file)
            if not cert_info.get('is_valid'):
                errors.append(f"证书文件无效: {cert_info.get('error', '未知错误')}")
        else:
            errors.append("请上传证书文件")
        
        # 验证私钥文件（如果提供）
        if key_file:
            key_info = CertParser.parse_private_key_file(key_file)
            if not key_info.get('is_valid'):
                errors.append(f"私钥文件无效: {key_info.get('error', '未知错误')}")
        
        return errors
