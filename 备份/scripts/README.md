# Daily Why 代码审查工具

本目录包含用于 daily-why 项目代码审查的自动化工具。

## 📁 文件结构

```
scripts/
├── README.md                      # 本文档
├── code_review_check.py           # 代码审查自动化检查工具
└── review_report_template.md      # 审查报告模板
```

## 🚀 快速开始

### 1. 检查单个文件

```bash
python scripts/code_review_check.py prepare_topics.py
```

### 2. 检查所有 Python 文件

```bash
python scripts/code_review_check.py
```

### 3. JSON 格式输出

```bash
python scripts/code_review_check.py --json
```

### 4. 严格模式（P0 不通过）

```bash
python scripts/code_review_check.py --strict
```

## 📋 审查标准

### 严重度定义

| 级别 | 含义 | 处理方式 |
|------|------|---------|
| **P0** | 致命问题 | 必须修复，阻断发布 |
| **P1** | 重要问题 | 建议修复，影响质量 |
| **P2** | 一般问题 | 可选修复，改进代码 |

### 检查类别

| 类别 | 检查内容 | 严重度 |
|------|---------|--------|
| **naming** | 命名规范 | P1-P2 |
| **security** | 安全问题 | P0-P2 |
| **performance** | 性能问题 | P2 |
| **style** | 代码风格 | P2 |
| **doc** | 文档完整性 | P2 |

## 🔧 工具使用

### code_review_check.py

**功能**：自动化检查 Python 代码质量

**参数**：
- `files`：要检查的文件路径（可选，默认检查所有 .py 文件）
- `--json`：JSON 格式输出
- `--fix`：自动修复可修复的问题（实验性）
- `--strict`：严格模式（P0 不通过）

**示例**：
```bash
# 检查所有文件
python scripts/code_review_check.py

# 检查指定文件
python scripts/code_review_check.py prepare_topics.py validate_article.py

# JSON 格式输出
python scripts/code_review_check.py --json > review_results.json

# 严格模式
python scripts/code_review_check.py --strict
```

**输出示例**：
```
============================================================
📋 代码审查报告: prepare_topics.py
============================================================
状态: ✅
分数: 85/100
P0(致命) = 0  P1(重要) = 2  P2(一般) = 5

--- 🟡 P1 重要问题（建议修复） ---
  ! 第 42 行: 硬编码路径，建议提取到配置或环境变量
  ! 第 108 行: 硬编码 Python 路径，建议使用 sys.executable

--- 🔵 P2 一般问题（可选修复） ---
  · 第 15 行: 函数缺少 docstring
  · 第 29 行: 函数长度超过 50 行
  ...

============================================================
```

### review_report_template.md

**功能**：代码审查报告模板

**使用方法**：
1. 复制模板内容
2. 替换占位符（如 `{filename}`、`{reviewer}` 等）
3. 填写审查发现和建议
4. 保存为 `{filename}_review_{date}.md`

## 📖 审查流程

### 1. 提交前自检

```bash
# 语法检查
python -m py_compile script.py

# 自动化审查
python scripts/code_review_check.py script.py

# 运行测试
python -m pytest tests/
```

### 2. 人工审查

1. 阅读代码，理解逻辑
2. 检查审查清单（见 CODE_REVIEW_GUIDE.md）
3. 记录问题和建议
4. 填写审查报告

### 3. 审查结论

- **通过**：代码质量良好，可以合并
- **有条件通过**：需要修复 P0 问题后合并
- **不通过**：需要重大修改后重新审查

## 🔗 相关文档

- [代码审查指南](../CODE_REVIEW_GUIDE.md)
- [项目文档](../README.md)
- [API 文档](../docs/api.md)

## 📝 更新日志

- **v1.0** (2026-06-05): 初始版本
  - 创建代码审查自动化检查工具
  - 创建审查报告模板
  - 创建使用文档

---

> 本工具由代码审查专家制定，用于 daily-why 项目代码质量管控。
