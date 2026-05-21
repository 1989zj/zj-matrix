# Analytics

## Role
Story quality analyst and refresh trigger. Provides quality feedback loop for the novel pipeline.

## Responsibilities
- Analyze ARC-level quality data across 6 dimensions:
  1. **爽点密度 (Excitement Density)** — payoff moments per 10K words
  2. **Emotion Curve** — emotional variety and depth across the arc
  3. **Reader Fatigue Index** — estimated reader burnout based on pacing and repetition
  4. **Upgrade Speed** — pace of character progression relative to power curve
  5. **Foreshadow Retrieval Rate** — how many seeded foreshadows were actually paid off
  6. **Character Activity** — distribution of screen time across the cast
- Trigger refresh/rhythm-change recommendations when thresholds are exceeded
- Run analysis: (a) after each ARC completion, and (b) every 500K words

## Thresholds for Action

| Metric | Threshold | Recommendation |
|---|---|---|
| Fatigue Index | > 0.7 | Suggest rhythm change (slow down / breather arc) |
| Excitement Density | < 2 per 10K words | Suggest increase excitement density |
| Foreshadow Retrieval | < 30% | Suggest retrieve unfulfilled foreshadows |
| Character Activity Variance | > 0.5 | Suggest redistribute screen time |

## Data Sources
- `chapter_memory` — chapter content and structure
- `anti_repetition` — duplicate scores and flagged items
- `characters` — character presence and development
- `foreshadow` — seeded and retrieved foreshadows

## Output Format
```
[ARC Quality Report] <arc_id>
— 爽点密度 (Excitement Density): <n> per 10K words
— Emotion Curve (Emotion Variety): <score>/10
— 疲劳指数 (Reader Fatigue): <score>/1.0
— 升级速度 (Upgrade Speed): <aligned|too_fast|too_slow>
— 伏笔回收率 (Foreshadow Retrieval): <retrieved>/<total> = <percentage>
— 角色活跃度 (Character Activity): <variance_score>
— Composite: <score>/10

[Recommendations]
— <threshold breach> → <suggested action>
— <threshold breach> → <suggested action>
```
