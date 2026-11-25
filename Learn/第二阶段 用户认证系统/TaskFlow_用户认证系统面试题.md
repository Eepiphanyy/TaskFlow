# TaskFlow 用户认证系统面试题

> 技术栈：Django、Django REST Framework、SimpleJWT、Vue
> 3、Axios、Pinia。\
> 使用方法：先独立回答，再对照参考要点补充。回答时结合 TaskFlow
> 实际实现，不建议死记定义。

## 一、项目整体介绍

### 1. 请介绍一下你在 TaskFlow 中实现的用户认证系统。

**参考回答要点：**

-   后端使用 Django REST Framework，前端使用 Vue 3。
-   后端提供注册、登录、当前用户、Token 刷新和退出登录接口。
-   使用 Django User 保存基础账号信息，UserProfile 扩展用户资料。
-   使用 SimpleJWT 签发 Access Token 和 Refresh Token。
-   前端通过 Axios 统一请求，使用 Pinia 管理认证状态。
-   Access Token 过期后，前端使用 Refresh Token 自动刷新并重试原请求。
-   自动化测试覆盖注册、登录、当前用户、刷新和退出等流程。

### 2. 为什么采用前后端分离？

**参考回答要点：**
前端负责页面与交互，后端负责业务逻辑、数据库和安全校验，双方通过 API
交换数据。前后端可以独立开发和部署，但真正的身份与权限校验必须由后端完成。

### 3. 用户认证系统包含哪些核心接口？

**参考回答要点：** 注册负责创建用户；登录负责验证身份并签发
Token；`/me/` 返回当前用户资料；刷新接口使用 Refresh 获取新
Token；退出接口撤销当前 Refresh 并清理前端状态。

## 二、Django 用户模型与密码安全

### 4. Authentication 和 Authorization 有什么区别？

**参考回答要点：** Authentication
是身份认证，解决"你是谁"；Authorization
是权限控制，解决"你能做什么"。登录属于身份认证，是否允许用户删除工单属于权限控制。

### 5. 为什么使用 `get_user_model()`？

**参考回答要点：** 它返回项目当前配置的用户模型，避免写死默认
User。未来替换或自定义用户模型时，代码更容易兼容。

### 6. User 和 UserProfile 为什么分开？

**参考回答要点：** User 保存基础认证信息；UserProfile
保存头像、简介等扩展资料。分离可以让认证模型保持精简，扩展资料也更容易演进。

### 7. Django 如何保存用户密码？

**参考回答要点：** 不应保存明文密码。使用 `create_user()`
等机制保存密码哈希，验证时使用 `check_password()`。

### 8. 为什么不能使用 `user.password == raw_password`？

**参考回答要点：** 数据库中的 password
是哈希，不是用户输入的明文。应使用
`user.check_password(raw_password)`，由 Django 执行密码校验。

### 9. 密码哈希是否意味着密码泄露后绝对安全？

**参考回答要点：**
不是。哈希通常不可逆，但攻击者仍可能通过字典或暴力猜测破解弱密码。需要可靠的密码哈希算法、盐和密码强度策略。

## 三、注册接口与 Serializer

### 10. DRF Serializer 的作用是什么？

**参考回答要点：**
校验请求数据、将可信数据交给业务逻辑，并将模型对象转换为响应数据；同时控制字段的读写行为。

### 11. `write_only=True` 有什么作用？

**参考回答要点：**
字段可以接收输入，但不会在序列化输出中返回。密码需要接收，但不能返回密码或密码哈希。

### 12. `validate_username()` 和 `validate()` 有什么区别？

**参考回答要点：** `validate_<field>()` 是字段级校验；`validate(attrs)`
是对象级校验，可以检查多个字段之间的关系。用户名查重属于字段校验，两次密码一致性属于对象校验。

### 13. `username__iexact` 是什么意思？

**参考回答要点：** Django ORM 的大小写不敏感精确匹配。例如 `Alice` 和
`alice` 会被视为匹配。

### 14. 查重为什么常用 `exists()`？

**参考回答要点：** `exists()`
只判断是否存在符合条件的记录，不需要统计数量，适合查重这种只关心"有没有"的场景。

### 15. 为什么要调用 Django 的 `validate_password()`？

**参考回答要点：** 两次密码一致不代表密码安全。`validate_password()`
可以根据配置的验证器检查长度、常见密码和与用户属性的相似度等。

### 16. 为什么注册时使用 `create_user()`？

