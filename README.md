# TaskFlow

企业工单与任务协作管理系统。

## 技术栈
- Backend: Python 3.11, Django 5.2, Django REST Framework
- Frontend: Vue 3, Vite, Element Plus
- Database: MySQL 8.0

## 启动后端
1. 进入 `backend`，创建并激活虚拟环境。
2. `pip install -r requirements.txt`
3. 复制 `.env.example` 为 `.env`，填写数据库密码。
4. 在 MySQL 中创建 taskflow 数据库和项目账号。
5. `python manage.py makemigrations departments users tickets`
6. `python manage.py migrate`
7. `python manage.py runserver 127.0.0.1:8000`

健康检查：`http://127.0.0.1:8000/api/health/`

## 用户注册 API

`POST http://127.0.0.1:8000/api/auth/register/`

注册请求需要提供 `username`、`email`、`password` 和
`password_confirm`。接口会创建 Django 内置用户及对应的 UserProfile，
密码由 Django 哈希后保存。详细字段和响应示例见
[docs/api_design.md](docs/api_design.md)。

## 用户登录 API

`POST http://127.0.0.1:8000/api/auth/login/`

登录请求需要提供 `username` 和 `password`，成功后返回有效期 30 分钟的
Access Token 和有效期 7 天的 Refresh Token。后续受保护请求使用：

```http
Authorization: Bearer <access-token>
```

DRF 全局默认权限为 `IsAuthenticated`。只有注册、登录、Token 刷新和退出登录
接口显式允许匿名访问；后续业务接口默认要求 JWT 认证。

部门只读查询接口位于 `/api/departments/`，支持分页和 `search` 名称搜索。
部门详情接口为 `/api/departments/{id}/`。部门名称和说明属于共享基础信息，
这两个 GET 接口有意对所有已登录用户开放，不额外要求业务角色。

创建和删除部门仅允许 `admin` 业务角色。PUT/PATCH 使用
`departments.change_department`：admin 可以修改任意部门，department_manager
只能修改自己当前所属的部门。`is_staff` 和 `is_superuser` 不等同于业务管理员。
删除仍有关联工单的部门会返回 HTTP 409，不会删除工单。

可通过 `PATCH /api/users/{id}/department/` 分配或清除用户部门。admin 可以
跨部门调动；department_manager 只能操作当前属于自己部门的用户，并且只能
将用户保留在自己部门。请求必须包含 `department_id`。

管理员可通过 `/api/users/{id}/roles/` 查询和分配用户业务角色，通过
`DELETE /api/users/{id}/roles/{role_id}/` 移除角色关联。

可通过 `/api/departments/{id}/members/` 分页查询部门成员，支持按用户名或邮箱
搜索。admin 可以查询任意部门，department_manager 只能查询自己当前部门。

系统禁止移除最后一个 `admin` 角色关联；并发管理员移除通过 Role 行锁串行化。

工单分类下拉数据由 `GET /api/ticket-categories/` 提供，要求 JWT 认证，
返回 `id`、`name`、`description`，该接口只读且不分页。

工单列表 `GET /api/tickets/` 支持 `status`、`priority`、`category`、
`created_after`、`created_before` 筛选，并可与 `search`、`ordering`、
`page`、`page_size` 组合。多个筛选条件使用 AND；创建日期按 Asia/Shanghai
自然日解释，结束日期当天完整包含。非法枚举、无效分类、非法日期或起止顺序
错误返回 HTTP 400。所有筛选均先受当前用户 Permission 和 Scope 限制。

工单候选处理人由 `GET /api/tickets/assignees/` 提供，仅允许拥有
`tickets.assign_ticket` 权限的用户查询，返回 active、有 Profile 且具有
`ticket_handler` 角色的用户摘要。

前端工单请求统一封装在 `frontend/src/api/tickets.js`，通过
`@/utils/request` 使用现有 Token 注入和 401 自动刷新能力。

工单列表、详情、分类和写操作的响应式状态由
`frontend/src/stores/tickets.js` 管理；该 Store 不复制后端权限判断。

前端工单列表提供状态、优先级、分类和创建日期筛选。分类选项复用
`GET /api/ticket-categories/`，应用筛选会回到第一页，清空筛选恢复原始列表；
搜索、筛选、排序和分页可以组合使用。

