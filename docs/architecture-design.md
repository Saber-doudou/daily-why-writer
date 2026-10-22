# Daily Why 2-Agent 架构设计文档

## 1. 架构概述

### 1.1 当前架构（单Agent）
```
用户请求 → 单Agent（选题→查证→写作→自检→审核→更新历史）
```

**问题**：
- 角色分裂：同一Agent既要"创作"又要"审核"
- 上下文膨胀：所有规则和工具都在一个Agent中
- 调试困难：错误定位需要检查多个环节

### 1.2 目标架构（2-Agent）
```
用户请求 → 内容生成Agent（选题→查证→写作→自检） → 审核发布Agent（审核→判例匹配→更新历史）
```

**优势**：
- 职责分离：创作与审核由不同Agent负责
- 上下文精简：每个Agent只加载必要的规则
- 调试容易：问题定位到具体Agent

---

## 2. Agent 设计

### 2.1 内容生成Agent

**职责**：
- 选题：从 topics_context.json 选择未用过的话题
- 查证：WebSearch 搜索关键词，验证事实准确性
- 写作：按 A+C+F 结构写文章
- 自检：边写边检查，写后总检

**工具需求**：
- WebSearch：查证事实
- Read：读取 topics_context.json、SKILL.md
- Write：保存文章草稿

**上下文规模**：约 2000 token
- 系统提示：~500 token
- SKILL.md（精简版）：~1000 token
- topics_context.json（精简版）：~200 token
- 其他：~300 token

**输入**：用户请求（可选）
**输出**：文章草稿（Markdown格式）

### 2.2 审核发布Agent

**职责**：
- 质量审核：运行 validate_article.py 检查文章质量
- 判例匹配：如果审核不通过，使用 case_matcher.py 匹配相关判例
- 修正建议：根据判例提供修正建议
- 历史更新：运行 update_history.py 更新记忆

**工具需求**：
- Bash：运行 Python 脚本
- Read：读取审核报告、判例库
- Edit：修正文章（如果需要）

**上下文规模**：约 1500 token
- 系统提示：~500 token
- 审核规则：~500 token
- 判例库索引：~300 token
- 其他：~200 token

**输入**：文章草稿（Markdown格式）
**输出**：审核结果 + 最终文章

---

## 3. 通信协议

### 3.1 消息格式

**内容生成Agent → 审核发布Agent**：
```json
{
  "type": "article_draft",
  "content": "文章内容（Markdown格式）",
  "metadata": {
    "topic": "为什么人会打哈欠？",
    "category": "生活常识",
    "word_count": 500,
    "generation_time": "2026-06-05T13:53:40"
  }
}
```

**审核发布Agent → 内容生成Agent**（如果需要修正）：
```json
{
  "type": "revision_request",
  "issues": [
    {
      "level": "P0",
      "description": "分隔线不足",
      "suggestion": "在A段后和F段前各添加一个分隔线"
    }
  ],
  "related_cases": ["CS-002", "CS-003"]
}
```

**审核发布Agent → 用户**（最终结果）：
```json
{
  "type": "final_result",
  "status": "success",
  "article": "最终文章内容",
  "validation": {
    "p0_count": 0,
    "p1_count": 1,
    "p2_count": 0,
    "score": 95
  },
  "file_path": "F:/WorkBuddy/daily-why/2026-06-05-每日冷知识.md"
}
```

### 3.2 回退机制

**审核不通过时的处理流程**：
1. 审核发布Agent 将审核报告和相关判例发送给内容生成Agent
2. 内容生成Agent 根据反馈修正文章
3. 修正后重新发送给审核发布Agent
4. 最多重试 2 次，如果仍然不通过，输出最终报告

---

## 4. 实施计划

### 4.1 第一步：创建Agent配置文件

创建两个Agent的配置文件：
- `agents/content-generator.json`：内容生成Agent配置
- `agents/quality-reviewer.json`：审核发布Agent配置

### 4.2 第二步：修改 automation prompt

将当前的单Agent prompt 拆分为两个Agent的prompt：
- 内容生成Agent prompt：选题→查证→写作→自检
- 审核发布Agent prompt：审核→判例匹配→修正建议→历史更新

### 4.3 第三步：实现通信协议

创建消息处理模块：
- `message_handler.py`：处理Agent间的消息传递
- 定义消息格式和解析逻辑

### 4.4 第四步：测试验证

- 单元测试：测试每个Agent的独立功能
- 集成测试：测试两个Agent的协作流程
- 端到端测试：测试完整的文章生成流程

---

## 5. 风险评估

### 5.1 风险点

| 风险 | 等级 | 描述 | 缓解措施 |
|------|------|------|---------|
| 协调复杂 | 🟡 中 | 两个Agent需要协调工作 | 设计清晰的通信协议 |
| Token消耗增加 | 🟡 中 | Agent间传递消息消耗额外Token | 精简消息格式 |
| 故障传播 | 🟡 中 | 一个Agent失败影响整个流程 | 实现回退机制 |
| 调试困难 | 🟢 低 | 问题定位到具体Agent | 添加详细日志 |

### 5.2 收益评估

| 收益 | 描述 |
|------|------|
| 职责分离 | 创作与审核由不同Agent负责，避免角色分裂 |
| 上下文精简 | 每个Agent只加载必要的规则，减少Token消耗 |
| 调试容易 | 问题定位到具体Agent，提高调试效率 |
| 质量提升 | 审核Agent有独立视角，提高审核质量 |

---

## 6. 监控指标

### 6.1 性能指标

- **Token消耗**：每次运行的总Token消耗
- **响应时间**：从请求到完成的时间
- **成功率**：审核通过率

### 6.2 质量指标

- **审核得分**：文章的平均审核得分
- **P0/P1问题数**：每篇文章的P0/P1问题数
- **修正次数**：平均修正次数

---

## 7. 总结

2-Agent架构通过职责分离，解决了当前单Agent架构的角色分裂问题。虽然增加了协调复杂度，但通过清晰的通信协议和回退机制，可以有效管理风险。预期收益包括职责分离、上下文精简、调试容易和质量提升。

建议先进行小规模试点，验证2-Agent架构的可行性，再逐步推广到整个系统。