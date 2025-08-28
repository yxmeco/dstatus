from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.notification import Notification, NotificationConfig
from app import db
from datetime import datetime
from app.utils.timezone import get_current_beijing_time

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/notifications')
def index():
    notifications = Notification.query.order_by(Notification.sent_at.desc()).limit(50).all()
    return render_template('notifications/index.html', notifications=notifications)

@notifications_bp.route('/notifications/config')
def config():
    configs = NotificationConfig.query.all()
    return render_template('notifications/config.html', configs=configs)

@notifications_bp.route('/notifications/config/new', methods=['GET', 'POST'])
def new_config():
    if request.method == 'POST':
        name = request.form.get('name')
        type = request.form.get('type')
        webhook_url = request.form.get('webhook_url')
        wechat_bot_key = request.form.get('wechat_bot_key')
        
        config = NotificationConfig(
            name=name,
            type=type,
            webhook_url=webhook_url,
            wechat_bot_key=wechat_bot_key
        )
        
        db.session.add(config)
        db.session.commit()
        
        flash('通知配置添加成功！', 'success')
        return redirect(url_for('notifications.config'))
    
    return render_template('notifications/new_config.html')

@notifications_bp.route('/notifications/config/<int:id>/edit', methods=['GET', 'POST'])
def edit_config(id):
    config = NotificationConfig.query.get_or_404(id)
    
    if request.method == 'POST':
        config.name = request.form.get('name')
        config.type = request.form.get('type')
        config.webhook_url = request.form.get('webhook_url')
        config.wechat_bot_key = request.form.get('wechat_bot_key')
        config.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('通知配置更新成功！', 'success')
        return redirect(url_for('notifications.config'))
    
    return render_template('notifications/edit_config.html', config=config)

@notifications_bp.route('/notifications/config/<int:id>/delete', methods=['POST'])
def delete_config(id):
    config = NotificationConfig.query.get_or_404(id)
    db.session.delete(config)
    db.session.commit()
    flash('通知配置删除成功！', 'success')
    return redirect(url_for('notifications.config'))

@notifications_bp.route('/notifications/test', methods=['POST'])
def test_notification():
    config_id = request.form.get('config_id')
    config = NotificationConfig.query.get_or_404(config_id)
    
    # 使用北京时区
    current_time = get_current_beijing_time()
    
    test_message = f"""
🚀 测试通知
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 发送时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
📋 配置名称: {config.name}
🔧 配置类型: {config.type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 这是一条测试通知，用于验证通知配置是否正确。
📝 如果您收到此消息，说明通知配置工作正常！

🔍 配置详情:
• 类型: {config.type}
• 状态: {'启用' if config.is_active else '禁用'}
• 创建时间: {config.created_at.strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 提示: 此消息由域名证书管理系统自动发送
    """
    
    from app.services.notifier import Notifier
    
    try:
        if config.type == 'webhook' and config.webhook_url:
            success = Notifier.send_webhook_notification(test_message, config.webhook_url)
        elif config.type == 'wechat_bot' and config.wechat_bot_key:
            success = Notifier.send_wechat_bot_notification(test_message, config.wechat_bot_key)
        else:
            success = False
            flash('通知配置不完整，无法发送测试通知！', 'error')
            return redirect(url_for('notifications.config'))
        
        if success:
            flash('✅ 测试通知发送成功！请检查您的通知渠道是否收到消息。', 'success')
        else:
            flash('❌ 测试通知发送失败！请检查网络连接和配置信息。', 'error')
    except Exception as e:
        flash(f'❌ 测试通知发送出错: {str(e)}', 'error')
    
    return redirect(url_for('notifications.config'))
