from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.domain import Domain
from app.models.certificate import Certificate
from app.models.notification import WhoisRecord, NotificationConfig
from app import db
from app.services.ssl_checker import check_single_certificate
from app.services.whois_checker import check_single_whois
from app.services.domain_access_checker import check_single_domain_access
from app.services.cert_parser import CertParser
from app.utils.timezone import get_current_beijing_time
from datetime import datetime
import os
import threading

domains_bp = Blueprint('domains', __name__)

@domains_bp.route('/domains')
def index():
    # 获取搜索参数
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 构建查询
    query = Domain.query
    
    # 搜索功能
    if search:
        query = query.filter(
            Domain.name.contains(search) |
            Domain.description.contains(search)
        )
    
    # 分页
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    domains = pagination.items
    
    return render_template('domains/index.html', 
                         domains=domains, 
                         pagination=pagination, 
                         search=search,
                         per_page=per_page)

@domains_bp.route('/domains/new', methods=['GET', 'POST'])
def new():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        check_ssl = 'check_ssl' in request.form
        check_whois = 'check_whois' in request.form
        check_access = 'check_access' in request.form
        notification_config_id = request.form.get('notification_config_id')
        
        # 验证必填字段
        if not name:
            flash('域名名称不能为空', 'error')
            return render_template('domains/new.html', notification_configs=NotificationConfig.query.filter_by(is_active=True).all())
        
        # 检查域名是否已存在
        existing_domain = Domain.query.filter_by(name=name).first()
        if existing_domain:
            flash('域名已存在', 'error')
            return render_template('domains/new.html', notification_configs=NotificationConfig.query.filter_by(is_active=True).all())
        
        domain = Domain(
            name=name,
            description=description,
            check_ssl=check_ssl,
            check_whois=check_whois,
            check_access=check_access,
            notification_config_id=notification_config_id if notification_config_id else None
        )
        
        db.session.add(domain)
        db.session.commit()
        
        # 处理证书文件上传
        cert_file = request.files.get('cert_file')
        key_file = request.files.get('key_file')
        
        if cert_file and cert_file.filename:
            # 验证证书文件
            validation_errors = CertParser.validate_certificate_files(cert_file, key_file)
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'error')
                # 删除已创建的域名
                db.session.delete(domain)
                db.session.commit()
                return render_template('domains/new.html', notification_configs=NotificationConfig.query.filter_by(is_active=True).all())
            
            try:
                # 解析证书信息
                cert_info = CertParser.parse_certificate_file(cert_file)
                
                # 保存证书文件
                cert_save_result = CertParser.save_certificate_file(cert_file, domain.name)
                
                # 保存私钥文件（如果提供）
                key_save_result = None
                if key_file and key_file.filename:
                    key_save_result = CertParser.save_private_key_file(key_file, domain.name)
                
                # 创建证书记录
                certificate = Certificate(domain_id=domain.id)
                certificate.issuer = cert_info['issuer']
                certificate.subject = cert_info['subject']
                certificate.serial_number = cert_info['serial_number']
                certificate.not_before = cert_info['not_before']
                certificate.not_after = cert_info['not_after']
                
                # 修复时区问题：确保两个datetime对象都是naive或都是aware
                not_after = cert_info['not_after']
                current_time = get_current_beijing_time()
                
                # 如果not_after是naive，将其转换为aware（假设为UTC）
                if not_after.tzinfo is None:
                    import pytz
                    not_after = pytz.UTC.localize(not_after)
                
                certificate.days_until_expiry = (not_after - current_time).days
                certificate.is_valid = True
                certificate.last_checked = get_current_beijing_time()
                
                # 保存域名信息
                certificate.common_name = cert_info.get('common_name')
                certificate.san_domains = cert_info.get('san_domains')
                certificate.cert_domains = cert_info.get('cert_domains')
                
                # 保存文件路径
                if cert_save_result['is_saved']:
                    certificate.cert_file_path = cert_save_result['file_path']
                    certificate.cert_file_name = cert_save_result['file_name']
                
                if key_save_result and key_save_result['is_saved']:
                    certificate.key_file_path = key_save_result['file_path']
                    certificate.key_file_name = key_save_result['file_name']
                
                db.session.add(certificate)
                db.session.commit()
                
                # 如果上传了证书，自动启用SSL检查
                if not check_ssl:
                    domain.check_ssl = True
                    db.session.commit()
                
                flash('证书文件上传成功，证书信息已自动解析，SSL检查已自动启用', 'success')
                
            except Exception as e:
                flash(f'证书文件处理失败: {str(e)}', 'error')
                # 删除已创建的域名
                db.session.delete(domain)
                db.session.commit()
                return render_template('domains/new.html', notification_configs=NotificationConfig.query.filter_by(is_active=True).all())
        
        # 如果启用了WHOIS检查，异步进行WHOIS查询
        if check_whois:
            def perform_whois_check():
                from app import create_app
                app = create_app(init_scheduler=False)
                with app.app_context():
                    try:
                        # 重新获取domain对象，避免会话绑定问题
                        current_domain = Domain.query.get(domain.id)
                        if current_domain:
                            print(f"开始WHOIS检查: {current_domain.name}")
                            result = check_single_whois(current_domain.id)
                            if result:
                                print(f"WHOIS检查成功: {current_domain.name}")
                            else:
                                print(f"WHOIS检查失败: {current_domain.name}")
                        else:
                            print(f"域名 {domain.name} 不存在")
                    except Exception as e:
                        print(f"WHOIS检查异常: {str(e)}")
            
            thread = threading.Thread(target=perform_whois_check)
            thread.daemon = False  # 改为非守护线程，确保线程能够完成
            thread.start()
            
            # 给线程更多时间开始执行，确保WHOIS检查能够完成
            import time
            time.sleep(0.5)  # 增加等待时间
        
        # 如果启用了访问检查，自动创建URL监控项
        if check_access:
            try:
                from app.models.url import URL
                
                # 创建官网URL监控项
                website_url = URL(
                    name=f"{domain.name} 官网监控",
                    url=f"https://{domain.name}",
                    description=f"域名 {domain.name} 的官网可用性监控",
                    check_interval=1,  # 默认1分钟检查一次，与URL监控默认值保持一致
                    timeout=10,  # 默认10秒超时
                    retry_count=1,  # 默认重试1次
                    method='GET',
                    expected_status_codes='200',
                    response_time_threshold=5.0,
                    follow_redirects=True,
                    verify_ssl=True,
                    notification_config_id=domain.notification_config_id
                )
                
                # 使用同一个会话添加URL监控项
                db.session.add(website_url)
                db.session.flush()  # 刷新以获取ID，但不提交
                
                # 关联到域名
                domain.website_url_id = website_url.id
                db.session.commit()  # 一次性提交所有更改
                
                flash('官网可用性监控已自动创建', 'success')
                
            except Exception as e:
                db.session.rollback()  # 发生错误时回滚
                flash(f'创建官网监控失败: {str(e)}', 'error')
                print(f"创建官网监控失败: {str(e)}")
        
        flash('域名添加成功！', 'success')
        return redirect(url_for('domains.index'))
    
    return render_template('domains/new.html', notification_configs=NotificationConfig.query.filter_by(is_active=True).all())

