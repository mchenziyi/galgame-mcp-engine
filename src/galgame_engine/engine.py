"""
引擎核心 — 协调存档读写和状态推断，不调 LLM。
LLM 叙事由客户端完成，引擎只负责：
1. 状态读写 + play_sessions 递增
2. 叙事格式校验
3. 字段自动维护（timeline / relationships / items）
"""
from dataclasses import dataclass

from .state_manager import (
    GameState, StateManager,
    TimelineEvent, Relation, Entity
)
from .response_builder import NarrBlock, parse as parse_narrative, validate


@dataclass
class TurnResult:
    """一轮对话的结果。"""
    scene: str
    sound: str
    narrative: str
    choices: list[dict]  # [{"key": "A", "text": "..."}]
    day: int
    phase: str
    session: int  # play_sessions 当前值


class Engine:
    def __init__(self, game_dir: str = ".game"):
        self.sm = StateManager(game_dir)

    def start(self, initial_narrative: str = "") -> TurnResult:
        """开始游戏或恢复存档。如无存档则初始化。首次调用时 initial_narrative 可为空（引擎自行构建初始场景）。"""
        if self.sm.is_initialized():
            state = self.sm.load_all()
        else:
            state = self.sm.init_default()

        if not initial_narrative:
            # 无叙事传入 → 返回当前状态摘要让客户端生成
            return self._state_snapshot(state)

        return self._process(state, initial_narrative)

    def action(self, choice: str, narrative: str) -> TurnResult:
        """处理玩家操作。choice 为 A/B/C/D文本，narrative 为客户端 LLM 生成的完整叙事文本。"""
        state = self.sm.load_all()

        # ── 🔒 play_sessions 强制递增 ──
        state.story.play_sessions += 1

        # ── 解析叙事 ──
        block = parse_narrative(narrative)
        errs = validate(block)
        if errs:
            # 格式不完整 → 返回错误信息让客户端重试
            raise FormatError("; ".join(errs), block)

        # ── 自动维护 ──
        self._auto_maintain(state, block, choice)

        # ── 保存 ──
        self.sm.save(state)

        return TurnResult(
            scene=block.scene,
            sound=block.sound,
            narrative=block.narrative,
            choices=[{"key": c.key, "text": c.text} for c in block.choices],
            day=state.story.current_day,
            phase=state.story.current_phase,
            session=state.story.play_sessions,
        )

    def _state_snapshot(self, state: GameState) -> TurnResult:
        """返回当前世界状态的结构化摘要（供客户端 LLM 生成起始场景）。"""
        return TurnResult(
            scene="",
            sound="",
            narrative="",
            choices=[],
            day=state.story.current_day,
            phase=state.story.current_phase,
            session=state.story.play_sessions,
        )

    def _auto_maintain(self, state: GameState, block: NarrBlock, choice: str) -> None:
        """自动维护不需要 LLM 判断的字段。"""
        # 1. timeline 追加事件
        event_id = self.sm.next_id(state, "event")
        event = TimelineEvent(
            id=event_id,
            arc=state.story.current_arc,
            title=self._extract_title(block.narrative[:60]),
            participants=self._current_participants(state),
            items=self._extract_items(block.narrative),
            day=state.story.current_day,
            importance="relationship",
        )
        state.timeline.active_timeline.append(event)

        # 2. world.json：新物品 → entity
        for item_name in event.items:
            item_id = self._slugify(item_name)
            if item_id not in state.world.entities:
                state.world.entities[item_id] = Entity(type="item", name=item_name)

    def _extract_title(self, text: str) -> str:
        """从叙事开头提取一个简短标题。"""
        text = text.strip()
        if len(text) > 30:
            text = text[:30] + "…"
        return text

    def _extract_items(self, text: str) -> list[str]:
        """从叙事中提取可能的关键物品名称。简单启发式：引号包裹的名词短语。"""
        import re
        items = set()
        # 匹配「」『』中的内容
        for m in re.finditer(r"[「『](.+?)[」』]", text):
            items.add(m.group(1))
        # 过滤掉太长或太短的
        return [item for item in items if 2 <= len(item) <= 20]

    def _current_participants(self, state: GameState) -> list[str]:
        """获取当前活跃的参与者列表。"""
        return list(state.characters.profiles.keys()) + ["player"]

    def _slugify(self, name: str) -> str:
        """中文名→英文ID。"""
        import re
        slug = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())[:30]
        return slug or f"item_{len(state.world.entities)}"


class FormatError(Exception):
    """格式校验失败异常。"""
    def __init__(self, message: str, block: NarrBlock):
        super().__init__(message)
        self.block = block

