# 实时一致性校验器（V3）

## 1. 设计目标

实时一致性校验器（live-consistency-validator）解决「Editor 太晚介入」的核心问题。V2 架构中，Draft 完成后才进入审校流程，此时底层错误（金额冲突、人设偏移等）已被后续章节建立在上面，修正成本极高。

**关键转变**：从「写后校验」变为「写中校验」—— Draft 输出**同时**进行一致性检查，尽早阻断结构性错误。

## 2. 校验时机

校验与 Draft 输出**并行执行**，非串行等待：

```
Draft Stream ──┬──▶ 写入章节缓存
               ├──▶ live-consistency-validator（实时）
               └──▶ 输出给用户
```

- 每个自然段/对话块输出后触发一次校验
- 校验结果附加到 Draft 元数据中，随输出一同呈现
- 不阻塞 Draft 写出流程（BLOCKER 仅警告，不暂停写入）

## 3. 校验维度（7 维）

### 3.1 金额一致性

- **检测内容**：本期出现的收入、支出、赏金、交易金额
- **冲突规则**：与之前设定的角色资产、世界经济体系、任务报酬对比
- **示例**：角色上章只剩 50 金币，本章花 1000 金币购买装备 → BLOCKER

### 3.2 战力一致性

- **检测内容**：战斗表现、技能使用、胜负结果
- **冲突规则**：与 `power_system` 中定义的战力等级、技能冷却、属性成长曲线对比
- **示例**：Lv.3 主角一击秒杀 BOSS → BLOCKER

### 3.3 时间线跳跃

- **检测内容**：时间状语、日月提及、季节变化
- **冲突规则**：与前文时间戳对比，检查是否存在未覆盖的时间段
- **示例**：第三章写到「三天后」，但第二章结尾已是「一周后」→ WARNING

### 3.4 女主称呼变化

- **检测内容**：对同一女性角色的称呼（名字、昵称、称号、关系称谓）
- **冲突规则**：与 `character_relations` 中登记的称呼一致性对比
- **示例**：本章叫「雪儿」，前文一直叫「林雪」→ BLOCKER

### 3.5 人设偏移

- **检测内容**：角色当前行为、对话风格、决策倾向
- **冲突规则**：与 `current_state` 中的性格向量、动机、当前情绪状态对比
- **示例**：冷酷男主突然热情助人且无铺垫 → WARNING

### 3.6 地点连续性

- **检测内容**：场景地理位置、地标、距离
- **冲突规则**：与 event sourcing 中的位置状态跟踪对比
- **示例**：上章在「北境雪原」，本章开头在「南部雨林」且无旅行描写 → WARNING

### 3.7 物品/能力一致性

- **检测内容**：使用或提及的物品、道具、特殊能力
- **冲突规则**：与 inventory 和能力列表中当前持有状态对比
- **示例**：使用已被销毁的「圣剑」→ BLOCKER

## 4. 校验结果分级

| 级别 | 代码 | 含义 | 对 Draft 影响 | 对应维度 |
|------|------|------|---------------|----------|
| **BLOCKER** | 🔴 | 必须立刻停写修正 | 输出告警，用户应暂停当前写作方向 | 金额、战力、称呼、物品 |
| **WARNING** | 🟡 | 标记但可继续 | Editor 审校时重点修复 | 时间线、人设、地点 |
| **INFO** | 🔵 | 记录但不影响 | 仅日志记录，供作者参考 | 所有维度的轻微偏差 |

### BLOCKER 触发条件

BLOCKER 是最高优先级，仅在以下情况触发：

1. **金额冲突**：差值超过角色总资产的 50%
2. **战力冲突**：当前战力与对手战力差超过 3 个数量级
3. **称呼变化**：同一段落内对同一角色使用不同称呼
4. **物品冲突**：使用了 inventory 中标记为「已销毁」「已丢失」「已赠出」的物品

## 5. 校验模式

### 5.1 Light 模式

- **适用范围**：Draft 高速写作阶段
- **Token 开销**：~50 tokens 每次校验
- **检测范围**：仅 BLOCKER 级别（维度 3.1、3.2、3.4、3.7 中的严重冲突）
- **行为**：不记录详细上下文，仅输出冲突摘要

### 5.2 Full 模式

- **适用范围**：Editor 审校前、章节完成后的全面检查
- **Token 开销**：~200 tokens 每次校验
- **检测范围**：全部 7 个维度，所有级别
- **行为**：记录完整上下文、冲突路径、建议修复方案

### 模式选择策略

