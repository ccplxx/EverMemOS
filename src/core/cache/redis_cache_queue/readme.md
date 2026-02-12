用户要求梳理 `src\core\cache\redis_cache_queue` 文件夹下的代码，并说明设计思路。我需要先查看该文件夹的内容。从项目布局看，这是核心缓存模块下的Redis缓存队列。我先列出该文件夹的文件。使用 list_files 工具。传入绝对路径：d:\open_code\EverMemOS\src\core\cache\redis_cache_queue。深度设为1，偏移0，限制200。
现在我需要读取这些文件的内容来理解其设计思路。首先读取 __init__.py，然后读取其他三个文件。由于文件可能较长，我会一次性读取所有内容。使用 read_file 工具并行读取。
现在我已经读取了所有四个文件。__init__.py 可能为空或包含导入。我需要检查一下。从之前读取的结果看，__init__.py 显示为0字节，可能是空的。不过我还是再确认一下。使用 read_file 工具读取 __init__.py 的内容。
看起来是空的。现在我已经有了所有文件的内容。接下来我需要梳理代码并说明设计思路。这个模块似乎是关于Redis缓存队列的，包含两个主要管理器：长度限制缓存管理器（redis_length_cache_manager）和时间窗口缓存管理器（redis_windows_cache_manager），以及一个数据处理器（redis_data_processor）。我需要分析它们的设计思路、职责和交互。

我将从整体架构、每个文件的功能、关键设计模式、数据流、错误处理等方面进行梳理。用中文回答，因为用户之前使用中文。开始组织答案。

首先，概述整个模块的职责：提供基于Redis的有序队列缓存，支持长度限制和时间窗口两种管理策略，以及统一的数据序列化/反序列化。

然后，分别分析每个文件：
1. `redis_data_processor.py`：数据处理器，负责序列化/反序列化，支持JSON和Pickle，添加唯一ID。
2. `redis_length_cache_manager.py`：长度限制缓存管理器，使用Redis有序集合（ZSET），按时间戳排序，限制最大长度，概率性清理。
3. `redis_windows_cache_manager.py`：时间窗口缓存管理器，同样使用ZSET，按时间戳排序，支持过期时间和随机清理过期数据。
4. `__init__.py`：空文件。

接着，说明设计思路：
- 使用工厂模式创建管理器实例（`RedisLengthCacheFactory`、`RedisWindowsCacheFactory`）。
- 使用组件装饰器（`@component`）实现依赖注入。
- 使用Lua脚本保证原子操作（长度清理、范围查询）。
- 概率性清理（cleanup_probability）减少性能开销。
- 数据唯一性通过UUID前缀保证。
- 支持多种数据类型（字符串、字典、列表等）的序列化。
- 错误处理和日志记录。

最后，总结模块的亮点和适用场景。

现在生成回答。
## `src\core\cache\redis_cache_queue` 模块设计思路梳理

### 一、模块整体定位与职责

该模块是 EverMemOS 核心缓存层的**Redis有序队列缓存组件**，为上层业务提供两种基于时间序列的缓存策略：

1.  **长度限制队列**：固定容量，先进先出（按时间），自动清理最早数据。
2.  **时间窗口队列**：固定时间窗口，自动清理过期数据。

两种策略均基于 Redis 的 **Sorted Set (ZSET)** 实现，将时间戳作为 Score，实现了高效的时间范围查询和数据管理。

---

### 二、核心文件与功能划分

| 文件 | 核心类 | 职责 | 设计模式 |
|------|--------|------|----------|
| `redis_data_processor.py` | `RedisDataProcessor` | **统一数据序列化/反序列化**：支持 JSON（首选）和 Pickle（备选），为每条数据附加唯一ID，处理 Redis 二进制/字符串兼容性。 | 工具类（静态方法） |
| `redis_length_cache_manager.py` | `RedisLengthCacheFactory`<br>`RedisLengthCacheManager`<br>`DefaultRedisLengthCacheManager` | **长度限制队列管理**：创建、追加、按时间范围查询、长度超限清理、队列统计。 | **工厂模式** + **组件化**（`@component`） |
| `redis_windows_cache_manager.py` | `RedisWindowsCacheFactory`<br>`RedisWindowsCacheManager`<br>`DefaultRedisWindowsCacheManager` | **时间窗口队列管理**：创建、追加、按时间范围查询、过期数据清理、队列统计。 | **工厂模式** + **组件化**（`@component`） |

---

### 三、详细设计思路解析

#### 1. **数据层：统一序列化与唯一性保障 (`RedisDataProcessor`)**

**设计目标**：屏蔽 Redis 存储的细节，让上层业务可以透明地存储任意 Python 对象。

- **序列化策略**：
  - **首选 JSON**（人类可读、跨语言、性能好）
  - **备选 Pickle**（当 JSON 无法序列化复杂对象时自动切换，并添加二进制标记 `PICKLE_MARKER`）
- **数据唯一性**：
  - 每条存储的数据都会附加一个**缩短的 UUID** 前缀（格式：`{uuid}:{data}`）
  - 避免 Sorted Set 中因完全相同的 data 导致成员覆盖
- **客户端兼容**：
  - 同时处理 `decode_responses=True`（返回字符串）和 `=False`（返回字节）两种 Redis 客户端配置
  - 自动检测数据格式并选择正确的反序列化方法

#### 2. **核心架构：工厂模式与组件化**

两类管理器都采用相同的架构模式：

