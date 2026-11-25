# TaskFlow 第二阶段：用户认证系统知识点整理

> 技术栈：Django 5.2、Django REST Framework、SimpleJWT、Vue
> 3、Axios、Pinia。\
> 学习目标：能解释认证流程、关键代码、设计原因、异常处理和测试方法。

## 一、第二阶段目标

完成一套前后端分离的用户认证系统，包含注册、登录、当前用户信息、Token
刷新、退出登录、后端测试和前端认证状态管理。

### 核心接口

  功能       方法   接口                         认证要求
  ---------- ------ ---------------------------- ------------------------
  注册       POST   `/api/auth/register/`        无
  登录       POST   `/api/auth/login/`           无
  当前用户   GET    `/api/auth/me/`              Access Token
  刷新       POST   `/api/auth/token/refresh/`   Refresh Token
  退出       POST   `/api/auth/logout/`          提交当前 Refresh Token

### 完整流程

``` text
注册 -> 登录 -> 获取 Access/Refresh
                    |
                    v
          Access 请求受保护 API
                    |
             Access 过期(401)
                    |
                    v
          Refresh Token 请求刷新
                    |
                    v
        保存新 Token -> 重试原请求
                    |
                    v
           退出：撤销 Refresh
             清理前端登录状态
```

## 二、2.1 用户模型与认证配置

### 1. Authentication 与 Authorization

-   Authentication（身份认证）：判断请求者是谁。
-   Authorization（权限控制）：判断已经识别的用户能做什么。

### 2. User 与 UserProfile

-   `User` 保存用户名、邮箱、密码哈希、账号状态等基础认证信息。
-   `UserProfile` 保存头像、简介等扩展业务资料。
-   分离基础身份与扩展资料，有利于保持模型职责清晰。

### 3. 密码安全

创建用户应使用：

``` python
User.objects.create_user(
    username="alice",
    email="alice@example.com",
    password="example-password"
)
```

验证密码应使用：

``` python
user.check_password(raw_password)
```

不能直接比较 `user.password == raw_password`，因为数据库中的 password
是密码哈希，不是明文。

### 4. 关键配置

-   `INSTALLED_APPS`：注册 Django、DRF、SimpleJWT 黑名单等应用。
-   `REST_FRAMEWORK`：配置默认认证类、权限类等。
-   `SIMPLE_JWT`：配置 Token 有效期、轮换和黑名单。
-   数据库与环境变量：敏感密钥、数据库密码不应硬编码或提交 Git。

## 三、2.2 用户注册 Serializer 与 API

### 1. Serializer 的职责

-   校验前端请求数据。
-   将校验后的数据交给业务逻辑。
-   将模型对象转换为响应数据。
-   控制字段是否可读、可写。

### 2. 注册字段

`username`、`email`、`password`、`password_confirm`。密码字段使用
`write_only=True`，允许接收输入但不在响应中输出。

### 3. 字段级与对象级校验

``` python
def validate_username(self, value):
    if User.objects.filter(username__iexact=value).exists():
        raise serializers.ValidationError("用户名已存在")
    return value
```

DRF 根据 `validate_<字段名>` 命名规则调用字段校验方法。

``` python
def validate(self, attrs):
    if attrs["password"] != attrs["password_confirm"]:
        raise serializers.ValidationError({
            "password_confirm": "两次密码不一致"
        })
    return attrs
```

-   `validate_username()`：单字段校验。
-   `validate_email()`：邮箱格式、规范化和重复校验。
-   `validate()`：多个字段之间的关系校验。

### 4. ORM 查重

`filter()` 构造查询；`username__iexact`
表示大小写不敏感的精确匹配；`exists()`
判断是否存在记录。查重只关心是否存在时，通常使用 `exists()`。

应用层查重不能代替数据库唯一约束。并发注册可能同时通过查重，因此数据库唯一约束仍应兜底，并处理冲突异常。

### 5. 密码强度验证

