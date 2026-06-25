"""
MCP Server 入口 — 3 个 tools 暴露给 AI 客户端。
"""
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .engine import Engine, FormatError
from .state_manager import StateManager
from .response_builder import to_dict

GAME_DIR = os.environ.get("GALGAME_DIR", ".game")

engine = Engine(GAME_DIR)
server = Server("galgame-engine")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="galgame_start",
            description="启动或恢复 Galgame 世界引擎。返回当前场景的上下文摘要（day/phase/角色列表等），供客户端 LLM 生成起始场景。",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="galgame_action",
            description="提交一轮玩家操作。choice 为 A/B/C 或自由文本(D)。narrative 为客户端 LLM 根据上下文生成的完整四段叙事文本（场景速写+环境音效+剧情对白+行动指令）。引擎校验格式后更新存档并返回结构化结果。",
            inputSchema={
                "type": "object",
                "properties": {
                    "choice": {"type": "string", "description": "玩家选择：A / B / C / 或自由文本（D）"},
                    "narrative": {"type": "string", "description": "LLM 生成的四段完整叙事文本"},
                },
                "required": ["choice", "narrative"],
            },
        ),
        Tool(
            name="galgame_status",
            description="获取世界状态的口吻式摘要。返回叙事风格的感知报告，不返回原始 JSON 数据。",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "galgame_start":
        result = engine.start()
        if result.choices:
            # 已有存档，返回当前状态
            return [TextContent(type="text", text=_format_start(result))]
        else:
            # 新游戏，返回初始上下文让客户端生成
            sm = StateManager(GAME_DIR)
            state = sm.load_all() if sm.is_initialized() else sm.init_default()
            ctx = _build_context(state)
            return [TextContent(type="text", text=ctx)]

    elif name == "galgame_action":
        choice = arguments["choice"]
        narrative = arguments["narrative"]
        try:
            result = engine.action(choice, narrative)
            return [TextContent(type="text", text=_format_result(result))]
        except FormatError as e:
            return [TextContent(
                type="text",
                text=f"格式校验失败：{e}\n请补充缺失的区块后重新调用 galgame_action。"
            )]

    elif name == "galgame_status":
        sm = StateManager(GAME_DIR)
        state = sm.load_all()
        ctx = _build_status_context(state)
        return [TextContent(type="text", text=ctx)]

    return [TextContent(type="text", text="未知工具")]


def _format_start(result) -> str:
    lines = [
        f"Day {result.day} | {result.phase} | Sessions: {result.session}",
        "",
        "请根据以上信息生成起始场景。格式要求：",
        "",
        "【📖 场景速写】（2-4行，光线/温度/气味/触感）",
        "【🎧 环境音效】（拟声词）",
        "【💬 剧情推进 & 对白】（旁白+角色对白）",
        "【🎮 行动指令】",
        "A. ...",
        "B. ...",
        "C. ...",
        "D. 输入任何你想做的事情",
    ]
    return "\n".join(lines)


def _format_result(result) -> str:
    lines = [
        f"【📖 场景速写】",
        result.scene,
        "",
        f"【🎧 环境音效】",
        result.sound,
        "",
        f"【💬 剧情推进 & 对白】",
        result.narrative,
        "",
        f"【🎮 行动指令】",
    ]
    for c in result.choices:
        lines.append(f"{c['key']}. {c['text']}")
    lines.append("")
    lines.append(f"--- Day {result.day} | {result.phase} | Session {result.session}")
    return "\n".join(lines)


def _build_context(state) -> str:
    """构建初始上下文（供客户端 LLM 使用）。"""
    chars = []
    for cid, prof in state.characters.profiles.items():
        name = state.world.entities.get(cid, Entity(type="character", name=cid)).name
        chars.append(f"- {name}: {prof.personality[:100]}")
    locs = []
    for eid, ent in state.world.entities.items():
        if ent.type == "location":
            locs.append(f"- {ent.name}")
    lines = [
        f"当前状态: Day {state.story.current_day} | {state.story.current_arc_name} | {state.story.current_phase}",
        f"活跃角色:",
        *chars,
        f"已知地点:",
        *locs,
        "",
        "请以上下文为基础生成起始场景。角色有独立人格，世界不围绕玩家旋转。",
        "",
        "输出格式:",
        "【📖 场景速写】...",
        "【🎧 环境音效】...",
        "【💬 剧情推进 & 对白】...",
        "【🎮 行动指令】",
        "A. ...",
        "B. ...",
        "C. ...",
        "D. 输入任何你想做的事情",
    ]
    return "\n".join(lines)


def _build_status_context(state) -> str:
    """构建状态模式的上下文。"""
    chars_summary = []
    for cid, prof in state.characters.profiles.items():
        name = state.world.entities.get(cid, Entity(type="character", name=cid)).name
        chars_summary.append(f"{name}: {prof.current_emotion[:80]}")
    lines = [
        f"Day {state.story.current_day} | {state.story.current_phase} | Sessions: {state.story.play_sessions}",
        f"Arc: {state.story.current_arc_name}",
        f"未解谜团: {len(state.story.narrative.active_mysteries)} 个",
        "",
        "角色状态:",
        *chars_summary,
        "",
        "请用叙事口吻（禁止输出JSON/数值）描述以上状态感知。",
    ]
    return "\n".join(lines)


def main():
    import asyncio
    async def run():
        async with stdio_server() as (read, write):
            await server.run(read, write)
    asyncio.run(run())


if __name__ == "__main__":
    main()
