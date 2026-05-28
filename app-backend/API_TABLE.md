# Smart Education System — API 接口文档

> **Base URL**: `http://<host>/api/v1`  
> **认证方式**: Bearer Token（JWT）  
> 登录后将返回的 `access_token` 放入请求 Header：`Authorization: Bearer <token>`  
> **角色说明**：`admin`（管理员）> `teacher`（教师）> `student`（学生）

---

## 目录

- [一、用户模块 `/users`](#一用户模块-users)
- [二、班级模块 `/classes`](#二班级模块-classes)
- [三、教材模块 `/textbooks`](#三教材模块-textbooks)
- [四、对话模块 `/chat`](#四对话模块-chat)
- [五、通知模块 `/notifications`](#五通知模块-notifications)
- [六、管理员模块 `/admin`](#六管理员模块-admin)
- [附录：公共数据类型](#附录公共数据类型)

---

## 一、用户模块 `/users`

### 1.1 用户注册

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/users/register` |
| **权限** | 无需登录 |
| **Content-Type** | `application/json` |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | `string` | ✅ | 用户名，3~50 字符 |
| `email` | `string` | ✅ | 电子邮箱，3~100 字符 |
| `password` | `string` | ✅ | 密码，6~100 字符 |
| `role` | `string` | ❌ | 角色，枚举值：`student`（默认）/ `teacher` / `admin` |

**响应 `201 Created`**

```json
{
  "id": 1,
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "role": "student",
  "status": "active"
}
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `400` | 用户名或邮箱已被注册 |
| `422` | 请求体格式校验失败 |

---

### 1.2 用户登录

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/users/login/access-token` |
| **权限** | 无需登录 |
| **Content-Type** | `application/x-www-form-urlencoded`（OAuth2 表单格式） |

**请求体（Form）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | `string` | ✅ | 用户名 |
| `password` | `string` | ✅ | 密码 |

**响应 `200 OK`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `400` | 用户名或密码错误 |
| `400` | 账户已被冻结 |

---

### 1.3 获取当前用户信息

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/users/me` |
| **权限** | 已登录（任意角色） |

**无请求参数**

**响应 `200 OK`**

```json
{
  "id": 1,
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "role": "student",
  "status": "active"
}
```

---

## 二、班级模块 `/classes`

### 2.1 教师创建班级

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/classes/` |
| **权限** | `teacher` / `admin` |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `string` | ✅ | 班级名称 |

**响应 `200 OK`**

```json
{
  "id": 1,
  "name": "高等数学 A 班",
  "class_code": "AB12CD",
  "teacher_id": 5
}
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `500` | 多次重试后仍无法生成唯一班级码 |

---

### 2.2 教师数据看板

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/classes/dashboard` |
| **权限** | `teacher` / `admin` |

**无请求参数**

**响应 `200 OK`**

```json
{
  "classes": [
    {
      "id": 1,
      "name": "高等数学 A 班",
      "class_code": "AB12CD",
      "textbooks": [
        { "id": 3, "title": "高等数学上册", "status": "success" }
      ],
      "students": [
        { "student_id": 10, "username": "lisi" }
      ]
    }
  ]
}
```

> `textbooks[].status` 枚举：`pending` / `processing` / `success` / `failed`

---

### 2.3 学生查看自己的班级列表

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/classes/my-classes` |
| **权限** | `student` |

**无请求参数**

**响应 `200 OK`**

```json
[
  {
    "application_id": 7,
    "class_id": 1,
    "class_name": "高等数学 A 班",
    "class_code": "AB12CD",
    "teacher_id": 5,
    "application_status": "approved"
  },
  {
    "application_id": 8,
    "class_id": 2,
    "class_name": "线性代数 B 班",
    "class_code": "XY99ZZ",
    "teacher_id": 6,
    "application_status": "pending"
  }
]
```

> `application_status` 枚举：`pending`（待审批）/ `approved`（已通过）/ `rejected`（已拒绝）

---

### 2.4 学生申请加入班级

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/classes/join` |
| **权限** | `student` |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `class_code` | `string` | ✅ | 6 位大写字母+数字的班级码（自动 trim & 转大写） |

**响应 `201 Created`**

```json
{
  "application_id": 7,
  "class_id": 1,
  "class_name": "高等数学 A 班",
  "status": "pending",
  "message": "申请已提交，请等待教师审批"
}
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 班级码无效 |
| `409` | 已申请加入或已在班级中 |

---

### 2.5 教师查看班级申请列表

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/classes/{class_id}/applications` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `class_id` | `integer` | 班级 ID |

**Query 参数（可选）**

| 参数 | 类型 | 说明 |
|------|------|------|
| `filter_status` | `string` | 按状态筛选：`pending` / `approved` / `rejected` |

**响应 `200 OK`**

```json
[
  {
    "application_id": 7,
    "student_id": 10,
    "student_username": "lisi",
    "status": "pending"
  }
]
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 班级不存在 |
| `403` | 无权操作此班级 |

---

### 2.6 教师批量审批申请

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/classes/{class_id}/applications/review` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `class_id` | `integer` | 班级 ID |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `application_ids` | `integer[]` | ✅ | 待审批的申请 ID 列表 |
| `action` | `string` | ✅ | `approve`（同意）或 `reject`（拒绝） |

**响应 `200 OK`**

```json
{
  "updated_count": 3,
  "action": "approve"
}
```

> 仅处于 `pending` 状态的申请才会被更新，`updated_count` 为实际更新条数。

---

### 2.7 教师将学生移出班级

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/classes/{class_id}/students/{student_id}` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `class_id` | `integer` | 班级 ID |
| `student_id` | `integer` | 被移除的学生 ID |

**响应 `200 OK`**

```json
{ "message": "已成功将学生移除该班级" }
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 该学生不在当前班级中 |

---

### 2.8 教师解散班级

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/classes/{class_id}` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `class_id` | `integer` | 班级 ID |

**响应 `200 OK`**

```json
{ "message": "班级已解散" }
```

---

### 2.9 学生主动退出班级

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/classes/{class_id}/quit` |
| **权限** | `student` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `class_id` | `integer` | 班级 ID |

**响应 `200 OK`**

```json
{ "message": "已成功退出班级" }
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 您当前不在该班级或已退出 |

---

## 三、教材模块 `/textbooks`

### 3.1 教师上传 PDF 教材

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/textbooks/upload` |
| **权限** | `teacher` / `admin` |
| **Content-Type** | `multipart/form-data` |

**请求体（Form）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | `string` | ✅ | 教材名称 |
| `file` | `file` | ✅ | PDF 文件，大小不超过系统配置的 `MAX_UPLOAD_MB`（默认 50MB） |

**响应 `201 Created`**

```json
{
  "id": 3,
  "title": "高等数学上册",
  "status": "pending",
  "processing_progress": 0,
  "chroma_collection_id": null,
  "file_path": "uploads/textbooks/2026/05/abc123.pdf",
  "created_at": "2026-05-27T08:00:00"
}
```

> 上传成功后系统自动入队解析任务，前端应轮询 `GET /textbooks/{id}/status` 查询进度。

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `415` | 文件格式不是 PDF |
| `413` | 文件超过大小限制 |
| `500` | 文件保存失败 |

---

### 3.2 教师查看教材列表

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/textbooks/` |
| **权限** | `teacher` / `admin` |

**无请求参数**

**响应 `200 OK`**

```json
[
  {
    "id": 3,
    "title": "高等数学上册",
    "status": "success",
    "processing_progress": 100,
    "chroma_collection_id": "textbook_vec_3",
    "file_path": "uploads/textbooks/2026/05/abc123.pdf",
    "created_at": "2026-05-27T08:00:00"
  }
]
```

---

### 3.3 查询教材解析进度

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/textbooks/{textbook_id}/status` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `textbook_id` | `integer` | 教材 ID |

**响应 `200 OK`**

```json
{
  "id": 3,
  "title": "高等数学上册",
  "status": "processing",
  "processing_progress": 45,
  "chroma_collection_id": null
}
```

> **解析状态流转**：`pending` → `processing` → `success` | `failed`  
> **建议轮询间隔**：3 秒，直到状态为 `success` 或 `failed` 时停止。  
> `processing_progress` 范围：0~100（%）

---

### 3.4 将教材绑定到班级

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/textbooks/{textbook_id}/bind-classes` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `textbook_id` | `integer` | 教材 ID（状态须为 `success`） |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `class_ids` | `integer[]` | ✅ | 目标班级 ID 列表（不可为空） |

**响应 `200 OK`**

```json
{
  "bound_count": 2,
  "skipped_count": 1,
  "already_bound_count": 1,
  "invalid_count": 0,
  "message": "绑定成功"
}
```

| 字段 | 说明 |
|------|------|
| `bound_count` | 本次成功新增绑定的班级数 |
| `skipped_count` | 总跳过数（= `already_bound_count` + `invalid_count`） |
| `already_bound_count` | 其中已绑定（幂等跳过）的班级数 |
| `invalid_count` | 其中越权或不存在的班级数 |

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 教材不存在或无权操作 |
| `422` | 教材尚未解析完成 / `class_ids` 为空 |

---

### 3.5 重新触发教材解析

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/textbooks/{textbook_id}/reprocess` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `textbook_id` | `integer` | 教材 ID（状态须为 `failed`） |

**响应 `200 OK`**

```json
{
  "id": 3,
  "status": "pending",
  "message": "已重新提交解析任务，请稍后轮询状态"
}
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `422` | 当前状态不是 `failed`，无法重试 |
| `404` | 原始文件已不存在，请重新上传 |
| `503` | 任务队列暂时不可用 |

---

### 3.6 解绑教材与班级

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/textbooks/{textbook_id}/unbind-classes` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `textbook_id` | `integer` | 教材 ID |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `class_ids` | `integer[]` | ✅ | 要解绑的班级 ID 列表 |

**响应 `200 OK`**

```json
{
  "message": "解绑成功",
  "unbound_count": 2
}
```

---

### 3.7 软删除教材

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/textbooks/{textbook_id}` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `textbook_id` | `integer` | 教材 ID |

**响应 `200 OK`**

```json
{ "message": "教材已成功删除" }
```

> 删除后同步清理对应的 ChromaDB 向量集合，关联该教材的会话将无法继续对话。

---

## 四、对话模块 `/chat`

### 4.1 创建 Chat 会话

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/chat/sessions` |
| **权限** | 已登录（任意角色，不同角色有不同鉴权逻辑） |

**权限说明**

| 角色 | 限制 |
|------|------|
| `student` | 必须通过已审批（`approved`）的班级关联到该教材 |
| `teacher` | 只能为自己名下、状态为 `success` 的教材创建测试会话 |
| `admin` | 可为系统内任意状态为 `success` 的教材创建会话 |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | `string` | ✅ | 会话标题（建议使用第一个问题作为标题） |
| `textbook_id` | `integer` | ✅ | 教材 ID |

**响应 `200 OK`**

```json
{
  "id": 12,
  "title": "向量空间的定义是什么",
  "textbook_id": 3,
  "created_at": "2026-05-27T10:00:00"
}
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `403` | 无权访问该教材（未在班级中 / 教材不属于当前教师 / 教材未解析完成） |

---

### 4.2 获取学生会话列表

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/chat/sessions` |
| **权限** | `student` |

**无请求参数**

**响应 `200 OK`**

```json
[
  {
    "id": 12,
    "title": "向量空间的定义是什么",
    "textbook_id": 3,
    "created_at": "2026-05-27T10:00:00"
  }
]
```

> 按创建时间倒序排列。教师审计请使用 `GET /chat/teacher/student-chats`。

---

### 4.3 获取会话历史消息

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/chat/sessions/{session_id}/messages` |
| **权限** | 已登录（仅限会话归属人） |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | `integer` | 会话 ID |

**Query 参数（可选）**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | `integer` | `0` | 分页偏移量 |
| `limit` | `integer` | `50` | 每页条数，建议首次 50，上翻时增加 skip |

**响应 `200 OK`**

```json
[
  {
    "id": 101,
    "sender": "user",
    "content": "向量空间的定义是什么？",
    "created_at": "2026-05-27T10:00:05"
  },
  {
    "id": 102,
    "sender": "ai",
    "content": "向量空间（线性空间）是一个集合...",
    "created_at": "2026-05-27T10:00:07"
  }
]
```

> `sender` 枚举：`user`（学生）/ `ai`（AI 回复）/ `system`（系统消息）  
> 按 `created_at` **升序**排列（对话时间顺序）。

---

### 4.4 SSE 流式问答（RAG）

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/chat/stream` |
| **权限** | 已登录（不同角色有实时鉴权拦截） |
| **响应类型** | `text/event-stream`（SSE） |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | `integer` | ✅ | 会话 ID |
| `content` | `string` | ✅ | 用户提问内容 |

**响应流格式**

每个 SSE 事件格式为 `data: <JSON>\n\n`：

```
data: {"content": "向量"}
data: {"content": "空间是"}
data: {"content": "一种数学结构..."}
data: [DONE]
```

| 事件数据 | 说明 |
|---------|------|
| `{"content": "..."}` | AI 回复的一个 Token 片段，前端拼接展示 |
| `[DONE]` | 流式输出结束标志 |
| `{"error": "..."}` | 出现异常时的错误信息 |

**处理逻辑**

1. 校验会话归属权限  
2. 实时拦截鉴权（防止教材被删除后继续对话）  
3. 持久化用户消息  
4. 检索最近 N 轮历史消息（N 由 `CHAT_HISTORY_WINDOW` 配置，默认 5 轮）  
5. 向 ChromaDB 检索教材相关文本块（RAG）  
6. 流式调用大语言模型  
7. 流结束后持久化 AI 完整回复  

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 会话不存在或不属于当前用户 |
| `403` | 教材或班级已被删除/解绑，无权继续对话 |

---

### 4.5 教师审计：获取学生会话列表

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/chat/teacher/student-chats` |
| **权限** | `teacher` / `admin` |

**Query 参数（可选）**

| 参数 | 类型 | 说明 |
|------|------|------|
| `class_id` | `integer` | 按班级筛选 |
| `student_id` | `integer` | 按学生筛选 |
| `textbook_id` | `integer` | 按教材筛选 |
| `skip` | `integer` | 分页偏移量，默认 `0` |
| `limit` | `integer` | 每页条数，默认 `50` |

**响应 `200 OK`**

```json
[
  {
    "id": 12,
    "title": "向量空间的定义是什么",
    "student_id": 10,
    "student_name": "lisi",
    "textbook_id": 3,
    "textbook_title": "高等数学上册",
    "class_id": 1,
    "class_name": "高等数学 A 班",
    "summary": "学生询问了向量空间定义及其基本性质，疑问已得到解答。",
    "summary_updated_at": "2026-05-27T10:05:00",
    "created_at": "2026-05-27T10:00:00"
  }
]
```

> `summary` 为 AI 自动生成的会话阶段性摘要，可能为 `null`（未开启或未达到触发条件）。

---

### 4.6 教师审计：调阅学生特定会话消息

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/chat/teacher/student-chats/{session_id}/messages` |
| **权限** | `teacher` / `admin` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | `integer` | 会话 ID |

**Query 参数（可选）**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | `integer` | `0` | 分页偏移量 |
| `limit` | `integer` | `100` | 每页条数 |

**响应 `200 OK`**（同 [4.3](#43-获取会话历史消息)）

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `403` | 会话不属于当前教师名下的班级，或学生未被审批通过 |

---

### 4.7 删除会话

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/chat/sessions/{session_id}` |
| **权限** | 已登录（仅限会话归属人） |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | `integer` | 会话 ID |

**响应 `200 OK`**

```json
{ "message": "会话已删除" }
```

---

## 五、通知模块 `/notifications`

### 5.1 查询个人通知列表

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/notifications` |
| **权限** | 已登录（任意角色） |

**Query 参数（可选）**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | `integer` | `0` | 分页偏移量 |
| `limit` | `integer` | `100` | 每页条数 |

**响应 `200 OK`**

```json
[
  {
    "id": 5,
    "sender_id": 1,
    "receiver_id": 10,
    "title": "您有新的入班申请待审批",
    "content": "学生 lisi 申请加入高等数学 A 班，请及时处理。",
    "is_read": false,
    "created_at": "2026-05-27T09:00:00"
  }
]
```

> 按创建时间**倒序**排列。`sender_id` 为 `null` 时表示系统通知。

---

### 5.2 标记单条通知为已读

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/notifications/{notification_id}/read` |
| **权限** | 已登录（仅限通知归属人） |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `notification_id` | `integer` | 通知 ID |

**响应 `200 OK`**

```json
{ "message": "已成功标记为已读" }
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 通知不存在 |
| `403` | 无权操作此通知 |

---

### 5.3 一键标记所有通知为已读

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/notifications/read-all` |
| **权限** | 已登录（任意角色） |

**无请求参数**

**响应 `200 OK`**

```json
{ "message": "成功将 5 条通知标记为已读" }
```

---

### 5.4 删除单条通知

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/notifications/{notification_id}` |
| **权限** | 已登录（仅限通知归属人） |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `notification_id` | `integer` | 通知 ID |

**响应 `200 OK`**

```json
{ "message": "通知已删除" }
```

**错误响应**

| HTTP 码 | 原因 |
|---------|------|
| `404` | 通知不存在 |
| `403` | 无权操作此通知 |

---

## 六、管理员模块 `/admin`

> ⚠️ **所有接口均需 `admin` 角色**，非管理员调用返回 `403 Forbidden`。

---

### 6.1 获取用户列表

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/admin/users` |

**Query 参数（可选）**

| 参数 | 类型 | 说明 |
|------|------|------|
| `role` | `string` | 按角色筛选：`admin` / `teacher` / `student` |
| `status` | `string` | 按状态筛选：`active` / `frozen` |
| `skip` | `integer` | 分页偏移量，默认 `0` |
| `limit` | `integer` | 每页条数，默认 `100` |

**响应 `200 OK`**

```json
[
  {
    "id": 10,
    "username": "lisi",
    "email": "lisi@example.com",
    "role": "student",
    "status": "active"
  }
]
```

---

### 6.2 审批教师资质

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/admin/users/{user_id}/approve-teacher` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_id` | `integer` | 用户 ID |

**响应 `200 OK`**（返回更新后的 UserResponse）

```json
{
  "id": 10,
  "username": "wangwu",
  "email": "wangwu@example.com",
  "role": "teacher",
  "status": "active"
}
```

---

### 6.3 冻结用户账号

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/admin/users/{user_id}/freeze` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_id` | `integer` | 用户 ID |

**响应 `200 OK`**（返回更新后的 UserResponse，`status` 变为 `frozen`）

---

### 6.4 解冻用户账号

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/admin/users/{user_id}/unfreeze` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_id` | `integer` | 用户 ID |

**响应 `200 OK`**（返回更新后的 UserResponse，`status` 变为 `active`）

---

### 6.5 强制软删除教材

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/admin/textbooks/{textbook_id}` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `textbook_id` | `integer` | 教材 ID |

**响应 `200 OK`**

```json
{ "message": "教材已成功强制软删除，并已向对应教师推送通知" }
```

> 同步向教材所属教师推送系统通知，并清理 ChromaDB 向量集合。

---

### 6.6 强制软删除聊天会话

| 项目 | 内容 |
|------|------|
| **方法** | `DELETE` |
| **路径** | `/admin/chat/sessions/{session_id}` |

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | `integer` | 会话 ID |

**响应 `200 OK`**

```json
{ "message": "会话已成功强制软删除" }
```

---

### 6.7 获取系统配置

| 项目 | 内容 |
|------|------|
| **方法** | `GET` |
| **路径** | `/admin/config` |

**响应 `200 OK`**

```json
{
  "LLM_API_KEY": "sk-xxxx",
  "LLM_BASE_URL": "https://api.openai.com/v1",
  "LLM_MODEL_NAME": "gpt-4o",
  "RAG_TOP_K": 4,
  "TEXTBOOK_CHUNK_SIZE": 200
}
```

---

### 6.8 动态修改系统配置

| 项目 | 内容 |
|------|------|
| **方法** | `PUT` |
| **路径** | `/admin/config` |

**请求体（JSON，所有字段均为可选）**

| 字段 | 类型 | 说明 | 取值范围 |
|------|------|------|---------|
| `LLM_API_KEY` | `string` | 大语言模型 API Key | — |
| `LLM_BASE_URL` | `string` | 大模型接口 Base URL | — |
| `LLM_MODEL_NAME` | `string` | 模型名称 | — |
| `RAG_TOP_K` | `integer` | 检索返回的文本块数量 | 1 ~ 20 |
| `TEXTBOOK_CHUNK_SIZE` | `integer` | 文本语义切片子块字数上限 | 50 ~ 2000 |

**响应 `200 OK`**（返回更新后的完整配置，同 [6.7](#67-获取系统配置)）

> 配置修改立即在当前运行时生效，并持久化写入 `config_override.json`。

---

### 6.9 向特定用户推送通知

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/admin/notifications` |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `receiver_id` | `integer` | ✅ | 接收者用户 ID |
| `title` | `string` | ✅ | 通知标题，最长 200 字符 |
| `content` | `string` | ✅ | 通知正文 |

**响应 `200 OK`**

```json
{ "message": "通知发送成功", "id": 5 }
```

---

### 6.10 向全员广播通知

| 项目 | 内容 |
|------|------|
| **方法** | `POST` |
| **路径** | `/admin/notifications/broadcast` |

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | `string` | ✅ | 通知标题，最长 200 字符 |
| `content` | `string` | ✅ | 通知正文 |

**响应 `200 OK`**

```json
{ "message": "广播发送成功，共发送给 128 名用户" }
```

> 仅向状态为 `active` 且未软删除的用户广播。

---

## 附录：公共数据类型

### 角色枚举（`UserRole`）

| 值 | 说明 |
|----|------|
| `student` | 学生 |
| `teacher` | 教师 |
| `admin` | 管理员 |

### 用户状态枚举（`UserStatus`）

| 值 | 说明 |
|----|------|
| `active` | 正常 |
| `frozen` | 已冻结（无法登录） |

### 教材状态枚举（`TextbookStatus`）

| 值 | 说明 |
|----|------|
| `pending` | 等待处理 |
| `processing` | 解析中 |
| `success` | 解析成功 |
| `failed` | 解析失败 |

### 申请状态枚举（`StudentClassStatus`）

| 值 | 说明 |
|----|------|
| `pending` | 待审批 |
| `approved` | 已通过 |
| `rejected` | 已拒绝 |

### 消息发送者枚举（`SenderRole`）

| 值 | 说明 |
|----|------|
| `user` | 学生发送 |
| `ai` | AI 回复 |
| `system` | 系统消息 |

### 通用错误格式

```json
{
  "detail": "错误描述文字"
}
```

### 认证相关错误码

| HTTP 码 | 场景 |
|---------|------|
| `401` | Token 无效、过期或未提供 |
| `403` | 已登录但角色权限不足，或操作了不属于自己的资源 |
| `404` | 资源不存在或已被软删除 |
| `422` | 请求体参数格式/值校验失败 |

---

*文档生成时间：2026-05-27 | 对应后端版本：commit 含全部三轮修复*