@domains_bp.route('/domains/<int:id>')
def show(id):
    domain = Domain.query.get_or_404(id)
    return render_template('domains/show.html', domain=domain)

@domains_bp.route('/domains/<int:id>/check', methods=['POST'])
def check(id):
    domain = Domain.query.get_or_404(id)
    
    if domain.check_ssl:
        check_single_certificate(domain.id)
    
    if domain.check_whois:
        check_single_whois(domain.id)
    
    if domain.check_access:
        check_single_domain_access(domain.id)
    
    flash('检查完成', 'info')
    return redirect(url_for('domains.show', id=id))

@domains_bp.route('/domains/<int:id>/check_async', methods=['POST'])
def check_async(id):
    """异步检查域名（WHOIS、SSL、访问）"""
    domain = Domain.query.get_or_404(id)
    
    if not domain.is_active:
        return jsonify({'status': 'error', 'message': '域名已禁用'})
    
    try:
        # 检查启用了哪些检查
        checks_to_perform = []
        if domain.check_whois:
            checks_to_perform.append('WHOIS')
        if domain.check_ssl and domain.certificates:
            checks_to_perform.append('SSL证书')
        if domain.check_access:
            checks_to_perform.append('访问检查')
        
        if not checks_to_perform:
            return jsonify({'status': 'error', 'message': '没有启用任何检查项目'})
        

        
        # 启动异步线程
        def perform_async_check():
            from app import create_app
            app = create_app(init_scheduler=False)
            with app.app_context():
                try:
                    results = []
                    
                    # 重新获取域名对象（在应用上下文中）
                    current_domain = Domain.query.get(domain.id)
                    if not current_domain:
                        print(f"域名 {domain.name} 不存在")
                        return
                    
                    # 执行WHOIS检查
                    if current_domain.check_whois:
                        try:
                            check_single_whois(current_domain.id)
                            results.append('WHOIS检查完成')
                        except Exception as e:
                            print(f'WHOIS检查失败: {str(e)}')
                            results.append(f'WHOIS检查失败: {str(e)}')
                    
                    # 执行SSL证书检查
                    if current_domain.check_ssl and current_domain.certificates:
                        try:
                            check_single_certificate(current_domain.id)
                            results.append('SSL证书检查完成')
                        except Exception as e:
                            print(f'SSL证书检查失败: {str(e)}')
                            results.append(f'SSL证书检查失败: {str(e)}')
                    
                    # 执行访问检查
                    if current_domain.check_access:
                        try:
                            # 优先使用URL监控检查
                            if current_domain.website_url_id:
                                from app.services.url_checker import URLChecker
                                URLChecker.check_single_url(current_domain.website_url_id)
                                results.append('官网可用性检查完成')
                            else:
                                # 回退到旧的访问检查
                                check_single_domain_access(current_domain.id)
                                results.append('访问检查完成')
                        except Exception as e:
                            print(f'访问检查失败: {str(e)}')
                            results.append(f'访问检查失败: {str(e)}')
                    
                    print(f"域名 {current_domain.name} 异步检查完成: {', '.join(results)}")
                        
                except Exception as e:
                    print(f"异步检查失败 {domain.name}: {str(e)}")
        
        thread = threading.Thread(target=perform_async_check)
        thread.daemon = True
        thread.start()
        
        checks_text = '、'.join(checks_to_perform)
        return jsonify({
            'status': 'success', 
            'message': f'已开始执行{checks_text}检查，请稍后刷新页面查看结果',
            'checks': checks_to_perform
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'启动检查失败: {str(e)}'})

