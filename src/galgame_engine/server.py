"""
MCP Server 入口 — 3 个 tools 暴露给 AI 客户端。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from galgame_engine.engine import Engine, FormatError
from galgame_engine.state_manager import StateManager, Entity

GAME_DIR = os.environ.get("GALGAME_DIR", ".game")

engine = Engine(GAME_DIR)
server = Server("galgame-engine")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="galgame_start",
            description="启动或恢复 Galgame 世界引擎。返回当前场景上下文。",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="galgame_action",
            description="提交一轮玩家操作。choice: A/B/C/自由文本。narrative: 完整四段叙事。引擎校验格式后更新存档。",
            inputSchema={
                "type": "object",
                "properties": {
                    "choice": {"type": "string"},
                    "narrative": {"type": "string"},
                },
                "required": ["choice", "narrative"],
            },
        ),
        Tool(
            name="galgame_status",
            description="获取世界状态的口吻式摘要。",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "galgame_start":
        result = engine.start()
        sm = StateManager(GAME_DIR)
        state = sm.load_all() if sm.is_initialized() else sm.init_default()
        chars = []
        for cid, prof in state.characters.profiles.items():
            ent = state.world.entities.get(cid)
            name = ent.name if ent else cid
            chars.append(f"- {name}: {prof.personality[:80]}")
        ctx = f"Day {state.story.current_day} | {state.story.current_arc_name} | {state.story.current_phase}\n\n角色:\n" + "\n".join(chars)
        ctx += "\n\n请以上下文为基础生成起始叙事。四段格式必须完整。"
        return [TextContent(type="text", text=ctx)]

    elif name == "galgame_action":
        choice = arguments["choice"]
        narrative = arguments["narrative"]
        try:
            result = engine.action(choice, narrative)
            lines = [
                "【📖 场景速写】", result.scene, "",
                "【🎧 环境音效】", result.sound, "",
                "【💬 剧情推进 & 对白】", result.narrative, "",
                "【🎮 行动指令】",
            ]
            for c in result.choices:
                lines.append(f"{c['key']}. {c['text']}")
            lines.append("")
            lines.append(f"--- Day {result.day} | {result.phase} | Session {result.session}")
            return [TextContent(type="text", text="\n".join(lines))]
        except FormatError as e:
            return [TextContent(type="text", text=f"FORMAT ERROR: {e}`n请在下一次 galgame_action 调用中补全以下缺失的区块标记，其他内容保持不变，重新提交完整叙事。")]

    elif name == "galgame_status":
        sm = StateManager(GAME_DIR)
        state = sm.load_all()
        ctx = f"Day {state.story.current_day} | {state.story.current_phase} | Sessions: {state.story.play_sessions}\nArc: {state.story.current_arc_name}\n未解谜团: {len(state.story.narrative.active_mysteries)} 个\n\n请用叙事口吻转述以上状态，禁止输出 JSON 或数值。"
        return [TextContent(type="text", text=ctx)]

    return [TextContent(type="text", text="未知工具")]


async def run():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()