```python
def select_validator_mode(session_state):
    if session_state.phase == "drafting" and session_state.writing_speed > 80:
        return ValidatorMode.LIGHT
    elif session_state.phase == "editing":
        return ValidatorMode.FULL
    elif session_state.phase == "drafting" and session_state.draft_progress > 0.7:
        return ValidatorMode.FULL  # 后期 Draft 自动切换 Full
    else:
        return ValidatorMode.LIGHT
```

## 6. Python 伪代码实现

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional

class ValidatorMode(Enum):
    LIGHT = auto()
    FULL = auto()

class Severity(Enum):
    BLOCKER = auto()
    WARNING = auto()
    INFO = auto()

@dataclass
class ConsistencyCheckResult:
    dimension: str          # 校验维度名称
    severity: Severity      # 级别
    message: str            # 人类可读的描述
    context: dict           # 冲突相关上下文
    fix_suggestion: str     # 建议修复方案（Full 模式）

@dataclass
class ConsistencyReport:
    results: list[ConsistencyCheckResult] = field(default_factory=list)
    mode: ValidatorMode = ValidatorMode.LIGHT

    def has_blockers(self) -> bool:
        return any(r.severity == Severity.BLOCKER for r in self.results)

    def summary(self) -> str:
        blocker_count = sum(1 for r in self.results if r.severity == Severity.BLOCKER)
        warning_count = sum(1 for r in self.results if r.severity == Severity.WARNING)
        info_count = sum(1 for r in self.results if r.severity == Severity.INFO)
        return f"🔴{blocker_count} 🟡{warning_count} 🔵{info_count}"