**参考回答要点：** `create_user()` 会按 Django
用户模型的机制处理密码哈希。不能把明文密码直接写入 password 字段后保存。

### 17. `transaction.atomic()` 在注册中有什么作用？

**参考回答要点：** 注册需要创建 User 和
UserProfile。事务保证两个操作一起成功或一起回滚，避免出现用户创建成功但资料创建失败的半成品数据。

### 18. 为什么 `serializer.save()` 会调用 `create()`？

**参考回答要点：** 没有传入已有模型实例时，`.save()` 根据
`validated_data` 调用 `create()`；传入已有实例时通常调用 `update()`。

### 19. 只在 Serializer 中检查用户名是否重复够不够？

**参考回答要点：**
不够。并发请求可能同时通过应用层查重，数据库唯一约束才是最终兜底，还应妥善处理唯一约束冲突。

## 四、JWT 与登录接口

### 20. JWT 是什么？由哪几部分组成？

**参考回答要点：** JWT 全称 JSON Web Token，常见结构为
Header、Payload、Signature。Header 描述令牌和算法信息；Payload
保存声明；Signature 用于验证内容完整性和签名可信性。

### 21. JWT Payload 是加密的吗？

**参考回答要点：** 通常不是，Payload 通常只是 Base64URL
编码，可以被解码读取。签名用于防止篡改，不负责隐藏内容，因此不能放入密码等敏感信息。

### 22. Access Token 和 Refresh Token 有什么区别？

**参考回答要点：** Access Token 用于访问受保护 API，有效期较短；Refresh
Token 用于获取新 Token，有效期较长。这样兼顾凭证风险和用户体验。

### 23. 为什么继承 `TokenObtainPairSerializer`？

**参考回答要点：** SimpleJWT 已实现账号认证和双 Token
签发。继承可以复用成熟逻辑，再按项目需要调整错误提示或响应处理。

### 24. SimpleJWT 登录 Serializer 的 `is_valid()` 做了什么？

**参考回答要点：**
不只是检查字段格式。父类验证流程还会执行用户认证，认证成功后生成 Token
并放入 `validated_data`。

### 25. `authenticate()` 和 `check_password()` 有什么区别？

**参考回答要点：** `check_password()` 验证某个 User
对象的密码；`authenticate()` 是 Django
认证框架的认证入口，会根据认证后端和凭据尝试识别、验证用户。SimpleJWT
登录流程会调用认证机制。

### 26. 为什么登录失败使用统一提示？

**参考回答要点：**
避免分别提示用户不存在和密码错误，减少攻击者通过错误信息枚举有效账号的机会。还应结合限流和监控。

### 27. HTTP 401 和 403 有什么区别？

**参考回答要点：** 401 表示身份认证未通过或凭证无效；403
表示请求被拒绝，通常是当前身份没有执行操作的权限。不能把所有 403 都当成
Token 过期。

## 五、JWTAuthentication 与当前用户接口

### 28. Access Token 通常放在哪里传给后端？

**参考回答要点：**

``` http
Authorization: Bearer <Access Token>
```

后端认证类从请求头中读取并验证 Token。

### 29. `JWTAuthentication` 的基本流程是什么？

**参考回答要点：** 解析 Authorization 请求头，验证 Token
格式、签名、有效期和类型，根据 Token
中的用户标识查询用户并检查状态；成功后返回用户和 Token，DRF 设置
`request.user`。

### 30. `request.user` 是怎么来的？

**参考回答要点：** DRF 在请求认证阶段调用认证类。JWTAuthentication 验证
Token 并识别用户后，DRF 才能在视图中通过 `request.user` 获取当前用户。

### 31. 为什么 `/me/` 不能使用前端传来的 `user_id`？

**参考回答要点：** 客户端数据不可信。攻击者可以修改 user_id
读取其他用户资料。后端应以已经验证的 `request.user` 为准。

### 32. `IsAuthenticated` 有什么作用？

**参考回答要点：** 它要求请求必须通过身份认证。它属于权限类，不负责解析
JWT 本身。

### 33. 把 Refresh Token 放到普通 API 的 Authorization 头会怎样？

**参考回答要点：** 普通受保护 API 需要 Access Token。Refresh Token
用于刷新，Token 类型校验会阻止它作为普通访问凭证使用。

## 六、Token 刷新、轮换与退出

### 34. Access Token 过期后，为什么不直接要求用户重新登录？