工单页面骨架位于 `/tickets`、`/tickets/new`、`/tickets/:id`，三者均受
现有登录守卫保护。Dashboard 提供进入工单列表的入口。

`/tickets/new` 已接入真实创建表单，通过 Pinia Store 加载分类并提交
`title`、`description`、`category`，创建成功后跳转新工单详情。

`/tickets/:id` 已接入真实详情加载，展示后端返回的工单、分类、状态、
优先级、创建人、处理人、部门和时间字段。

工单详情页已接入处理人分配操作。admin 可管理全部工单，department_manager
只能看到自己当前部门工单的分配入口；可分配、重新分配或取消 pending 和
processing 状态的工单。候选处理人来自后端 `GET /api/tickets/assignees/`，
允许跨部门选择。前端按钮仅用于交互提示，权限和 Scope 最终仍由后端校验。
分配成功后页面会重新加载工单详情；403、404、409 和网络错误会显示明确提示。

工单详情页已接入“开始处理”和“标记解决”操作。pending 工单可开始处理并
进入 processing，processing 工单可标记为 resolved；resolved 和 closed
不再显示处理按钮。admin 可处理全部符合状态的工单，department_manager 只能
处理本部门工单，ticket_handler 只能处理当前分配给自己的工单。前端按钮仅
用于交互提示，后端 Permission、Scope、角色和负责人校验仍是最终安全边界。
处理成功后页面会重新加载详情；403、404、409 和网络错误会显示稳定提示。

resolved 工单的详情页提供“关闭工单”操作，并在提交前通过 Element Plus
二次确认防止误操作。admin 可关闭全部已解决工单，department_manager 只能
关闭本部门工单，ticket_handler 只能关闭当前分配给自己的工单。关闭请求调用
现有 `POST /api/tickets/{id}/close/`，不发送请求体；成功后刷新详情并展示
后端返回的 closed 状态。关闭成功但详情刷新失败时会明确提示状态已更新，
不会误报为关闭失败。

初始化默认工单分类（可重复执行，不覆盖已有分类描述）：

```powershell
python manage.py init_default_ticket_categories
```

初始化默认业务角色：

```powershell
python manage.py init_default_roles
```

为单个已存在且拥有 UserProfile 的用户分配角色：

```powershell
python manage.py assign_user_role --username admin_user --role admin
```

两个命令均不会自动创建用户或自动授予管理员角色。

`role_permissions` 表保存业务角色与 Django Permission 的关联。默认绑定通过
显式管理命令初始化，不会在应用启动时自动写入。

初始化默认角色权限矩阵：

```powershell
python manage.py sync_rbac_permissions
```

命令可重复执行；已有 Scope 与默认矩阵冲突时默认保留并报告，
只有显式添加 `--force` 才更新 Scope。

## 当前用户 API

`GET http://127.0.0.1:8000/api/auth/me/`

请求必须携带有效的 Access Token，响应只包含当前用户的 `id`、`username`
、`email`、所属部门、业务角色和有效 TaskFlow 业务权限。接口始终以 JWT
对应的登录用户为准，不接受客户端指定用户 ID。

`permissions` 由现有 Permission Resolver 计算，只包含
`REQUIRED_PERMISSIONS` 中当前用户实际拥有的权限代码，并按字母顺序返回。
例如：

```json
{
  "permissions": [
    "tickets.assign_ticket",
    "tickets.process_ticket"
  ]
}
```

TaskFlow admin 继续使用 Resolver 的 admin 旁路规则获得全部已注册业务权限。
Django Admin 权限和其他第三方应用的权限不会出现在该列表中。

## Token 刷新 API

`POST http://127.0.0.1:8000/api/auth/token/refresh/`

请求体携带登录得到的 `refresh`。项目启用了 Token 轮换和旧 Token 黑名单，
因此成功响应会同时返回新的 `access` 和 `refresh`，前端必须替换本地保存的
Refresh Token。

## 退出登录 API

`POST http://127.0.0.1:8000/api/auth/logout/`

