from app import db
from datetime import datetime
import json

class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    
    # 监控配置
    check_interval = db.Column(db.Integer, default=1)  # 检查间隔（分钟）
    timeout = db.Column(db.Integer, default=10)  # 超时时间（秒）
    retry_count = db.Column(db.Integer, default=1)  # 重试次数
    
    # HTTP请求配置
    method = db.Column(db.String(10), default='GET')  # GET, POST, PUT, DELETE等
    headers = db.Column(db.Text)  # JSON格式的请求头
    body = db.Column(db.Text)  # 请求体
    content_type = db.Column(db.String(100), default='application/json')  # 内容类型
    
    # 验证配置
    expected_status_codes = db.Column(db.String(100), default='200')  # 期望的状态码，逗号分隔
    expected_response_contains = db.Column(db.Text)  # 期望响应包含的内容
    expected_response_not_contains = db.Column(db.Text)  # 期望响应不包含的内容
    response_time_threshold = db.Column(db.Float, default=5.0)  # 响应时间阈值（秒）
    
    # 高级配置
    follow_redirects = db.Column(db.Boolean, default=True)  # 是否跟随重定向
    verify_ssl = db.Column(db.Boolean, default=True)  # 是否验证SSL证书
    accept_invalid_cert = db.Column(db.Boolean, default=False)  # 是否接受无效证书
    
    # 通知配置
    notification_config_id = db.Column(db.Integer, db.ForeignKey('notification_config.id'), nullable=True)
    
    # 代理配置
    proxy_id = db.Column(db.Integer, db.ForeignKey('proxies.id'), nullable=True)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    url_checks = db.relationship('URLCheck', backref='url', lazy=True, cascade='all, delete-orphan')
    notification_config = db.relationship('NotificationConfig', backref='urls')
    proxy = db.relationship('Proxy', back_populates='url_checks')
    # 注意：domain关联关系在Domain模型中定义，这里不需要重复定义
    
    @property
    def headers_dict(self):
        """将JSON格式的headers转换为字典"""
        if self.headers:
            try:
                return json.loads(self.headers)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    @property
    def expected_status_codes_list(self):
        """将期望状态码字符串转换为列表"""
        if self.expected_status_codes:
            return [int(code.strip()) for code in self.expected_status_codes.split(',') if code.strip().isdigit()]
        return [200]
    
    @property
    def status_display(self):
        """获取URL状态显示"""
        if not self.is_active:
            return '已禁用'
        
        latest_check = self.url_checks[-1] if self.url_checks else None
        if not latest_check:
            return '未检查'
        
        if latest_check.is_available:
            return '正常'
        else:
            return '异常'
    
    @property
    def status_badge_class(self):
        """获取状态徽章样式类"""
        if not self.is_active:
            return 'bg-secondary'
        
        latest_check = self.url_checks[-1] if self.url_checks else None
        if not latest_check:
            return 'bg-secondary'
        
        if latest_check.is_available:
            return 'bg-success'
        else:
            return 'bg-danger'
    
    @property
    def uptime_percentage(self):
        """计算可用性百分比"""
        if not self.url_checks:
            return 0.0
        
        total_checks = len(self.url_checks)
        successful_checks = sum(1 for check in self.url_checks if check.is_available)
        return round((successful_checks / total_checks) * 100, 2)
    
    @property
    def average_response_time(self):
        """计算平均响应时间"""
        if not self.url_checks:
            return 0.0
        
        response_times = [check.response_time for check in self.url_checks if check.response_time is not None]
        if not response_times:
            return 0.0
        
        return round(sum(response_times) / len(response_times), 2)
    
    @property
    def availability_progress_data(self):
        """生成10格可用性进度条数据（管道插入法：最右侧最新，最左侧无数据）"""
        if not self.url_checks:
            return {
                'bars': [{'status': 'empty'} for _ in range(10)],
                'percentage': 0.0,
                'total_checks': 0,
                'successful_checks': 0
            }
        
        # 获取最近的10次检查记录
        recent_checks = self.url_checks[-10:] if len(self.url_checks) >= 10 else self.url_checks
        
        # 生成10格进度条数据（管道插入法）
        bars = []
        
        # 先填充无数据状态（左侧）
        empty_count = 10 - len(recent_checks)
        for i in range(empty_count):
            bars.append({'status': 'empty'})
        
        # 然后填充检查数据（右侧），最新的在最右边
        for check in recent_checks:
            bars.append({
                'status': 'success' if check.is_available else 'failure',
                'tooltip': f"{'成功' if check.is_available else '失败'} - {check.checked_at.strftime('%m-%d %H:%M')}"
            })
        
        # 计算成功率
        total_checks = len(recent_checks)
        successful_checks = sum(1 for check in recent_checks if check.is_available)
        percentage = round((successful_checks / total_checks) * 100, 1) if total_checks > 0 else 0.0
        
        return {
            'bars': bars,
            'percentage': percentage,
            'total_checks': total_checks,
            'successful_checks': successful_checks
        }
    
    def __repr__(self):
        return f'<URL {self.name}>'
