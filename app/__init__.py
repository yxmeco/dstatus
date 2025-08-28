from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from config import config

db = SQLAlchemy()
migrate = Migrate()
scheduler = APScheduler()

def create_app(config_name='default', init_scheduler=True):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    
    # 只在主线程中初始化调度器
    if init_scheduler:
        scheduler.init_app(app)
    
    # 注册蓝图
    from app.views.dashboard import dashboard_bp
    from app.views.domains import domains_bp
    from app.views.urls import urls_bp
    from app.views.notifications import notifications_bp
    from app.views.proxies import proxies_bp
    from app.views.api import api_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(domains_bp)
    app.register_blueprint(urls_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(proxies_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # 只在主线程中注册定时任务
    if init_scheduler:
        register_scheduled_jobs(app)
    
    return app

def register_scheduled_jobs(app):
    """注册定时任务"""
    from app.services.ssl_checker import check_all_certificates
    from app.services.whois_checker import check_all_whois
    from app.services.url_checker import check_all_urls
    
    with app.app_context():
        # 每天凌晨2点检查所有证书
        scheduler.add_job(
            id='check_certificates',
            func=check_all_certificates,
            trigger='cron',
            hour=2,
            minute=0,
            replace_existing=True
        )
        
        # 每天凌晨3点检查所有WHOIS
        scheduler.add_job(
            id='check_whois',
            func=check_all_whois,
            trigger='cron',
            hour=3,
            minute=0,
            replace_existing=True
        )
        
        # 每小时检查所有URL
        scheduler.add_job(
            id='check_urls',
            func=check_all_urls,
            trigger='cron',
            minute=0,
            replace_existing=True
        )
    
    # 只在主线程中启动调度器
    if not scheduler.running:
        scheduler.start()
