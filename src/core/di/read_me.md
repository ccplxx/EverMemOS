我需要分析src/core/di目录下的DI模块实现，梳理设计原理，并提供使用示例。我已经阅读了所有相关文件。现在我需要综合这些信息并提供分析。

首先，让我快速回顾一下我读取的文件内容，以便准确分析。我需要组织分析结构：1) 概述，2) 核心组件，3) 设计原理，4) 使用示例。

让我开始撰写响应。
根据对 `src/core/di` 目录的代码分析，以下是 EverMemOS 依赖注入 (DI) 模块的详细实现梳理、设计原理说明和完整使用示例。

## 1. DI 模块概述

EverMemOS 的 DI 模块是一个**类型安全、装饰器驱动、支持多作用域和模拟模式的现代依赖注入系统**。它采用 Python 3.12+ 特性，支持异步/同步依赖，提供自动组件扫描和灵活的依赖解析。

**核心设计目标**：
- **类型安全**：充分利用 Python 类型注解进行依赖声明和解析
- **零配置**：通过装饰器最小化样板代码
- **灵活性**：支持多种作用域（单例、原型、工厂）、模拟实现、条件注册
- **高性能**：使用并行扫描和高效的数据结构（前缀树）优化启动性能

## 2. 核心组件与架构

### 2.1 容器核心 (`DIContainer`)
- **位置**：`container.py`
- **职责**：Bean 注册表、依赖解析器、生命周期管理器
- **关键特性**：
  - 支持三种作用域：`SINGLETON`（默认）、`PROTOTYPE`、`FACTORY`
  - 基于类型的依赖解析，支持泛型类型
  - 模拟模式切换，便于测试
  - 线程安全的容器操作

### 2.2 Bean 定义元数据 (`BeanDefinition`)
- **位置**：`bean_definition.py`
- **数据结构**：
  ```python
  class BeanDefinition:
      bean_type: type[T]          # Bean 类型
      bean_name: str              # Bean 名称（默认为类型名）
      scope: BeanScope            # 作用域（SINGLETON/PROTOTYPE/FACTORY）
      is_primary: bool           # 是否为主要实现
      is_mock: bool              # 是否为模拟实现
      metadata: dict[str, Any]   # 自定义元数据
  ```

### 2.3 装饰器系统 (`decorators.py`)
提供多种装饰器来声明和配置 Bean：

| 装饰器 | 用途 | 默认作用域 | 默认 primary |
|--------|------|------------|--------------|
| `@component` | 通用组件 | SINGLETON | False |
| `@service` | 业务服务 | SINGLETON | False |
| `@repository` | 数据访问层 | SINGLETON | False |
| `@controller` | API 控制器 | SINGLETON | False |
| `@injectable` | 可注入类 | SINGLETON | False |
| `@mock_impl` | 模拟实现 | SINGLETON | True |
| `@factory` | 工厂 Bean | FACTORY | False |
| `@prototype` | 原型 Bean | PROTOTYPE | False |

### 2.4 组件扫描器 (`ComponentScanner`)
- **位置**：`scanner.py`
- **功能**：自动扫描指定目录，发现带装饰器的类并注册到容器
- **优化**：支持并行扫描，使用 `ScanContextRegistry` 管理路径条件

### 2.5 Bean 排序策略 (`BeanOrderStrategy`)
- **位置**：`bean_order_strategy.py`
- **算法**：当多个 Bean 实现同一接口时，按以下优先级选择：
  1. 模拟状态匹配当前容器模式（`mock_mode`）
  2. 直接类型匹配优于子类匹配
  3. `is_primary=True` 的 Bean
  4. `SINGLETON` 优于 `PROTOTYPE`/`FACTORY`
  5. 注册顺序（后注册的优先）

### 2.6 扫描上下文注册表 (`ScanContextRegistry`)
- **位置**：`scan_context.py`
- **数据结构**：前缀树（Trie）存储路径到元数据的映射
- **用途**：支持条件 Bean 注册（如根据文件路径决定是否注册）

## 3. 设计原理

### 3.1 类型驱动的依赖解析
```python
# 依赖通过类型注解声明
class UserService:
    def __init__(self, user_repo: UserRepository, logger: Logger):
        self.user_repo = user_repo
        self.logger = logger
```
容器自动分析构造函数参数的类型注解，递归解析依赖图。

