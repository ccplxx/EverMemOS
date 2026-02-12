用户要求梳理 `src\core\authorize` 文件夹下代码的设计思路。我需要先探索这个目录的结构和内容。使用 list_files 工具查看目录。同时，考虑到用户可能已经打开了 `enums.py` 文件，我应该也读取它。为了全面了解，我应该并行读取所有文件的内容。但首先要知道有哪些文件。调用 list_files 获取目录结构。
现在有5个文件：`__init__.py`、`decorators.py`、`enums.py`、`interfaces.py`、`strategies.py`。我应该并行读取所有文件以了解整个授权模块的设计思路。使用 read_file 工具。
现在我已经读取了所有文件。我需要梳理设计思路，并总结给用户。这个授权模块看起来是一个基于角色的授权系统，支持策略模式。让我分析每个文件：

1. **`__init__.py`**：暴露了模块的公共接口，包括枚举、接口、策略实现和装饰器。

2. **`enums.py`**：定义了 `Role` 枚举，包含 `ANONYMOUS`、`USER`、`ADMIN`、`SIGNATURE`。

3. **`interfaces.py`**：定义了抽象基类 `AuthorizationStrategy` 和上下文类 `AuthorizationContext`。`AuthorizationStrategy` 有一个抽象方法 `check_permission`。

4. **`strategies.py`**：提供了三个具体的策略实现：
   - `DefaultAuthorizationStrategy`：默认的权限检查逻辑，基于角色进行简单比较。
   - `RoleBasedAuthorizationStrategy`：基于角色层级的策略，定义了角色的层次结构（数值级别），用户级别必须大于等于所需级别。
   - `CustomAuthorizationStrategy`：允许用户传入自定义检查函数，支持同步和异步函数。

5. **`decorators.py`**：提供了装饰器函数，用于将授权逻辑应用到函数或方法上。主要装饰器是 `authorize`，它创建 `AuthorizationContext` 并附加到函数上。还提供了便捷装饰器：`require_anonymous`、`require_user`、`require_admin`、`require_signature` 和 `custom_authorize`。此外，`check_and_apply_default_auth` 用于检查是否已存在授权装饰器，如果没有则应用默认的 `require_user`。

设计思路：
- **基于策略模式**：授权逻辑可以通过不同的 `AuthorizationStrategy` 实现来定制。
- **装饰器驱动**：通过装饰器将授权逻辑非侵入式地应用到业务函数上。
- **角色基础**：使用 `Role` 枚举定义权限级别。
- **上下文管理**：`AuthorizationContext` 封装了授权检查所需的所有信息。
- **灵活扩展**：支持自定义策略和检查函数。
- **异步友好**：支持异步函数和同步函数，内部处理事件循环。
- **默认安全**：提供默认的 `require_user` 授权，确保未明确授权的端点默认需要用户登录。

现在我需要组织一个清晰的回答。应该先概述模块的整体目标，然后分部分说明每个组件的职责和设计思路，最后总结设计原则和优势。用中文回答。现在开始撰写。
## `src\core\authorize` 模块设计思路梳理

该模块是EverMemOS的**授权 (Authorization) 核心**，实现了基于策略模式的、可插拔的授权系统，支持角色控制、自定义策略，并通过装饰器提供简洁的API。

### 一、 整体设计目标
- **职责分离**：将权限检查逻辑从业务代码中解耦，独立为可配置的策略。
- **灵活扩展**：支持多种授权策略（默认、基于角色、自定义），并允许运行时切换。
- **最小侵入**：通过装饰器（Decorator）模式，在不修改函数签名和内部逻辑的情况下添加权限控制。
- **异步友好**：同时支持同步与异步函数，内部正确处理事件循环。
- **默认安全**：提供便捷的默认授权，确保未明确配置的端点默认需要用户登录。

### 二、 核心组件与职责

#### 1. **枚举定义 (`enums.py`)**
- `Role` 枚举：定义了系统的四个基础角色
  - `ANONYMOUS`：匿名用户（最低权限）
  - `USER`：普通登录用户
  - `ADMIN`：管理员
  - `SIGNATURE`：HMAC签名验证用户（特殊权限）

#### 2. **接口抽象 (`interfaces.py`)**
采用**策略模式 (Strategy Pattern)** 进行抽象：
- `AuthorizationStrategy` (抽象基类)
  - 核心方法：`async def check_permission(user_info, required_role, **kwargs) -> bool`
  - **作用**：定义统一的权限检查接口，任何具体策略都必须实现此方法。
- `AuthorizationContext`
  - **作用**：封装单次授权检查所需的全部上下文信息。
  - **包含**：用户信息、所需角色、使用的策略实例、额外参数。
  - **方法**：`need_auth()` 判断当前请求是否需要授权（非匿名角色即需要）。

