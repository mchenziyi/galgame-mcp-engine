"""
引擎核心 — 协调存档读写和状态推断，不调 LLM。
LLM 叙事由客户端完成，引擎只负责：
1. 状态读写 + play_sessions 递增
2. 叙事格式校验 + 自动修复
3. 字段自动维护（timeline / relationships / items）
"""
import re
from dataclasses import dataclass

from .state_manager import (
    GameState, StateManager,
    TimelineEvent, Relation, Entity
)
from .response_builder import NarrBlock, parse as parse_narrative, validate, repair


@dataclass
class TurnResult:
    scene: str
    sound: str
    narrative: str
    choices: list[dict]
    day: int
    phase: str
    session: int


class Engine:
    def __init__(self, game_dir: str = ".game"):
        self.sm = StateManager(game_dir)

    def start(self, initial_narrative: str = "") -> TurnResult:
        if self.sm.is_initialized():
            state = self.sm.load_all()
        else:
            state = self.sm.init_default()
        return self._state_snapshot(state)

    def action(self, choice: str, narrative: str) -> TurnResult:
        state = self.sm.load_all()
        state.story.play_sessions += 1

        block = parse_narrative(narrative)
        errs = validate(block)
        if errs:
            block = repair(block, narrative)
            errs = validate(block)
            if errs:
                raise FormatError("; ".join(errs), block)

        self._auto_maintain(state, block, choice)
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
        return TurnResult(scene="", sound="", narrative="", choices=[], day=state.story.current_day, phase=state.story.current_phase, session=state.story.play_sessions)

    def _auto_maintain(self, state: GameState, block: NarrBlock, choice: str) -> None:
        event_id = self.sm.next_id(state, "event")
        event = TimelineEvent(
            id=event_id, arc=state.story.current_arc,
            title=self._extract_title(block.narrative[:60]),
            participants=self._current_participants(state),
            items=self._extract_items(block.narrative),
            day=state.story.current_day, importance="relationship",
        )
        state.timeline.active_timeline.append(event)
        for item_name in event.items:
            item_id = self._slugify(item_name)
            if item_id not in state.world.entities:
                state.world.entities[item_id] = Entity(type="item", name=item_name)

    def _extract_title(self, text: str) -> str:
        text = text.strip()
        return text[:30] + "…" if len(text) > 30 else text

    def _extract_items(self, text: str) -> list[str]:
        items = set()
        for m in re.finditer(r"[「『](.+?)[」』]", text):
            items.add(m.group(1))
        return [i for i in items if 2 <= len(i) <= 20]

    def _current_participants(self, state: GameState) -> list[str]:
        return list(state.characters.profiles.keys()) + ["player"]

    def _slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())[:30]
        return slug or f"item_{hash(name) % 10000}"


class FormatError(Exception):
    def __init__(self, message: str, block: NarrBlock):
        super().__init__(message)
        self.block = block