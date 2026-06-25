"""
状态管理层 — 读写 .game/ 下的 5 个 JSON，Pydantic 校验，ID 生成。
"""
import json
import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


# ── Pydantic 模型 ──────────────────────────────────────────

class Entity(BaseModel):
    type: str
    name: str

class Relation(BaseModel):
    from_: str = Field(alias="from")
    to: str
    type: str

class WorldState(BaseModel):
    version: int = Field(alias="_version", default=1)
    entities: dict[str, Entity] = {}
    relations: list[Relation] = []

class Relationship(BaseModel):
    trust: int = 0
    romance: int = 0
    dependency: int = 0
    hostility: int = 0

class CharacterProfile(BaseModel):
    personality: str = ""
    goals: list[str] = []
    secrets: list[str] = []
    important_memories: list[str] = []
    current_emotion: str = ""

class CharacterState(BaseModel):
    version: int = Field(alias="_version", default=1)
    profiles: dict[str, CharacterProfile] = {}
    relationships: dict[str, dict[str, Relationship]] = Field(alias="_relationships", default_factory=dict)

class Foreshadowing(BaseModel):
    id: str
    content: str
    created_day: int
    importance: str = "side"
    planned_arc: str = ""
    planned_event: str = ""

class NarrativeState(BaseModel):
    active_mysteries: list[str] = []
    resolved_mysteries: list[str] = []
    foreshadowing_pool: list[Foreshadowing] = []
    unresolved_questions: list[str] = []
    future_payoffs: list[str] = []

class NarrativeBudget(BaseModel):
    max_active_mysteries: int = 5
    max_active_foreshadowing: int = 10
    max_core_characters: int = 7

class NPCSchedule(BaseModel):
    morning: str = ""
    afternoon: str = ""
    evening: str = ""

class BackgroundEvent(BaseModel):
    id: str
    trigger_day: int
    description: str
    affected_entities: list[str] = []

class StoryState(BaseModel):
    version: int = Field(alias="_version", default=1)
    mode: str = "game"
    current_day: int = 1
    current_arc: str = "ARC_001"
    current_arc_name: str = "日常篇"
    current_phase: str = "Phase1"
    current_route: str = "Common"
    main_quest: str | None = None
    sub_quests: list[str] = []
    world_age: int = 0
    play_sessions: int = 0
    major_turning_points: list[str] = []
    narrative: NarrativeState = Field(default_factory=NarrativeState)
    narrative_budget: NarrativeBudget = Field(default_factory=NarrativeBudget)
    npc_schedules: dict[str, NPCSchedule] = {}
    background_events: list[BackgroundEvent] = []
    offscreen_changes: list[str] = []

class TimelineEvent(BaseModel):
    id: str
    arc: str
    title: str
    participants: list[str] = []
    items: list[str] = []
    day: int = 1
    importance: str = "side"

class SummarizedHistory(BaseModel):
    period: str
    arc: str
    summary: str

class TimelineState(BaseModel):
    version: int = Field(alias="_version", default=1)
    active_timeline: list[TimelineEvent] = []
    summarized_history: list[SummarizedHistory] = []
    archived_events: list[str] = []

class MetaState(BaseModel):
    version: int = Field(alias="_version", default=1)
    next_event_id: int = 1
    next_arc_id: int = 2
    next_foreshadowing_id: int = 1
    next_background_id: int = 1

class GameState(BaseModel):
    meta: MetaState
    world: WorldState
    characters: CharacterState
    story: StoryState
    timeline: TimelineState


# ── StateManager ───────────────────────────────────────────

class StateManager:
    def __init__(self, game_dir: str = ".game"):
        self.dir = Path(game_dir)

    # ── 加载 ──────────────────────────────────────────

    def load_all(self) -> GameState:
        return GameState(
            meta=self._load("meta.json", MetaState),
            world=self._load("world.json", WorldState),
            characters=self._load_characters(),
            story=self._load("story.json", StoryState),
            timeline=self._load("timeline.json", TimelineState),
        )

    def _load[T: BaseModel](self, filename: str, model: type[T]) -> T:
        path = self.dir / filename
        if not path.exists():
            return model()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return model(**data)

    def _load_characters(self) -> CharacterState:
        path = self.dir / "characters.json"
        if not path.exists():
            return CharacterState()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        version = data.get("_version", 1)
        relationships_raw = data.get("_relationships", {})

        profiles = {
            k: CharacterProfile(**v)
            for k, v in data.items()
            if k not in ("_version", "_relationships")
        }
        rels = {
            a: {b: Relationship(**r) for b, r in inner.items()}
            for a, inner in relationships_raw.items()
        }
        return CharacterState(version=version, profiles=profiles, relationships=rels)

    # ── 保存 ──────────────────────────────────────────

    def save(self, state: GameState) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._save("meta.json", state.meta)
        self._save("world.json", state.world)
        self._save_characters(state.characters)
        self._save("story.json", state.story)
        self._save("timeline.json", state.timeline)

    def _save(self, filename: str, model: BaseModel) -> None:
        path = self.dir / filename
        data = json.loads(model.model_dump_json(by_alias=True, exclude_none=True))
        # Pydantic dump 用 alias，但 _version 等需要原样
        if "_version" not in data:
            data["_version"] = 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_characters(self, state: CharacterState) -> None:
        path = self.dir / "characters.json"
        data: dict[str, Any] = {"_version": state.version}
        for char_id, profile in state.profiles.items():
            data[char_id] = json.loads(profile.model_dump_json(exclude_none=True))
        data["_relationships"] = json.loads(
            json.dumps(state.relationships, default=lambda o: o.model_dump(), ensure_ascii=False)
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── ID 生成 ───────────────────────────────────────

    def next_id(self, state: GameState, kind: str) -> str:
        """原子取号：读 meta → 取对应字段 → +1 → 写回 → 返回格式化的 ID。"""
        mapping = {
            "event": ("next_event_id", "EVT"),
            "arc": ("next_arc_id", "ARC"),
            "foreshadowing": ("next_foreshadowing_id", "FS"),
            "background": ("next_background_id", "BG"),
        }
        field, prefix = mapping[kind]
        current = getattr(state.meta, field)
        setattr(state.meta, field, current + 1)
        self._save("meta.json", state.meta)
        return f"{prefix}_{current:03d}"

    # ── 初始化 ────────────────────────────────────────

    def init_default(self) -> GameState:
        return GameState(
            meta=MetaState(next_event_id=1, next_arc_id=2, next_foreshadowing_id=1, next_background_id=1),
            world=WorldState(
                entities={
                    "player": Entity(type="player", name="你"),
                    "old_apartment": Entity(type="location", name="坂の上の荘"),
                },
                relations=[
                    Relation(from_="player", to="old_apartment", type="located_in"),
                ],
            ),
            characters=CharacterState(),
            story=StoryState(),
            timeline=TimelineState(),
        )

    def is_initialized(self) -> bool:
        return (self.dir / "story.json").exists()
