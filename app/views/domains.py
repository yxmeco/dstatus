from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.domain import Domain
from app.models.certificate import Certificate
from app.models.notification import WhoisRecord, NotificationConfig
from app import db
from app.services.ssl_checker import check_single_certificate
from app.services.whois_checker import check_single_whois
from app.services.domain_access_checker import check_single_domain_access
from app.services.cert_parser import CertParser
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
                certificate.days_until_expiry = (cert_info['not_after'] - datetime.utcnow()).days
                certificate.is_valid = True
                certificate.last_checked = datetime.utcnow()
                
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
        
        # 如果启用了WHOIS检查，立即创建WHOIS记录并设置为查询中状态
        if check_whois:
            # 立即创建WHOIS记录，设置为查询中状态
            from app.services.whois_checker import WhoisChecker
            whois_record = WhoisRecord.query.filter_by(domain_id=domain.id).first()
            if not whois_record:
                whois_record = WhoisRecord(domain_id=domain.id)
            
            whois_record.last_checked = datetime.utcnow()
            whois_record.is_valid = False  # 暂时标记为无效，表示正在查询
            whois_record.error_message = "查询中..."  # 临时错误信息表示查询中
            whois_record.whois_server = "querying"
            
            db.session.add(whois_record)
            db.session.commit()
            
            # 然后异步进行WHOIS查询
            def async_whois_check():
                try:
                    from flask import current_app
                    with current_app.app_context():
                        WhoisChecker.update_whois_record(domain)
                except Exception as e:
                    print(f"异步WHOIS查询失败 {domain.name}: {str(e)}")
            
            # 启动异步线程
            from flask import current_app
            app_instance = current_app._get_current_object()
            thread = threading.Thread(target=lambda: async_whois_check())
            thread.daemon = True
            thread.start()
        
        # 如果启用了访问检查，立即创建访问记录并异步检查
        if check_access:
            # 立即创建访问记录，设置为检查中状态
            from app.models.notification import DomainAccessCheck
            access_record = DomainAccessCheck.query.filter_by(domain_id=domain.id).first()
            if not access_record:
                access_record = DomainAccessCheck(domain_id=domain.id)
            
            access_record.last_checked = datetime.utcnow()
            access_record.is_accessible = False  # 暂时标记为不可访问，表示正在检查
            access_record.error_message = "检查中..."  # 临时错误信息表示检查中
            
            db.session.add(access_record)
            db.session.commit()
            
            # 然后异步进行访问检查
            def async_access_check():
                try:
                    from flask import current_app
                    with current_app.app_context():
                        from app.services.domain_access_checker import DomainAccessChecker
                        DomainAccessChecker.update_domain_access_record(domain)
                except Exception as e:
                    print(f"异步访问检查失败 {domain.name}: {str(e)}")
            
            # 启动异步线程
            from flask import current_app
            app_instance = current_app._get_current_object()
            thread = threading.Thread(target=lambda: async_access_check())
            thread.daemon = True
            thread.start()
        
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
        
        # 启动异步检查
        def async_check_with_app(app_instance):
            try:
                with app_instance.app_context():
                    results = []
                    
                    # 重新获取域名对象（在应用上下文中）
                    current_domain = Domain.query.get(domain.id)
                    if not current_domain:
                        print(f"域名 {domain.name} 不存在")
                        return
                    
                    # 执行WHOIS检查
                    if current_domain.check_whois:
                        try:
                            from app.services.whois_checker import WhoisChecker
                            WhoisChecker.update_whois_record(current_domain)
                            results.append('WHOIS检查完成')
                        except Exception as e:
                            print(f'WHOIS检查失败: {str(e)}')
                            results.append(f'WHOIS检查失败: {str(e)}')
                    
                    # 执行SSL证书检查
                    if current_domain.check_ssl and current_domain.certificates:
                        try:
                            from app.services.ssl_checker import SSLChecker
                            SSLChecker.update_certificate_info(current_domain)
                            results.append('SSL证书检查完成')
                        except Exception as e:
                            print(f'SSL证书检查失败: {str(e)}')
                            results.append(f'SSL证书检查失败: {str(e)}')
                    
                    # 执行访问检查
                    if current_domain.check_access:
                        try:
                            from app.services.domain_access_checker import DomainAccessChecker
                            DomainAccessChecker.update_domain_access_record(current_domain)
                            results.append('访问检查完成')
                        except Exception as e:
                            print(f'访问检查失败: {str(e)}')
                            results.append(f'访问检查失败: {str(e)}')
                    
                    print(f"域名 {current_domain.name} 异步检查完成: {', '.join(results)}")
                        
            except Exception as e:
                print(f"异步检查失败 {domain.name}: {str(e)}")
        
        # 启动异步线程，传递应用实例
        from flask import current_app
        app_instance = current_app._get_current_object()
        thread = threading.Thread(target=lambda: async_check_with_app(app_instance))
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
        
        # 如果启用了WHOIS检查且之前未启用，立即创建WHOIS记录并异步查询
        if domain.check_whois and not old_check_whois:
            # 立即创建WHOIS记录，设置为查询中状态
            whois_record = WhoisRecord.query.filter_by(domain_id=domain.id).first()
            if not whois_record:
                whois_record = WhoisRecord(domain_id=domain.id)
            
            whois_record.last_checked = datetime.utcnow()
            whois_record.is_valid = False  # 暂时标记为无效，表示正在查询
            whois_record.error_message = "查询中..."  # 临时错误信息表示查询中
            whois_record.whois_server = "querying"
            
            db.session.add(whois_record)
            db.session.commit()
            
            # 然后异步进行WHOIS查询
            def async_whois_check():
                try:
                    from flask import current_app
                    with current_app.app_context():
                        from app.services.whois_checker import WhoisChecker
                        WhoisChecker.update_whois_record(domain)
                except Exception as e:
                    print(f"异步WHOIS查询失败 {domain.name}: {str(e)}")
            
            # 启动异步线程
            from flask import current_app
            app_instance = current_app._get_current_object()
            thread = threading.Thread(target=lambda: async_whois_check())
            thread.daemon = True
            thread.start()
        
        # 如果启用了访问检查且之前未启用，立即创建访问记录并异步检查
        if domain.check_access and not old_check_access:
            # 立即创建访问记录，设置为检查中状态
            from app.models.notification import DomainAccessCheck
            access_record = DomainAccessCheck.query.filter_by(domain_id=domain.id).first()
            if not access_record:
                access_record = DomainAccessCheck(domain_id=domain.id)
            
            access_record.last_checked = datetime.utcnow()
            access_record.is_accessible = False  # 暂时标记为不可访问，表示正在检查
            access_record.error_message = "检查中..."  # 临时错误信息表示检查中
            
            db.session.add(access_record)
            db.session.commit()
            
            # 然后异步进行访问检查
            def async_access_check():
                try:
                    from flask import current_app
                    with current_app.app_context():
                        from app.services.domain_access_checker import DomainAccessChecker
                        DomainAccessChecker.update_domain_access_record(domain)
                except Exception as e:
                    print(f"异步访问检查失败 {domain.name}: {str(e)}")
            
            # 启动异步线程
            from flask import current_app
            app_instance = current_app._get_current_object()
            thread = threading.Thread(target=lambda: async_access_check())
            thread.daemon = True
            thread.start()
        
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
                certificate.days_until_expiry = (cert_info['not_after'] - datetime.utcnow()).days
                certificate.is_valid = True
                certificate.last_checked = datetime.utcnow()
                
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
