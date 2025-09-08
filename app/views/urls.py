from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.url import URL
from app.models.notification import URLCheck, NotificationConfig
from app.models.proxy import Proxy
from app import db
from app.services.url_checker import check_single_url
from app.utils.timezone import get_current_beijing_time
import json

urls_bp = Blueprint('urls', __name__)

@urls_bp.route('/urls')
def index():
    # 获取搜索参数
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 构建查询
    query = URL.query
    
    # 搜索功能
    if search:
        query = query.filter(
            URL.name.contains(search) |
            URL.url.contains(search) |
            URL.description.contains(search)
        )
    
    # 分页
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    urls = pagination.items
    
    return render_template('urls/index.html', 
                         urls=urls, 
                         pagination=pagination, 
                         search=search,
                         per_page=per_page)

@urls_bp.route('/urls/new', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        name = request.form.get('name')
        url = request.form.get('url')
        description = request.form.get('description')
        check_interval = int(request.form.get('check_interval', 60))
        timeout = int(request.form.get('timeout', 10))
        retry_count = int(request.form.get('retry_count', 1))
        
        # HTTP请求配置
        method = request.form.get('method', 'GET')
        headers = request.form.get('headers', '')
        body = request.form.get('body', '')
        content_type = request.form.get('content_type', 'application/json')
        
        # 验证配置
        expected_status_codes = request.form.get('expected_status_codes', '200')
        expected_response_contains = request.form.get('expected_response_contains', '')
        expected_response_not_contains = request.form.get('expected_response_not_contains', '')
        response_time_threshold = float(request.form.get('response_time_threshold', 5.0))
        
        # 高级配置
        follow_redirects = 'follow_redirects' in request.form
        verify_ssl = 'verify_ssl' in request.form
        accept_invalid_cert = 'accept_invalid_cert' in request.form
        
        notification_config_id = request.form.get('notification_config_id')
        proxy_id = request.form.get('proxy_id')
        
        # 验证必填字段
        if not name or not url:
            flash('名称和URL不能为空', 'error')
            return render_template('urls/new.html', 
                                 notification_configs=NotificationConfig.query.filter_by(is_active=True).all(),
                                 proxies=Proxy.query.filter_by(is_active=True).all())
        
        # 验证headers格式
        if headers:
            try:
                json.loads(headers)
            except json.JSONDecodeError:
                flash('请求头格式错误，请输入有效的JSON格式', 'error')
                return render_template('urls/new.html', 
                                     notification_configs=NotificationConfig.query.filter_by(is_active=True).all(),
                                     proxies=Proxy.query.filter_by(is_active=True).all())
        
        # 验证body格式（如果是JSON）
        if body and content_type == 'application/json':
            try:
                json.loads(body)
            except json.JSONDecodeError:
                flash('请求体格式错误，请输入有效的JSON格式', 'error')
                return render_template('urls/new.html', 
                                     notification_configs=NotificationConfig.query.filter_by(is_active=True).all(),
                                     proxies=Proxy.query.filter_by(is_active=True).all())
        
        url_obj = URL(
            name=name,
            url=url,
            description=description,
            check_interval=check_interval,
            timeout=timeout,
            retry_count=retry_count,
            method=method,
            headers=headers,
            body=body,
            content_type=content_type,
            expected_status_codes=expected_status_codes,
            expected_response_contains=expected_response_contains,
            expected_response_not_contains=expected_response_not_contains,
            response_time_threshold=response_time_threshold,
            follow_redirects=follow_redirects,
            verify_ssl=verify_ssl,
            accept_invalid_cert=accept_invalid_cert,
            notification_config_id=notification_config_id if notification_config_id else None,
            proxy_id=proxy_id if proxy_id else None
        )
        
        db.session.add(url_obj)
        db.session.commit()
        
        flash('URL监控添加成功！', 'success')
        return redirect(url_for('urls.index'))
    
    return render_template('urls/new.html', 
                         notification_configs=NotificationConfig.query.filter_by(is_active=True).all(),
                         proxies=Proxy.query.filter_by(is_active=True).all())

@urls_bp.route('/urls/<int:id>')
def show(id):
    url_obj = URL.query.get_or_404(id)
    return render_template('urls/show.html', url=url_obj)

@urls_bp.route('/urls/<int:id>/check', methods=['POST'])
def check(id):
    """立即检查URL并返回结果"""
    url_obj = URL.query.get_or_404(id)
    
    if not url_obj.is_active:
        return jsonify({'status': 'error', 'message': 'URL监控已禁用'})
    
    try:
        from app.services.url_checker import URLChecker
        
        # 执行检查
        result = URLChecker._perform_check(url_obj)
        
        # 保存检查结果
        URLChecker._save_check_result(url_obj, result)
        
        # 准备返回数据
        if result['is_available']:
            return jsonify({
                'status': 'success',
                'message': f'URL检查成功！响应时间: {result["response_time"]:.2f}秒',
                'response_time': result['response_time'],
                'status_code': result['status_code'],
                'response_size': result['response_size']
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'URL检查失败: {result.get("error_message", "未知错误")}',
                'response_time': result.get('response_time'),
                'status_code': result.get('status_code'),
                'response_size': result.get('response_size')
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'检查失败: {str(e)}'
        })

@urls_bp.route('/urls/<int:id>/check_async', methods=['POST'])
def check_async(id):
    """异步检查URL"""
    url_obj = URL.query.get_or_404(id)
    
    if not url_obj.is_active:
        return jsonify({'status': 'error', 'message': 'URL监控已禁用'})
    
    try:
        import threading
        from app.services.url_checker import URLChecker
        
        def async_check():
            from app import create_app
            app = create_app(init_scheduler=False)
            with app.app_context():
                try:
                    URLChecker.check_single_url(url_obj.id)
                except Exception as e:
                    print(f"异步URL检查失败 {url_obj.name}: {str(e)}")
        
        thread = threading.Thread(target=async_check)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success', 
            'message': f'已开始检查 {url_obj.name}，请稍后刷新页面查看结果'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'启动检查失败: {str(e)}'})

