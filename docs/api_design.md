# TaskFlow API 设计（第三阶段）

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /api/health/ | 检查后端服务是否运行 |
| POST | /api/auth/register/ | 注册用户并创建用户资料 |
| POST | /api/auth/login/ | 验证用户并获取 JWT |
| GET | /api/auth/me/ | 获取 JWT 对应的当前用户 |
| POST | /api/auth/token/refresh/ | 轮换 Refresh Token 并获取新 Access Token |
| POST | /api/auth/logout/ | 拉黑当前 Refresh Token |
| GET | /api/departments/ | 分页查询部门，可使用 search 搜索名称 |
| GET | /api/departments/{id}/ | 查询部门详情 |
| POST | /api/departments/ | 管理员创建部门 |
| PUT | /api/departments/{id}/ | 修改部门：admin 或本部门负责人 |
| PATCH | /api/departments/{id}/ | 修改部门：admin 或本部门负责人 |
| DELETE | /api/departments/{id}/ | 管理员删除部门；有关联工单时返回 409 |
| PATCH | /api/users/{id}/department/ | admin 分配用户部门；manager 仅限本部门 |
| GET | /api/users/{id}/roles/ | 管理员查询用户业务角色 |
| POST | /api/users/{id}/roles/ | 管理员为用户分配角色 |
| DELETE | /api/users/{id}/roles/{role_id}/ | 管理员移除用户角色关联 |
| GET | /api/departments/{id}/members/ | admin 或本部门负责人查询部门成员 |
| GET | /api/tickets/ | 分页查询工单，并支持搜索、筛选和排序 |
| GET | /api/ticket-categories/ | 登录用户查询工单分类 |
| GET | /api/tickets/assignees/ | 分配权限用户查询可用处理人 |
| PATCH | /api/tickets/{id}/ | 编辑工单标题、描述和分类 |

部门列表和详情 GET 有意允许所有已登录用户访问；它们属于共享基础信息，
不要求额外业务角色。未认证访问返回 401。

成功响应示例：

```json
{
  "code": 200,
  "message": "TaskFlow API is running",
  "data": {
    "service": "taskflow-backend",
    "status": "ok",
    "timestamp": "..."
  }
}
```

## 用户登录

请求：

```json
{
  "username": "testuser",
  "password": "Test123456"
}
```

成功响应（HTTP 200）：

```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access": "<access-token>",
    "refresh": "<refresh-token>"
  }
}
```

账号、密码错误或账号被禁用时返回 HTTP 401：

```json
{
  "code": 401,
  "message": "用户名或密码错误，或账号不可用。"
}
```

## 当前用户

请求头：

```http
Authorization: Bearer <access-token>
```

成功响应（HTTP 200）：

```json
{
  "code": 200,
  "message": "获取当前用户成功",
  "data": {
    "id": 1,
    "username": "testuser",
    "email": "testuser@example.com",
    "department": {
      "id": 1,
      "name": "研发部"
    },
    "roles": [
      {
        "id": 1,
        "name": "普通员工",
        "code": "employee"
      }
    ]
  }
}
```

用户没有部门时 `department` 为 `null`，没有角色时 `roles` 为 `[]`。

### 用户部门分配

`PATCH /api/users/{id}/department/` 请求体必须包含 `department_id`：

```json
{
  "department_id": 1
}
```

清除部门：

```json
{
  "department_id": null
}
```

admin 可以跨部门调动或清除用户部门。department_manager 必须同时满足：

- 拥有 `users.assign_user_department` 的 DEPARTMENT Scope。
- 操作者有 UserProfile 和当前部门。
- 目标用户当前属于操作者部门。
- 目标 `department_id` 等于操作者当前部门，不能调入或调出。

服务在事务中锁定请求的目标部门、操作者与目标用户及其 Profile，锁后重新读取
部门归属并校验，避免检查与写入之间的权限竞态。成功响应包含目标用户 ID、
用户名和更新后的部门摘要；用户或部门不存在、缺少 Profile、字段缺失或类型
错误时返回对应的 JSON 错误。

### 用户角色管理

查询：

```http
GET /api/users/{id}/roles/
```

分配：

```json
{
  "role_id": 1
}
```

移除：

```http
DELETE /api/users/{id}/roles/{role_id}/
```

所有接口要求 `admin` 业务角色。重复分配保持幂等；移除只删除 UserRole，
不会删除 Role，也不会修改用户账号、密码或部门。

### 部门成员查询

```http
GET /api/departments/1/members/?page=1&page_size=10&search=user
```

admin 可以查询任意部门；department_manager 只能查询自己当前所属部门。
无 Profile、无部门或查询其他部门时返回 403。响应返回目标部门信息、成员总数
和分页结果，成员只包含 `id`、`username`、`email` 和 `roles`。

### 工单列表查询

```http
GET /api/tickets/
```

支持参数：