#### 3. **策略实现 (`strategies.py`)**
提供了三种开箱即用的策略，均实现 `AuthorizationStrategy` 接口：

| 策略类 | 设计思路 | 核心逻辑 |
|--------|----------|----------|
| `DefaultAuthorizationStrategy` | **硬编码的角色比较** | 直接比较用户角色与所需角色：USER可访问USER/ADMIN资源；ADMIN仅限ADMIN；SIGNATURE仅限SIGNATURE。 |
| `RoleBasedAuthorizationStrategy` | **角色层级模型** | 为每个角色分配数值“层级”，用户层级≥所需层级即通过。例如：ANONYMOUS(0), USER(1), ADMIN(2), SIGNATURE(1)。 |
| `CustomAuthorizationStrategy` | **完全自定义逻辑** | 接受一个用户提供的检查函数（可同步/异步），将其包装为标准策略接口，提供最大灵活性。 |

#### 4. **装饰器层 (`decorators.py`)**
**核心设计**：通过装饰器将授权逻辑“织入”业务函数，实现声明式权限控制。

- **主装饰器 `authorize`**
  - **输入**：`required_role` (默认ANONYMOUS)、`strategy` (可选，默认使用 `DefaultAuthorizationStrategy`)。
  - **机制**：
    1. 创建 `AuthorizationContext` 对象。
    2. 通过 `setattr` 将其附加到被装饰函数的 `__authorization_context__` 属性上。
    3. 根据原函数是同步/异步，返回对应的包装器 (`async_wrapper` / `sync_wrapper`)。
  - **执行时**：包装器从线程局部存储 (`get_current_user_info()`) 获取用户信息，调用策略的 `check_permission` 方法。失败则抛出 `HTTPException(403)`。

- **便捷装饰器** (语法糖)
  - `require_anonymous`、`require_user`、`require_admin`、`require_signature`：预设了对应的`required_role`。
  - `custom_authorize`：预设了自定义策略。

- **智能默认授权 `check_and_apply_default_auth`**
  - **设计巧思**：检查函数是否已有授权上下文 (`__authorization_context__`)。
  - **若没有**，则自动应用 `require_user` 装饰器，实现“默认安全”。
  - **特殊处理**：能正确识别并处理**绑定方法 (bound method)**，避免装饰器在类实例方法上失效的问题。

### 三、 设计原则与架构优势

1. **开闭原则 (Open/Closed Principle)**
   - 系统对扩展开放：新增授权策略只需实现 `AuthorizationStrategy` 接口。
   - 对修改封闭：业务函数无需修改即可接入新的授权逻辑。

2. **单一职责原则 (Single Responsibility Principle)**
   - 策略类只负责权限验证逻辑。
   - 装饰器只负责权限逻辑的“织入”和执行。
   - 上下文类只负责数据的封装和传递。

3. **依赖倒置原则 (Dependency Inversion Principle)**
   - 高层模块（装饰器、业务代码）依赖抽象的 `AuthorizationStrategy`，而非具体策略实现。
   - 具体策略的切换不影响高层模块。

4. **可测试性**
   - 策略类可独立进行单元测试。
   - 可通过 `CustomAuthorizationStrategy` 注入Mock函数进行集成测试。

5. **生产环境友好**
   - **默认安全**：通过 `check_and_apply_default_auth` 避免因疏忽导致未授权访问。
   - **灵活配置**：可根据不同环境（开发、测试、生产）切换或组合策略。
   - **细粒度控制**：支持通过 `**kwargs` 向策略传递任意上下文参数（如资源ID、操作类型）。

### 四、 典型使用示例
```python
from core.authorize import require_user, require_admin, custom_authorize
from core.authorize.strategies import RoleBasedAuthorizationStrategy

# 1. 基本角色控制
@require_user
async def user_only_endpoint(): ...

@require_admin  
async def admin_only_endpoint(): ...

# 2. 自定义策略
def my_custom_check(user_info, required_role, resource_id):
    # 复杂业务逻辑
    return user_info.get('department') == 'IT'

@custom_authorize(CustomAuthorizationStrategy(my_custom_check), resource_id=123)
async def complex_auth_endpoint(): ...

# 3. 自动应用默认授权（适用于控制器方法）
# 在框架层调用 check_and_apply_default_auth 确保所有端点都有基本保护
```

**总结**：`authorize` 模块是一个设计精良、符合现代软件工程原则的授权框架。它通过策略模式实现逻辑可插拔，通过装饰器实现声明式配置，通过智能默认机制保障安全性，为EverMemOS提供了强大而灵活的权限控制基础。