class LiveConsistencyValidator:
    """
    实时一致性校验器主类。
    与 DraftEngine 和 EventSourcingStore 协作。
    """

    def __init__(self, store: "EventSourcingStore", mode: ValidatorMode = ValidatorMode.LIGHT):
        self.store = store
        self.mode = mode
        self._checkers = self._register_checkers()

    def _register_checkers(self) -> dict:
        """注册所有校验函数"""
        return {
            "financial": self._check_financial_consistency,
            "combat_power": self._check_combat_power_consistency,
            "timeline": self._check_timeline_jumps,
            "character_name": self._check_character_name_consistency,
            "personality": self._check_personality_deviation,
            "location": self._check_location_continuity,
            "inventory": self._check_inventory_consistency,
        }

    def validate(self, draft_text: str, current_state: dict) -> ConsistencyReport:
        """
        对 Draft 文本执行一致性校验。

        Args:
            draft_text: 刚输出的 Draft 文本块
            current_state: 当前故事状态（角色、资产、位置等）

        Returns:
            ConsistencyReport: 校验报告
        """
        report = ConsistencyReport(mode=self.mode)

        for dim_name, checker in self._checkers.items():
            # Light 模式下跳过非 BLOCKER 维度
            if self.mode == ValidatorMode.LIGHT and dim_name in ("timeline", "personality", "location"):
                continue

            result = checker(draft_text, current_state)
            if result is not None:
                # Light 模式下只保留 BLOCKER
                if self.mode == ValidatorMode.LIGHT and result.severity != Severity.BLOCKER:
                    continue
                report.results.append(result)

        return report

    def _check_financial_consistency(self, text: str, state: dict) -> Optional[ConsistencyCheckResult]:
        """
        金额一致性校验。

        扫描文本中的金额表达，与 state.assets 对比。
        如果某笔支出超过角色总资产的 50%，标记 BLOCKER。
        """
        amounts = self._extract_amounts(text)
        if not amounts:
            return None

        total_wealth = state.get("total_wealth", 0)
        max_allowed = total_wealth * 0.5

        for amount in amounts:
            if amount > max_allowed:
                return ConsistencyCheckResult(
                    dimension="financial",
                    severity=Severity.BLOCKER,
                    message=f"支出 {amount} 超过角色总资产 {total_wealth} 的 50%",
                    context={"amount": amount, "total_wealth": total_wealth},
                    fix_suggestion=f"将支出降低至 {int(total_wealth * 0.3)} 以内，或补充收入来源",
                )
        return None

    def _check_combat_power_consistency(self, text: str, state: dict) -> Optional[ConsistencyCheckResult]:
        """
        战力一致性校验。

        检测战斗描述中的双方战力对比。
        如果主角战力与对手相差超过 3 个数量级仍打成平手，标记 BLOCKER。
        """
        fights = self._detect_combat_scenes(text)
        if not fights:
            return None

        for fight in fights:
            protag_power = state.get("protagonist_power", 1)
            opponent_power = fight.get("opponent_power", 1)
            ratio = max(protag_power, opponent_power) / min(protag_power, opponent_power)

            if ratio >= 1000:
                return ConsistencyCheckResult(
                    dimension="combat_power",
                    severity=Severity.BLOCKER,
                    message=f"战力差距极大（ratio={ratio:.1f}），结果不合理",
                    context={"protag_power": protag_power, "opponent_power": opponent_power},
                    fix_suggestion=f"调整对手战力至 {protag_power} 附近，或描写主角被碾压",
                )
        return None

    def _check_timeline_jumps(self, text: str, state: dict) -> Optional[ConsistencyCheckResult]:
        """时间线跳跃校验（Full 模式）"""
        current_time = state.get("current_timestamp")
        mentioned_time = self._extract_timestamp(text)
        if not current_time or not mentioned_time:
            return None

        gap = abs((mentioned_time - current_time).days)
        if gap > 30:  # 超过 30 天未覆盖
            return ConsistencyCheckResult(
                dimension="timeline",
                severity=Severity.WARNING,
                message=f"时间跳跃 {gap} 天，中间时间段未覆盖",
                context={"from": str(current_time), "to": str(mentioned_time), "gap_days": gap},
                fix_suggestion="补充中间 1-2 章过渡章节",
            )
        return None

    def _check_character_name_consistency(self, text: str, state: dict) -> Optional[ConsistencyCheckResult]:
        """
        女主称呼一致性校验。

        将文本中的称呼与 state.character_relations 中登记的标准称呼对比。
        同一段落内对同一角色使用不同称呼 → BLOCKER。
        """
        standard_names = state.get("character_names", {})
        for char_id, expected_name in standard_names.items():
            mentions = self._find_character_mentions(text, char_id)
            unique_names = set(mentions)
            if len(unique_names) > 1:
                return ConsistencyCheckResult(
                    dimension="character_name",
                    severity=Severity.BLOCKER,
                    message=f"角色 {char_id} 在同一段中使用多个称呼: {unique_names}",
                    context={"character_id": char_id, "used_names": list(unique_names)},
                    fix_suggestion=f"统一使用「{expected_name}」",
                )
        return None

    def _check_personality_deviation(self, text: str, state: dict) -> Optional[ConsistencyCheckResult]:
        """人设偏移校验（Full 模式）"""
        persona = state.get("personality_traits", {})
        deviations = self._detect_personality_deviation(text, persona)
        if deviations:
            return ConsistencyCheckResult(
                dimension="personality",
                severity=Severity.WARNING,
                message=f"人设偏移: {', '.join(deviations)}",
                context={"traits": persona, "deviations": deviations},
                fix_suggestion="为异常行为添加动机铺垫，或调整 current_state 的人设",
            )
        return None

    def _check_location_continuity(self, text: str, state: dict) -> Optional[ConsistencyCheckResult]:
        """地点连续性校验（Full 模式）"""
        current_location = state.get("current_location")
        mentioned_locations = self._extract_locations(text)
        if not current_location or not mentioned_locations:
            return None

        for loc in mentioned_locations:
            if not self._is_connected(current_location, loc):
                return ConsistencyCheckResult(
                    dimension="location",
                    severity=Severity.WARNING,
                    message=f"场景从「{current_location}」跳跃到「{loc}」无过渡",
                    context={"from": current_location, "to": loc},
                    fix_suggestion=f"添加旅行描写或中间场景",
                )
        return None

    def _check_inventory_consistency(self, text: str, state: dict) -> Optional[ConsistencyCheckResult]:
        """
        物品/能力一致性校验。

        扫描文本中使用的物品名称，与 state.inventory 对比。
        如果使用了标记为「已销毁」「已丢失」「已赠出」的物品 → BLOCKER。
        """
        inventory = state.get("inventory", {})
        used_items = self._extract_item_uses(text)

        for item_name in used_items:
            item_state = inventory.get(item_name)
            if item_state and item_state.get("status") in ("destroyed", "lost", "given_away"):
                return ConsistencyCheckResult(
                    dimension="inventory",
                    severity=Severity.BLOCKER,
                    message=f"使用了已{item_state['status']}的物品: {item_name}",
                    context={"item": item_name, "status": item_state["status"]},
                    fix_suggestion=f"将物品状态改回「持有」，或更换为其他可用物品",
                )
        return None

    # --- 辅助方法（伪实现） ---

    def _extract_amounts(self, text: str) -> list[float]:
        """从文本中提取所有金额表达（伪实现）"""
        # 实际实现使用正则 / regex NLP
        return []

    def _detect_combat_scenes(self, text: str) -> list[dict]:
        """检测战斗场景（伪实现）"""
        return []

    def _extract_timestamp(self, text: str):
        """提取时间戳（伪实现）"""
        return None

    def _find_character_mentions(self, text: str, char_id: str) -> list[str]:
        """查找角色提及（伪实现）"""
        return []

    def _detect_personality_deviation(self, text: str, traits: dict) -> list[str]:
        """检测人设偏移（伪实现）"""
        return []

    def _extract_locations(self, text: str) -> list[str]:
        """提取地点（伪实现）"""
        return []

    def _is_connected(self, loc_a: str, loc_b: str) -> bool:
        """判断两地是否连通（伪实现）"""
        return True

    def _extract_item_uses(self, text: str) -> list[str]:
        """提取物品使用（伪实现）"""
        return []
