"""
# 社交记忆系统插件 (Social Memory System)

为 AI 提供完整的社交记忆能力，整合用户好感度追踪和个性化记忆管理。

## 设计理念

借鉴 `history_travel` 的历史检索能力 + `note.py` 的持久化机制，设计一个专注于**社交关系**的记忆系统：

1. **关系维度**: 按用户追踪关系发展（好感度 + 事件历史）
2. **记忆维度**: 按用户聚合关键信息（偏好、约定、兴趣）
3. **智能注入**: 根据当前上下文自动注入相关记忆
4. **灵活配置**: 提供多个配置项控制行为

## 主要功能

### 好感度系统
- 6 级关系等级（敌人 → 陌生人 → 熟人 → 朋友 → 密友 → 灵魂伴侣）
- 事件驱动的好感度变化（正面/负面/中性/危机）
- 羁绊系统解锁特殊能力

### 用户记忆
- 5 种记忆类型（偏好/信息/约定/兴趣/习惯）
- 重要性评分（0-10）
- 自动过期清理

### 智能注入
- 自动将关系状态注入 AI 上下文
- 自动注入用户记忆
- 可配置的注入数量和阈值

## 使用方法

此插件主要由 AI 在后台自动使用。例如：
- 当用户表达感谢时，AI 记录好感度事件
- 当用户提到偏好时，AI 自动提取并存储记忆
- AI 根据当前关系状态调整对话风格

## 配置说明

在 `nekro-agent.yaml` 中配置：

```yaml
plugins:
  social_memory:
    # 记忆保留天数
    RETENTION_DAYS: 30
    # 注入到提示的最大记忆数
    MAX_INJECTED_MEMORIES: 5
    # 最小重要性分数
    MIN_IMPORTANCE_SCORE: 5
    # 默认初始好感度
    DEFAULT_AFFECTION: 0
    # 启用羁绊系统
    ENABLE_BOND_SYSTEM: true
```

## 沙盒方法

### 好感度相关
| 方法 | 类型 | 描述 |
|------|------|------|
| `获取关系状态` | TOOL | 查询用户好感度和关系等级 |
| `记录关系事件` | BEHAVIOR | 记录好感度变化事件 |
| `获取互动历史` | TOOL | 查看关系发展历史 |
| `获取羁绊信息` | TOOL | 查看羁绊解锁进度 |

### 用户记忆相关
| 方法 | 类型 | 描述 |
|------|------|------|
| `记录用户记忆` | BEHAVIOR | 记录用户特定信息 |
| `查询用户记忆` | TOOL | 按条件查询记忆 |
| `搜索用户记忆` | TOOL | 关键词搜索记忆 |
| `获取用户摘要` | TOOL | 获取用户摘要统计 |

### 聚合功能
| 方法 | 类型 | 描述 |
|------|------|------|
| `获取用户档案` | AGENT | 整合生成用户档案 |

## 事件类型

### 关系事件 (affection_events)
- **positive**: 正面事件（感谢、赞扬等）
- **negative**: 负面事件（批评、不满等）
- **neutral**: 中性事件（日常对话等）
- **crisis**: 危机事件（一起面对困难）

### 记忆类型 (memory_types)
- **preference**: 用户偏好
- **personal_info**: 个人信息
- **commitment**: 承诺/约定
- **interest**: 兴趣话题
- **habit**: 行为习惯
"""

import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from nekro_agent.api import core, i18n, schemas
from nekro_agent.api.message import ChatMessage
from nekro_agent.api.plugin import (
    ConfigBase,
    ExtraField,
    NekroPlugin,
    SandboxMethodType,
)
from nekro_agent.api.signal import MsgSignal

plugin = NekroPlugin(
    name="社交记忆系统",
    module_name="social_memory",
    description="整合用户好感度追踪和个性化记忆管理",
    version="0.1.0",
    author="Yuki",
    url="https://github.com/YukiAcerium/nekro-plugin-social-memory",
    i18n_name=i18n.i18n_text(
        zh_CN="社交记忆系统",
        en_US="Social Memory System",
    ),
    i18n_description=i18n.i18n_text(
        zh_CN="整合用户好感度追踪和个性化记忆管理",
        en_US="Integrated user affection tracking and personalized memory management",
    ),
)