| 参数 | 说明 |
|---|---|
| page | 页码 |
| page_size | 每页数量，最大 100 |
| search | 标题搜索 |
| ordering | 排序字段 |
| status | pending、processing、resolved、closed |
| priority | low、medium、high、urgent |
| category | TicketCategory ID |
| created_after | 创建日期起始值，YYYY-MM-DD |
| created_before | 创建日期结束值，YYYY-MM-DD |

示例：

```http
GET /api/tickets/?search=网络&status=processing&priority=high
    &category=2&created_after=2026-11-01&created_before=2026-11-30
    &ordering=-created_at&page=1&page_size=10
```

多个筛选条件使用 AND。创建日期按 Asia/Shanghai 自然日处理，
`created_before` 包含结束日期当天。筛选在 Permission 和 Scope 已限定的
QuerySet 上执行，不会扩大用户可见数据范围。非法状态、优先级、分类 ID、
日期格式或起止顺序返回 HTTP 400。

### 工单分类查询

```http
GET /api/ticket-categories/
```

该接口要求 JWT 认证，返回全部工单分类，不分页。当前模型没有启用状态或排序
字段，因此按 `id` 升序返回：

```json
[
  {
    "id": 1,
    "name": "系统问题",
    "description": "系统故障或异常"
  }
]
```

分类接口只支持 GET，不允许创建、修改或删除分类。默认分类通过独立管理命令
初始化：

```powershell
python manage.py init_default_ticket_categories
```

命令可重复执行，只补充不存在的分类，不覆盖已有分类描述。

### 工单编辑

```http
PATCH /api/tickets/{id}/
```

允许字段：

```json
{
  "title": "更新后的标题",
  "description": "更新后的描述",
  "category": 2
}
```

至少提交一个可编辑字段。`category` 可以传 `null` 清除分类，不能传不存在的
分类 ID。creator、department、assignee、status、priority 等字段不允许在
编辑请求中出现。

编辑要求 `tickets.change_ticket`，并同时检查 Scope、角色和状态：

- admin：可以编辑全部 pending/processing 工单。
- department_manager：可以编辑本部门 pending/processing 工单。
- employee：只能编辑自己创建且仍为 pending 的工单。
- ticket_handler：不允许编辑。
- resolved、closed：返回 HTTP 409。
- 工单不存在或超出对象范围：返回 HTTP 404。

工单部门是创建时快照，编辑不会跟随创建人后续部门变化。

### 工单候选处理人查询

```http
GET /api/tickets/assignees/
```

仅拥有 `tickets.assign_ticket` 的用户可以访问。返回 active、有
UserProfile 且拥有 `ticket_handler` 角色的用户，按用户 ID 升序排列：

```json
[
  {
    "id": 8,
    "username": "handler",
    "department": {
      "id": 2,
      "name": "研发部"
    }
  }
]
```

没有部门的处理人仍可作为候选人，`department` 返回 `null`。接口只读，
不会执行工单分配。

删除部门时，没有成员关联不会阻塞删除；UserProfile.department 会置空。
如果仍有 Ticket 引用该部门，返回 HTTP 409，部门和工单历史保持不变。

系统至少保留一个拥有 `admin` 角色的用户。移除 admin 角色时，服务端会先锁定
对应 Role 行并统计关联；只剩一个管理员时返回 HTTP 409。

缺少 Token、Token 无效、Token 过期或用户不可用时返回 HTTP 401：

```json
{
  "code": 401,
  "message": "身份认证失败",
  "errors": {
    "detail": "..."
  }
}
```

## Token 刷新

请求：

```json
{
  "refresh": "<refresh-token>"
}
```

成功响应（HTTP 200）：

```json
{
  "code": 200,
  "message": "Token 刷新成功",
  "data": {
    "access": "<new-access-token>",
    "refresh": "<new-refresh-token>"
  }
}
```

Refresh Token 无效、过期或已进入黑名单时返回 HTTP 401：

```json
{
  "code": 401,
  "message": "Refresh Token 无效、已过期或已被拉黑"
}
```

## 退出登录

请求：

```json
{
  "refresh": "<refresh-token>"
}
```

成功响应（HTTP 200）：

```json
{
  "code": 200,
  "message": "退出登录成功",
  "data": null
}
```

Refresh Token 无效、过期或已拉黑时返回 HTTP 401；缺少 `refresh` 时返回
HTTP 400。

## 用户注册

请求：

```json
{
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "password": "TaskFlow#2026",
  "password_confirm": "TaskFlow#2026"
}
```

成功响应（HTTP 201）：

```json
{
  "code": 201,
  "message": "注册成功",
  "data": {
    "id": 1,
    "username": "zhangsan",
    "email": "zhangsan@example.com"
  }
}
```

校验失败响应（HTTP 400）：

```json
{
  "code": 400,
  "message": "注册信息校验失败",
  "errors": {
    "username": ["该用户名已被使用。"]
  }
}
```