### 3.2 装饰器元编程
装饰器在类定义时收集元数据，存储到 `__bean_metadata__` 类属性中：
```python
def component(bean_name: str | None = None, is_primary: bool = False):
    def decorator(cls: type[T]) -> type[T]:
        setattr(cls, "__bean_metadata__", {
            "bean_type": cls,
            "bean_name": bean_name or cls.__name__,
            "is_primary": is_primary,
            # ... 其他元数据
        })
        return cls
    return decorator
```

### 3.3 多作用域策略
- **SINGLETON**：容器范围内单实例，支持懒加载
- **PROTOTYPE**：每次获取时创建新实例
- **FACTORY**：通过工厂函数创建实例，支持复杂初始化逻辑

### 3.4 模拟模式与测试支持
通过 `@mock_impl` 装饰器声明模拟实现，运行时可通过 `container.set_mock_mode(True)` 切换：
```python
@mock_impl
class MockUserRepository(UserRepository):
    """测试用的模拟实现"""
```

### 3.5 并行扫描优化
组件扫描使用 `concurrent.futures` 实现并行文件系统遍历，显著提升大型项目的启动速度。

## 4. 完整使用示例

### 示例 1：基础服务层依赖注入

**场景**：用户管理模块，包含服务层、仓库层和工具类。

#### 4.1.1 定义领域模型和接口
```python
# src/user/domain.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    id: str
    username: str
    email: str
    created_at: datetime
    updated_at: datetime

# src/user/repository.py
from abc import ABC, abstractmethod
from typing import Optional

class UserRepository(ABC):
    """用户仓库接口"""
    
    @abstractmethod
    async def find_by_id(self, user_id: str) -> Optional[User]:
        pass
    
    @abstractmethod
    async def save(self, user: User) -> User:
        pass
    
    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        pass
```

#### 4.1.2 实现具体组件
```python
# src/user/infrastructure/mongodb_user_repository.py
from src.core.di import repository
from src.user.repository import UserRepository
from src.user.domain import User
import motor.motor_asyncio
from typing import Optional

@repository
class MongoDBUserRepository(UserRepository):
    """MongoDB 用户仓库实现"""
    
    def __init__(self, mongo_client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = mongo_client
        self.db = self.client.get_database("app_db")
        self.collection = self.db.users
    
    async def find_by_id(self, user_id: str) -> Optional[User]:
        doc = await self.collection.find_one({"_id": user_id})
        return self._to_user(doc) if doc else None
    
    async def save(self, user: User) -> User:
        doc = {
            "_id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        await self.collection.update_one(
            {"_id": user.id},
            {"$set": doc},
            upsert=True
        )
        return user
    
    async def find_by_email(self, email: str) -> Optional[User]:
        doc = await self.collection.find_one({"email": email})
        return self._to_user(doc) if doc else None
    
    def _to_user(self, doc: dict) -> User:
        return User(
            id=doc["_id"],
            username=doc["username"],
            email=doc["email"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"]
        )
```

```python
# src/user/service.py
from src.core.di import service, inject
from src.user.repository import UserRepository
from src.user.domain import User
from datetime import datetime
import uuid
from typing import Optional

@service
class UserService:
    """用户服务"""
    
    def __init__(
        self,
        user_repo: UserRepository,
        # 支持多个依赖注入
        logger: "Logger" = inject("app_logger")
    ):
        self.user_repo = user_repo
        self.logger = logger
    
    async def register_user(self, username: str, email: str) -> User:
        """注册新用户"""
        # 检查邮箱是否已存在
        existing = await self.user_repo.find_by_email(email)
        if existing:
            raise ValueError(f"邮箱 {email} 已被注册")
        
        # 创建用户
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 保存到数据库
        saved_user = await self.user_repo.save(user)
        
        self.logger.info(f"用户注册成功: {saved_user.username} ({saved_user.email})")
        return saved_user
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """获取用户信息"""
        return await self.user_repo.find_by_id(user_id)
```

#### 4.1.3 配置和基础设施组件
```python
# src/infrastructure/database.py
from src.core.di import component
import motor.motor_asyncio

@component("mongo_client")
def create_mongo_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    """创建 MongoDB 客户端（工厂 Bean）"""
    return motor.motor_asyncio.AsyncIOMotorClient(
        "mongodb://localhost:27017",
        maxPoolSize=10,
        minPoolSize=1
    )

# src/infrastructure/logging.py
import logging
from src.core.di import component

@component("app_logger")
def create_logger() -> logging.Logger:
    """创建应用日志器（工厂 Bean）"""
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger
```