# ============================================================================
# 配置 (Configuration)
# ============================================================================

class AffectionTier(str, Enum):
    """关系等级枚举"""
    ENEMY = "enemy"           # 敌人 (-100 ~ -60)
    STRANGER = "stranger"     # 陌生人 (-59 ~ -20)
    ACQUAINTANCE = "acquaintance"  # 熟人 (-19 ~ 10)
    FRIEND = "friend"         # 朋友 (11 ~ 50)
    CLOSE_FRIEND = "close_friend"  # 密友 (51 ~ 80)
    SOULMATE = "soulmate"     # 灵魂伴侣 (81 ~ 100)


class MemoryType(str, Enum):
    """记忆类型枚举"""
    PREFERENCE = "preference"
    PERSONAL_INFO = "personal_info"
    COMMITMENT = "commitment"
    INTEREST = "interest"
    HABIT = "habit"
    CUSTOM = "custom"


@plugin.mount_config()
class SocialMemoryConfig(ConfigBase):
    """社交记忆系统配置"""

    # 记忆配置
    RETENTION_DAYS: int = Field(
        default=30,
        title="记忆保留天数",
        description="记忆保留的天数，过期后自动清理",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="记忆保留天数",
                en_US="Memory Retention Days",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="记忆保留的天数，过期后自动清理",
                en_US="Days to retain memories before auto-cleanup",
            ),
        ).model_dump(),
    )
    MAX_INJECTED_MEMORIES: int = Field(
        default=5,
        title="最大注入记忆数",
        description="注入到提示词中的最大记忆数量",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="最大注入记忆数",
                en_US="Max Injected Memories",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="注入到提示词中的最大记忆数量",
                en_US="Maximum memories to inject into prompt",
            ),
        ).model_dump(),
    )
    MIN_IMPORTANCE_SCORE: int = Field(
        default=5,
        title="最小重要性分数",
        description="只有达到此分数的记忆才会被注入（0-10）",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="最小重要性分数",
                en_US="Min Importance Score",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="只有达到此分数的记忆才会被注入（0-10）",
                en_US="Minimum importance score for injection (0-10)",
            ),
        ).model_dump(),
    )

    # 好感度配置
    DEFAULT_AFFECTION: int = Field(
        default=0,
        title="默认好感度",
        description="新用户的初始好感度值（-100 到 100）",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="默认好感度",
                en_US="Default Affection",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="新用户的初始好感度值（-100 到 100）",
                en_US="Initial affection for new users (-100 to 100)",
            ),
        ).model_dump(),
    )
    MAX_HISTORY_EVENTS: int = Field(
        default=20,
        title="最大历史事件数",
        description="每个用户保留的最大关系事件数量",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="最大历史事件数",
                en_US="Max History Events",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="每个用户保留的最大关系事件数量",
                en_US="Max events to keep per user",
            ),
        ).model_dump(),
    )
    ENABLE_BOND_SYSTEM: bool = Field(
        default=True,
        title="启用羁绊系统",
        description="是否启用羁绊解锁功能",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="启用羁绊系统",
                en_US="Enable Bond System",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="是否启用羁绊系统",
                en_US="Enable bond unlock features",
            ),
        ).model_dump(),
    )

    # 提示注入配置
    AFFECTION_PROMPT_LIMIT: int = Field(
        default=3,
        title="提示注入事件数",
        description="注入到提示词中的最近事件数量",
        json_schema_extra=ExtraField(
            i18n_title=i18n.i18n_text(
                zh_CN="提示注入事件数",
                en_US="Affection Prompt Limit",
            ),
            i18n_description=i18n.i18n_text(
                zh_CN="注入到提示词中的最近事件数量",
                en_US="Recent events to inject into prompt",
            ),
        ).model_dump(),
    )


# 获取配置
config = plugin.get_config(SocialMemoryConfig)
store = plugin.store


# ============================================================================
# 数据模型 (Data Models)
# ============================================================================

class AffectionEvent(BaseModel):
    """关系事件"""
    timestamp: int
    change_amount: int
    event_type: str  # positive, negative, neutral, crisis
    description: str
    context: Optional[str] = None

    @classmethod
    def create(
        cls,
        change_amount: int,
        event_type: str,
        description: str,
        context: Optional[str] = None,
    ) -> "AffectionEvent":
        return cls(
            timestamp=int(time.time()),
            change_amount=change_amount,
            event_type=event_type,
            description=description,
            context=context,
        )