@domains_bp.route('/domains/<int:id>/check_whois_async', methods=['POST'])
def check_whois_async(id):
    """异步WHOIS检查接口"""
    domain = Domain.query.get_or_404(id)
    
    def async_whois_check():
        from app import create_app
        app = create_app(init_scheduler=False)
        with app.app_context():
            try:
                check_single_whois(domain.id)
            except Exception as e:
                print(f"异步WHOIS查询失败 {domain.name}: {str(e)}")
    
    # 启动异步线程
    thread = threading.Thread(target=async_whois_check)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'success', 'message': 'WHOIS查询已开始'})

@domains_bp.route('/domains/<int:id>/check_access_async', methods=['POST'])
def check_access_async(id):
    """异步访问检查接口"""
    domain = Domain.query.get_or_404(id)
    
    def async_access_check():
        from app import create_app
        app = create_app(init_scheduler=False)
        with app.app_context():
            try:
                check_single_domain_access(domain.id)
            except Exception as e:
                print(f"异步访问检查失败 {domain.name}: {str(e)}")
    
    # 启动异步线程
    thread = threading.Thread(target=async_access_check)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'success', 'message': '访问检查已开始'})

@domains_bp.route('/domains/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    domain = Domain.query.get_or_404(id)
    
    if request.method == 'POST':
        old_check_whois = domain.check_whois
        old_check_access = domain.check_access
        domain.name = request.form.get('name')
        domain.description = request.form.get('description')
        domain.check_ssl = 'check_ssl' in request.form
        domain.check_whois = 'check_whois' in request.form
        domain.check_access = 'check_access' in request.form
        notification_config_id = request.form.get('notification_config_id')
        domain.notification_config_id = notification_config_id if notification_config_id else None
        
        # 如果启用了WHOIS检查且之前未启用，异步进行WHOIS查询
        if domain.check_whois and not old_check_whois:
            def perform_whois_check():
                from app import create_app
                app = create_app(init_scheduler=False)
                with app.app_context():
                    try:
                        # 重新获取domain对象，避免会话绑定问题
                        current_domain = Domain.query.get(domain.id)
                        if current_domain:
                            check_single_whois(current_domain.id)
                        else:
                            print(f"域名 {domain.name} 不存在")
                    except Exception as e:
                        print(f"WHOIS检查失败: {str(e)}")
            
            thread = threading.Thread(target=perform_whois_check)
            thread.daemon = True
            thread.start()
        
        # 如果启用了访问检查且之前未启用，创建URL监控项
        if domain.check_access and not old_check_access:
            try:
                from app.models.url import URL
                
                # 检查是否已经有官网URL监控项
                if not domain.website_url_id:
                    # 创建官网URL监控项
                    website_url = URL(
                        name=f"{domain.name} 官网监控",
                        url=f"https://{domain.name}",
                        description=f"域名 {domain.name} 的官网可用性监控",
                        check_interval=1,  # 默认1分钟检查一次，与URL监控默认值保持一致
                        timeout=10,  # 默认10秒超时
                        retry_count=1,  # 默认重试1次
                        method='GET',
                        expected_status_codes='200',
                        response_time_threshold=5.0,
                        follow_redirects=True,
                        verify_ssl=True,
                        notification_config_id=domain.notification_config_id
                    )
                    
                    # 使用同一个会话添加URL监控项
                    db.session.add(website_url)
                    db.session.flush()  # 刷新以获取ID，但不提交
                    
                    # 关联到域名
                    domain.website_url_id = website_url.id
                    db.session.commit()  # 一次性提交所有更改
                    
                    flash('官网可用性监控已自动创建', 'success')
                
            except Exception as e:
                db.session.rollback()  # 发生错误时回滚
                flash(f'创建官网监控失败: {str(e)}', 'error')
                print(f"创建官网监控失败: {str(e)}")
        
        # 如果禁用了访问检查，删除关联的URL监控项
        elif not domain.check_access and old_check_access and domain.website_url_id:
            try:
                from app.models.url import URL
                website_url = URL.query.get(domain.website_url_id)
                if website_url:
                    db.session.delete(website_url)
                    domain.website_url_id = None
                    db.session.commit()
                    flash('官网可用性监控已删除', 'success')
            except Exception as e:
                flash(f'删除官网监控失败: {str(e)}', 'error')
                print(f"删除官网监控失败: {str(e)}")
        
        # 处理证书文件更新
        cert_file = request.files.get('cert_file')
        key_file = request.files.get('key_file')
        
        if cert_file and cert_file.filename:
            # 验证证书文件
            validation_errors = CertParser.validate_certificate_files(cert_file, key_file)
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'error')
                return render_template('domains/edit.html', domain=domain, notification_configs=NotificationConfig.query.filter_by(is_active=True).all())
            
            try:
                # 删除旧的证书文件
                for certificate in domain.certificates:
                    if certificate.cert_file_path and os.path.exists(certificate.cert_file_path):
                        os.remove(certificate.cert_file_path)
                    if certificate.key_file_path and os.path.exists(certificate.key_file_path):
                        os.remove(certificate.key_file_path)
                
                # 解析新证书信息
                cert_info = CertParser.parse_certificate_file(cert_file)
                
                # 保存新证书文件
                cert_save_result = CertParser.save_certificate_file(cert_file, domain.name)
                
                # 保存新私钥文件（如果提供）
                key_save_result = None
                if key_file and key_file.filename:
                    key_save_result = CertParser.save_private_key_file(key_file, domain.name)
                
                # 更新或创建证书记录
                if domain.certificates:
                    certificate = domain.certificates[0]
                else:
                    certificate = Certificate(domain_id=domain.id)
                    db.session.add(certificate)
                
                certificate.issuer = cert_info['issuer']
                certificate.subject = cert_info['subject']
                certificate.serial_number = cert_info['serial_number']
                certificate.not_before = cert_info['not_before']
                certificate.not_after = cert_info['not_after']
                
                # 修复时区问题：确保两个datetime对象都是naive或都是aware
                not_after = cert_info['not_after']
                current_time = get_current_beijing_time()
                
                # 如果not_after是naive，将其转换为aware（假设为UTC）
                if not_after.tzinfo is None:
                    import pytz
                    not_after = pytz.UTC.localize(not_after)
                
                certificate.days_until_expiry = (not_after - current_time).days
                certificate.is_valid = True
                certificate.last_checked = get_current_beijing_time()
                
                # 更新域名信息
                certificate.common_name = cert_info.get('common_name')
                certificate.san_domains = cert_info.get('san_domains')
                certificate.cert_domains = cert_info.get('cert_domains')
                
                # 更新文件路径
                if cert_save_result['is_saved']:
                    certificate.cert_file_path = cert_save_result['file_path']
                    certificate.cert_file_name = cert_save_result['file_name']
                
                if key_save_result and key_save_result['is_saved']:
                    certificate.key_file_path = key_save_result['file_path']
                    certificate.key_file_name = key_save_result['file_name']
                
                # 如果上传了证书，自动启用SSL检查
                if not domain.check_ssl:
                    domain.check_ssl = True
                
                flash('证书文件更新成功，证书信息已自动解析，SSL检查已自动启用', 'success')
                
            except Exception as e:
                flash(f'证书文件处理失败: {str(e)}', 'error')
                return render_template('domains/edit.html', domain=domain, notification_configs=NotificationConfig.query.filter_by(is_active=True).all())
        
        db.session.commit()
        flash('域名更新成功！', 'success')
        return redirect(url_for('domains.show', id=id))
    
    return render_template('domains/edit.html', domain=domain, notification_configs=NotificationConfig.query.filter_by(is_active=True).all())