Django 的 `validate_password(password, user=...)`
可按配置的密码验证器检查密码长度、常见密码和与用户属性的相似度。Django
的 `ValidationError` 需要转换为 DRF 的
`serializers.ValidationError`，以便按 API 格式返回。

### 6. 注册事务

``` python
with transaction.atomic():
    user = User.objects.create_user(...)
    UserProfile.objects.create(user=user)
```

User 和 UserProfile
是同一个注册业务。事务保证两个操作一起成功或一起回滚，避免出现用户已创建但资料创建失败的半成品数据。相关
MySQL 表应使用 InnoDB 等支持事务的存储引擎。

### 7. `save()` 与 `create()`

调用 `serializer.is_valid()` 后执行
`serializer.save()`。如果没有传入已有 `instance`，`.save()` 会调用
Serializer 的 `create(validated_data)`；有已有实例时通常调用
`update()`。

### 注册安全要点

-   密码字段设置 `write_only=True`。
-   使用 `create_user()` 保存密码。
-   不返回密码或密码哈希。
-   校验密码强度和重复字段。
-   使用数据库唯一约束防止并发重复。
-   用事务保证 User 与 UserProfile 一致。

## 四、2.3 SimpleJWT 登录接口

### 1. JWT 结构

JWT 全称 **JSON Web Token**，通常由三部分组成：

``` text
Header.Payload.Signature
```

-   Header：令牌类型、签名算法等信息。
-   Payload：用户标识、过期时间等声明。
-   Signature：验证内容是否被篡改以及签名是否可信。

Payload 通常只是 Base64URL 编码，不等于加密。不要把密码等敏感信息放入
Payload。

### 2. Access Token 与 Refresh Token

  类型            用途             TaskFlow 配置
  --------------- ---------------- ---------------
  Access Token    访问受保护 API   30 分钟
  Refresh Token   获取新 Token     7 天

Access 有效期较短，Refresh 有效期较长，兼顾凭证风险与用户体验。

### 3. 继承登录 Serializer

``` python
class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        "no_active_account": "用户名或密码错误，或账号不可用。"
    }
```

继承 SimpleJWT 的 `TokenObtainPairSerializer`，复用账号认证与 Token
签发流程，再覆盖项目需要的错误提示。

### 4. 登录 API 流程

1.  通过 `request.data` 获取请求体。
2.  `self.get_serializer(data=request.data)` 创建登录 Serializer。
3.  调用 `serializer.is_valid()`。
4.  父类验证流程执行用户认证。
5.  认证成功后签发 Access 和 Refresh。
6.  从 `serializer.validated_data` 读取结果并返回。

这里的 `is_valid()` 不只是检查字段格式；SimpleJWT 登录 Serializer
的验证流程还会执行身份认证和 Token 签发。

### 5. HTTP 状态码与响应体 code

响应体中的 `code` 是 JSON 数据字段；真正的 HTTP 状态码由
`Response(..., status=...)` 决定。两者应保持一致。

-   200：成功。
-   201：资源创建成功。
-   400：请求数据校验失败。
-   401：未认证或凭证无效。
-   403：身份可能已识别，但无权执行操作。
-   404：资源不存在。
-   500：服务器内部错误。

统一登录失败提示可以减少攻击者通过错误信息枚举有效账号的机会。

## 五、2.4 当前用户信息接口

请求示例：

``` http
GET /api/auth/me/
Authorization: Bearer <Access Token>
```

登录负责验证身份并签发 Token；`/me/` 根据当前请求的 Access Token
返回当前用户资料。

DRF 调用认证类后，将识别出的用户放入 `request.user`。应使用：

``` python
RegisteredUserSerializer(request.user).data
```

不要信任前端传来的 `user_id`，否则客户端可能篡改 ID 读取其他用户资料。

`permission_classes = [IsAuthenticated]`
表示该接口要求请求已经通过身份认证。响应只返回必要字段，如
`id`、`username`、`email`，不应输出密码哈希等内部信息。

