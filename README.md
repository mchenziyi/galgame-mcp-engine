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

## 安装

```bash
git clone https://github.com/mchenziyi/galgame-mcp-engine.git
cd galgame-mcp-engine
pip install -e .
```

依赖：Python 3.12+，DeepSeek API（由客户端调用，MCP Server 自身不调 LLM）。

## 配置

### Reasonix

在项目根目录的 `reasonix.toml` 中添加：

```toml
[[plugins]]
name = "galgame-engine"
command = "python"
args = ["路径/galgame-mcp-engine/src/galgame_engine/server.py"]
env = { GALGAME_DIR = ".game" }
```

然后将 `skill/galgame_world_engine.md` 复制到 `.reasonix/skills/galgame_world_engine/SKILL.md`。

重启 Reasonix，输入 `/galgame_world_engine` 开始。

### Claude Desktop

```json
{
  "mcpServers": {
    "galgame-engine": {
      "command": "python",
      "args": ["路径/galgame-mcp-engine/src/galgame_engine/server.py"],
      "env": { "GALGAME_DIR": "路径/你的/.game目录" }
    }
  }
}
```

### Cursor / Windsurf

在 MCP 配置中添加同上的 stdio server 配置。

## 使用

安装并配置后，在 AI 客户端中调用 MCP tools：

| Tool | 说明 |
|------|------|
| `galgame_start` | 加载存档，返回完整世界上下文（角色/关系/时间线/谜团） |
| `galgame_action` | 提交玩家操作，引擎校验叙事格式并自动维护存档 |
| `galgame_status` | 叙事口吻的世界状态摘要 |

推荐配合 `skill/galgame_world_engine.md` 提示词文件使用——它定义了叙事品质标准、角色规则和决策优先级。

## 架构

```
skill/galgame_world_engine.md  ← 提示词（叙事哲学、品质要求）
         │
         ▼
    AI 客户端（LLM）
         │ 生成叙事
         ▼
┌─────────────────────────────┐
│   galgame-engine (MCP)      │
│                             │
│  server.py      工具入口     │
│  engine.py      核心协调     │
│  state_manager  存档读写     │
│  response_builder 格式校验   │
└─────────────────────────────┘
         │
         ▼
    .game/ (4 个 JSON)
```

## 许可证

MIT
