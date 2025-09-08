from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.proxy import Proxy
from app import db
from datetime import datetime
import requests
import time

proxies_bp = Blueprint('proxies', __name__)

@proxies_bp.route('/proxies')
def index():
    # 获取搜索参数
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 构建查询
    query = Proxy.query
    
    # 搜索功能
    if search:
        query = query.filter(
            Proxy.name.contains(search) |
            Proxy.host.contains(search) |
            Proxy.description.contains(search)
        )
    
    # 排序
    query = query.order_by(Proxy.created_at.desc())
    
    # 分页
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    proxies = pagination.items
    
    return render_template('proxies/index.html', 
                         proxies=proxies, 
                         pagination=pagination, 
                         search=search,
                         per_page=per_page)

@proxies_bp.route('/proxies/new', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        name = request.form.get('name')
        proxy_type = request.form.get('type')
        host = request.form.get('host')
        port = request.form.get('port')
        username = request.form.get('username')
        password = request.form.get('password')
        description = request.form.get('description')
        is_active = 'is_active' in request.form
        is_default = 'is_default' in request.form
        
        # 验证必填字段
        if not all([name, proxy_type, host, port]):
            flash('请填写所有必填字段', 'error')
            return render_template('proxies/new.html')
        
        try:
            port = int(port)
            if port < 1 or port > 65535:
                raise ValueError("端口号无效")
        except ValueError:
            flash('端口号必须是1-65535之间的数字', 'error')
            return render_template('proxies/new.html')
        
        # 检查代理名称是否已存在
        existing_proxy = Proxy.query.filter_by(name=name).first()
        if existing_proxy:
            flash('代理名称已存在', 'error')
            return render_template('proxies/new.html')
        
        # 如果设置为默认代理，取消其他默认代理
        if is_default:
            Proxy.query.filter_by(is_default=True).update({'is_default': False})
        
        proxy = Proxy(
            name=name,
            type=proxy_type,
            host=host,
            port=port,
            username=username if username else None,
            password=password if password else None,
            description=description,
            is_active=is_active,
            is_default=is_default
        )
        
        db.session.add(proxy)
        db.session.commit()
        
        flash('代理添加成功！', 'success')
        return redirect(url_for('proxies.index'))
    
    return render_template('proxies/new.html')

@proxies_bp.route('/proxies/<int:id>')
def show(id):
    proxy = Proxy.query.get_or_404(id)
    return render_template('proxies/show.html', proxy=proxy)

@proxies_bp.route('/proxies/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    proxy = Proxy.query.get_or_404(id)
    
    if request.method == 'POST':
        old_is_default = proxy.is_default
        
        proxy.name = request.form.get('name')
        proxy.type = request.form.get('type')
        proxy.host = request.form.get('host')
        proxy.port = int(request.form.get('port'))
        proxy.username = request.form.get('username') if request.form.get('username') else None
        proxy.password = request.form.get('password') if request.form.get('password') else None
        proxy.description = request.form.get('description')
        proxy.is_active = 'is_active' in request.form
        proxy.is_default = 'is_default' in request.form
        
        # 如果设置为默认代理，取消其他默认代理
        if proxy.is_default and not old_is_default:
            Proxy.query.filter_by(is_default=True).update({'is_default': False})
        
        db.session.commit()
        flash('代理更新成功！', 'success')
        return redirect(url_for('proxies.index'))
    
    return render_template('proxies/edit.html', proxy=proxy)

@proxies_bp.route('/proxies/<int:id>/delete', methods=['POST'])
def delete(id):
    proxy = Proxy.query.get_or_404(id)
    
    # 检查是否有URL监控在使用此代理
    if proxy.url_checks.count() > 0:
        flash('无法删除：有URL监控正在使用此代理', 'error')
        return redirect(url_for('proxies.index'))
    
    db.session.delete(proxy)
    db.session.commit()
    flash('代理已删除', 'success')
    return redirect(url_for('proxies.index'))

@proxies_bp.route('/proxies/<int:id>/test', methods=['POST'])
def test_proxy(id):
    """测试代理连接"""
    proxy = Proxy.query.get_or_404(id)
    
    try:
        # 准备测试URL
        test_url = 'http://httpbin.org/ip'
        
        # 准备代理配置
        proxies = {}
        if proxy.type in ['http', 'https']:
            proxies[proxy.type] = proxy.proxy_url
        elif proxy.type in ['socks4', 'socks5']:
            # 使用代理模型的proxy_dict方法
            proxies = proxy.proxy_dict
        
        # 测试代理
        start_time = time.time()
        response = requests.get(
            test_url,
            proxies=proxies,
            timeout=10,
            verify=False
        )
        response_time = (time.time() - start_time) * 1000  # 转换为毫秒
        
        if response.status_code == 200:
            # 更新代理状态
            proxy.is_working = True
            proxy.response_time = response_time
            proxy.last_checked = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': f'代理测试成功！响应时间: {response_time:.2f}ms',
                'response_time': response_time,
                'ip_info': response.json()
            })
        else:
            proxy.is_working = False
            proxy.last_checked = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'status': 'error',
                'message': f'代理测试失败，状态码: {response.status_code}'
            })
            
    except requests.exceptions.ProxyError:
        proxy.is_working = False
        proxy.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'error',
            'message': '代理连接失败'
        })
    except requests.exceptions.Timeout:
        proxy.is_working = False
        proxy.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'error',
            'message': '代理连接超时'
        })
    except Exception as e:
        proxy.is_working = False
        proxy.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'error',
            'message': f'代理测试失败: {str(e)}'
        })

@proxies_bp.route('/proxies/<int:id>/toggle', methods=['POST'])
def toggle(id):
    """启用/禁用代理"""
    proxy = Proxy.query.get_or_404(id)
    proxy.is_active = not proxy.is_active
    db.session.commit()
    
    status = "启用" if proxy.is_active else "禁用"
    flash(f'代理已{status}', 'success')
    return redirect(url_for('proxies.index'))