class BondStatus(BaseModel):
    """羁绊状态"""
    bond_id: str
    unlocked: bool = False
    unlock_time: int = 0

    @classmethod
    def create(cls, bond_id: str) -> "BondStatus":
        return cls(bond_id=bond_id)


class UserAffection(BaseModel):
    """用户好感度数据"""
    user_id: str
    affection_value: int = 0
    total_positive: int = 0
    total_negative: int = 0
    first_met_time: int = 0
    last_interaction_time: int = 0
    events: List[AffectionEvent] = []
    bonds: Dict[str, BondStatus] = {}

    @classmethod
    def create(
        cls,
        user_id: str,
        initial_affection: int = 0,
    ) -> "UserAffection":
        now = int(time.time())
        return cls(
            user_id=user_id,
            affection_value=initial_affection,
            first_met_time=now,
            last_interaction_time=now,
        )

    def add_event(self, event: AffectionEvent, max_events: int = 20) -> None:
        self.events.append(event)
        self.events = self.events[-max_events:]
        self.last_interaction_time = event.timestamp
        if event.change_amount > 0:
            self.total_positive += event.change_amount
        elif event.change_amount < 0:
            self.total_negative += abs(event.change_amount)

    def get_tier(self) -> AffectionTier:
        value = self.affection_value
        if value >= 81:
            return AffectionTier.SOULMATE
        elif value >= 51:
            return AffectionTier.CLOSE_FRIEND
        elif value >= 11:
            return AffectionTier.FRIEND
        elif value >= -19:
            return AffectionTier.ACQUAINTANCE
        elif value >= -59:
            return AffectionTier.STRANGER
        return AffectionTier.ENEMY

    def get_unlocked_bonds(self) -> List[str]:
        return [bid for bid, status in self.bonds.items() if status.unlocked]


class UserMemory(BaseModel):
    """用户记忆"""
    memory_id: str
    memory_type: str
    content: str
    importance: int = 5
    source_chat_key: str
    created_at: int
    expires_at: int
    tags: List[str] = []

    @classmethod
    def create(
        cls,
        memory_id: str,
        memory_type: str,
        content: str,
        source_chat_key: str,
        importance: int = 5,
        retention_days: int = 30,
        tags: Optional[List[str]] = None,
    ) -> "UserMemory":
        now = int(time.time())
        return cls(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            importance=max(0, min(10, importance)),
            source_chat_key=source_chat_key,
            created_at=now,
            expires_at=now + retention_days * 24 * 60 * 60,
            tags=tags or [],
        )

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class SocialData(BaseModel):
    """用户社交数据（好感度 + 记忆）"""
    affection: UserAffection
    memories: Dict[str, UserMemory] = {}

    @classmethod
    def create(cls, user_id: str, initial_affection: int = 0) -> "SocialData":
        return cls(
            affection=UserAffection.create(user_id, initial_affection),
            memories={},
        )


# ============================================================================
# 预定义羁绊 (Predefined Bonds)
# ============================================================================

BOND_DEFINITIONS = {
    "first_meet": {"name": "初次相遇", "condition": "always"},
    "shared_laugh": {"name": "欢笑共鸣", "condition": "event_count_positive >= 5"},
    "deep_conversation": {"name": "深入交流", "condition": "event_count_positive >= 10"},
    "trusted_confidant": {"name": "信赖倾诉", "condition": "event_count_positive >= 20"},
    "storm_together": {"name": "共渡难关", "condition": "event_type_crisis >= 3"},
    "heart_to_heart": {"name": "心心相印", "condition": "affection >= 80"},
}


# ============================================================================
# 存储操作 (Storage Operations)
# ============================================================================

def generate_id(prefix: str, user_id: str, content: str) -> str:
    """生成唯一ID"""
    import hashlib
    content_hash = hashlib.md5(f"{user_id}:{content}:{time.time()}".encode()).hexdigest()[:12]
    return f"{prefix}_{content_hash}"


