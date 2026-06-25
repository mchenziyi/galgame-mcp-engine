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
from galgame_engine.state_manager import StateManager, Entity, GameState

GAME_DIR = os.environ.get("GALGAME_DIR", ".game")

engine = Engine(GAME_DIR)
server = Server("galgame-engine")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="galgame_start",
            description="启动或恢复 Galgame 世界引擎。返回完整世界状态上下文（角色全档案+关系+时间线+谜团+位置+物品）。",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="galgame_action",
            description="提交一轮玩家操作。choice: A/B/C/自由文本。narrative: 完整四段叙事。引擎校验格式后更新存档并返回下一幕上下文。",
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
        ctx = _build_rich_context(state)
        ctx += "\n\n---\n\n请以上下文为基础生成起始场景的完整四段叙事。长度参考旧 galgame 文本风格——每块内容充实，叙事部分至少 3~5 段完整的场景描写和对白。"
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
            return [TextContent(type="text", text=f"FORMAT ERROR: {e}\n请在下一次 galgame_action 调用中补全缺失的区块标记，其他内容保持不变，重新提交完整叙事。")]

    elif name == "galgame_status":
        sm = StateManager(GAME_DIR)
        state = sm.load_all()
        ctx = _build_status_context(state)
        return [TextContent(type="text", text=ctx)]

    return [TextContent(type="text", text="未知工具")]


