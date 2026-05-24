Repo-Agent 的操作规范。本文件的优先级高于通用编程习惯。
所有规则以"唯一正确做法"形式给出——不提供备选，不需要判断。

## 运行时与工具链

- Python **3.12**，不得使用 3.12 前引入的 workaround（如手写 `TypeAlias`）
- 包管理：`uv`（`uv add`、`uv run`、`uv sync`）
- 格式化 + lint：`ruff check --fix && ruff format`（单一工具，不引入 black/flake8/isort）
- 类型检查：`pyright --pythonversion 3.12`（strict mode，不用 mypy）
- 测试：`pytest -x --tb=short`

在提交任何变更前必须按顺序通过：
```bash
ruff check --fix .
ruff format .
pyright .
pytest -x --tb=short
```

---

## 语言规则：只有一种写法

### 类型标注

- **所有**函数签名必须有完整类型标注，包括返回值。`-> None` 不可省略。
- 用 `type` 关键字定义类型别名（3.12 原生语法）：
  ```python
  type UserId = int
  type Callback[T] = Callable[[T], None]
  ```
- 容器类型用内置泛型（`list[str]`、`dict[str, int]`），不用 `List`/`Dict`。
- `X | None` 替代 `Optional[X]`，`X | Y` 替代 `Union[X, Y]`。
- 禁止 `Any`。确实无法确定类型时用 `object` 并加注释说明原因。

### 数据结构

- **结构化数据一律用 `pydantic.BaseModel`**（不用 `dataclass`、不用 `TypedDict`、不用裸 `dict`）。
- `pydantic` model 必须启用：
  ```python
  model_config = ConfigDict(frozen=True, strict=True)
  ```
- 模型字段不得有默认值为 `None` 的非 Optional 字段。

### 控制流

- 分支匹配用 `match`，不用 if-elif 链（超过 2 个分支时强制）：
  ```python
  match result:
      case Ok(value):
          ...
      case Err(code, msg):
          ...
  ```
- 禁止裸 `except:`，禁止 `except Exception as e: pass`。

### 导入

- 标准库 → 第三方 → 本地，三组之间空一行。
- 禁止 `from module import *`。
- 禁止循环导入；如发生，通过拆包或 `TYPE_CHECKING` 块解决。

---

## 错误处理：结构化事实，而非消息字符串

所有业务错误继承统一基类，携带机器可读字段：

```python
from enum import StrEnum
from pydantic import BaseModel

class ErrorCode(StrEnum):
    NOT_FOUND       = "NOT_FOUND"
    VALIDATION      = "VALIDATION"
    PERMISSION      = "PERMISSION"
    EXTERNAL        = "EXTERNAL"

class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        context: dict[str, object] | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.context = context or {}
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, object]:
        return {
            "error": self.code,
            "message": self.message,
            "context": self.context,
            **({"suggestion": self.suggestion} if self.suggestion else {}),
        }
```

规则：
- 不得 `raise Exception("something went wrong")`，必须 `raise AppError(ErrorCode.X, ...)`。
- `context` 字段放所有定位问题需要的变量（文件路径、入参值、外部响应摘要）。
- `suggestion` 字段写 agent 可以直接执行的修复动作，不写"请检查……"。

---

## CLI 工具：机器优先输出

所有 CLI 入口必须支持 `--json` flag，输出到 stdout，stderr 保持人类可读：

```python
import json, sys

def print_result(data: object, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=None))
    else:
        # human-readable fallback
        ...

def print_error(err: AppError, *, as_json: bool) -> None:
    payload = err.to_dict()
    if as_json:
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    else:
        print(f"[{err.code}] {err.message}", file=sys.stderr)
    sys.exit(1)
```

Exit code 规范：
- `0` = 成功
- `1` = 业务错误（AppError）
- `2` = 参数错误（argparse 默认行为）
- `3` = 外部依赖不可用

---

## 日志：结构化，可过滤

使用 `structlog`，禁止 `print()` 和 `logging.info("string %s", x)`：

```python
import structlog

log = structlog.get_logger()

log.info("task_started", task_id=task_id, input_size=len(data))
log.error("fetch_failed", url=url, status=resp.status_code, error=str(e))
```

每条日志必须有：
- 事件名（`snake_case` 动词+名词）
- 所有定位该事件所需的 key-value（不依赖上下文推断）

---

## 测试：规格，而非验证

测试文件命名：`test_<module>.py`，函数命名：`test_<行为>_<条件>_<预期结果>`。

```python
def test_create_user_with_duplicate_email_raises_validation_error() -> None:
    ...
```

规则：
- 每个测试只断言一个行为。
- 禁止 `assert result is not None`——断言具体值或具体异常类型。
- 错误路径测试必须同时断言 `ErrorCode` 和 `context` 的关键字段：
  ```python
  with pytest.raises(AppError) as exc_info:
      create_user(email="dup@example.com")

  assert exc_info.value.code == ErrorCode.VALIDATION
  assert exc_info.value.context["field"] == "email"
  ```
- fixture 只做数据准备，不做断言。
- 禁止测试之间共享可变状态（`global`、模块级变量）。

---

## 依赖管理

允许引入新依赖之前，必须验证：
1. `uv add <package>` 能解析（无冲突）
2. 包在 pypi 上的最新版支持 Python 3.12
3. 该功能不在标准库或已有依赖中重复提供

**已确定的依赖选型（不得替换）：**

| 用途 | 包 |
|---|---|
| 数据验证 / 序列化 | `pydantic` |
| HTTP 客户端 | `httpx` |
| CLI 解析 | `argparse`（stdlib）|
| 结构化日志 | `structlog` |
| 测试 | `pytest` |
| Lint / 格式化 | `ruff` |
| 类型检查 | `pyright` |

---

## 禁止事项（快速参考）

| 禁止 | 替代 |
|---|---|
| `Any` | `object` + 注释 |
| `Optional[X]` | `X \| None` |
| `dataclass` / `TypedDict` | `pydantic.BaseModel` |
| `print()` 调试 | `structlog` |
| 裸 `except:` | 具体异常类型 |
| `from x import *` | 显式导入 |
| `raise Exception("msg")` | `raise AppError(code, msg)` |
| `assert x  # 在非测试代码中` | 显式检查 + `AppError` |
| 多种写法并存 | 本文件规定的唯一写法 |

---

## 修改本文件的条件

仅当以下情况才允许修改规则：
1. Python 版本升级导致有更好的原生支持
2. 选型依赖出现安全漏洞或停止维护
3. 规则之间产生实际冲突（附具体复现场景）

不得因为"有时候另一种写法更简洁"而修改。
```

---

**几个设计决策值得说明：**

- **`frozen=True` + `strict=True` 的 pydantic model**：消除"字段可能被意外修改"的歧义，Agent 生成的代码不需要跟踪状态变化。
- **`suggestion` 字段在 AppError 里**：错误发生时就把下一步动作编码进去，Agent 不需要推断"遇到这个错误该怎么办"。
- **exit code 规范**：让 Agent 在 shell 脚本或工具调用链里能确定性地分支，不需要解析错误消息。
- **测试命名格式 `test_行为_条件_预期`**：Agent 读测试列表就能知道已覆盖哪些场景，不需要读测试体。