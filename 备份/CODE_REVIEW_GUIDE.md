# Daily Why 代码审查指南

**版本**：v1.0  
**日期**：2026-06-05  
**适用范围**：daily-why 项目所有 Python 脚本

---

## 📋 目录

1. [审查标准](#审查标准)
2. [审查流程](#审查流程)
3. [审查清单](#审查清单)
4. [工具配置](#工具配置)
5. [常见问题](#常见问题)

---

## 审查标准

### 1. 代码质量标准

#### 1.1 可读性
- **命名规范**：变量、函数、类名使用有意义的英文名称
- **注释**：复杂逻辑必须有注释说明
- **文档字符串**：所有公开函数必须有 docstring
- **代码长度**：单个函数不超过 50 行，单个文件不超过 500 行

#### 1.2 可维护性
- **单一职责**：每个函数只做一件事
- **避免重复**：提取公共逻辑到独立模块
- **配置外部化**：硬编码值提取到配置文件
- **错误处理**：关键操作必须有异常处理

#### 1.3 可测试性
- **依赖注入**：避免硬编码依赖
- **接口清晰**：函数参数和返回值类型明确
- **副作用最小化**：纯函数优先

### 2. 安全标准

#### 2.1 路径安全
- **路径验证**：所有文件路径必须验证合法性
- **路径遍历防护**：防止 `../` 攻击
- **权限检查**：文件操作前检查权限

#### 2.2 输入验证
- **参数校验**：所有外部输入必须校验
- **类型检查**：使用 type hints 明确类型
- **边界检查**：数值参数检查范围

#### 2.3 数据安全
- **敏感信息**：不硬编码密码、token 等
- **编码处理**：统一使用 UTF-8 编码
- **文件锁定**：并发写入时使用文件锁

### 3. 性能标准

#### 3.1 时间复杂度
- **避免嵌套循环**：O(n²) 以上操作需优化
- **使用生成器**：大数据集使用生成器处理
- **缓存结果**：重复计算结果缓存

#### 3.2 空间复杂度
- **流式处理**：大文件不一次性加载
- **及时释放**：不再使用的资源及时释放
- **内存监控**：长时间运行脚本监控内存

---

## 审查流程

### 1. 提交前自检

```bash
# 1. 语法检查
python -m py_compile script.py

# 2. 静态分析（如果安装了）
python -m flake8 script.py
python -m pylint script.py

# 3. 运行测试
python -m pytest tests/
```

### 2. 审查流程图

```
┌─────────────────────────────────────────────────────────┐
│  开发者提交代码                                           │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  自动化检查（CI）                                         │
│  - 语法检查                                              │
│  - 静态分析                                              │
│  - 单元测试                                              │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  人工审查                                                │
│  - 代码质量                                              │
│  - 安全检查                                              │
│  - 性能评估                                              │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  审查通过 → 合并代码                                      │
│  审查不通过 → 返回修改                                    │
└─────────────────────────────────────────────────────────┘
```

### 3. 审查角色

| 角色 | 职责 | 权限 |
|------|------|------|
| **开发者** | 编写代码、自检、提交 | 写入代码 |
| **审查者** | 审查代码、提出建议 | 评论、批准 |
| **维护者** | 合并代码、发布版本 | 合并、发布 |

---

## 审查清单

### ✅ 代码质量检查

- [ ] **命名规范**
  - [ ] 变量名有意义，不使用单字母（循环变量除外）
  - [ ] 函数名动词开头，描述行为
  - [ ] 类名名词，使用 PascalCase
  - [ ] 常量全大写，下划线分隔

- [ ] **文档完整性**
  - [ ] 模块级 docstring
  - [ ] 函数级 docstring（参数、返回值、异常）
  - [ ] 复杂逻辑有行内注释
  - [ ] README 更新（如果需要）

- [ ] **代码结构**
  - [ ] 函数长度 ≤ 50 行
  - [ ] 文件长度 ≤ 500 行
  - [ ] 嵌套层级 ≤ 4 层
  - [ ] 避免重复代码

- [ ] **错误处理**
  - [ ] 关键操作有 try-except
  - [ ] 异常信息清晰
  - [ ] 资源释放使用 finally 或 with
  - [ ] 不吞掉异常（至少 log）

### ✅ 安全检查

- [ ] **路径安全**
  - [ ] 文件路径验证（Path.exists()）
  - [ ] 防止路径遍历（../）
  - [ ] 权限检查（os.access()）

- [ ] **输入验证**
  - [ ] 外部输入校验
  - [ ] 类型检查（type hints）
  - [ ] 边界检查

- [ ] **数据安全**
  - [ ] 无硬编码敏感信息
  - [ ] 编码统一 UTF-8
  - [ ] 临时文件及时清理

### ✅ 性能检查

- [ ] **时间效率**
  - [ ] 无 O(n²) 以上算法
  - [ ] 大数据集使用生成器
  - [ ] 重复计算缓存

- [ ] **空间效率**
  - [ ] 大文件流式处理
  - [ ] 资源及时释放
  - [ ] 内存使用合理

### ✅ 测试检查

- [ ] **测试覆盖**
  - [ ] 核心函数有单元测试
  - [ ] 边界条件测试
  - [ ] 异常路径测试

- [ ] **测试质量**
  - [ ] 测试用例独立
  - [ ] 测试数据可重复
  - [ ] 断言明确

---

## 工具配置

### 1. 静态分析工具

#### flake8 配置（.flake8）
```ini
[flake8]
max-line-length = 120
max-complexity = 10
ignore = E501,W503
exclude = .git,__pycache__,build,dist
```

#### pylint 配置（.pylintrc）
```ini
[MASTER]
load-plugins=pylint.extensions.docparams

[FORMAT]
max-line-length=120

[MESSAGES CONTROL]
disable=C0114,C0115,C0116
```

### 2. 类型检查工具

#### mypy 配置（mypy.ini）
```ini
[mypy]
python_version = 3.13
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
```

### 3. 代码格式化工具

#### black 配置（pyproject.toml）
```toml
[tool.black]
line-length = 120
target-version = ['py313']
```

### 4. 测试工具

#### pytest 配置（pytest.ini）
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

---

## 常见问题

### Q1: 函数太长怎么办？

**A**: 提取子函数，每个子函数只做一件事。

```python
# ❌ 不好
def process_data(data):
    # 100 行代码...

# ✅ 好
def process_data(data):
    cleaned = clean_data(data)
    validated = validate_data(cleaned)
    result = transform_data(validated)
    return result

def clean_data(data):
    # 清理逻辑...
    pass

def validate_data(data):
    # 验证逻辑...
    pass

def transform_data(data):
    # 转换逻辑...
    pass
```

### Q2: 如何处理硬编码路径？

**A**: 提取到配置文件或环境变量。

```python
# ❌ 不好
WORKSPACE = Path(r"F:\WorkBuddy\daily-why")

# ✅ 好
WORKSPACE = Path(os.getenv("DAILY_WHY_WORKSPACE", r"F:\WorkBuddy\daily-why"))
```

### Q3: 如何避免重复代码？

**A**: 提取到公共模块。

```python
# ❌ 不好：多个文件重复定义
def count_chinese_chars(text):
    return len(re.findall(r"[\u4e00-\u9fff]", text))

# ✅ 好：提取到 topic_utils.py
from topic_utils import count_chinese_chars
```

### Q4: 如何处理异常？

**A**: 明确异常类型，提供有用信息。

```python
# ❌ 不好
try:
    data = json.loads(content)
except Exception:
    pass

# ✅ 好
try:
    data = json.loads(content)
except json.JSONDecodeError as e:
    logger.error(f"JSON 解析失败: {e}")
    raise ValueError(f"无效的 JSON 格式: {e}") from e
```

### Q5: 如何编写可测试的代码？

**A**: 使用依赖注入，避免全局状态。

```python
# ❌ 不好
def get_data():
    return Path("data.json").read_text()

# ✅ 好
def get_data(filepath: Path):
    return filepath.read_text()

# 测试时可以注入 mock 路径
```

---

## 附录

### A. 审查报告模板

```markdown
# 代码审查报告

**文件**: script.py
**审查者**: [审查者]
**日期**: YYYY-MM-DD

## 总体评价
- 代码质量: ⭐⭐⭐⭐☆
- 安全性: ⭐⭐⭐⭐⭐
- 性能: ⭐⭐⭐⭐☆
- 可测试性: ⭐⭐⭐☆☆

## 发现的问题

### 🔴 严重问题
1. [问题描述]
   - 位置: 第 XX 行
   - 建议: [修改建议]

### 🟡 一般问题
1. [问题描述]
   - 位置: 第 XX 行
   - 建议: [修改建议]

### 🟢 建议改进
1. [改进建议]

## 审查结论
- [ ] 通过
- [ ] 需要修改
- [ ] 需要重新审查
```

### B. 审查频率建议

| 类型 | 频率 | 审查者 |
|------|------|--------|
| 新功能 | 每次提交 | 至少 1 人 |
| Bug 修复 | 每次提交 | 至少 1 人 |
| 重构 | 每次提交 | 至少 2 人 |
| 配置变更 | 每次提交 | 维护者 |
| 文档更新 | 可选 | 任何人 |

### C. 审查工具推荐

| 工具 | 用途 | 安装命令 |
|------|------|---------|
| flake8 | 代码风格 | `pip install flake8` |
| pylint | 代码质量 | `pip install pylint` |
| mypy | 类型检查 | `pip install mypy` |
| black | 代码格式化 | `pip install black` |
| pytest | 测试框架 | `pip install pytest` |
| coverage | 测试覆盖 | `pip install coverage` |

---

> 本指南由代码审查专家制定，定期更新以适应项目发展。