**参考回答要点：** 如果 Refresh Token 仍有效，可以用它获取新的 Access 和
Refresh，减少用户重新输入账号密码的次数。

### 35. 什么是 Refresh Token 轮换？

**参考回答要点：** 使用旧 Refresh 刷新时，后端签发新的 Access 和
Refresh，并按配置将旧 Refresh 加入黑名单。前端必须同时保存新双 Token。

### 36. 旧 Refresh 被拉黑后，旧 Access 会立即失效吗？

**参考回答要点：** 不会自动失效。黑名单机制针对 Refresh Token，旧 Access
可能继续有效到自身过期。立即撤销 Access 需要额外的服务端撤销设计。

### 37. TaskFlow 的退出登录如何实现？

**参考回答要点：** 前端提交当前 Refresh
Token，后端尝试加入黑名单；前端清理 sessionStorage 和 Pinia
状态。若服务端请求失败，前端可以本地退出，但不能声称服务端一定撤销成功。

### 38. 当前退出登录会让用户所有设备同时退出吗？

**参考回答要点：** 不会。当前设计只撤销本次提交的 Refresh
Token，其他设备的 Refresh Token 不会自动失效。

### 39. 为什么退出后 Access Token 可能仍然有效？

**参考回答要点：** 退出时拉黑的是 Refresh Token，普通 JWT Access
通常按签名和过期时间验证，不会自动查询 Refresh
黑名单，因此可能继续有效到过期。

### 40. 如果要求退出后 Access Token 立即失效，怎么设计？

**参考回答要点：** 可以引入服务端 Token 黑名单、Token
版本或会话版本机制。需要考虑每次请求的校验开销、数据库/缓存压力和清理策略。

## 七、Axios 自动刷新与前端认证状态

### 41. Axios 请求拦截器和响应拦截器分别做什么？

**参考回答要点：** 请求拦截器在请求发出前添加 Authorization
等请求头；响应拦截器统一处理响应、错误、401 刷新和重试。

### 42. 为什么封装统一 Axios 实例？

**参考回答要点：** 统一管理
baseURL、超时、请求头、拦截器和错误处理，减少重复代码，保持接口行为一致。

### 43. 为什么刷新 Token 使用独立 Axios 客户端？

**参考回答要点：** 避免刷新接口本身进入普通请求的 401
自动刷新逻辑，导致递归或循环。登录、注册、退出和刷新接口也应按项目规则排除自动刷新。

### 44. 多个请求同时返回 401，为什么不能各自刷新？

**参考回答要点：** 会造成重复刷新和竞争。开启 Refresh
轮换后，多个请求同时使用同一个旧 Refresh 可能发生冲突。应使用共享
Promise 锁合并刷新操作。

### 45. Promise 锁如何解决并发刷新？

**参考回答要点：** 第一个 401 创建刷新 Promise，其他请求等待同一个
Promise；成功后各请求使用新 Token 重试，刷新结束后释放锁。

### 46. 什么是迟到的 401？TaskFlow 如何处理？

**参考回答要点：** 多个请求都用旧 Access
发出，一个请求先刷新成功，另一个请求的 401
响应稍后才到。后者应比较请求实际使用的 Token 和当前
Token；若已更新，直接用新 Token 重试。TaskFlow 通过记录
`_accessTokenUsed` 等方式处理。

### 47. 为什么 403 不应该自动刷新 Token？

**参考回答要点：** 403 通常表示权限不足，不是凭证过期。刷新 Token
无法解决权限不足，还会产生无意义请求。

### 48. 网络错误或 500 是否应该清空 Token？

**参考回答要点：** 不能简单清空。网络错误和 500 不代表 Token
无效，应区分认证失败与服务不可用。

### 49. 为什么使用 Pinia 管理认证状态？

**参考回答要点：** 用户资料和登录状态会被多个页面共享。Pinia 集中管理
Token、用户资料和加载状态，避免组件状态不一致。前端状态不能替代后端认证。

### 50. 页面刷新后为什么需要重新请求 `/me/`？

**参考回答要点：** 刷新会重建 Vue 应用，Pinia 内存状态丢失。前端从
sessionStorage 读取 Token，再请求 `/me/` 验证身份并恢复用户资料。

### 51. sessionStorage 是否绝对安全？

**参考回答要点：** 不是。同源 JavaScript 可以读取，XSS 可能窃取
Token。应结合 XSS 防护、CSP，并评估 HttpOnly、Secure、SameSite Cookie
等方案。