#### 4.1.4 应用启动和依赖解析
```python
# src/main.py
import asyncio
from src.core.di import DIContainer, scan_components
from src.user.service import UserService

async def main():
    # 创建容器
    container = DIContainer()
    
    # 方式1：手动注册（适用于测试或特殊场景）
    # container.register_bean(MongoDBUserRepository)
    # container.register_bean(UserService)
    
    # 方式2：自动扫描（推荐生产环境）
    await scan_components(
        container,
        scan_paths=["src/user", "src/infrastructure"],
        base_package="src"
    )
    
    # 获取服务实例（依赖自动解析）
    user_service = await container.get_bean(UserService)
    
    # 使用服务
    try:
        new_user = await user_service.register_user(
            username="john_doe",
            email="john@example.com"
        )
        print(f"注册成功: {new_user.username}")
        
        # 查询用户
        user = await user_service.get_user(new_user.id)
        print(f"查询结果: {user.username if user else '未找到'}")
    except ValueError as e:
        print(f"错误: {e}")
    
    # 容器统计
    stats = container.get_stats()
    print(f"容器统计: {stats}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 2：模拟模式与测试

#### 4.2.1 定义模拟实现
```python
# tests/mocks/mock_user_repository.py
from src.core.di import mock_impl
from src.user.repository import UserRepository
from src.user.domain import User
from datetime import datetime
from typing import Optional, Dict
import uuid