async def get_social_data(user_id: str) -> SocialData:
    """获取用户社交数据"""
    data = await store.get(user_key=user_id, store_key="social_data")
    if data:
        return SocialData.model_validate_json(data)
    return SocialData.create(user_id, config.DEFAULT_AFFECTION)


async def save_social_data(user_id: str, data: SocialData) -> None:
    """保存用户社交数据"""
    await store.set(
        user_key=user_id,
        store_key="social_data",
        value=data.model_dump_json(),
    )


# ============================================================================
# 提示词注入 (Prompt Injection)
# ============================================================================

@plugin.mount_prompt_inject_method("social_memory_prompt_inject")
async def social_memory_prompt_inject(_ctx: schemas.AgentCtx) -> str:
    """社交记忆提示注入

    注意：对于提示注入方法，我们使用 chat_key 作为用户标识。
    对于私聊，chat_key 包含用户信息；对于群聊，会返回当前频道的整体状态。
    如果需要针对特定用户，请使用沙盒方法。
    """
    # 使用 chat_key 作为用户标识
    user_id = _ctx.chat_key
    social_data = await get_social_data(user_id)

    lines = ["## 社交记忆 (Social Memory)"]

    # 关系状态
    tier = social_data.affection.get_tier()
    tier_names = {
        AffectionTier.ENEMY: "敌人",
        AffectionTier.STRANGER: "陌生人",
        AffectionTier.ACQUAINTANCE: "熟人",
        AffectionTier.FRIEND: "朋友",
        AffectionTier.CLOSE_FRIEND: "密友",
        AffectionTier.SOULMATE: "灵魂伴侣",
    }
    lines.append(f"- 关系: [{tier_names[tier]}] 好感度: {social_data.affection.affection_value}/100")

    # 最近事件
    recent_events = social_data.affection.events[-config.AFFECTION_PROMPT_LIMIT:]
    if recent_events:
        lines.append("\n### 最近互动:")
        for event in recent_events:
            emoji = "😊" if event.change_amount > 0 else ("😔" if event.change_amount < 0 else "💬")
            time_str = time.strftime("%m-%d %H:%M", time.gmtime(event.timestamp))
            lines.append(f"- {emoji} [{time_str}] {event.description}")

    # 用户记忆
    valid_memories = [
        m for m in social_data.memories.values()
        if not m.is_expired() and m.importance >= config.MIN_IMPORTANCE_SCORE
    ]
    valid_memories.sort(key=lambda x: (-x.importance, -x.created_at))
    valid_memories = valid_memories[:config.MAX_INJECTED_MEMORIES]

    if valid_memories:
        lines.append("\n### 用户记忆:")
        type_names = {
            "preference": "偏好", "personal_info": "信息",
            "commitment": "约定", "interest": "兴趣", "habit": "习惯"
        }
        for mem in valid_memories:
            type_name = type_names.get(mem.memory_type, mem.memory_type)
            stars = "★" * mem.importance + "☆" * (10 - mem.importance)
            lines.append(f"- [{type_name}] {mem.content} {stars}")

    # 已解锁羁绊
    if config.ENABLE_BOND_SYSTEM:
        unlocked = social_data.affection.get_unlocked_bonds()
        if unlocked:
            lines.append("\n### 已解锁羁绊:")
            for bond_id in unlocked:
                if bond_id in BOND_DEFINITIONS:
                    lines.append(f"- {BOND_DEFINITIONS[bond_id]['name']}")

    return "\n".join(lines)


# ============================================================================
# 沙盒方法 - 好感度相关
# ============================================================================

@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="获取关系状态",
    description="查询用户当前的好感度和关系等级",
)
async def get_affection_state(
    _ctx: schemas.AgentCtx,
    user_id: str,
) -> dict:
    """Get Affection State (获取关系状态)"""
    social_data = await get_social_data(user_id)
    tier = social_data.affection.get_tier()

    return {
        "user_id": user_id,
        "affection_value": social_data.affection.affection_value,
        "tier": tier.value,
        "tier_name": {
            AffectionTier.ENEMY: "敌人",
            AffectionTier.STRANGER: "陌生人",
            AffectionTier.ACQUAINTANCE: "熟人",
            AffectionTier.FRIEND: "朋友",
            AffectionTier.CLOSE_FRIEND: "密友",
            AffectionTier.SOULMATE: "灵魂伴侣",
        }[tier],
        "total_positive": social_data.affection.total_positive,
        "total_negative": social_data.affection.total_negative,
        "unlocked_bonds": social_data.affection.get_unlocked_bonds(),
    }