```

## 7. 与 Event Sourcing 集成

实时一致性校验器从 Event Sourcing Store 中读取当前状态快照，作为校验依据。

### 数据流

```
Event Sourcing Store
    │
    ├──▶ get_current_state() ──▶ state snapshot
    │                              │
    │                              ├── assets
    │                              ├── protagonist_power
    │                              ├── current_timestamp
    │                              ├── character_relations
    │                              ├── personality_traits
    │                              ├── current_location
    │                              └── inventory
    │
    └──▶ get_timeline_events() ──▶ 供时间线校验使用
         get_character_events() ──▶ 供人设校验使用
         get_location_history() ──▶ 供地点校验使用
```

### 状态快照接口（伪代码）

```python
class EventSourcingStore:
    def get_current_state(self) -> dict:
        """返回当前最新状态快照"""
        return {
            "total_wealth": self.replay_events("wealth"),
            "protagonist_power": self.replay_events("power"),
            "current_timestamp": self.replay_events("timestamp"),
            "character_names": self.replay_events("character_names"),
            "personality_traits": self.replay_events("personality"),
            "current_location": self.replay_events("location"),
            "inventory": self.replay_events("inventory"),
        }
```

### 集成要点

1. **无状态设计**：校验器不持有状态，每次从 Store 获取最新快照
2. **事件回放**：通过 replay_events 聚合历史事件得到当前值
3. **增量校验**：只校验新写入的 Draft 块，避免重复检查
4. **跨章状态跟踪**：时间线、地点等维度依赖事件流中的累积状态

## 8. 与 DraftEngine 的集成界面

```python
class DraftEngine:
    """
    Draft 引擎。集成实时校验器。
    """

    def __init__(self, store: EventSourcingStore):
        self.store = store
        self.validator = LiveConsistencyValidator(store)

    def write_chunk(self, prompt: str) -> tuple[str, ConsistencyReport]:
        """
        写一个 Draft 块，同时进行一致性校验。

        Returns:
            (draft_text, report)
        """
        draft_text = self._generate_draft(prompt)
        current_state = self.store.get_current_state()

        # 根据当前阶段选择模式
        mode = select_validator_mode(self.session_state)
        self.validator.mode = mode

        report = self.validator.validate(draft_text, current_state)
        return draft_text, report
```

## 9. 输出格式

校验结果附加到 Draft 输出的末尾，格式如下：

```
【实时一致性校验 - Light模式】
🔴 金额冲突: 支出 2000 金币超过总资产 3000 的 50%
🔴 称呼变化: 女主「林雪」在同一段中被称作「雪儿」
```

Full 模式下额外输出修复建议：

```
【实时一致性校验 - Full模式】
🔴 金额冲突: 支出 2000 金币超过总资产 3000 的 50%
   → 建议: 将支出降低至 900 以内，或补充收入来源

🔴 称呼变化: 女主「林雪」在同一段中被称作「雪儿」
   → 建议: 统一使用「林雪」

🟡 时间线跳跃: 时间跳跃 45 天，中间未覆盖
   → 建议: 补充 1-2 章过渡章节

🟡 地点跳跃: 场景从「北境雪原」跳跃到「南部雨林」
   → 建议: 添加旅行描写
```

## 10. 性能考量

| 指标 | Light 模式 | Full 模式 |
|------|-----------|-----------|
| Token 消耗/次 | ~50 | ~200 |
| 延迟 | <10ms | <50ms |
| 维度覆盖 | 4 维（仅 BLOCKER） | 7 维（全级别） |
| 适用阶段 | Draft 高速写作 | Editor 审校前 |

- 校验器运行在 Draft 写出后的**异步回调**中，不阻塞主流程
- 结果通过回调/事件机制传递给 UI 层
- 高频写入场景（短句模式）可合并校验批次以降低开销