@mock_impl
class MockUserRepository(UserRepository):
    """用于测试的模拟用户仓库"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
    
    async def find_by_id(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)
    
    async def save(self, user: User) -> User:
        self.users[user.id] = user
        return user
    
    async def find_by_email(self, email: str) -> Optional[User]:
        for user in self.users.values():
            if user.email == email:
                return user
        return None
    
    def add_test_user(self, username: str, email: str) -> User:
        """测试辅助方法"""
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.users[user.id] = user
        return user
```

#### 4.2.2 单元测试
```python
# tests/test_user_service.py
import pytest
import asyncio
from src.core.di import DIContainer, scan_components
from src.user.service import UserService
from tests.mocks.mock_user_repository import MockUserRepository

@pytest.fixture
async def container():
    """测试容器 fixture"""
    container = DIContainer()
    container.set_mock_mode(True)  # 启用模拟模式
    
    # 扫描测试组件
    await scan_components(
        container,
        scan_paths=["src/user", "tests/mocks"],
        base_package="src"
    )
    
    return container

@pytest.mark.asyncio
async def test_register_user(container):
    """测试用户注册"""
    # 获取服务（会自动注入 UserService
    user_service = await container.get_bean(UserService)
    
    # 注册用户
    user = await user_service.register_user("test_user", "test@example.com")
    
    assert user.username == "test_user"
    assert user.email == "test@example.com"
    assert user.id is not None
    
    # 验证用户已保存（通过模拟仓库）
    mock_repo = await container.get_bean(MockUserRepository)
    saved_user = await mock_repo.find_by_id(user.id)
    assert saved_user is not None
    assert saved_user.username == user.username

@pytest.mark.asyncio
async def test_register_duplicate_email(container):
    """测试重复邮箱注册"""
    user_service = await container.get_bean(UserService)
    mock_repo = await container.get_bean(MockUserRepository)
    
    # 添加测试用户
    mock_repo.add_test_user("existing_user", "duplicate@example.com")
    
    # 尝试用相同邮箱注册
    with pytest.raises(ValueError, match="邮箱 duplicate@example.com 已被注册"):
        await user_service.register_user("new_user", "duplicate@example.com")

@pytest.mark.asyncio
async def test_get_user(container):
    """测试获取用户"""
    user_service = await container.get_bean(UserService)
    mock_repo = await container.get_bean(MockUserRepository)
    
    # 准备测试数据
    test_user = mock_repo.add_test_user("test", "test@example.com")
    
    # 获取用户
    user = await user_service.get_user(test_user.id)
    assert user is not None
    assert user.id == test_user.id
    
    # 获取不存在的用户
    user = await user_service.get_user("non_existent_id")
    assert user is None

# 测试模拟模式切换
@pytest.mark.asyncio
async def test_mock_mode_switch():
    """测试模拟模式切换"""
    container = DIContainer()
    
    # 注册真实实现和模拟实现
    from src.user.infrastructure.mongodb_user_repository import MongoDBUserRepository
    from tests.mocks.mock_user_repository import MockUserRepository
    
    container.register_bean(MongoDBUserRepository)
    container.register_bean(MockUserRepository)
    
    # 默认模式（模拟模式关闭）-> 应返回真实实现
    container.set_mock_mode(False)
    repo1 = await container.get_bean(UserRepository)
    assert isinstance(repo1, MongoDBUserRepository)
    
    # 开启模拟模式 -> 应返回模拟实现
    container.set_mock_mode(True)
    repo2 = await container.get_bean(UserRepository)
    assert isinstance(repo2, MockUserRepository)
    
    # 切换回真实模式
    container.set_mock_mode(False)
    repo3 = await container.get_bean(UserRepository)
    assert isinstance(repo3, MongoDBUserRepository)
```

#### 4.2.3 集成测试
```python
# tests/integration/test_user_flow.py
import pytest
import asyncio
from src.core.di import DIContainer
from src.user.service import UserService
from src.user.infrastructure.mongodb_user_repository import MongoDBUserRepository
from src.infrastructure.database import create_mongo_client
from src.infrastructure.logging import create_logger

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_database_integration():
    """真实数据库集成测试"""
    # 创建容器并注册真实组件
    container = DIContainer()
    
    # 注册工厂 Bean
    container.register_factory_bean("mongo_client", create_mongo_client)
    container.register_factory_bean("app_logger", create_logger)
    
    # 注册其他组件
    container.register_bean(MongoDBUserRepository)
    container.register_bean(UserService)
    
    # 获取服务
    user_service = await container.get_bean(UserService)
    
    # 执行真实操作（需要 MongoDB 运行）
    try:
        user = await user_service.register_user(
            username="integration_test",
            email="integration@example.com"
        )
        
        assert user.username == "integration_test"
        
        # 清理测试数据
        mongo_client = await container.get_bean("mongo_client")
        db = mongo_client.get_database("app_db")
        await db.users.delete_one({"_id": user.id})
        
    except Exception as e:
        pytest.skip(f"集成测试跳过: {e}")
```

## 5. 最佳实践

### 5.1 Bean 命名规范
```python
# 明确命名 Bean，便于调试
@component("email_service")
class EmailService:
    pass

# 接口实现使用描述性名称
@repository("postgres_user_repo")
class PostgresUserRepository(UserRepository):
    pass

@mock_impl("mock_user_repo")
class MockUserRepository(UserRepository):
    pass
```

### 5.2 作用域选择指南
- **SINGLETON**：无状态服务、工具类、配置对象（默认）
- **PROTOTYPE**：有状态对象、请求上下文、线程不安全对象
- **FACTORY**：复杂初始化、需要参数的对象、第三方库适配器

### 5.3 循环依赖处理
```python
# 方案1：使用属性注入
class ServiceA:
    def __init__(self):
        self.service_b: Optional[ServiceB] = None
    
    @inject("service_b")
    def set_service_b(self, service_b: ServiceB):
        self.service_b = service_b

class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a

# 方案2：重新设计（推荐）
# 提取公共逻辑到第三个类，或使用事件驱动
```

### 5.4 性能优化
```python
# 1. 限制扫描范围
await scan_components(
    container,
    scan_paths=["src/user", "src/product"],  # 只扫描必要目录
    base_package="src"
)

# 2. 使用并行扫描（默认启用）
scanner = ComponentScanner(parallel=True, max_workers=4)

# 3. 懒加载单例
@component(lazy=True)
class HeavyService:
    """只在首次使用时初始化"""
    def __init__(self):
        # 耗时的初始化操作
        time.sleep(5)
```

## 6. 总结

EverMemOS 的 DI 模块通过以下设计实现了一个强大而灵活的依赖注入系统：

1. **类型安全第一**：充分利用 Python 类型系统，提供编译时依赖检查
2. **装饰器驱动**：最小化配置代码，声明式编程风格
3. **多作用域支持**：适应不同场景的生命周期需求
4. **测试友好**：内置模拟模式和条件注册，简化测试编写
5. **高性能优化**：并行扫描和高效数据结构保障启动速度

该模块完美支持 EverMemOS 的**多层架构**（API层、服务层、业务层、代理层、内存层、核心层、基础设施层），为各层间的松耦合和可测试性提供了坚实基础。