@urls_bp.route('/urls/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    url_obj = URL.query.get_or_404(id)
    
    if request.method == 'POST':
        url_obj.name = request.form.get('name')
        url_obj.url = request.form.get('url')
        url_obj.description = request.form.get('description')
        url_obj.check_interval = int(request.form.get('check_interval', 60))
        url_obj.timeout = int(request.form.get('timeout', 10))
        url_obj.retry_count = int(request.form.get('retry_count', 1))
        
        # HTTP请求配置
        url_obj.method = request.form.get('method', 'GET')
        url_obj.headers = request.form.get('headers', '')
        url_obj.body = request.form.get('body', '')
        url_obj.content_type = request.form.get('content_type', 'application/json')
        
        # 验证配置
        url_obj.expected_status_codes = request.form.get('expected_status_codes', '200')
        url_obj.expected_response_contains = request.form.get('expected_response_contains', '')
        url_obj.expected_response_not_contains = request.form.get('expected_response_not_contains', '')
        url_obj.response_time_threshold = float(request.form.get('response_time_threshold', 5.0))
        
        # 高级配置
        url_obj.follow_redirects = 'follow_redirects' in request.form
        url_obj.verify_ssl = 'verify_ssl' in request.form
        url_obj.accept_invalid_cert = 'accept_invalid_cert' in request.form
        
        notification_config_id = request.form.get('notification_config_id')
        url_obj.notification_config_id = notification_config_id if notification_config_id else None
        
        proxy_id = request.form.get('proxy_id')
        url_obj.proxy_id = proxy_id if proxy_id else None
        
        # 验证headers格式
        if url_obj.headers:
            try:
                json.loads(url_obj.headers)
            except json.JSONDecodeError:
                flash('请求头格式错误，请输入有效的JSON格式', 'error')
                return render_template('urls/edit.html', 
                                     url=url_obj, 
                                     notification_configs=NotificationConfig.query.filter_by(is_active=True).all(),
                                     proxies=Proxy.query.filter_by(is_active=True).all())
        
        # 验证body格式（如果是JSON）
        if url_obj.body and url_obj.content_type == 'application/json':
            try:
                json.loads(url_obj.body)
            except json.JSONDecodeError:
                flash('请求体格式错误，请输入有效的JSON格式', 'error')
                return render_template('urls/edit.html', 
                                     url=url_obj, 
                                     notification_configs=NotificationConfig.query.filter_by(is_active=True).all(),
                                     proxies=Proxy.query.filter_by(is_active=True).all())
        
        db.session.commit()
        flash('URL监控更新成功！', 'success')
        return redirect(url_for('urls.show', id=id))
    
    return render_template('urls/edit.html', 
                         url=url_obj, 
                         notification_configs=NotificationConfig.query.filter_by(is_active=True).all(),
                         proxies=Proxy.query.filter_by(is_active=True).all())

@urls_bp.route('/urls/<int:id>/toggle', methods=['POST'])
def toggle(id):
    """切换URL监控状态"""
    url_obj = URL.query.get_or_404(id)
    url_obj.is_active = not url_obj.is_active
    db.session.commit()
    
    status = '启用' if url_obj.is_active else '禁用'
    flash(f'URL监控已{status}', 'success')
    return redirect(url_for('urls.index'))

@urls_bp.route('/urls/<int:id>/delete', methods=['POST'])
def delete(id):
    url_obj = URL.query.get_or_404(id)
    db.session.delete(url_obj)
    db.session.commit()
    flash('URL监控删除成功！', 'success')
    return redirect(url_for('urls.index'))
