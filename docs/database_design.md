# TaskFlow 数据库设计（第一阶段）

数据库：taskflow；字符集：utf8mb4。

| 表 | 用途 |
|---|---|
| auth_user | Django内置用户表，保存账号与密码哈希 |
| roles | 角色定义 |
| user_profiles | 用户扩展信息、部门 |
| user_roles | 用户与角色多对多关系 |
| role_permissions | 业务角色与 Django Permission 的授权及 Scope 关系 |
| departments | 部门 |
| ticket_categories | 工单分类 |
| tickets | 工单主体 |
| ticket_comments | 工单评论 |

说明：
- 第一阶段使用 Django 内置 User，避免过早自定义认证模型。
- `UserProfile` 与内置 User 一对一关联。
- `RolePermission` 使用 Django 内置 `auth.Permission` 作为权限定义，scope 支持
  `all`、`department`、`self`，同一角色和权限只能绑定一次。
- 业务权限继续使用 `auth_permission`，自定义操作通过模型 Meta.permissions
  声明，不创建重复 Permission 表。
- 工单 creator 使用 PROTECT，防止误删创建人导致历史工单失去归属。
- assignee 使用 SET_NULL，员工离职或账号删除时保留工单。
- 工单状态与优先级使用枚举值。
- 后续阶段再增加附件、任务、通知和操作日志表。