```
Factory（工厂）
    ├── 负责 Lua 脚本的一次性注册（避免重复编译）
    ├── 根据配置参数创建 Manager 实例
    └── 通过 `@component` 注册到 DI 容器
Manager（管理器）
    ├── 实现具体的业务逻辑（append、query、cleanup）
    ├── 持有 Redis 连接和 Lua 脚本引用
    └── 通过 `@component` 提供默认实例（向后兼容）
```

**优势**：
- **解耦**：工厂负责初始化，管理器负责业务，职责清晰。
- **性能优化**：Lua 脚本在工厂中一次性注册，后续直接调用，减少网络传输。
- **依赖注入**：通过 `@component` 装饰器，管理器可以轻松被其他组件注入使用。

#### 3. **长度限制队列 (`RedisLengthCacheManager`)**

**核心设计**：用 Sorted Set 实现一个**固定容量的时间序列队列**。

- **容量控制**：
  - `max_length`：队列最大长度（默认 100）
  - `cleanup_probability`：每次追加数据时，以 **10% 的概率**触发长度清理
  - **Lua 脚本原子清理**：`ZREMRANGEBYRANK` 删除最早（Score 最小）的超额数据
- **过期时间**：
  - `expire_minutes`：队列整体 TTL（默认 60 分钟），每次追加都会刷新
- **时间范围查询**：
  - 使用 Lua 脚本 `ZRANGEBYSCORE` 高效获取指定时间范围内的数据
  - 返回结果包含原始数据、时间戳、格式化时间

**适用场景**：需要保留**最近 N 条**时间序列数据的场景，如用户最近操作、API 调用日志。

#### 4. **时间窗口队列 (`RedisWindowsCacheManager`)**

**核心设计**：用 Sorted Set 实现一个**滑动时间窗口队列**。

- **时间窗口**：
  - `expire_minutes`：数据过期时间（默认 10 分钟）
  - `cleanup_probability`：每次追加数据时，以 **10% 的概率**触发过期数据清理
  - **清理阈值**：`DEFAULT_CLEANUP_MULTIPLIER=2`，清理早于 `2 * expire_minutes` 的数据（提供缓冲）
- **原子操作**：
  - 使用 Redis Pipeline 保证 `ZADD` 和 `EXPIRE` 的原子性
- **时间范围查询**：
  - 与长度限制队列共享相同的 Lua 脚本，实现高效查询

**适用场景**：需要**按时间窗口**统计或查询的场景，如最近1小时的错误日志、实时监控数据。

#### 5. **性能与原子性优化：Lua 脚本**

两个管理器都重度使用 Lua 脚本保证复杂操作的**原子性**：

- **`LENGTH_CLEANUP_LUA_SCRIPT`**：检查队列长度，如果超限则删除最早的数据。
- **`FETCH_BY_DATE_TIMESTAMP_RANGE_LUA_SCRIPT`**：按 Score（时间戳）范围查询数据，并返回 Score。

**优势**：
- **原子性**：避免在查询和删除之间发生数据竞争。
- **减少网络往返**：多个 Redis 操作在服务器端一次性执行。
- **性能**：脚本在 Redis 中编译缓存，后续执行更快。

#### 6. **清理策略：概率性清理与手动清理**

- **概率性清理**：
  - 默认 `cleanup_probability=0.1`，即 10% 的概率触发清理
  - **避免每次操作都清理**，平衡性能与内存控制
- **手动清理**：
  - 提供 `cleanup_excess()`（长度队列）和 `cleanup_expired()`（时间窗口）方法
  - 供外部系统在需要时主动触发

#### 7. **错误处理与可观测性**

- **异常捕获**：所有 Redis 操作都包裹在 try-catch 中，避免单点故障影响主流程。
- **详细日志**：使用 `core.observation.logger` 记录关键操作、错误和调试信息。
- **优雅降级**：当 Redis 操作失败时，返回默认值（如空列表、False）而非抛出异常。

#### 8. **向后兼容设计**

每个模块都提供了一个 `DefaultRedis*CacheManager` 类：
- 通过 `@component` 注册为默认组件
- **懒加载**真正的管理器实例
- 对外提供完全相同的接口，确保现有代码无需修改即可使用

---

### 四、数据流示例

#### 长度限制队列追加数据：
```
业务数据 → RedisDataProcessor.serialize_data() → 添加 UUID 前缀 → ZADD 到 Sorted Set (Score=时间戳)
      → EXPIRE 刷新 TTL → 10% 概率触发 Lua 脚本长度清理
```

#### 时间窗口队列查询：
```
指定时间范围 → 转换为毫秒时间戳 → Lua 脚本 ZRANGEBYSCORE → 解析结果（数据+Score）
      → RedisDataProcessor.deserialize_data() → 返回结构化数据列表
```

---

### 五、设计亮点总结

1.  **策略分离**：长度限制 vs 时间窗口，满足不同业务场景。
2.  **原子性保障**：关键操作通过 Lua 脚本实现，避免竞态条件。
3.  **性能优化**：概率性清理减少不必要的 Redis 操作；Lua 脚本减少网络往返。
4.  **数据兼容**：统一数据处理器支持任意 Python 对象，透明处理序列化。
5.  **可观测性**：详细日志和队列统计方法，便于监控和调试。
6.  **开箱即用**：通过 `@component` 集成到 DI 容器，易于注入使用。
7.  **健壮性**：全面的错误处理，Redis 故障不影响主流程。

该模块是 EverMemOS 中**时间序列数据缓存**的核心基础设施，设计上兼顾了功能性、性能、可靠性和易用性。