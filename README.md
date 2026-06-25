# 旮旯给木里不是这样的 — MCP 版

> Galgame 不是这样的。

一个**视觉小说世界引擎**，以 MCP Server 形式运行。任何支持 MCP 协议的 AI 客户端都能驱动它。

谁不想在公司摸鱼的时候来一场甜甜的恋爱呢。

## 与 skill 版的关系

这是 [galgame_world_engine skill](https://github.com/mchenziyi/galgame-is-not-like-this) 的 MCP 重构版。

| | Skill 版 | MCP 版 |
|---|---------|--------|
| 运行方式 | Reasonix subagent | 独立 MCP Server |
| 格式保证 | 提示词约束 | 代码强制 |
| 兼容性 | 仅 Reasonix | 所有 MCP 客户端 |
| 状态管理 | LLM 自觉维护 | 代码自动维护 |

MCP 版完全兼容 skill 版的 `.game/` 存档，无需迁移。

## 许可证

MIT