@plugin.mount_sandbox_method(
    SandboxMethodType.BEHAVIOR,
    name="记录关系事件",
    description="记录一次影响好感度的事件",
)
async def record_affection_event(
    _ctx: schemas.AgentCtx,
    user_id: str,
    change_amount: int,
    event_type: str,
    description: str,
    context: Optional[str] = None,
) -> dict:
    """Record Affection Event (记录关系事件)"""
    change_amount = max(-20, min(20, change_amount))
    social_data = await get_social_data(user_id)

    old_tier = social_data.affection.get_tier()

    event = AffectionEvent.create(change_amount, event_type, description, context)
    social_data.affection.add_event(event, config.MAX_HISTORY_EVENTS)
    social_data.affection.affection_value = max(-100, min(100, social_data.affection.affection_value + change_amount))

    # 检查羁绊解锁
    new_tier = social_data.affection.get_tier()
    unlocked_bonds = []

    if config.ENABLE_BOND_SYSTEM:
        for bond_id, bond_def in BOND_DEFINITIONS.items():
            if bond_id not in social_data.affection.bonds:
                social_data.affection.bonds[bond_id] = BondStatus.create(bond_id)

            status = social_data.affection.bonds[bond_id]
            if not status.unlocked:
                should_unlock = False
                aff = social_data.affection

                if bond_def["condition"] == "always":
                    should_unlock = True
                elif bond_def["condition"] == "affection >= 80":
                    should_unlock = aff.affection_value >= 80
                elif bond_def["condition"] == "event_count_positive >= 5":
                    should_unlock = aff.total_positive >= 5
                elif bond_def["condition"] == "event_count_positive >= 10":
                    should_unlock = aff.total_positive >= 10
                elif bond_def["condition"] == "event_count_positive >= 20":
                    should_unlock = aff.total_positive >= 20
                elif bond_def["condition"] == "event_type_crisis >= 3":
                    crisis_count = sum(1 for e in aff.events if e.event_type == "crisis" and e.change_amount > 0)
                    should_unlock = crisis_count >= 3

                if should_unlock:
                    status.unlocked = True
                    status.unlock_time = int(time.time())
                    unlocked_bonds.append(bond_id)

    await save_social_data(user_id, social_data)

    return {
        "success": True,
        "new_affection": social_data.affection.affection_value,
        "tier_changed": old_tier != new_tier,
        "new_tier": new_tier.value,
        "unlocked_bonds": unlocked_bonds,
    }


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="获取互动历史",
    description="获取用户的关系发展历史",
)
async def get_interaction_history(
    _ctx: schemas.AgentCtx,
    user_id: str,
    limit: int = 10,
) -> list:
    """Get Interaction History (获取互动历史)"""
    social_data = await get_social_data(user_id)
    return [
        {
            "timestamp": e.timestamp,
            "change_amount": e.change_amount,
            "event_type": e.event_type,
            "description": e.description,
            "context": e.context,
        }
        for e in social_data.affection.events[-limit:]
    ]


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="获取羁绊信息",
    description="查询用户的羁绊状态和进度",
)
async def get_bond_info(
    _ctx: schemas.AgentCtx,
    user_id: str,
) -> dict:
    """Get Bond Info (获取羁绊信息)"""
    social_data = await get_social_data(user_id)

    bonds_data = []
    aff = social_data.affection

    for bond_id, bond_def in BOND_DEFINITIONS.items():
        if bond_id not in aff.bonds:
            aff.bonds[bond_id] = BondStatus.create(bond_id)

        status = aff.bonds[bond_id]

        # 计算进度
        progress = 0.0
        if bond_def["condition"] == "always":
            progress = 1.0
        elif bond_def["condition"] == "affection >= 80":
            progress = min(1.0, aff.affection_value / 80)
        elif bond_def["condition"] == "event_count_positive >= 5":
            progress = min(1.0, aff.total_positive / 5)
        elif bond_def["condition"] == "event_count_positive >= 10":
            progress = min(1.0, aff.total_positive / 10)
        elif bond_def["condition"] == "event_count_positive >= 20":
            progress = min(1.0, aff.total_positive / 20)
        elif bond_def["condition"] == "event_type_crisis >= 3":
            crisis_count = sum(1 for e in aff.events if e.event_type == "crisis" and e.change_amount > 0)
            progress = min(1.0, crisis_count / 3)

        bonds_data.append({
            "bond_id": bond_id,
            "name": bond_def["name"],
            "unlocked": status.unlocked,
            "progress": round(progress * 100, 1),
        })

    return {
        "total_bonds": len(BOND_DEFINITIONS),
        "unlocked_count": sum(1 for b in bonds_data if b["unlocked"]),
        "bonds": bonds_data,
    }