## 六、JWTAuthentication 请求认证流程

``` text
Authorization: Bearer <Access Token>
                |
                v
       JWTAuthentication
                |
                v
    解析请求头并验证 Token
                |
                v
 检查签名、有效期、Token 类型
                |
                v
     根据用户标识查询 User
                |
                v
       返回 user 和 token
                |
                v
     DRF 设置 request.user
                |
                v
       执行权限检查和视图
```

需要区分：

-   Authentication 负责识别用户。
-   Permission 负责判断用户能否执行操作。
-   Access Token 用于访问 API。
-   Refresh Token 用于刷新，不应当作普通 API 的访问凭证。
-   JWT 签名可检测篡改，但不代表 Payload 被加密。

常见认证失败：没有 Token、格式错误、签名无效、Token 过期、Refresh
被用于普通 API、用户不存在或已禁用。

## 七、2.5 Token 刷新与退出登录

### 1. 为什么需要刷新

Access Token 过期后，受保护 API 返回 401。若 Refresh Token
仍有效，前端可以用它换取新 Token，不必立即要求用户重新输入账号密码。

### 2. Refresh Token 轮换

``` python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
```

示例：初始 A1/R1；使用 R1 刷新后得到 A2/R2，R1
被加入黑名单。前端必须同时保存 A2 和 R2。

### 3. 重要边界：旧 Access 不会自动失效

Refresh 被拉黑不代表此前签发的 Access 同时失效。旧 Access
可能继续有效到自身过期。若要求立即撤销
Access，需要额外的服务端撤销机制，例如 Token
版本、黑名单校验或集中式会话管理。

### 4. 退出登录

1.  前端读取当前 Refresh Token。
2.  向退出接口提交 Refresh Token。
3.  后端尝试将其加入黑名单。
4.  前端清理 sessionStorage 中的 Token。
5.  Pinia 清理用户和认证状态。
6.  跳转登录页。

若网络错误或
500，前端可以本地退出，但服务端是否成功撤销无法确认，应提示这一点。TaskFlow
当前只撤销本次提交的 Refresh Token，不会自动撤销其他设备会话。

### 5. 401 与 403

-   401：身份凭证缺失、无效或过期，可按具体情况尝试刷新。
-   403：通常表示权限不足，不应仅因 403 就刷新 Token。

## 八、2.6 后端认证自动化测试

### 1. 测试目的

验证正常流程和异常流程，防止后续修改破坏注册、登录、当前用户、刷新和退出功能。

### 2. 测试范围

  模块       成功场景                   失败场景
  ---------- -------------------------- -------------------------------------
  注册       创建 User 和 Profile       用户名/邮箱重复、密码不一致、弱密码
  登录       返回双 Token               密码错误、用户不存在、账号禁用
  当前用户   有效 Access 获取本人信息   无 Token、无效或过期 Token
  刷新       返回新 Token               Refresh 无效、过期或已拉黑
  退出       当前 Refresh 被撤销        缺少或无效 Refresh

### 3. 常见测试工具

-   `TestCase`：Django 测试类。
-   `APITestCase`：DRF API 测试类。
-   `APIClient`：模拟 HTTP 请求。
-   `setUp()`：每个测试方法执行前准备数据。
-   `assertEqual()`：断言相等。
-   `force_authenticate()`：直接为测试请求设置用户身份，适合测试视图权限或业务逻辑，但不会完整验证真实
    JWT 请求头、签名和过期时间。

测试真实 JWT 流程时，应通过登录接口取得 Token，并在请求头中携带 Bearer
Token。

### 4. 测试数据库与 MySQL 1044

Django 通常创建独立测试数据库，例如
`test_taskflow`，以避免污染开发数据。如果数据库账号没有创建或操作测试库的权限，可能出现
MySQL 1044。

处理原则：

