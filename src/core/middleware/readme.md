用户要我梳理 `src\core\middleware` 文件夹下所有代码，分析中间件设计思路。首先我需要查看这个目录的结构和内容。用 list_files 来获取文件列表，深度设为2应该够了。然后并行读取所有文件的内容。之后进行分析。开始吧。
现在需要读取这些文件的内容。为了全面分析，我将并行读取所有文件。使用 read_file 工具。
现在所有文件都读取完毕。我需要分析这些中间件的设计思路。首先，我看到有9个文件。从内容来看，每个中间件都有特定的功能。让我逐一分析：

1. `__init__.py` - 可能为空或导出。
2. `app_logic_middleware.py` - 应用逻辑中间件，负责设置应用上下文，调用AppLogicProvider的回调。
3. `database_session_middleware.py` - 数据库会话中间件，为每个请求提供数据库会话，智能处理事务提交和回滚。
4. `global_exception_handler.py` - 全局异常处理器，统一处理HTTP异常和其他异常。
5. `hmac_signature_middleware.py` - HMAC签名验证中间件，验证请求的HMAC签名，防止重放攻击。
6. `profile_middleware.py` - 性能剖析中间件，基于pyinstrument提供性能剖析功能。
7. `prometheus_middleware.py` - Prometheus指标中间件，自动记录HTTP请求指标。
8. `sse_exception_middleware.py` - SSE异常处理中间件，将HTTP异常转换为SSE事件格式。
9. `user_context_middleware.py` - 用户上下文中间件，从请求中提取用户信息并设置到上下文变量中。

整体设计思路：这些中间件围绕FastAPI/Starlette的BaseHTTPMiddleware构建，每个中间件专注于一个横切关注点（cross-cutting concern）。它们遵循单一职责原则，通过DI容器获取依赖（如get_bean_by_type）。中间件之间通过请求/响应管道串联，每个中间件可以修改请求或响应，或处理异常。

需要总结出共同的设计模式：如依赖注入、上下文管理、异常处理、资源生命周期管理、可配置性、异步支持等。

现在开始整理回答。我会先概述模块整体设计思路，然后分类介绍各中间件的职责和设计特点，最后总结设计原则和架构优势。

开始撰写。
## `src\core\middleware` 模块梳理与中间件设计思路分析

该模块是 EverMemOS 的**横切关注点 (Cross-Cutting Concerns) 集中处理层**，基于 FastAPI/Starlette 的中间件体系，实现了**认证、上下文管理、数据库事务、监控、异常处理**等基础设施功能。所有中间件均遵循 **"单一职责、依赖注入、资源感知"** 的核心设计理念。

### 一、 整体设计理念
1. **关注点分离**：将公共基础设施逻辑从业务代码中剥离，通过中间件管道统一处理。
2. **请求生命周期管理**：每个中间件精确控制其在请求处理链中的位置和作用时机。
3. **DI 容器集成**：通过 `get_bean_by_type()` 从容器获取依赖，支持 Mock 替换和测试。
4. **异步优先**：所有中间件基于 `async/await`，支持高并发场景。
5. **优雅降级**：关键中间件具备容错能力（如 Redis 不可用时跳过重放检查）。

### 二、 中间件分类与职责

#### 1. **认证与安全中间件**
| 中间件 | 核心职责 | 设计特点 |
|--------|----------|----------|
| **`HMACSignatureMiddleware`** (`hmac_signature_middleware.py`) | **API 签名验证与重放攻击防护**。验证请求的 HMAC-SHA256 签名，确保请求完整性和真实性。 | - **时间窗口校验**：请求时间戳与服务器时间差不得超过配置窗口（默认5分钟）。<br>- **Nonce 防重放**：通过 Redis SET NX EX 原子操作记录已使用的 Nonce。<br>- **开发环境快捷方式**：当 `ENV=dev` 时，可使用固定签名 `1234567890` 快速测试。<br>- **OpenAPI 集成**：提供 `get_hmac_openapi_security_schemes()` 生成详细的 API 文档描述。 |
| **`UserContextMiddleware`** (`user_context_middleware.py`) | **用户身份提取与上下文设置**。从请求中提取用户信息并设置到线程局部存储 (`ContextVar`) 中。 | - **分级处理**：优先尝试获取完整用户数据；失败则设置匿名用户上下文。<br>- **异常隔离**：身份提取失败不影响请求继续处理（401 除外）。<br>- **上下文清理**：在 `finally` 块中确保清理，避免跨请求污染。 |

#### 2. **业务逻辑与上下文中间件**
| 中间件 | 核心职责 | 设计特点 |
|--------|----------|----------|
| **`AppLogicMiddleware`** (`app_logic_middleware.py`) | **应用级请求生命周期管理**。调用 `AppLogicProvider` 的回调方法，实现配额检查、请求统计等业务逻辑。 | - **条件执行**：通过 `should_process_request()` 控制是否执行业务逻辑。<br>- **三阶段回调**：`validate_request()` → `on_request_begin()` → `on_request_complete()`。<br>- **异常传播**：业务逻辑异常正常抛出，由上层处理器捕获。 |
| **`DatabaseSessionMiddleware`** (`database_session_middleware.py`) | **数据库会话与事务管理**。为每个 HTTP 请求提供数据库会话，智能决定事务提交或回滚。 | - **智能提交**：请求成功时检查会话状态并提交；失败时自动回滚。<br>- **流式响应支持**：特殊处理 `StreamingResponse`，通过包装生成器延长会话生命周期。<br>- **资源安全关闭**：`_close_session_safely()` 确保连接正确归还连接池。 |

