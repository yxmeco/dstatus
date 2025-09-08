# 官网可用性与URL监控集成功能总结

## 功能概述

本次更新将官网可用性检查功能与URL监控系统进行了深度集成，实现了以下功能：

1. **自动创建URL监控项**：当在添加域名时勾选"官网可用性"选项时，系统会自动创建一个对应的URL监控项
2. **状态复用**：域名列表中的官网可用性状态直接复用URL监控中的各项最终状态
3. **统一管理**：官网可用性检查现在完全基于URL监控系统，提供更丰富的监控功能

## 主要变更

### 1. 数据库模型更新

#### Domain模型 (`app/models/domain.py`)
- 新增 `website_url_id` 字段，用于关联URL监控项
- 更新访问状态相关属性，优先使用URL监控状态
- 保持向后兼容，支持旧的访问检查功能

```python
# 新增字段
website_url_id = db.Column(db.Integer, db.ForeignKey('url.id'), nullable=True)

# 新增关联关系
website_url = db.relationship('URL', backref='domain', foreign_keys=[website_url_id])
```

#### 访问状态属性更新
- `access_status`: 优先使用URL监控状态，回退到旧访问检查
- `latest_access_status_code`: 优先使用URL监控状态码
- `latest_access_check_time`: 优先使用URL监控检查时间

### 2. 域名管理功能更新

#### 域名添加功能 (`app/views/domains.py`)
- 当勾选"官网可用性"时，自动创建URL监控项
- 自动配置监控参数（60分钟间隔、10秒超时等）
- 自动关联通知配置

#### 域名编辑功能
- 启用访问检查时自动创建URL监控项
- 禁用访问检查时自动删除关联的URL监控项
- 保持数据一致性

#### 域名删除功能
- 删除域名时自动删除关联的URL监控项
- 确保数据完整性

### 3. 检查功能更新

#### 官网可用性刷新
- 优先使用URL监控的检查功能
- 回退到旧的访问检查功能
- 保持向后兼容性

#### 异步检查功能
- 集成URL监控检查
- 提供更详细的检查结果

### 4. 用户界面更新

#### 域名列表页面 (`app/templates/domains/index.html`)
- 官网可用性列显示URL监控状态
- 添加"查看监控详情"链接
- 显示检查时间和状态码

## 技术实现

### 1. 数据库迁移
- 自动添加 `website_url_id` 字段到 `domain` 表
- 建立与 `url` 表的外键关系

### 2. 状态优先级
```python
# 访问状态获取逻辑
if self.website_url and self.website_url.is_active:
    # 使用URL监控状态
    return self.website_url.url_checks[-1].is_available
else:
    # 回退到旧访问检查
    return self.access_checks[-1].is_accessible
```

### 3. 自动创建URL监控项
```python
website_url = URL(
    name=f"{domain.name} 官网监控",
    url=f"https://{domain.name}",
    description=f"域名 {domain.name} 的官网可用性监控",
    check_interval=60,
    timeout=10,
    retry_count=1,
    method='GET',
    expected_status_codes='200',
    response_time_threshold=5.0,
    follow_redirects=True,
    verify_ssl=True,
    notification_config_id=domain.notification_config_id
)
```

## 功能优势

### 1. 统一监控体系
- 官网可用性检查现在完全基于URL监控系统
- 享受URL监控的所有高级功能（重试、内容验证、响应时间监控等）

### 2. 更丰富的监控数据
- 响应时间统计
- 可用性百分比
- 详细的检查历史
- 性能指标分析

### 3. 更好的用户体验
- 一键创建官网监控
- 统一的监控界面
- 详细的监控报告

### 4. 向后兼容
- 保留旧的访问检查功能作为备用
- 平滑迁移，不影响现有数据

## 使用说明

### 1. 添加域名时启用官网可用性
1. 在添加域名页面勾选"官网可用性"选项
2. 系统会自动创建对应的URL监控项
3. 监控项会自动关联域名的通知配置

### 2. 查看官网可用性状态
1. 在域名列表页面查看"官网可用性"列
2. 点击"查看监控详情"链接查看详细监控信息
3. 状态显示包括：可用性、状态码、检查时间

### 3. 管理官网监控
1. 可以通过URL监控页面管理官网监控项
2. 可以调整监控参数（检查间隔、超时时间等）
3. 可以查看详细的监控历史和统计信息

## 注意事项

1. **数据迁移**：现有域名的官网可用性检查会自动使用新的URL监控系统
2. **通知配置**：官网监控会自动继承域名的通知配置
3. **性能影响**：URL监控系统提供更丰富的功能，但资源消耗略高于简单访问检查
4. **兼容性**：旧的访问检查功能仍然保留，确保系统稳定性

## 测试验证

功能已通过完整测试验证：
- ✅ 域名添加时自动创建URL监控项
- ✅ 域名编辑时正确管理URL监控项
- ✅ 域名删除时正确清理关联数据
- ✅ 状态显示正确复用URL监控数据
- ✅ 向后兼容性验证通过

## 总结

本次更新成功将官网可用性检查功能与URL监控系统进行了深度集成，提供了更强大、更统一的监控解决方案。用户现在可以享受URL监控系统的所有高级功能，同时保持了简单易用的操作体验。
