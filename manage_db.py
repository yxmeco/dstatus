#!/usr/bin/env python3
"""
数据库管理脚本
提供数据库的创建、检查、备份、恢复等功能
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime
from app import create_app, db

def get_database_path():
    """从配置中获取数据库路径"""
    app = create_app(init_scheduler=False)  # 不初始化调度器
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.getcwd(), db_path)
        # 确保目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
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

def ensure_instance_directory():
    """确保instance目录存在"""
    instance_dir = os.path.join(os.getcwd(), 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)
        print(f"📁 创建instance目录: {instance_dir}")
    return instance_dir

def import_all_models():
    """导入所有模型"""
    try:
        from app.models.domain import Domain
        from app.models.url import URL
        from app.models.certificate import Certificate
        from app.models.notification import URLCheck, WhoisRecord, Notification, NotificationConfig, DomainAccessCheck
        from app.models.proxy import Proxy
        return True
    except ImportError as e:
        print(f"❌ 模型导入失败: {e}")
        return False

def create_database():
    """创建数据库"""
    print("🚀 开始创建数据库...")
    
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
                with db.engine.connect() as conn:
                    conn.execute(db.text('SELECT 1'))
                print("✅ 数据库连接正常")
            except Exception as e:
                print(f"❌ 数据库连接失败: {e}")
                return False
            
            # 创建所有表
            db.create_all()
            print("✅ 数据库表创建成功！")
            
            # 验证表是否创建成功
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📋 创建的表: {tables}")
            
            return True
            
    except Exception as e:
        print(f"❌ 创建数据库时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_database():
    """检查数据库状态"""
    print("🔍 开始检查数据库...")
    
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
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
        return False

def backup_database():
    """备份数据库"""
    print("💾 开始备份数据库...")
    
    db_path = get_actual_database_path()
    if not db_path or not os.path.exists(db_path):
        print("❌ 数据库文件不存在，无法备份")
        return False
    
    # 创建备份目录
    backup_dir = os.path.join(os.getcwd(), 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 生成备份文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'database_backup_{timestamp}.db')
    
    try:
        # 复制数据库文件
        shutil.copy2(db_path, backup_path)
        print(f"✅ 数据库备份成功: {backup_path}")
        print(f"📊 备份文件大小: {os.path.getsize(backup_path):,} 字节")
        return True
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return False

def restore_database(backup_path):
    """恢复数据库"""
    print(f"🔄 开始恢复数据库: {backup_path}")
    
    if not os.path.exists(backup_path):
        print("❌ 备份文件不存在")
        return False
    
    db_path = get_actual_database_path()
    if not db_path:
        print("❌ 无法获取数据库路径")
        return False
    
    try:
        # 备份当前数据库
        if os.path.exists(db_path):
            current_backup = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(db_path, current_backup)
            print(f"📁 当前数据库已备份到: {current_backup}")
        
        # 恢复数据库
        shutil.copy2(backup_path, db_path)
        print(f"✅ 数据库恢复成功")
        return True
    except Exception as e:
        print(f"❌ 恢复失败: {e}")
        return False

def list_backups():
    """列出所有备份"""
    print("📋 列出所有备份文件...")
    
    backup_dir = os.path.join(os.getcwd(), 'backups')
    if not os.path.exists(backup_dir):
        print("📁 备份目录不存在")
        return
    
    backups = []
    for file in os.listdir(backup_dir):
        if file.startswith('database_backup_') and file.endswith('.db'):
            file_path = os.path.join(backup_dir, file)
            stat = os.stat(file_path)
            backups.append({
                'name': file,
                'path': file_path,
                'size': stat.st_size,
                'mtime': datetime.fromtimestamp(stat.st_mtime)
            })
    
    if not backups:
        print("📁 没有找到备份文件")
        return
    
    # 按修改时间排序
    backups.sort(key=lambda x: x['mtime'], reverse=True)
    
    print(f"📋 找到 {len(backups)} 个备份文件:")
    for i, backup in enumerate(backups, 1):
        print(f"  {i}. {backup['name']}")
        print(f"     大小: {backup['size']:,} 字节")
        print(f"     时间: {backup['mtime'].strftime('%Y-%m-%d %H:%M:%S')}")

def optimize_database():
    """优化数据库"""
    print("⚡ 开始优化数据库...")
    
    db_path = get_actual_database_path()
    if not db_path or not os.path.exists(db_path):
        print("❌ 数据库文件不存在")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 执行VACUUM优化
        print("🔄 执行VACUUM优化...")
        cursor.execute("VACUUM")
        
        # 更新统计信息
        print("📊 更新统计信息...")
        cursor.execute("ANALYZE")
        
        # 检查优化结果
        cursor.execute("PRAGMA stats")
        stats = cursor.fetchall()
        print("📈 优化后的统计信息:")
        for stat in stats:
            print(f"  {stat[0]}: {stat[1]}")
        
        conn.close()
        print("✅ 数据库优化完成")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 优化失败: {e}")
        return False

def show_help():
    """显示帮助信息"""
    print("""
🔧 数据库管理工具

用法: python manage_db.py <命令> [参数]

命令:
  create      创建数据库和所有表
  check       检查数据库状态
  backup      备份数据库
  restore <文件>  从备份文件恢复数据库
  list        列出所有备份文件
  optimize    优化数据库
  help        显示此帮助信息

示例:
  python manage_db.py create
  python manage_db.py check
  python manage_db.py backup
  python manage_db.py restore backups/database_backup_20241201_120000.db
  python manage_db.py list
  python manage_db.py optimize
""")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'create':
        success = create_database()
        if success:
            print("🎉 数据库创建完成！")
            sys.exit(0)
        else:
            print("💥 数据库创建失败！")
            sys.exit(1)
    
    elif command == 'check':
        success = check_database()
        if success:
            print("🎉 数据库检查完成！")
            sys.exit(0)
        else:
            print("💥 数据库检查失败！")
            sys.exit(1)
    
    elif command == 'backup':
        success = backup_database()
        if success:
            print("🎉 数据库备份完成！")
            sys.exit(0)
        else:
            print("💥 数据库备份失败！")
            sys.exit(1)
    
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("❌ 请指定备份文件路径")
            sys.exit(1)
        backup_path = sys.argv[2]
        success = restore_database(backup_path)
        if success:
            print("🎉 数据库恢复完成！")
            sys.exit(0)
        else:
            print("💥 数据库恢复失败！")
            sys.exit(1)
    
    elif command == 'list':
        list_backups()
        sys.exit(0)
    
    elif command == 'optimize':
        success = optimize_database()
        if success:
            print("🎉 数据库优化完成！")
            sys.exit(0)
        else:
            print("💥 数据库优化失败！")
            sys.exit(1)
    
    elif command == 'help':
        show_help()
        sys.exit(0)
    
    else:
        print(f"❌ 未知命令: {command}")
        show_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
