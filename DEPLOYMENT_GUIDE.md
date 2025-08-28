# 部署指南

## 🚀 快速部署

### 开发环境部署

#### 1. 环境准备
```bash
# 安装Python 3.8+
python --version

# 安装Git
git --version

# 安装虚拟环境工具
pip install virtualenv
```

#### 2. 项目克隆
```bash
git clone <repository-url>
cd aicode
```

#### 3. 虚拟环境设置
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

#### 4. 依赖安装
```bash
# 升级pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

#### 5. 数据库初始化
```bash
# 创建数据库
python create_db.py

# 或使用Flask-Migrate
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

#### 6. 启动应用
```bash
# 开发模式启动
python run.py

# 或使用Flask命令
export FLASK_APP=run.py
export FLASK_ENV=development
flask run
```

#### 7. 访问应用
打开浏览器访问 `http://localhost:5000`

### 生产环境部署

#### 1. 服务器环境准备

**Ubuntu/Debian系统**:
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python和必要工具
sudo apt install python3 python3-pip python3-venv nginx supervisor -y

# 安装数据库（可选）
sudo apt install postgresql postgresql-contrib -y
# 或
sudo apt install mysql-server mysql-client -y
```

**CentOS/RHEL系统**:
```bash
# 更新系统
sudo yum update -y

# 安装Python和必要工具
sudo yum install python3 python3-pip nginx supervisor -y

# 安装EPEL仓库
sudo yum install epel-release -y
```

#### 2. 项目部署
```bash
# 创建应用目录
sudo mkdir -p /var/www/aicode
sudo chown $USER:$USER /var/www/aicode

# 克隆项目
cd /var/www/aicode
git clone <repository-url> .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install gunicorn  # 生产环境WSGI服务器
```

#### 3. 环境配置

**创建环境变量文件**:
```bash
# /var/www/aicode/.env
export FLASK_ENV=production
export SECRET_KEY=your-production-secret-key
export DATABASE_URL=postgresql://user:password@localhost/aicode
export MAIL_SERVER=smtp.gmail.com
export MAIL_PORT=587
export MAIL_USERNAME=your-email@gmail.com
export MAIL_PASSWORD=your-app-password
```

**创建配置文件**:
```python
# /var/www/aicode/config.py
import os
from datetime import timedelta
import pytz

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20
    }
    
    # 安全配置
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # 日志配置
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/aicode/app.log'
    ERROR_LOG_FILE = '/var/log/aicode/error.log'
```

#### 4. Gunicorn配置

**创建Gunicorn配置文件**:
```python
# /var/www/aicode/gunicorn.conf.py
import multiprocessing

# 服务器配置
bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "/var/log/aicode/gunicorn_access.log"
errorlog = "/var/log/aicode/gunicorn_error.log"
loglevel = "info"

# 进程配置
preload_app = True
daemon = False

# 超时配置
timeout = 30
keepalive = 2

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)
```

#### 5. Supervisor配置

**创建Supervisor配置文件**:
```ini
# /etc/supervisor/conf.d/aicode.conf
[program:aicode]
directory=/var/www/aicode
command=/var/www/aicode/venv/bin/gunicorn -c gunicorn.conf.py run:app
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/aicode/supervisor.log
environment=FLASK_ENV="production"
```

**启动Supervisor**:
```bash
# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动应用
sudo supervisorctl start aicode

# 查看状态
sudo supervisorctl status aicode
```

#### 6. Nginx配置

**创建Nginx配置文件**:
```nginx
# /etc/nginx/sites-available/aicode
server {
    listen 80;
    server_name your-domain.com;
    
    # 重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL证书配置
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # 安全头
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # 静态文件
    location /static/ {
        alias /var/www/aicode/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # 上传文件
    location /uploads/ {
        alias /var/www/aicode/uploads/;
        expires 1d;
    }
    
    # 代理到Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # 超时配置
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

**启用Nginx配置**:
```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/aicode /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
```

#### 7. 日志配置

**创建日志目录**:
```bash
sudo mkdir -p /var/log/aicode
sudo chown www-data:www-data /var/log/aicode
```

**配置日志轮转**:
```bash
# /etc/logrotate.d/aicode
/var/log/aicode/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        supervisorctl restart aicode
    endscript
}
```

### Docker部署

#### 1. Dockerfile
```dockerfile
# Dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "run:app"]
```

#### 2. Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://user:password@db:5432/aicode
      - SECRET_KEY=your-secret-key
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    restart: unless-stopped

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=aicode
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:6-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

#### 3. 部署命令
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

### 监控和维护

#### 1. 健康检查
```bash
# 应用健康检查
curl -f http://localhost:8000/health

# 数据库连接检查
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.engine.execute('SELECT 1')"
```

#### 2. 性能监控
```bash
# 查看进程状态
ps aux | grep gunicorn

# 查看内存使用
free -h

# 查看磁盘使用
df -h

# 查看网络连接
netstat -tulpn | grep :8000
```

#### 3. 日志监控
```bash
# 查看应用日志
tail -f /var/log/aicode/app.log

# 查看错误日志
tail -f /var/log/aicode/error.log

# 查看Nginx访问日志
tail -f /var/log/nginx/access.log
```

#### 4. 备份策略
```bash
# 数据库备份
pg_dump -h localhost -U user aicode > backup_$(date +%Y%m%d_%H%M%S).sql

# 文件备份
tar -czf uploads_backup_$(date +%Y%m%d_%H%M%S).tar.gz /var/www/aicode/uploads/

# 配置备份
tar -czf config_backup_$(date +%Y%m%d_%H%M%S).tar.gz /var/www/aicode/config.py /var/www/aicode/.env
```

### 安全配置

#### 1. 防火墙配置
```bash
# Ubuntu/Debian
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# CentOS/RHEL
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

#### 2. SSL证书配置
```bash
# 使用Let's Encrypt
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo crontab -e
# 添加以下行
0 12 * * * /usr/bin/certbot renew --quiet
```

#### 3. 安全加固
```bash
# 禁用不必要的服务
sudo systemctl disable telnet
sudo systemctl disable ftp

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装安全工具
sudo apt install fail2ban -y
```

### 故障排除

#### 1. 常见问题

**应用无法启动**:
```bash
# 检查日志
sudo supervisorctl tail aicode

# 检查端口占用
sudo netstat -tulpn | grep :8000

# 检查权限
ls -la /var/www/aicode/
```

**数据库连接失败**:
```bash
# 检查数据库服务
sudo systemctl status postgresql

# 检查连接
psql -h localhost -U user -d aicode

# 检查配置文件
cat /var/www/aicode/.env
```

**Nginx配置错误**:
```bash
# 测试配置
sudo nginx -t

# 查看错误日志
sudo tail -f /var/log/nginx/error.log
```

#### 2. 性能优化

**Gunicorn优化**:
```python
# 调整worker数量
workers = multiprocessing.cpu_count() * 2 + 1

# 调整超时时间
timeout = 30
keepalive = 2
```

**Nginx优化**:
```nginx
# 启用gzip压缩
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

# 启用缓存
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

**注意**: 生产环境部署前请确保：
1. 修改所有默认密码
2. 配置SSL证书
3. 设置防火墙规则
4. 配置监控和告警
5. 制定备份策略
