# 代码审查报告模板

**文件**: `{filename}`  
**审查者**: {reviewer}  
**日期**: {date}  
**版本**: {version}

---

## 📊 总体评价

| 指标 | 评分 | 说明 |
|------|------|------|
| 代码质量 | ⭐⭐⭐⭐☆ | {quality_comment} |
| 安全性 | ⭐⭐⭐⭐⭐ | {security_comment} |
| 性能 | ⭐⭐⭐⭐☆ | {performance_comment} |
| 可测试性 | ⭐⭐⭐☆☆ | {testability_comment} |
| 文档完整性 | ⭐⭐⭐⭐☆ | {doc_comment} |

**总体分数**: {score}/100

---

## 🔍 审查发现

### 🔴 P0 致命问题（必须修复）

| # | 行号 | 问题描述 | 建议修复方案 |
|---|------|---------|-------------|
| 1 | {line} | {problem} | {solution} |

### 🟡 P1 重要问题（建议修复）

| # | 行号 | 问题描述 | 建议修复方案 |
|---|------|---------|-------------|
| 1 | {line} | {problem} | {solution} |

### 🟢 P2 一般问题（可选修复）

| # | 行号 | 问题描述 | 建议修复方案 |
|---|------|---------|-------------|
| 1 | {line} | {problem} | {solution} |

---

## ✅ 优点

1. {strength_1}
2. {strength_2}
3. {strength_3}

---

## 📝 改进建议

### 短期改进（1-2 周）

- [ ] {improvement_1}
- [ ] {improvement_2}

### 长期改进（1-2 月）

- [ ] {improvement_3}
- [ ] {improvement_4}

---

## 🧪 测试建议

### 单元测试

```python
def test_{function_name}():
    # 测试用例
    pass
```

### 集成测试

```python
def test_{integration_scenario}():
    # 集成测试用例
    pass
```

### 边界条件测试

```python
def test_{edge_case}():
    # 边界条件测试用例
    pass
```

---

## 📚 相关资源

- [代码审查指南](../CODE_REVIEW_GUIDE.md)
- [项目文档](../README.md)
- [API 文档](../docs/api.md)

---

## 审查结论

- [ ] ✅ **通过** - 代码质量良好，可以合并
- [ ] ⚠️ **有条件通过** - 需要修复 P0 问题后合并
- [ ] ❌ **不通过** - 需要重大修改后重新审查

**审查者签名**: {reviewer_signature}  
**日期**: {date}

---

> 本报告由代码审查专家制定，用于 daily-why 项目代码质量管控。