@domains_bp.route('/domains/<int:id>/delete', methods=['POST'])
def delete(id):
    domain = Domain.query.get_or_404(id)
    
    # 删除相关的证书文件
    for certificate in domain.certificates:
        if certificate.cert_file_path and os.path.exists(certificate.cert_file_path):
            os.remove(certificate.cert_file_path)
        if certificate.key_file_path and os.path.exists(certificate.key_file_path):
            os.remove(certificate.key_file_path)
    
    # 删除关联的官网URL监控项
    if domain.website_url_id:
        from app.models.url import URL
        website_url = URL.query.get(domain.website_url_id)
        if website_url:
            db.session.delete(website_url)
    
    db.session.delete(domain)
    db.session.commit()
    flash('域名及其相关记录已删除', 'success')
    return redirect(url_for('domains.index'))

@domains_bp.route('/domains/<int:id>/clear_certificate', methods=['POST'])
def clear_certificate(id):
    """清空域名的SSL证书"""
    domain = Domain.query.get_or_404(id)
    
    try:
        # 删除相关的证书文件
        for certificate in domain.certificates:
            if certificate.cert_file_path and os.path.exists(certificate.cert_file_path):
                os.remove(certificate.cert_file_path)
            if certificate.key_file_path and os.path.exists(certificate.key_file_path):
                os.remove(certificate.key_file_path)
        
        # 删除数据库中的证书记录
        for certificate in domain.certificates:
            db.session.delete(certificate)
        
        # 禁用SSL检查
        domain.check_ssl = False
        
        db.session.commit()
        flash('证书已成功清空，SSL检查已禁用', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'清空证书失败: {str(e)}', 'error')
    
    return redirect(url_for('domains.show', id=id))