def _build_rich_context(state: GameState) -> str:
    """从 GameState 构建完整的叙事上下文（世界圣经）。"""
    s = state.story
    w = state.world
    c = state.characters
    t = state.timeline

    lines = []

    # ── 头部 ──
    lines.append("═" * 50)
    lines.append(f"世界状态 · Day {s.current_day} | {s.current_arc_name} Phase{s.current_phase[-1]} | Session {s.play_sessions}")
    lines.append("═" * 50)
    lines.append("")
    lines.append(f'Arc: {s.current_arc} \u201c{s.current_arc_name}\u201d')
    lines.append(f"Route: {s.current_route}")
    lines.append(f"活跃谜团: {len(s.narrative.active_mysteries)} 个")
    lines.append(f"活跃伏笔: {len(s.narrative.foreshadowing_pool)} 个")
    lines.append("")

    # ── 角色完整档案 ──
    lines.append("─" * 40)
    lines.append("【角色档案】")
    lines.append("")

    for cid, prof in c.profiles.items():
        ent = w.entities.get(cid)
        name = ent.name if ent else cid
        lines.append(f"■ {name} ({cid})")
        lines.append(f"  性格: {prof.personality}")
        if prof.goals:
            lines.append(f"  目标:")
            for g in prof.goals:
                lines.append(f"    · {g}")
        if prof.secrets:
            lines.append(f"  秘密:")
            for sec in prof.secrets:
                lines.append(f"    · {sec}")
        if prof.important_memories:
            lines.append(f"  重要记忆:")
            for mem in prof.important_memories:
                lines.append(f"    ✦ {mem}")
        lines.append(f"  当前心境: {prof.current_emotion}")
        lines.append("")

    # ── 关系网络 ──
    lines.append("─" * 40)
    lines.append("【关系网络】")
    if c.relationships:
        for a, inner in c.relationships.items():
            a_name = _entity_name(w, a)
            for b, rel in inner.items():
                if rel.trust > 0 or rel.romance > 0:
                    b_name = _entity_name(w, b)
                    parts = []
                    if rel.trust > 0:
                        parts.append(f"trust={rel.trust}")
                    if rel.romance > 0:
                        parts.append(f"romance={rel.romance}")
                    if rel.dependency > 0:
                        parts.append(f"dependency={rel.dependency}")
                    if rel.hostility > 0:
                        parts.append(f"hostility={rel.hostility}")
                    if parts:
                        lines.append(f"  {a_name} ↔ {b_name}: {', '.join(parts)}")
    lines.append("")

    # ── 时间线 ──
    lines.append("─" * 40)
    lines.append(f"【时间线（共 {len(t.active_timeline)} 条事件）】")
    recent = t.active_timeline[-10:]  # 最近 10 条
    for evt in recent:
        participants_names = [_entity_name(w, p) for p in evt.participants]
        lines.append(f"  {evt.id} · Day {evt.day} · {evt.title}")
        lines.append(f"    参与者: {', '.join(participants_names)}")
        if evt.items:
            lines.append(f"    物品: {', '.join(evt.items)}")
        lines.append(f"    重要性: {evt.importance}")
    lines.append("")

    # ── 谜团与伏笔 ──
    if s.narrative.active_mysteries:
        lines.append("─" * 40)
        lines.append("【活跃谜团】")
        for m in s.narrative.active_mysteries:
            lines.append(f"  · {m}")
        lines.append("")

    if s.narrative.foreshadowing_pool:
        lines.append("─" * 40)
        lines.append("【伏笔池】")
        for fs in s.narrative.foreshadowing_pool:
            lines.append(f"  {fs.id} (Day {fs.created_day}, {fs.importance}): {fs.content}")
        lines.append("")

    if s.narrative.unresolved_questions:
        lines.append("【未解问题】")
        for q in s.narrative.unresolved_questions:
            lines.append(f"  · {q}")
        lines.append("")

    # ── 世界 ──
    lines.append("─" * 40)
    lines.append("【已知地点】")
    for eid, ent in w.entities.items():
        if ent.type == "location":
            lines.append(f"  · {ent.name}")
    lines.append("")

    lines.append("【已拥有物品】")
    for eid, ent in w.entities.items():
        if ent.type == "item":
            owner = _find_owner(w, eid)
            owner_name = _entity_name(w, owner) if owner else "未知"
            lines.append(f"  · {ent.name} ({owner_name})")
    lines.append("")

    # ── 离屏事件 ──
    if s.offscreen_changes:
        lines.append("─" * 40)
        lines.append("【离屏变化】")
        for oc in s.offscreen_changes:
            lines.append(f"  · {oc}")
        lines.append("")

    # ── NPC 行程 ──
    if s.npc_schedules:
        lines.append("─" * 40)
        lines.append("【NPC 当前行程】")
        for nid, sched in s.npc_schedules.items():
            name = _entity_name(w, nid)
            lines.append(f"  {name}: 早={sched.morning} 午={sched.afternoon} 晚={sched.evening}")
        lines.append("")

    # ── 叙事方针 ──
    lines.append("─" * 40)
    lines.append("【叙事方针】")
    lines.append("  · 场景速写聚焦感官（光线/温度/气味/触感），禁止流水账")
    lines.append("  · 角色拥有独立人格、目标、秘密，不围绕玩家旋转")
    lines.append("  · 玩家缺席时世界继续运转（离屏事件真实发生）")
    lines.append("  · 日常比高潮更重要，羁绊比离别更珍贵")
    lines.append("  · 当玩家开始珍惜日常时，故事才真正开始")
    lines.append("  · 所有输出使用简体中文，禁止繁体")
    lines.append("")
    lines.append("═" * 50)

    return "\n".join(lines)


def _entity_name(w, eid: str) -> str:
    ent = w.entities.get(eid)
    return ent.name if ent else eid


def _find_owner(w, eid: str) -> str | None:
    for rel in w.relations:
        if rel.to == eid and (rel.type == "owns" or rel.type == "belongs_to"):
            return rel.from_
    return None


def _build_status_context(state: GameState) -> str:
    s = state.story
    w = state.world
    c = state.characters
    chars_summary = []
    for cid, prof in c.profiles.items():
        name = _entity_name(w, cid)
        chars_summary.append(f"{name}: {prof.current_emotion[:80]}")
    lines = [
        f"Day {s.current_day} | {s.current_phase} | Sessions: {s.play_sessions}",
        f"Arc: {s.current_arc_name}",
        f"未解谜团: {len(s.narrative.active_mysteries)} 个",
        "",
        "角色状态:",
        *chars_summary,
        "",
        "请用叙事口吻（禁止输出JSON/数值）描述以上状态感知。",
    ]
    return "\n".join(lines)


async def run():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