请求体携带当前设备的 `refresh`。接口不需要 Access Token，会严格验证并拉黑
该 Refresh Token，适合 Access Token 已经过期的场景。接口只撤销当前提交的
Refresh Token，不影响其他设备或其他用户的会话。

## 启动前端
1. 进入 `frontend`
2. 确认 `.env.development` 中 `VITE_API_BASE_URL=/api`
3. `npm install`
4. `npm run dev`
5. 打开 `http://127.0.0.1:5173`

前端首页会自动请求 `/api/health/`。看到“前后端连接成功”即表示联调成功。
所有前端 API 请求统一通过 `src/utils/request.js` 发出，开发环境地址由
`VITE_API_BASE_URL=/api` 配置，并由 Vite 代理到 Django。

前端 Token 使用 `sessionStorage` 保存。Token 的读取、写入和清除统一通过
`src/utils/token.js`，业务组件不要直接操作 `sessionStorage`。

工单详情页根据 `/api/auth/me/` 返回的 Permission code 控制分配、处理和关闭
入口。admin、department_manager 和 ticket_handler 仍保留原有的部门或当前
处理人对象范围判断；拥有对应自定义角色的用户也可以显示入口。前端权限仅
控制界面展示，后端 Permission、Scope 和 Service 校验仍是最终安全边界。

工单详情支持 `PATCH /api/tickets/{id}/` 编辑标题、描述和分类。接口要求
`tickets.change_ticket`：admin 可以编辑全部 pending/processing 工单，
department_manager 可以编辑本部门 pending/processing 工单，employee 只能
编辑自己创建且仍为 pending 的工单，ticket_handler 不允许编辑。resolved 和
closed 工单返回 HTTP 409。creator、department、assignee、status 和 priority
均由后端保护，请求中出现这些字段会返回 HTTP 400。

前端详情页通过编辑对话框预填当前内容，并复用 `/api/ticket-categories/`
加载分类。提交只发送 `title`、`description`、`category`，成功后重新加载
详情；提交期间防止重复请求，失败时保留已输入内容。

Pinia 认证状态位于 `src/stores/auth.js`，它管理 Token 对应的响应式状态、
当前用户和初始化状态。Token 实际存储仍由 `utils/token.js` 负责。

登录页面位于 `http://127.0.0.1:5173/login`。登录成功后，页面会获取当前用户、
保存 Token 并跳转到 Dashboard。

注册页面位于 `http://127.0.0.1:5173/register`。注册成功后跳转登录页，不会
自动登录。Dashboard 展示当前用户名和邮箱，并支持撤销当前 Refresh Token 后退出。

新建 Django User 时会通过 `post_save` 信号自动创建对应的 UserProfile；
注册接口使用 `get_or_create` 与信号保持幂等兼容。

Dashboard 使用 `meta.requiresAuth` 保护。页面刷新时，路由守卫会等待
`initializeAuth()` 验证 sessionStorage 中的 Access Token，再决定放行或跳转
登录页。登录成功后会优先返回原本访问的页面。

业务请求返回 401 时，Axios 会使用 Refresh Token 自动刷新并重试原请求一次。
并发 401 通过共享 Promise 合并，只发送一次刷新请求。刷新接口使用独立 Axios
实例，避免递归刷新。

请求会记录实际使用的 Access Token。迟到的旧 Token 401 如果发现当前 Token
已被其他请求刷新，会直接使用新 Token 重试，不再重复轮换 Refresh Token。

运行前端轻量测试：

```powershell
Set-Location 'F:\Demo\TaskFlow\frontend'
npm test
```

`npm test` 使用 Node 内置测试运行器。

## 运行测试

在 `backend` 目录并激活虚拟环境后运行：

```powershell
python manage.py test apps.users
```

Django 会创建独立的 `test_taskflow` 数据库。项目 MySQL 账号还需要由管理员授予该测试库的权限：

```sql
GRANT ALL PRIVILEGES ON `test_taskflow`.* TO 'taskflow_user'@'localhost';
```

## 注意
- `.env` 不要提交到 Git。
- 示例密钥和数据库密码仅用于本地开发，部署前必须更换。
- 第一阶段的默认 API 权限为 AllowAny，后续实现 JWT 和角色权限时再收紧。
