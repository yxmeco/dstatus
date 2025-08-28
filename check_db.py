import sqlite3
import os
import sys
from app import create_app

def get_database_path():
    """从配置中获取数据库路径"""
    app = create_app(init_scheduler=False)  # 不初始化调度器
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.getcwd(), db_path)
        return db_path
    return None

def get_actual_database_path():
    """获取实际的数据库文件路径（考虑Flask的instance_path）"""
    app = create_app(init_scheduler=False)  # 不初始化调度器
    # 首先尝试从配置中获取的路径
    config_path = get_database_path()
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

def check_database():
    """检查数据库状态"""
    db_path = get_actual_database_path()
    
    if not db_path:
        print("❌ 无法获取数据库路径")
        return False
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False

    print(f"💾 数据库文件路径: {db_path}")
    print(f"📊 数据库文件大小: {os.path.getsize(db_path):,} 字节")

    # 连接到数据库
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查数据库完整性
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()
        if integrity[0] == 'ok':
            print("✅ 数据库完整性检查通过")
        else:
            print(f"❌ 数据库完整性检查失败: {integrity[0]}")
            return False
        
        # 检查所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n📋 数据库中的表 ({len(tables)} 个):")
        
        expected_tables = [
            'domain', 'url', 'certificate', 'proxies', 
            'url_check', 'whois_record', 'notification', 
            'notification_config', 'domain_access_check'
        ]
        
        found_tables = [table[0] for table in tables]
        
        for table_name in expected_tables:
            if table_name in found_tables:
                # 检查表结构
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                print(f"  ✅ {table_name}: {len(columns)} 列")
                
                # 检查记录数
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"     📊 记录数: {count:,}")
            else:
                print(f"  ❌ {table_name}: 表不存在")
        
        # 检查额外的表
        extra_tables = [table[0] for table in tables if table[0] not in expected_tables]
        if extra_tables:
            print(f"\n⚠️  额外的表: {extra_tables}")
        
        # 检查数据库统计信息
        cursor.execute("PRAGMA stats")
        stats = cursor.fetchall()
        print(f"\n📈 数据库统计信息:")
        for stat in stats:
            print(f"  {stat[0]}: {stat[1]}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
        return False

if __name__ == '__main__':
    print("🔍 开始检查数据库...")
    success = check_database()
    if success:
        print("🎉 数据库检查完成！")
        sys.exit(0)
    else:
        print("💥 数据库检查失败！")
        sys.exit(1)
