# 域名证书管理系统 (Domain Certificate Manager)

一个基于Flask的现代化域名证书管理系统，提供域名监控、SSL证书管理、URL可用性监控、代理管理等功能。

所有的功能都是基于cursor 使用Ai编写

![img_6.png](img_6.png)
![img_8.png](img_8.png)
![img_7.png](img_7.png)
![img_11.png](img_11.png)
![img_10.png](img_10.png)

![img_1.png](img_1.png)
![img_5.png](img_5.png)
![img_2.png](img_2.png)
![img_3.png](img_3.png)
![img_4.png](img_4.png)
## 🌟 功能特性

### 核心功能
- **域名管理**: 域名信息管理、WHOIS查询、官网可用性检查
- **SSL证书监控**: 自动检查SSL证书有效期，到期提醒
- **URL监控**: 实时监控URL可用性，支持SOCKS代理
- **代理管理**: 支持HTTP/HTTPS/SOCKS代理配置和测试
- **通知系统**: 支持邮件、Webhook、企业微信机器人通知
- **仪表盘**: 实时数据统计和可视化展示

### 技术特性
- **异步处理**: 后台线程执行检查任务，不阻塞用户界面
- **时区支持**: 统一使用北京时区，确保时间显示准确
- **响应式设计**: 现代化UI设计，支持移动端访问
- **搜索分页**: 高效的数据查询和分页展示
- **实时反馈**: Toast通知和状态指示器

## 🏗️ 项目架构

### 目录结构
```
aicode/
├── app/                          # 应用主目录
│   ├── __init__.py              # 应用工厂函数
│   ├── models/                  # 数据模型
│   │   ├── domain.py           # 域名模型
│   │   ├── certificate.py      # 证书模型
│   │   ├── url.py              # URL监控模型
│   │   ├── proxy.py            # 代理模型
│   │   └── notification.py     # 通知模型
│   ├── views/                   # 视图控制器
│   │   ├── dashboard.py        # 仪表盘
│   │   ├── domains.py          # 域名管理
│   │   ├── urls.py             # URL监控
│   │   ├── proxies.py          # 代理管理
│   │   ├── notifications.py    # 通知管理
│   │   └── api.py              # API接口
│   ├── services/                # 业务服务层
│   │   ├── ssl_checker.py      # SSL证书检查
│   │   ├── whois_checker.py    # WHOIS查询
│   │   ├── url_checker.py      # URL可用性检查
│   │   ├── domain_access_checker.py  # 域名访问检查
│   │   ├── notifier.py         # 通知服务
│   │   └── cert_parser.py      # 证书解析
│   ├── templates/               # 前端模板
│   │   ├── base.html           # 基础模板
│   │   ├── dashboard/          # 仪表盘模板
│   │   ├── domains/            # 域名管理模板
│   │   ├── urls/               # URL监控模板
│   │   ├── proxies/            # 代理管理模板
│   │   └── notifications/      # 通知管理模板
│   └── utils/                   # 工具模块
│       ├── timezone.py         # 时区工具
│       └── scheduler_jobs.py   # 调度任务
├── migrations/                  # 数据库迁移文件
├── instance/                    # 实例配置
├── uploads/                     # 文件上传目录
├── config.py                    # 配置文件
├── run.py                       # 应用入口
├── requirements.txt             # 依赖包
└── README.md                    # 项目文档
```

### 架构设计

#### 1. 分层架构
- **表现层 (Views)**: 处理HTTP请求，返回响应
- **业务层 (Services)**: 核心业务逻辑，数据处理
- **数据层 (Models)**: 数据模型定义，数据库操作
- **工具层 (Utils)**: 通用工具函数和辅助功能

#### 2. 核心组件
- **Flask应用工厂**: 支持多环境配置
- **SQLAlchemy ORM**: 数据库操作抽象
- **APScheduler**: 定时任务调度
- **Blueprint**: 模块化路由管理

#### 3. 异步架构
- **后台线程**: 执行耗时操作（WHOIS查询、URL检查等）
- **应用上下文管理**: 确保线程安全
- **调度器分离**: 主线程和后台线程调度器独立

## 🚀 快速开始

### 环境要求
- Python 3.8+
- SQLite/MySQL/PostgreSQL
- 现代浏览器（支持ES6+）

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd aicode
```

2. **创建虚拟环境**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **初始化数据库**
```bash
python create_db.py
```

5. **启动应用**
```bash
python run.py
```

6. **访问应用**
打开浏览器访问 `http://localhost:5000`

### 环境变量配置