## 八、Vue Router、CORS 与页面流程

### 52. `requiresAuth` 和 `guestOnly` 分别是什么？

**参考回答要点：** `requiresAuth` 表示访问路由前必须登录；`guestOnly`
表示仅允许未登录用户访问，如登录和注册页。

### 53. 为什么已登录用户访问登录页通常要跳 Dashboard？

**参考回答要点：** 避免已登录用户重复进入登录/注册页面，具体由
`guestOnly` 路由规则处理。

### 54. 为什么 redirect 参数需要校验？

**参考回答要点：** redirect 来自
URL，是不可信输入。不校验可能产生开放重定向或跳转循环。应限制为应用内部合法路径，排除外部地址和登录页循环。

### 55. 什么是 CORS？浏览器为什么会出现跨域问题？

**参考回答要点：**
浏览器同源策略限制页面脚本访问不同源资源。协议、域名或端口不同都可能构成不同
Origin。CORS 是服务器声明允许跨源访问的机制。

### 56. Vite 代理和生产环境部署有什么区别？

**参考回答要点：** Vite 代理主要服务开发环境，把前端 API
请求转发给后端。生产环境通常由
Nginx、网关或同源部署方案处理，不能依赖开发服务器代理。

### 57. 出现 `No match found for location with path "/dashboard"`，先查什么？

**参考回答要点：** 检查路由表是否注册 `/dashboard`、path
拼写、组件导入路径、`app.use(router)`、`<router-view />`
和路由守卫。这首先是路由匹配问题，不应直接判断为 Token 失效。

## 九、自动化测试与故障排查

### 58. 为什么认证系统需要自动化测试？

**参考回答要点：**
认证涉及多个接口和状态变化。自动化测试可以反复验证正常与异常行为，防止后续修改破坏注册、登录、刷新和退出。

### 59. `APITestCase` 和 `APIClient` 是什么？

**参考回答要点：** `APITestCase` 是 DRF 的 API 测试类；`APIClient`
用于模拟 HTTP 请求，可测试状态码、响应内容和数据库变化。

### 60. `force_authenticate()` 和真实 JWT 请求有什么区别？

**参考回答要点：** `force_authenticate()`
直接为测试请求设置用户身份，适合测试视图权限和业务逻辑；它不会完整验证请求头、JWT
签名、过期时间和 Token 类型。真实 JWT 流程应使用实际签发的 Bearer Token
测试。

### 61. Django 为什么创建 `test_taskflow`？

**参考回答要点：** 测试需要独立数据库，避免污染开发数据。Django
通常根据数据库配置创建测试数据库。

### 62. MySQL 1044 提示无权创建测试库，是否说明测试代码有问题？

**参考回答要点：** 不一定。1044
通常是数据库账号权限问题。应确认测试库名称和账号，由管理员授予指定测试库所需的最小权限，不要给普通应用账号整个
MySQL 实例的全局管理权限。

### 63. 测试全部通过是否代表系统没有 Bug？

**参考回答要点：**
不代表。测试只能证明已覆盖场景满足断言，还要检查覆盖范围、并发、网络故障、安全边界和真实部署环境。

“你在 TaskFlow 项目中是如何测试用户认证功能的？”

可以这样回答：

> 我使用 Django REST Framework 提供的 APITestCase 和 APIClient 编写认证接口自动化测试。
>
> 测试范围包括用户注册、JWT登录、当前用户信息、Token刷新和退出登录。
>
> 对于正常场景，我会检查HTTP状态码、响应数据和数据库变化；对于异常场景，则会验证重复注册、错误密码、未认证访问以及无效Refresh Token等情况。
>
> 此外，我还会验证Refresh Token轮换后旧Token是否进入黑名单，确保认证流程不仅能正常运行，也能正确处理异常情况。

## 十、场景分析题

### 64. 登录成功拿到 Token，但 `/me/` 返回 401，如何排查？

**回答思路：**

1.  检查登录响应是否返回 Access Token。
2.  检查请求头是否为 `Authorization: Bearer <Access Token>`。
3.  检查是否误用 Refresh Token。
4.  检查 Token 是否过期、签名是否有效。
5.  检查 Django 是否配置 JWTAuthentication。
6.  检查用户是否存在、是否启用。
7.  结合浏览器 Network 和后端日志定位。

### 65. Access 过期后页面直接跳回登录页，如何排查？

**回答思路：**