-   确认 Django 实际使用的数据库账号和测试库名称。
-   由管理员为测试账号授予指定测试库所需的最小权限。
-   不要给普通应用账号整个 MySQL 实例的全局管理权限。
-   测试完成后确认测试数据隔离和清理情况。

### 5. 常用命令

``` powershell
python manage.py test
python manage.py test users
python manage.py test users.tests
python manage.py test --keepdb
python manage.py check
```

`--keepdb`
可保留测试数据库以加快重复测试，具体行为取决于项目和数据库配置。

测试通过只说明已覆盖的场景满足断言，不代表系统绝对没有缺陷；还要关注覆盖范围、数据库状态、并发和网络异常。

## 九、2.7 Vue 登录注册页面与 API 接入

### 1. 前后端分离

Vue 负责页面、交互和前端状态；Django/DRF 负责
API、业务逻辑、数据持久化、身份认证和权限校验。双方通过 HTTP 和 JSON
交换数据。

### 2. CORS 与 Vite 代理

不同协议、域名或端口可能构成不同
Origin，浏览器同源策略会限制跨源访问。CORS
是服务器声明允许跨源访问的机制。Vite
代理主要解决开发环境请求转发问题，不等于生产环境部署方案；生产环境通常由
Nginx、网关或同源部署架构处理。

### 3. Axios 封装

统一 Axios 实例集中处理
baseURL、超时、请求拦截器、响应拦截器和错误映射，避免每个页面重复编写请求逻辑。

请求拦截器在发出请求前附加：

``` http
Authorization: Bearer <Access Token>
```

不要把 Refresh Token 作为普通 API 的 Authorization 凭证。

### 4. Token 存储与安全边界

TaskFlow 当前使用 `sessionStorage` 保存 Access 和 Refresh
Token。它适合同一标签页会话内使用，但同源 JavaScript 可以读取，因此 XSS
可能窃取 Token。它不是绝对安全的存储方案。需要结合 XSS 防护、CSP 和
HttpOnly/Secure/SameSite Cookie 等方案评估。

### 5. Pinia 认证状态

Store 管理
`accessToken`、`refreshToken`、`user`、`isLoading`、`isAuthenticated`
等共享状态。`isAuthenticated` 可由当前用户和 Token
状态派生。前端状态只服务于界面，真正的访问控制必须由后端执行。

### 6. 登录流程

``` text
提交账号密码 -> login API -> 获取双 Token
-> 使用 Access 请求 /me/
-> 获取用户资料 -> 写入 Token 管理模块和 Pinia
-> 跳转 Dashboard
```

登录后请求
`/me/`，可以获得服务端确认的用户资料，而不是仅根据表单内容拼接用户信息。

### 7. 注册流程

前端做必要的表单校验，调用注册
API；后端仍需重新校验，不能信任前端校验。TaskFlow
当前注册成功后不自动登录，而是跳转登录页并显示成功提示。

## 十、2.8 前端登录状态恢复与路由守卫

### 1. 页面刷新后的恢复

页面刷新会重建 Vue 应用和 Pinia Store，内存状态丢失，但 sessionStorage
中的 Token 可能仍在。应用启动时应读取 Token、请求 `/me/`
验证身份，并按需要尝试刷新；认证明确失败时清理状态。网络错误或 500
不应简单等同于凭证失效。

### 2. 路由元信息

-   `requiresAuth`：访问路由前必须登录。
-   `guestOnly`：仅允许未登录用户访问，例如登录和注册页。

  场景                          预期
  ----------------------------- --------------------
  未登录访问 Dashboard          跳转登录页
  已登录访问 Dashboard          正常进入
  已登录访问 Login/Register     跳转 Dashboard
  redirect 为合法站内地址       登录后返回目标页面
  redirect 指向外部或危险地址   拒绝或回退默认页

### 3. redirect 安全

URL 参数不可信。应阻止外部网站、`//example.com`
协议相对地址、登录页循环跳转和不合法路径，避免开放重定向。