创建 `.env` 文件（可选）：
```env
# 数据库配置
DATABASE_URL=sqlite:///domain_cert_manager.db

# 邮件配置
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# 应用配置
SECRET_KEY=your-secret-key
FLASK_ENV=development
```

## 📖 使用指南

### 1. 域名管理
- **添加域名**: 输入域名名称和描述，选择检查功能
- **WHOIS查询**: 自动获取域名注册信息
- **官网可用性**: 检查域名HTTPS访问状态
- **异步刷新**: 点击按钮实时更新域名信息

### 2. URL监控
- **添加监控**: 配置URL地址、检查间隔、代理设置
- **实时检查**: 立即执行URL可用性检查
- **进度条显示**: 10格进度条显示最近检查结果
- **状态码显示**: 显示HTTP响应状态码

### 3. 代理管理
- **代理类型**: 支持HTTP、HTTPS、SOCKS4、SOCKS5
- **连接测试**: 实时测试代理连接状态
- **认证支持**: 用户名密码认证
- **状态监控**: 显示代理响应时间和状态

### 4. 通知配置
- **邮件通知**: 配置SMTP服务器
- **Webhook**: 支持自定义Webhook URL
- **企业微信**: 企业微信机器人通知
- **测试功能**: 发送测试通知验证配置

### 5. 仪表盘
- **数据统计**: 域名数量、URL监控、异常统计
- **实时更新**: 自动刷新统计数据
- **可视化**: 卡片式布局展示关键指标

## 🔧 配置说明

### 数据库配置
```python
# config.py
SQLALCHEMY_DATABASE_URI = 'sqlite:///domain_cert_manager.db'
# 或使用MySQL
# SQLALCHEMY_DATABASE_URI = 'mysql://user:password@localhost/dbname'
```

### 时区配置
```python
TIMEZONE = pytz.timezone('Asia/Shanghai')  # 北京时区
```

### 监控间隔配置
```python
CERT_CHECK_INTERVAL = 24  # 证书检查间隔（小时）
URL_CHECK_INTERVAL = 1    # URL检查间隔（小时）
NOTIFICATION_DAYS_BEFORE = 30  # 到期前通知天数
```

## 🛠️ 开发指南

### 添加新功能

1. **创建数据模型**
```python
# app/models/example.py
from app import db
from datetime import datetime

class Example(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

2. **创建视图**
```python
# app/views/example.py
from flask import Blueprint, render_template
from app.models.example import Example

example_bp = Blueprint('example', __name__)

@example_bp.route('/examples')
def index():
    examples = Example.query.all()
    return render_template('examples/index.html', examples=examples)
```

3. **注册蓝图**
```python
# app/__init__.py
from app.views.example import example_bp
app.register_blueprint(example_bp)
```

### 数据库迁移

```bash
# 创建迁移
flask db migrate -m "Add new table"

# 应用迁移
flask db upgrade
```

### 测试

```bash
# 运行测试
python -m pytest tests/

# 代码覆盖率
coverage run -m pytest
coverage report
```

## 📊 性能优化

### 1. 数据库优化
- 使用索引优化查询性能
- 定期清理历史数据
- 使用连接池管理数据库连接

### 2. 缓存策略
- Redis缓存热点数据
- 浏览器缓存静态资源
- 数据库查询结果缓存

### 3. 异步处理
- 后台线程执行耗时操作
- 队列处理大量任务
- 定时任务优化执行时间

## 🔒 安全考虑

### 1. 数据安全
- 敏感信息加密存储
- 数据库访问权限控制
- 定期备份重要数据

### 2. 应用安全
- 输入验证和过滤
- SQL注入防护
- XSS攻击防护
- CSRF令牌保护

### 3. 网络安全
- HTTPS强制使用
- 代理认证安全
- 防火墙配置

## 🐛 故障排除

### 常见问题

1. **调度器冲突**
```
错误: Scheduler is already running
解决: 检查后台线程是否正确使用init_scheduler=False
```

2. **应用上下文错误**
```
错误: Working outside of application context
解决: 确保在Flask应用上下文中执行数据库操作
```

3. **时区显示错误**
```
问题: 时间显示不正确
解决: 检查时区配置和前端JavaScript时区设置
```

### 日志查看

```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log
```

## 📈 监控和维护

### 系统监控
- 应用性能监控
- 数据库性能监控
- 网络连接监控
- 磁盘空间监控

### 定期维护
- 数据库备份
- 日志清理
- 证书更新
- 依赖包更新

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系方式

- 项目维护者: [yxmeco]
- 邮箱: [yx@meco.pro]
- 项目地址: [https://github.com/yxmeco/dstatus]

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者和用户！

---

**注意**: 这是一个开发中的项目，请在生产环境中使用前进行充分测试。