# ============================================================================
# 沙盒方法 - 用户记忆相关
# ============================================================================

@plugin.mount_sandbox_method(
    SandboxMethodType.BEHAVIOR,
    name="记录用户记忆",
    description="记录用户的特定信息",
)
async def record_user_memory(
    _ctx: schemas.AgentCtx,
    user_id: str,
    memory_type: str,
    content: str,
    importance: int = 5,
    tags: Optional[List[str]] = None,
) -> dict:
    """Record User Memory (记录用户记忆)"""
    memory_id = generate_id("mem", user_id, content)
    social_data = await get_social_data(user_id)

    # 检查是否已存在
    for mem in social_data.memories.values():
        if mem.content == content:
            if importance > mem.importance:
                mem.importance = importance
            await save_social_data(user_id, social_data)
            return {"memory_id": mem.memory_id, "success": True, "message": "已更新"}

    memory = UserMemory.create(
        memory_id=memory_id,
        memory_type=memory_type,
        content=content,
        source_chat_key=_ctx.chat_key,
        importance=importance,
        retention_days=config.RETENTION_DAYS,
        tags=tags,
    )
    social_data.memories[memory_id] = memory
    await save_social_data(user_id, social_data)

    return {"memory_id": memory_id, "success": True, "message": "已记录"}


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="查询用户记忆",
    description="按条件查询用户记忆",
)
async def query_user_memory(
    _ctx: schemas.AgentCtx,
    user_id: str,
    memory_types: Optional[List[str]] = None,
    min_importance: int = 0,
    limit: int = 20,
) -> list:
    """Query User Memory (查询用户记忆)"""
    social_data = await get_social_data(user_id)
    now = time.time()

    results = []
    for mem in social_data.memories.values():
        if mem.expires_at < now:
            continue
        if memory_types and mem.memory_type not in memory_types:
            continue
        if mem.importance < min_importance:
            continue
        results.append(mem)

    results.sort(key=lambda x: (-x.importance, -x.created_at))
    return [
        {
            "memory_id": m.memory_id,
            "memory_type": m.memory_type,
            "content": m.content,
            "importance": m.importance,
            "created_at": m.created_at,
            "tags": m.tags,
        }
        for m in results[:limit]
    ]


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="搜索用户记忆",
    description="搜索用户记忆",
)
async def search_user_memory(
    _ctx: schemas.AgentCtx,
    user_id: str,
    keyword: str,
    memory_types: Optional[List[str]] = None,
    limit: int = 10,
) -> list:
    """Search User Memory (搜索用户记忆)"""
    social_data = await get_social_data(user_id)
    now = time.time()
    results = []

    for mem in social_data.memories.values():
        if mem.expires_at < now:
            continue
        if memory_types and mem.memory_type not in memory_types:
            continue
        if keyword.lower() in mem.content.lower():
            results.append(mem)
        if len(results) >= limit:
            break

    return [{"memory_id": m.memory_id, "memory_type": m.memory_type, "content": m.content, "importance": m.importance} for m in results]


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="获取用户摘要",
    description="获取用户社交数据的摘要统计",
)
async def get_user_summary(
    _ctx: schemas.AgentCtx,
    user_id: str,
) -> dict:
    """Get User Summary (获取用户摘要)"""
    social_data = await get_social_data(user_id)

    by_type = {"preference": 0, "personal_info": 0, "commitment": 0, "interest": 0, "habit": 0, "custom": 0}
    now = time.time()
    for mem in social_data.memories.values():
        if mem.expires_at >= now:
            by_type[mem.memory_type] = by_type.get(mem.memory_type, 0) + 1

    return {
        "total_memories": len(social_data.memories),
        "by_type": by_type,
        "affection": social_data.affection.affection_value,
        "tier": social_data.affection.get_tier().value,
        "total_events": len(social_data.affection.events),
        "unlocked_bonds": social_data.affection.get_unlocked_bonds(),
    }