@domains_bp.route('/domains/<int:id>/refresh_whois', methods=['POST'])
def refresh_whois(id):
    """异步刷新域名的WHOIS信息"""
    domain = Domain.query.get_or_404(id)
    
    if not domain.check_whois:
        return jsonify({
            'status': 'error',
            'message': '该域名未启用WHOIS检查功能'
        })
    
    try:
        # 在后台线程中执行WHOIS检查
        def perform_whois_check():
            from app import create_app
            app = create_app(init_scheduler=False)
            with app.app_context():
                try:
                    check_single_whois(domain.id)
                except Exception as e:
                    print(f"WHOIS检查失败: {str(e)}")
        
        thread = threading.Thread(target=perform_whois_check)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'WHOIS信息刷新已开始，请稍后查看结果'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'WHOIS刷新失败: {str(e)}'
        })

@domains_bp.route('/domains/<int:id>/refresh_access', methods=['POST'])
def refresh_access(id):
    """异步刷新域名的官网可用性"""
    domain = Domain.query.get_or_404(id)
    
    if not domain.check_access:
        return jsonify({
            'status': 'error',
            'message': '该域名未启用官网可用性检查功能'
        })
    
    # 优先使用URL监控检查
    if domain.website_url_id:
        try:
            from app.services.url_checker import URLChecker
            
            # 在后台线程中执行URL检查
            def perform_url_check():
                from app import create_app
                app = create_app(init_scheduler=False)
                with app.app_context():
                    try:
                        URLChecker.check_single_url(domain.website_url_id)
                    except Exception as e:
                        print(f"URL检查失败: {str(e)}")
            
            thread = threading.Thread(target=perform_url_check)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'status': 'success',
                'message': '官网可用性检查已开始，请稍后查看结果'
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'官网可用性刷新失败: {str(e)}'
            })
    else:
        # 回退到旧的访问检查
        try:
            # 在后台线程中执行访问检查
            def perform_access_check():
                from app import create_app
                app = create_app(init_scheduler=False)
                with app.app_context():
                    try:
                        check_single_domain_access(domain.id)
                    except Exception as e:
                        print(f"访问检查失败: {str(e)}")
            
            thread = threading.Thread(target=perform_access_check)
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'status': 'success',
                'message': '官网可用性检查已开始，请稍后查看结果'
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'官网可用性刷新失败: {str(e)}'
            })