1.  查看受保护 API 是否返回 401。
2.  查看是否发起 Refresh API 请求。
3.  检查 Refresh 是否存在、过期或被拉黑。
4.  检查刷新响应格式和前端解析逻辑。
5.  检查新双 Token 是否同时保存。
6.  检查原请求是否用新 Access 重试。
7.  检查是否把网络错误或 500 错误地当成认证失败。

### 66. 多个 API 同时返回 401，刷新接口被调用多次，可能是什么原因？

**回答思路：** 检查刷新 Promise
是否共享、锁是否正确释放、并发请求是否复用同一 Promise，以及迟到的 401
是否比较请求实际使用的 Token 与当前 Token。

### 67. 用户退出后刷新页面又显示已登录，可能是什么原因？

**回答思路：** 检查退出时是否清理 sessionStorage、Pinia
是否清空、是否存在多个 Token 存储位置，以及应用初始化是否读取到旧
Token。

### 68. User 创建成功但 UserProfile 创建失败，如何避免脏数据？

**回答思路：** 使用 `transaction.atomic()`
把两个操作放在同一事务中，异常时整体回滚。

### 69. 一个设备退出后另一个设备仍可访问，一定是 Bug 吗？

**回答思路：** 不一定。当前设计只撤销本次提交的 Refresh
Token，其他设备会话不受影响；旧 Access
也可能在过期前继续有效。应先明确产品要求是单设备退出还是全设备退出。

## 十一、综合表达题

### 70. 请用 2---3 分钟介绍 TaskFlow 用户认证系统的设计。

**建议回答结构：**

1.  **技术选型**：Django REST Framework + SimpleJWT，前端 Vue 3 +
    Axios + Pinia。
2.  **后端注册**：校验字段和密码强度，使用 `create_user()`
    保存密码，通过事务创建 User 和 UserProfile。
3.  **登录与身份识别**：登录成功签发双 Token；前端用 Bearer Access
    请求受保护 API；JWTAuthentication 验证后设置 `request.user`。
4.  **Token 生命周期**：Access 短期访问，Refresh 长期刷新；开启 Refresh
    轮换和黑名单。
5.  **前端状态管理**：Axios 统一注入 Access，Pinia
    管理用户状态，刷新页面时请求 `/me/` 恢复状态。
6.  **异常处理**：401 时通过共享 Promise 刷新并重试；处理并发和迟到
    401；403 不触发刷新，网络错误不直接清空 Token。
7.  **退出与测试**：退出时撤销当前 Refresh
    并清理本地状态；自动化测试覆盖正常和异常流程。
8.  **设计边界**：Refresh 被撤销不代表旧 Access
    立即失效；当前退出只撤销当前提交的 Refresh Token。

## 十二、面试前重点复习清单

-   [ ] Authentication 与 Authorization 的区别。
-   [ ] Django 密码哈希、`create_user()` 和 `check_password()`。
-   [ ] Serializer 字段级校验、对象级校验和 `create()`。
-   [ ] `transaction.atomic()` 的作用。
-   [ ] JWT 三部分及 Payload 不加密。
-   [ ] Access Token 与 Refresh Token 的区别。
-   [ ] SimpleJWT 登录 Serializer 的执行流程。
-   [ ] JWTAuthentication 如何设置 `request.user`。
-   [ ] 为什么 `/me/` 不信任前端 user_id。
-   [ ] Refresh Token 轮换和黑名单。
-   [ ] 为什么旧 Access 不会因 Refresh 被拉黑而立即失效。
-   [ ] 退出登录的前后端流程及多设备边界。
-   [ ] Axios 请求/响应拦截器。
-   [ ] Promise 锁与迟到 401。
-   [ ] Pinia 认证状态和页面刷新恢复。
-   [ ] `requiresAuth`、`guestOnly` 与 redirect 校验。
-   [ ] `APITestCase`、`APIClient`、`force_authenticate()`。
-   [ ] 401、403、MySQL 1044 和路由不匹配的排查。

## 十三、面试回答原则

1.  先讲结论，再讲项目中的实现。
2.  结合 TaskFlow 的真实代码和接口，不只背概念。
3.  讲清楚为什么这样设计，而不只是用了什么技术。
4.  不夸大安全性：JWT Payload 不加密，sessionStorage 也不是绝对安全。
5.  明确实现边界：Refresh 黑名单不自动撤销旧
    Access；当前退出只撤销当前提交的 Refresh。
6.  不确定的细节回到源码和测试验证，不凭印象编造。
