from app import create_app, db
import os
import sys

def ensure_instance_directory():
    """确保instance目录存在"""
    instance_dir = os.path.join(os.getcwd(), 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)
        print(f"创建instance目录: {instance_dir}")
    return instance_dir

def get_database_path(app):
    """获取数据库文件路径"""
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///'):
        # 移除sqlite:///前缀
        db_path = db_uri.replace('sqlite:///', '')
        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.getcwd(), db_path)
        # 确保目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        return db_path
    return None

def get_actual_database_path(app):
    """获取实际的数据库文件路径（考虑Flask的instance_path）"""
    # 首先尝试从配置中获取的路径
    config_path = get_database_path(app)
    if config_path and os.path.exists(config_path):
        return config_path
    
    # 如果配置路径不存在，检查instance目录
    instance_path = os.path.join(app.instance_path, 'database.db')
    if os.path.exists(instance_path):
        return instance_path
    
    # 最后检查当前目录
    current_path = os.path.join(os.getcwd(), 'database.db')
    if os.path.exists(current_path):
        return current_path
    
    return config_path  # 返回配置路径，即使文件不存在

def import_all_models():
    """导入所有模型以确保表被创建"""
    try:
        from app.models.domain import Domain
        from app.models.url import URL
        from app.models.certificate import Certificate
        from app.models.notification import URLCheck, WhoisRecord, Notification, NotificationConfig, DomainAccessCheck
        from app.models.proxy import Proxy
        print("✅ 所有模型导入成功")
        return True
    except ImportError as e:
        print(f"❌ 模型导入失败: {e}")
        return False

def create_database():
    """创建数据库和所有表"""
    try:
        # 确保instance目录存在
        ensure_instance_directory()
        
        # 创建应用实例
        app = create_app()
        
        with app.app_context():
            # 导入所有模型
            if not import_all_models():
                return False
            
            # 检查数据库连接
            try:
                print(f"🔍 尝试连接数据库: {app.config['SQLALCHEMY_DATABASE_URI']}")
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
                print("✅ 数据库连接正常")
            except Exception as e:
                print(f"❌ 数据库连接失败: {e}")
                print(f"🔍 数据库URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
                return False
            
            # 创建所有表
            db.create_all()
            print("✅ 数据库表创建成功！")
            
            # 验证表是否创建成功
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📋 创建的表: {tables}")
            
            # 检查数据库文件
            db_path = get_actual_database_path(app)
            if db_path and os.path.exists(db_path):
                size = os.path.getsize(db_path)
                print(f"💾 数据库文件路径: {db_path}")
                print(f"📊 数据库文件大小: {size:,} 字节")
                
                # 验证表结构
                for table_name in tables:
                    columns = inspector.get_columns(table_name)
                    print(f"  📋 {table_name}: {len(columns)} 列")
            else:
                print("⚠️  数据库文件不存在或无法访问")
                print(f"🔍 尝试的路径: {get_database_path(app)}")
                print(f"🔍 Flask instance路径: {os.path.join(app.instance_path, 'database.db')}")
                print(f"🔍 当前目录路径: {os.path.join(os.getcwd(), 'database.db')}")
            
            return True
            
    except Exception as e:
        print(f"❌ 创建数据库时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🚀 开始创建数据库...")
    success = create_database()
    if success:
        print("🎉 数据库创建完成！")
        sys.exit(0)
    else:
        print("💥 数据库创建失败！")
        sys.exit(1)