### 4. Dashboard 白屏排查

如果出现：

``` text
[Vue Router warn]: No match found for location with path "/dashboard"
```

优先检查路由表是否存在 `/dashboard`、path 拼写、Dashboard
组件导入路径、`main.js` 是否 `app.use(router)`、`App.vue` 是否包含
`<router-view />`，以及路由守卫配置。这首先是路由匹配问题，不应直接归因于
Token。

## 十一、Axios 自动刷新与并发控制

### 1. 自动刷新流程

``` text
业务请求携带 Access
-> 后端返回 401
-> 响应拦截器判断是否允许刷新
-> 独立 Axios 客户端请求 Refresh API
-> 保存新 Access + Refresh
-> 使用新 Access 重试原请求
```

### 2. 为什么使用独立刷新客户端

避免刷新接口本身再次进入普通请求的 401
自动刷新逻辑，形成递归或循环。登录、注册、退出、刷新等接口应按项目规则排除自动刷新。

### 3. Promise 锁解决并发

多个请求同时 401 时，如果每个请求都刷新，会产生竞争；开启 Refresh
轮换时尤其容易冲突。第一个请求创建刷新 Promise，后续请求等待同一个
Promise；成功后各自使用新 Token 重试，最后释放锁。

### 4. 迟到的 401

请求 A、B 都使用旧 Access A1 发出。A 先 401 并刷新得到 A2，B 的 401
响应稍后才到。B 应比较请求发出时使用的 Token 与当前 Token；若当前 Token
已更新，直接用 A2 重试，不要再次刷新。TaskFlow 通过记录请求实际使用的
Access Token（例如 `_accessTokenUsed`）处理。

### 5. 错误处理原则

  情况                         处理原则
  ---------------------------- ------------------------------------
  Access 过期、Refresh 有效    刷新并重试
  Refresh 过期、无效或已拉黑   清理认证状态，要求重新登录
  403                          不应仅因 403 自动刷新
  网络错误                     不应直接认定 Token 失效
  服务器 500                   不应直接认定 Token 失效
  Token 保存失败               清理不一致状态，避免继续使用旧状态

## 十二、第二阶段自查清单

### 后端

-   [ ] 能解释 User 与 UserProfile 的职责。
-   [ ] 能解释密码哈希、`create_user()` 和 `check_password()`。
-   [ ] 能解释 Serializer 字段校验、对象校验和 `create()`。
-   [ ] 能解释 `transaction.atomic()`。
-   [ ] 能讲清注册、登录和 `/me/` 的流程。
-   [ ] 能解释 JWT 三部分以及 Payload 不加密。
-   [ ] 能解释 Access/Refresh 的职责和有效期。
-   [ ] 能解释 JWTAuthentication 如何设置 `request.user`。
-   [ ] 能解释 Token 轮换、黑名单和退出边界。
-   [ ] 能运行并理解认证测试。

### 前端

-   [ ] 能解释前后端分离、CORS 和 Vite 代理。
-   [ ] 能解释 Axios 请求/响应拦截器。
-   [ ] 能解释 sessionStorage 的安全边界。
-   [ ] 能解释 Pinia 认证状态。
-   [ ] 能讲清登录、注册 API 流程。
-   [ ] 能解释页面刷新后的状态恢复。
-   [ ] 能解释 `requiresAuth` 和 `guestOnly`。
-   [ ] 能讲清 401 自动刷新、Promise 锁和迟到 401。
-   [ ] 能排查 401、403、网络错误和路由不匹配。

### 达标标准

1.  不看教程能画出注册、登录、`/me/`、刷新和退出流程。
2.  能定位对应的后端 View、Serializer、认证类和前端模块。
3.  能解释关键代码为什么这样写。
4.  能使用 Network、后端日志和自动化测试定位问题。
5.  能说明当前设计的安全边界。
6.  能用 2---3 分钟向面试官介绍认证系统。