# ============================================================================
# 沙盒方法 - 聚合功能
# ============================================================================

@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="获取用户档案",
    description="整合生成用户档案",
)
async def get_user_profile(
    _ctx: schemas.AgentCtx,
    user_id: str,
) -> str:
    """Get User Profile (获取用户档案)"""
    social_data = await get_social_data(user_id)
    aff = social_data.affection

    lines = [f"## 用户 {user_id} 档案", ""]

    # 关系状态
    tier = aff.get_tier()
    tier_names = {
        AffectionTier.ENEMY: "敌人",
        AffectionTier.STRANGER: "陌生人",
        AffectionTier.ACQUAINTANCE: "熟人",
        AffectionTier.FRIEND: "朋友",
        AffectionTier.CLOSE_FRIEND: "密友",
        AffectionTier.SOULMATE: "灵魂伴侣",
    }
    lines.append(f"### 关系状态")
    lines.append(f"- 当前关系: {tier_names[tier]}")
    lines.append(f"- 好感度: {aff.affection_value}/100")
    lines.append(f"- 累计正面: {aff.total_positive}, 负面: {aff.total_negative}")
    lines.append("")

    # 用户记忆
    now = time.time()
    valid_memories = [m for m in social_data.memories.values() if m.expires_at >= now]
    valid_memories.sort(key=lambda x: (-x.importance, -x.created_at))

    if valid_memories:
        lines.append("### 用户记忆")
        type_names = {"preference": "偏好", "personal_info": "信息", "commitment": "约定", "interest": "兴趣", "habit": "习惯"}
        for mem in valid_memories[:10]:
            type_name = type_names.get(mem.memory_type, mem.memory_type)
            stars = "★" * mem.importance + "☆" * (10 - mem.importance)
            lines.append(f"- [{type_name}] {mem.content} {stars}")
        lines.append("")

    # 羁绊
    unlocked = aff.get_unlocked_bonds()
    if unlocked:
        lines.append("### 已解锁羁绊")
        for bond_id in unlocked:
            if bond_id in BOND_DEFINITIONS:
                lines.append(f"- {BOND_DEFINITIONS[bond_id]['name']}")

    return "\n".join(lines)


# ============================================================================
# 自动提取 (Auto-Extract)
# ============================================================================

EXTRACT_PATTERNS = {
    "preference": [r"我喜欢", r"我习惯", r"我讨厌", r"I (?:prefer|like|enjoy|hate)"],
    "personal_info": [r"我的邮箱", r"我的电话", r"我的名字", r"My (?:email|phone|name)"],
    "commitment": [r"我会", r"记得", r"别忘了", r"待会儿", r"I will|remember to"],
    "interest": [r"对.*感兴趣", r"喜欢.*研究", r"热衷", r"intereste?d in"],
    "habit": [r"通常", r"一般", r"经常", r"usually|often"],
}


@plugin.mount_on_user_message()
async def auto_extract(
    _ctx: schemas.AgentCtx,
    message: ChatMessage,
) -> MsgSignal:
    """从用户消息中自动提取记忆"""
    content = message.content_text
    if not content:
        return MsgSignal.CONTINUE

    # 使用 message.sender_id 作为用户标识
    user_id = message.sender_id
    if not user_id:
        return MsgSignal.CONTINUE

    import re
    for mem_type, patterns in EXTRACT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                default_importance = {"personal_info": 10, "commitment": 7, "preference": 6, "interest": 5, "habit": 4}.get(mem_type, 5)
                await record_user_memory(
                    _ctx=_ctx,
                    user_id=user_id,
                    memory_type=mem_type,
                    content=content[:200],
                    importance=default_importance - 2,
                )
                break

    return MsgSignal.CONTINUE


# ============================================================================
# 清理
# ============================================================================

@plugin.mount_cleanup_method()
async def cleanup():
    """清理插件资源"""
    core.logger.info("社交记忆系统插件已清理")
