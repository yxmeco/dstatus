from flask import Blueprint, jsonify, request
from app.models.domain import Domain
from app.models.certificate import Certificate
from app.models.notification import URLCheck
from app.services.ssl_checker import check_single_certificate
from app.services.url_checker import check_single_url

api_bp = Blueprint('api', __name__)

@api_bp.route('/domains')
def get_domains():
    domains = Domain.query.all()
    return jsonify([{
        'id': domain.id,
        'name': domain.name,
        'url': domain.url,
        'description': domain.description,
        'is_active': domain.is_active,
        'check_ssl': domain.check_ssl,
        'check_url': domain.check_url,
        'created_at': domain.created_at.isoformat()
    } for domain in domains])

@api_bp.route('/domains/<int:id>')
def get_domain(id):
    domain = Domain.query.get_or_404(id)
    return jsonify({
        'id': domain.id,
        'name': domain.name,
        'url': domain.url,
        'description': domain.description,
        'is_active': domain.is_active,
        'check_ssl': domain.check_ssl,
        'check_url': domain.check_url,
        'created_at': domain.created_at.isoformat()
    })

@api_bp.route('/domains/<int:id>/check', methods=['POST'])
def check_domain(id):
    domain = Domain.query.get_or_404(id)
    
    result = {'success': True, 'messages': []}
    
    if domain.check_ssl:
        try:
            check_single_certificate(domain.id)
            result['messages'].append('SSL证书检查完成')
        except Exception as e:
            result['messages'].append(f'SSL证书检查失败: {str(e)}')
            result['success'] = False
    
    if domain.check_url:
        try:
            check_single_url(domain.id)
            result['messages'].append('URL可用性检查完成')
        except Exception as e:
            result['messages'].append(f'URL可用性检查失败: {str(e)}')
            result['success'] = False
    
    return jsonify(result)

@api_bp.route('/certificates')
def get_certificates():
    certificates = Certificate.query.all()
    return jsonify([{
        'id': cert.id,
        'domain_id': cert.domain_id,
        'domain_name': cert.domain.name,
        'issuer': cert.issuer,
        'subject': cert.subject,
        'not_before': cert.not_before.isoformat() if cert.not_before else None,
        'not_after': cert.not_after.isoformat() if cert.not_after else None,
        'days_until_expiry': cert.days_until_expiry,
        'is_valid': cert.is_valid,
        'is_expired': cert.is_expired,
        'is_expiring_soon': cert.is_expiring_soon,
        'last_checked': cert.last_checked.isoformat() if cert.last_checked else None
    } for cert in certificates])
