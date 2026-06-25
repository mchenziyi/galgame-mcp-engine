"""
响应构建器 — 解析客户端提交的叙事文本，校验格式，组装结构化输出。
"""
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Choice:
    key: str
    text: str


@dataclass
class NarrBlock:
    scene: str = ""
    sound: str = ""
    narrative: str = ""
    choices: list[Choice] = field(default_factory=list)


# 区块标记
_BLOCKS = [
    ("scene",     "【📖 场景速写】"),
    ("sound",     "【🎧 环境音效】"),
    ("narrative", "【💬 剧情推进 & 对白】"),
    ("choices",   "【🎮 行动指令】"),
]


def _to_simplified(text: str) -> str:
    """将文本中的繁体字替换为简体。优先使用 zhconv 库，不可用时用内建映射。"""
    try:
        from zhconv import convert
        return convert(text, "zh-cn")
    except ImportError:
        return _fallback_fan2jian(text)


def _fallback_fan2jian(text: str) -> str:
    """内建繁体→简体映射。覆盖 galgame 叙事常见字。"""
    mapping = {
        "為": "为", "會": "会", "個": "个", "們": "们", "時": "时", "說": "说",
        "過": "过", "來": "来", "對": "对", "開": "开", "關": "关", "門": "门",
        "後": "后", "麼": "么", "於": "于", "與": "与", "從": "从", "這": "这",
        "著": "着", "當": "当", "還": "还", "進": "进", "沒": "没", "給": "给",
        "讓": "让", "問": "问", "間": "间", "樣": "样", "經": "经", "現": "现",
        "實": "实", "點": "点", "業": "业", "書": "书", "寫": "写", "見": "见",
        "聽": "听", "風": "风", "電": "电", "車": "车", "頭": "头", "臉": "脸",
        "聲": "声", "氣": "气", "動": "动", "邊": "边", "國": "国", "學": "学",
        "覺": "觉", "愛": "爱", "樹": "树", "葉": "叶", "鳥": "鸟", "魚": "鱼",
        "飯": "饭", "飲": "饮", "湯": "汤", "買": "买", "賣": "卖", "錢": "钱",
        "輕": "轻", "靜": "静", "應": "应", "該": "该", "願": "愿", "總": "总",
        "確": "确", "認": "认", "話": "话", "請": "请", "謝": "谢", "誰": "谁",
        "張": "张", "強": "强", "難": "难", "變": "变", "遠": "远", "處": "处",
        "備": "备", "復": "复", "劃": "划", "團": "团", "隊": "队", "機": "机",
        "陽": "阳", "陰": "阴", "雲": "云", "員": "员", "廠": "厂", "廣": "广",
        "醫": "医", "護": "护", "選": "选", "際": "际", "樂": "乐", "樓": "楼",
        "夠": "够", "採": "采", "購": "购", "籃": "篮", "餅": "饼", "廳": "厅",
        "轉": "转", "離": "离", "場": "场", "體": "体", "並": "并", "髮": "发",
        "麵": "面", "妳": "你", "週": "周", "臺": "台", "鬆": "松", "乾": "干",
        "鬱": "郁", "託": "托", "捨": "舍", "歷": "历", "曆": "历", "鐘": "钟",
        "闆": "板", "誌": "志", "範": "范", "餘": "余", "併": "并", "嚐": "尝",
        "曬": "晒", "擺": "摆", "擁": "拥", "擡": "抬", "換": "换", "揚": "扬",
        "揮": "挥", "搖": "摇", "擇": "择", "擋": "挡", "擠": "挤", "據": "据",
        "掃": "扫", "掛": "挂", "擴": "扩", "擾": "扰", "擊": "击", "擔": "担",
        "驚": "惊", "驗": "验", "馬": "马", "飛": "飞", "養": "养", "黃": "黄",
        "歡": "欢", "條": "条", "殺": "杀", "殘": "残", "淚": "泪", "溫": "温",
        "準": "准", "滿": "满", "漸": "渐", "潛": "潜", "灣": "湾", "濕": "湿",
        "無": "无", "煙": "烟", "燒": "烧", "燙": "烫", "營": "营", "爭": "争",
        "爾": "尔", "牆": "墙", "獨": "独", "獲": "获", "環": "环", "產": "产",
        "畫": "画", "儘": "尽", "監": "监", "盤": "盘", "睜": "睁", "瞭": "了",
        "碼": "码", "礎": "础", "禮": "礼", "禍": "祸", "積": "积", "稱": "称",
        "穩": "稳", "筆": "笔", "簡": "简", "紅": "红", "約": "约", "紙": "纸",
        "級": "级", "細": "细", "終": "终", "結": "结", "絕": "绝", "統": "统",
        "絲": "丝", "綠": "绿", "緊": "紧", "線": "线", "編": "编", "緣": "缘",
        "繞": "绕", "續": "续", "繪": "绘", "繼": "继", "歸": "归", "錄": "录",
        "鐵": "铁", "鏡": "镜", "長": "长", "閃": "闪", "閉": "闭", "開": "开",
        "閱": "阅", "際": "际", "隨": "随", "隱": "隐", "雙": "双", "雜": "杂",
        "響": "响", "頂": "顶", "順": "顺", "預": "预", "頓": "顿", "領": "领",
        "頻": "频", "題": "题", "額": "额", "顧": "顾", "養": "养", "驗": "验",
        "體": "体", "鬥": "斗", "麽": "么", "黃": "黄",
    }
    result = []
    for ch in text:
        result.append(mapping.get(ch, ch))
    return "".join(result)


def parse(raw: str) -> NarrBlock:
    """解析四段格式。繁体→简体自动转换。"""
    raw = _to_simplified(raw)
    block = NarrBlock()

    positions: list[tuple[int, str, str]] = []
    for field_name, marker in _BLOCKS:
        for m in re.finditer(re.escape(marker), raw):
            positions.append((m.start(), field_name, marker))

    positions.sort()

    for i, (start, field_name, marker) in enumerate(positions):
        content_start = start + len(marker)
        content_end = positions[i + 1][0] if i + 1 < len(positions) else len(raw)
        content = raw[content_start:content_end].strip()

        if field_name == "choices":
            block.choices = _parse_choices(content)
        else:
            setattr(block, field_name, content)

    return block


def _parse_choices(text: str) -> list[Choice]:
    choices: list[Choice] = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"([A-D])[.、．]\s*(.+)", line)
        if m:
            choices.append(Choice(key=m.group(1), text=m.group(2).strip()))
    return choices


def validate(block: NarrBlock) -> list[str]:
    errors: list[str] = []
    if not block.scene.strip():
        errors.append("【📖 场景速写】为空")
    if not block.sound.strip():
        errors.append("【🎧 环境音效】为空")
    if not block.narrative.strip():
        errors.append("【💬 剧情推进 & 对白】为空")
    if len(block.choices) < 3:
        errors.append(f"【🎮 行动指令】至少需要 A/B/C 三个选项，当前 {len(block.choices)} 个")
    return errors


def to_dict(block: NarrBlock) -> dict[str, Any]:
    return {
        "scene": block.scene,
        "sound": block.sound,
        "narrative": block.narrative,
        "choices": [{"key": c.key, "text": c.text} for c in block.choices],
    }