#### 3. **监控与可观测性中间件**
| 中间件 | 核心职责 | 设计特点 |
|--------|----------|----------|
| **`PrometheusMiddleware`** (`prometheus_middleware.py`) | **HTTP 请求指标自动采集**。记录请求数、延迟、请求/响应大小等 Prometheus 指标。 | - **路径规范化**：将动态路径（如 `/api/users/123`）映射为模板（`/api/users/{user_id}`）。<br>- **跳过内省端点**：自动忽略 `/metrics`、`/health` 等监控端点，避免自监控循环。<br>- **延迟测量**：使用 `time.perf_counter()` 高精度计时。 |
| **`ProfileMiddleware`** (`profile_middleware.py`) | **请求性能剖析**。基于 pyinstrument 提供代码级性能分析报告。 | - **按需触发**：通过 URL 参数 `?profile=true` 控制剖析开关。<br>- **环境变量配置**：`PROFILING_ENABLED` 控制全局启用/禁用。<br>- **优雅降级**：若 pyinstrument 未安装，自动禁用功能而不影响正常请求。 |

#### 4. **异常处理中间件**
| 中间件 | 核心职责 | 设计特点 |
|--------|----------|----------|
| **`global_exception_handler`** (`global_exception_handler.py`) | **全局异常统一格式化**。捕获所有未处理异常，返回结构化的 JSON 错误响应。 | - **分级处理**：`HTTPException` 保留原状态码和详情；其他异常统一转为 500。<br>- **日志分类**：HTTP 异常记录为 WARNING，系统异常记录为 ERROR。<br>- **标准化响应**：统一包含 `status`、`code`、`message`、`timestamp`、`path` 字段。 |
| **`sse_exception_handler`** (`sse_exception_middleware.py`) | **SSE 流异常格式转换**。将异步生成器中的异常转换为 SSE 格式的事件流。 | - **装饰器模式**：通过 `@sse_exception_handler` 包装 SSE 生成器函数。<br>- **流式错误传递**：异常被转换为 `{"type": "error", "data": {...}}` 事件，保持流不中断。<br>- **异常类型区分**：HTTP 异常保留状态码，其他异常统一为 500。 |

### 三、 核心设计模式与架构优势

#### 1. **管道与过滤器模式 (Pipeline & Filter)**
所有中间件继承 `BaseHTTPMiddleware`，通过 `dispatch()` 方法串联。每个中间件可：
- 修改请求（如设置上下文）
- 拦截响应（如性能剖析）
- 处理异常（如全局异常捕获）

#### 2. **依赖注入与可测试性**
- **容器集成**：通过 `get_bean_by_type()` 获取 `AuthProvider`、`DatabaseSessionProvider` 等依赖。
- **配置驱动**：HMAC 密钥、时间窗口、剖析开关等均支持环境变量配置。
- **易于 Mock**：DI 机制允许在测试中替换实际实现。

#### 3. **资源生命周期管理**
- **请求级资源**：数据库会话、用户上下文等严格遵循 `try-finally` 模式清理。
- **流式响应适配**：`DatabaseSessionMiddleware` 特殊处理流式传输，确保会话生命周期匹配数据生成周期。
- **连接池安全**：数据库连接、Redis 连接均通过 Provider 管理，避免泄漏。

#### 4. **生产环境就绪特性**
- **防重放攻击**：HMAC 中间件结合时间戳和 Redis 实现双重防护。
- **性能隔离**：监控中间件跳过自监控端点，避免指标失真。
- **优雅降级**：关键组件（如 Redis）不可用时，系统仍可运行（功能降级）。

#### 5. **开发者体验优化**
- **开发快捷方式**：HMAC 签名在开发环境支持固定值，便于快速测试。
- **按需剖析**：性能剖析通过 URL 参数触发，不影响生产性能。
- **详细文档**：HMAC 中间件提供完整的 OpenAPI 描述和代码示例。

### 四、 中间件执行顺序（典型）
1. **`PrometheusMiddleware`**：记录请求开始时间、大小
2. **`HMACSignatureMiddleware`**：验证 API 签名
3. **`UserContextMiddleware`**：提取并设置用户身份
4. **`AppLogicMiddleware`**：执行业务逻辑回调
5. **`DatabaseSessionMiddleware`**：提供数据库会话
6. **路由处理器**：执行业务代码
7. **`ProfileMiddleware`**：按需生成性能报告
8. **异常处理器**：捕获并格式化异常
9. **`PrometheusMiddleware`**：记录响应指标

**总结**：`middleware` 模块是 EverMemOS 实现**企业级可观测性、安全性和可维护性**的关键基础设施。通过精心设计的中间件管道，系统实现了业务逻辑与横切关注点的彻底分离，为高并发、高可用的生产环境提供了坚实基础。每个中间件都体现了 **"做一件事，并做好"** 的 Unix 哲学，共同构建了一个稳定、透明、易于扩展的 HTTP 处理层。