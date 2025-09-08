import os
from datetime import timedelta
import pytz

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///domain_cert_manager.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 数据库连接池配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20
    }
    
    # 邮件配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # 时区配置
    TIMEZONE = pytz.timezone('Asia/Shanghai')  # 北京时区
    
    # 监控配置
    CERT_CHECK_INTERVAL = int(os.environ.get('CERT_CHECK_INTERVAL') or 24)  # 小时
    URL_CHECK_INTERVAL = int(os.environ.get('URL_CHECK_INTERVAL') or 1)     # 小时
    NOTIFICATION_DAYS_BEFORE = int(os.environ.get('NOTIFICATION_DAYS_BEFORE') or 30)

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

