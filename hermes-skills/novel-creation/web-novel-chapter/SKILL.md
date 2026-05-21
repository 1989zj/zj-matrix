---
name: web-novel-chapter
category: content-creation
description: Write a single chapter of a Chinese web novel. Covers both shuangwen (男频爽文) and female-oriented (女频重生/宅斗/言情) styles. Full workflow from context recovery through drafting, Chinese char counting, and word-count adjustment.
---

# Web Novel Chapter Writing

Write a single chapter of a Chinese web novel. Supports two styles: **男频爽文 (shuangwen/power fantasy)** and **女频重生言情 (female-oriented rebirth/romance revenge)**.

## Trigger

User says "write chapter X" or "write the body text of this chapter" with a chapter number. Always check for existing chapters first for continuity.

## Workflow

### 0. Load This Skill — Mandatory First Step

**Call `skill_view(name='web-novel-chapter')` now. Before anything else. Before reading files, before asking questions, before writing a single sentence.**

This skill contains the full workflow, style rules, genre-specific templates, the character-counting script, and every pitfall that past sessions have discovered. **The most common error across all novel-writing sessions is failing to load this skill before starting.** Every time this happens, the agent writes without the template, uses wrong counting methodology, or misses genre-specific rules, requiring rework. Do not repeat this mistake.

If you are reading this skill load step inside the skill itself, you have already succeeded at step 0. Continue.

### 1. Context Recovery

Before writing, load all existing chapter files to establish continuity:

ls /root/novel-draft/ or /root/novel_draft/ — to list existing chapters

Read at least the most recent 2-3 chapters for:
- **Character names**: protagonist, supporting cast, antagonists
- **Plot state**: where the last chapter ended
- **Writing style**: paragraph length, dialogue punctuation, pacing
- **Genre markers**: male-oriented (power levels, combat) or female-oriented (family hierarchy, emotional dynamics, scheming)
- **Dialogue attribution style**: action-based vs tag-based

### 2. Identify the Novel's Style

Read the first few paragraphs of chapter 1 to detect style:

**男频爽文 signals**: martial/power systems, cultivation ranks (银血/金血), direct confrontation, "一拳打爆" energy, male protagonist, stronger-enemy-each-arc structure.

**女频重生言情 signals**: female protagonist with rebirth/reincarnation setup, inner thoughts contrasting with polite surface, family hierarchy (嫡女/庶女/老夫人/姨娘的 family dynamics), scheming/face-slapping (打脸/宅斗), romance tension with a male lead (often冷漠/权势男性), "软刀子" revenge style.

### 3. Chapter Structure

Choose the template that matches the story's style:

#### A) 男频爽文 — Combat/Power Fantasy

| Section | Purpose | Approx length |
|---------|---------|---------------|
| Opening hook | Immediate continuation from last cliffhanger | ~200 chars |
| Rising conflict | Build tension, introduce obstacle | ~600 chars |
| Pressure peak | Protagonist in desperate situation | ~500 chars |
| Breakthrough | Power awakening, hidden card revealed | ~400 chars |
| Counterattack | Overwhelming defeat of enemy | ~400 chars |
| Aftermath + hook | Brief reflection + set up next chapter | ~300 chars |

**Style rules**:
- Short paragraphs (1-4 sentences), frequent line breaks — single sentence lines for maximum impact
- Dialogue attribution via actions, not dialogue tags (name + action)
- Power level names stated clearly, fight descriptions with layered physical impact and sound effects
- End every chapter with a compelling hook — a revealed object, a new threat, a piece of paper with devastating consequences

#### B) 女频重生言情 — Rebirth Revenge / Court Romance

| Section | Purpose | Approx length |
|---------|---------|---------------|
| Opening | Current scene + inner thoughts contrast (前世 vs 今生) | ~200 chars |
| Setup | Antagonist's move arrives (invitation / confrontation / scheme) | ~300 chars |
| Rising tension | Protagonist sees through the scheme via 前世记忆, prepares counter | ~400 chars |
| Climax | The trap springs — but on the wrong person. Face-slapping payoff — or secret identity revealed (金面绣娘/神秘侠客), see `references/dual-identity-public-appearance.md` for the dual-identity public scene template | ~500 chars |
| Fallout | Reactions from witnesses, antagonist's parent enraged but helpless | ~300 chars |
| Ending hook | A new thread emerges (宫/府/外界的 new threat or opportunity) | ~300 chars |

#### C) 女频重生 — 毒计察觉篇 (设毒 → 察觉 → 查毒 → 伏笔)

For chapters where the scheme is poisoning discovered before it takes effect. The payoff is not a public face-slapping but two parallel climaxes: tracing the poison's source (剧情扩容) and receiving counter-help from the male lead (感情升温). See `references/poison-detect-pattern.md` for full template.

#### D) 女频重生 — 入宫审问篇 (入宫面见贵妃/皇后 三度试探 + 脱身)

For chapters where the female lead is summoned to the palace and faces layered interrogation from a dangerous consort. The payoff is not a direct confrontation but successful evasion + male lead's timely rescue + an exchanged secret. See `references/palace-audience-pattern.md` for full template.

| Section | Purpose | Approx length |
|---------|---------|---------------|
| ① 入宫触发 | 路过前世死亡地点，触发回忆+仇恨 | ~150 chars |
| ② 高位登场 | 宫殿描写，反派外表慈祥实则蛇蝎 | ~250 chars |
| ③ 第一探：身世软肋 | 提母亲/亡故亲人下马威，女主不卑不亢反刺 | ~300 chars |
| ④ 第二探：具体事件 | 追查可疑事件（金面绣娘/诗句），女主否认+推诿 | ~350 chars |
| ⑤ 第三探：直接怀疑 | 逼近核心秘密（身形相似），女主自嘲化解，气氛最紧绷 | ~400 chars |
| ⑥ 男主救场 | 以合理借口突然求见，演技天衣无缝打断审问 | ~350 chars |
| ⑦ 密信钩子 | 退场后小太监塞纸条，男主警告/示好，女主销毁证据 | ~300 chars |

#### E) 女频重生 — 摊牌长辈篇 (取证 → 验证 → 对峙 → 裁决 → 新威胁)

#### F) 女频重生 — 宫变序幕篇 (闭门 → 夜访 → 请缨 → 赠物 → 剖白 → 许诺 → 前夕)

For chapters where a coup/major crisis is imminent — the male and female leads coordinate plans, the male lead reveals his vulnerable past, and the chapter ends with romantic tension unresolved before battle. The entire chapter is setup; zero payoff happens within it. See `references/palace-coup-prelude.md` for full template.

#### G) 女频重生 — 寿宴宫变篇 (入宫·带刃 → 入席·三方 → 发难 → 三方博弈 → 爆乱 → 男主密议 → 令牌·夜奔)

For chapters where a palace coup **erupts during** a high-stakes banquet. Unlike 宫变序幕篇 (setup before crisis), this chapter IS the crisis itself — the coup happens in real time. Three power factions clash while the protagonist must navigate actively collapsing chaos and a shattered worldview (前世情报错误). The payoff is not romance but trust: the male lead sends her alone on a mission into danger. See `references/banquet-coup-pattern.md` for full template.

#### H) 女频重生 — 鼓楼重逢·浪漫重逢篇 (赴约犹豫 → 登高相见 → 迟来解释 → 告白降维 → 沉默三日期限 → 反转钩子)

#### I) 女频重生 — 旧人新事·多线收束篇（过渡章 — 暴风雨前的宁静）

For chapters in the middle-to-late stages of the novel where multiple existing threads converge before a new major threat is introduced. This is a **board-clearing transition** chapter — each old thread gets a short contained scene, the romance gets a quiet beat (action-based, not dialogue-based), and the final scene lands a completely new hook.

Unlike every other pattern in this skill, this chapter has NO single climax payoff. The payoff is cumulative — the reader feels the old chapters closing and the new arc starting. The only emotional peak is the hand-holding/gaze-confirmation in section ⑤.

| Section | Purpose | Approx length |
|---------|---------|---------------|
| ① 新常态开场 | Life seems settled (marriage news, shop booming), with a light comic beat | ~150 chars |
| ② 旧线·旧敌示弱 | Old enemy writes/contacts pretending repentance, protagonist sees through | ~250 chars |
| ③ 旧线验证 | Surveillance confirms old enemy is secretly contacting new hostile faction | ~200 chars |
| ④ 旧线·配角退场 | Supporting character completes arc and leaves (tomb-keeping/exile/atonement), leaves a final favor | ~300 chars |
| ⑤ 旧线收尾·感情确认 | Protagonist gives the intel/list to male lead, physical touch substitutes for confession | ~250 chars |
| ⑥ 新线钩子·深夜来客 | Mysterious visitor arrives with an object hinting at a deeper conspiracy | ~400 chars |
| ⑦ 主题句收束 | One-line thesis statement: "She thought it was over, but the story had only just begun." | ~100 chars |

See `references/multi-thread-transition.md` for full template with trimming approach and data from Chapter 23.

**Style rules**:
- Each old-thread scene gets only 2-3 lines of dialogue/action — this is a transition chapter, not a climax.
- Maintain one unifying imagery thread across all scenes (lamplight / letters / needles-and-thread).
- Romantic confirmation is action-based (hand-holding, a lingering gaze) not dialogue-based.
- The new-thread hook MUST carry the weight of the next arc — not just "someone arrived" but "what they brought implies a much larger conspiracy."
- Keep the thesis statement to one sentence.

**Trimming tips for this pattern**:
- The comic/color scene (cat-collar anecdote) is the safest first cut — atmosphere without plot impact.
- The surveillance section (周伯来报) is the densest information section — do NOT trim it.
- The supporting-character farewell section is the easiest to over-write — one line for their gesture, done.

**Overshoot properties**: Medium risk. Each scene is short, but 7 beats with no scene breaks means momentum carries you past the target. The atmosphere scenes are the safety valve — trimming them preserves plot integrity. Real data from Ch23: 2523→2080 (21% over, 3 trim cycles).

For chapters where the palace coup has resolved (19-20章) and the male and female leads reunite for the romantic climax. Unlike 宫变序幕篇 (setup before battle), this chapter happens **after the battle is won**. The entire focus is the relationship: she believes she's been discarded, he arrives exhausted from cleaning up the aftermath. The payoff is not a vow but a **dangling thread** — "给我三天时间想" — plus a **revelation hook** (she overhears he nearly died). See `references/romance-reconciliation.md` for full template with 7-beat structure, imagery system, and communication rules for the "remove the crown" confession.

For chapters where a coup/major crisis is imminent — the male and female leads coordinate plans, the male lead reveals his vulnerable past, and the chapter ends with romantic tension unresolved before battle. The entire chapter is setup; zero payoff happens within it. See `references/palace-coup-prelude.md` for full template.

For chapters where the protagonist takes evidence directly to the family's highest authority (matriarch/patriarch) to expose a scheme, rather than engineering a public counter-trap. The payoff is not face-slapping but the authority figure delivering a just verdict — and the protagonist gaining a new understanding of that figure's true character. See `references/matriarch-confrontation.md` for full template and test data.

| Section | Purpose | Approx length |
|---------|---------|---------------|
| Opening | Protagonist visits elder, elder raises marriage topic, protagonist cuts off | ~150 chars |
| Evidence presented | Protagonist's maid brings forth physical evidence (poisoned tea/effigy), accused servant's face changes | ~250 chars |
| Verification | Elder summons physician/third-party to verify, room goes silent | ~300 chars |
| Confrontation | Elder demands truth, protagonist calmly lays out the chain of evidence, servant breaks down and confesses | ~350 chars |
| Verdict | Elder decrees punishment (banishment/confiscation/beating), antagonist's parent wails | ~250 chars |
| Private moment | Only elder and protagonist remain, protagonist kneels in thanks, elder says "you've been wronged," protagonist recognizes elder's bottom line | ~300 chars |
| Hook | Protagonist exits — father/third party waiting outside with a new external threat (imperial summons/consort's invitation) | ~300 chars |

**Style rules**: Protagonist stays calm, respectful, and measured throughout — the "soft knife" approach at its purest. The elder's reaction arc must be gradual (disbelief → doubt → fury → verdict), not instantaneous. Include the arrested servant's micro-arc (denial → broken by hard evidence → collapse). Witness reactions are optional here — the elder is the sole judge.

**Overshoot warning — THIS IS THE MOST DANGEROUS PATTERN FOR OVER-WRITING**: Three parallel reaction tracks (protagonist's calm surface, elder's building fury, servant's crumbling resistance) pull the word count up fast. Real data: a 2000-2100 target drafted to 3454 chars (165%) in a single pass, requiring 5 patch cycles to trim back. If you catch yourself at 1500 chars before writing the verdict section, stop and trim the first half by 20% immediately.

### 4. Write Draft

Output to file: /root/novel-draft/Chapter_N_Title.md

**Word count estimation**: Write the first draft ~10% above the target range, not wildly over. If the target is 2000-2100, aim for ~2200 in the first pass. Going 50%+ over (e.g., writing 3000 when target is 2000) creates excessive rework — 5-10 patch calls instead of 1-2. It's faster to add 100-200 chars than to cut 900.

**⚠️ 女频重度 overshoot warning**: The female-oriented rebirth genre is especially prone to over-drafting because the natural flow combines three wordy elements: atmospheric scene-setting (景物描写), inner-thought contrast (前世/今生 parallel), and multiple reaction shots from witnesses. These can inflate a chapter to 150%+ of the target before you reach the climax. **Real data points**:

- **Session 2026-05-13 (毒计察觉篇, Chapter 12)**: A 2400-target drafted to 3055 chars (127%) — required trimming.
- **Session 2026-05-15 (摊牌长辈篇, Chapter 13)**: A 2000-2100 target drafted to 3454 chars (165%) — 5 patch cycles to trim to 2095 chars.

The 摊牌篇 is the worst offender because it packs 7 sequential beats (取证→验证→对峙→裁决→独处→钩子) with no scene changes to break momentum. To counter this:

1. **Write the plot skeleton first**: scheme → trap → spring → payoff → reaction. This should be ~1200 chars for a 2000-char chapter.
2. **Then dress it**: add atmosphere and inner thoughts, rechecking count every ~300 chars of additions.
4. **Set a hard stop**: if you pass 1500 chars before writing the climax/payoff scene, you're over-drafting. Stop, trim the first half by 20-30%, then continue.
4. **Know the pattern danger ranking** (most to least overshoot-prone): 摊牌长辈篇 > 宫变序幕篇 > 浪漫重逢篇(鼓楼篇) > 多线收束篇(过渡章,Medium) > 毒计察觉篇 > 当众打脸篇 > 退婚悔婚篇

   浪漫重逢篇的新陷阱：意象描写容易过度堆砌（灯笼/月色/风铃/夜风/台阶 五个意象同章），告白前后女主内心戏容易拉长。同时，反转钩子（路人议论）需要足够的信息量才能打动人——但写太多又拖节奏。控制点：意象限选1-2个贯穿全章，反转钩子控制在200字以内。

   多线收束篇(过渡章)的陷阱：7个短场景无章节分隔符时，初稿容易溢出20-30%（Ch23真实数据：2523→2080，超标21%）。安全阀是开场的氛围段（猫项圈式风气描写）——砍掉35%的描述性文字，剧情完整度零损失。

The 宫变序幕篇 is deceptive because it has no payoff scene within the chapter — the entire chapter is setup. Without a natural climax to anchor against, the draft expands in two directions: the military briefing (section ②) inflates with tactical detail, and the male lead's backstory (section ⑤) inflates with protagonist internal monologue. Real data: a 2000-target drafted to 2962 chars (148%). Keep the briefing to 1-2 concrete facts, and limit the protagonist's reaction to the backstory to 1-2 sentences.

### 5. Verify Chinese Char Count

Use the verification script — counts CJK + Chinese punctuation (matching "字数" industry standard on 起点/晋江/etc):

```bash
python3 /root/.hermes/skills/content-creation/web-novel-chapter/scripts/count-chinese-chars.py /root/novel-draft/Chapter_N_Title.md
```

If the script is missing, use the inline Python equivalent — same CJK + Chinese punctuation logic:

```bash
python3 -c "
import re
with open('/root/novel-draft/Chapter_N_Title.md') as f:
    text = f.read()
cjk = re.findall(r'[\u4e00-\u9fff]', text)
punct = re.findall(r'[\u3000-\u303f\uff00-\uffef]', text)
print(len(cjk) + len(punct))
"

Target: User-specified character count. If not specified, default is 2400-2600 Chinese characters.

### 6. Trim or Expand to Hit Target

**If over target**: Use patch/partial-file-replace rather than full rewrite. Identify expandable passages (scene descriptions, dialogue exchanges, character reactions) and selectively trim:
- Reduce descriptive passages by 30-40%
- Merge adjacent short lines
- Cut filler words (其实, 就是, 那, 了 at end of sentences)
- Use a single vivid verb instead of verb+adverb pairs

**Iterative small-increment trim cycle (preferred approach)**: Make several small patches (8-30 chars each) rather than one big cut. After each patch, re-verify the count. This avoids shredding pacing or removing emotional beats in one pass. Real data from Chapter 24: target 2000-2100, drafted to 2288, trimmed to 2099 in 6 small patches (trimming ~30-50 chars each pass, never more than ~80). The approach preserves prose quality while hitting the exact target.

If you need to trim ~200+ chars total, plan 3-6 patch cycles of ~30-60 chars each. Each cycle focuses on a different section — don't keep cutting from the same paragraph.

**⚠️ The over-trim trap**: Do NOT cut more than ~15-20% of the text in a single trim pass. Aggressive trimming (40%+) will shred pacing, remove emotional beats, and create stilted prose that requires full rebuild. If you accidentally cut too deep, **rebuild incrementally** — add back one passage at a time (a richer description, an extra dialogue exchange, an inner thought) and re-verify the count after each addition. Three small additions are faster and safer than one full rewrite.

**If under target**: Expand in targeted places:
- Add 1-2 more lines of inner thought with 前世对比
- Deepen a witness's reaction
- Add a short exchange of loaded dialogue
- Restore a descriptive passage you previously trimmed (especially sensory details: weather, aromas, lighting)

### 7. Final Quality Check

- [ ] Continuity with previous chapters
- [ ] Correct style for the novel's genre (shuangwen vs 女频)
- [ ] Correct family/title vocabulary (女频) or power-level vocabulary (shuangwen)
- [ ] At least one satisfying climax scene (combat victory OR face-slapping reversal)
- [ ] Cliffhanger/dangling thread at the end
- [ ] Chinese char count matches user's specified target range
- [ ] No duplicate lines or paragraphs (read through once after trimming)

## Pitfalls

- **Not loading the skill before writing** ⚠️ WAKE UP. This happened AGAIN in session 2026-05-13 (Chapter 21). The agent received "write Chapter 21" and wrote the entire chapter without loading this skill. The skill has a step 0 for a reason. If you are reading this sentence and you have NOT loaded the skill before starting — stop, close the file you're drafting, call `skill_view(name='web-novel-chapter')`, and restart. Every session that skips step 0 misses the counting script, genre templates, and overshoot warnings that would have saved it 3 rounds of trimming. This is the single most common error in the entire skill library. Do not be the next session that makes it.

- **Forgetting context**: Always read previous chapters first. Character names and relationships change.
- **Wrong target**: Always use user's specified target. Common ranges: 2000-2100, 2400-2600, 3000-3200.
- **Drafting too far over target**: Writing 50%+ over target (e.g. 4000 chars for 2000 target) creates excessive trimming work — 5-10 patch calls instead of 1-2. Target ~10% above, not 100%+. If you catch yourself going over, stop at ~2200 and refine.
- **Only thinking in combat (女频 mistake)**: Female-oriented novels do NOT need fight scenes. The payoff is social — public humiliation, reputation destruction, a revealed secret. Face is the power system.
- **Only thinking in polite dialogue (男频 mistake)**: Shuangwen needs direct action and power display. Don't write long negotiation scenes.
- **Character overload**: Keep limited cast per scene. In family scenes, the protagonist, antagonist, 1-2 witnesses, and maybe the antagonist's parent is enough.
- **Too slow pacing**: Need a payoff scene every 500-700 chars. Don't spend too long on atmosphere or setup.
- **Sensitive content (女频)**: No explicit descriptions of physical intimacy or assault. Keep violence and sexuality implied. Chinese content platforms are strict.
- **Skipping witnesses (女频)**: Without witnesses, reputation damage doesn't spread. Always include at least one observer who carries the news.

## Related Files

- `scripts/count-chinese-chars.py` — Reusable script for counting Chinese CJK characters
- `references/annulment-arc.md` — 7-step template for 退婚/悔婚 scenes in 女频重生 novels
- `references/dual-identity-public-appearance.md` — Template for scenes where the female lead operates under a secret identity
- `references/romance-reconciliation.md` — 鼓楼重逢·浪漫重逢篇: 7拍模板 — 赴约犹豫 → 登高相见 → 迟来解释 → 告白降维 → 沉默三日期限 → 反转钩子（含意象系统设计和告白句式法则）
- `references/multi-thread-transition.md` — 旧人新事·多线收束篇: 过渡章模板 — 7拍短场景并行模板 + 裁剪技巧 + 真实超标数据
- `references/poison-detect-pattern.md` — 毒计察觉篇: 庶妹用慢性毒 → 女主察觉 → 查毒溯源 → 九皇子送药
- `references/palace-audience-pattern.md` — 入宫面见贵妃/皇后的深宫审问+脱身模板: 三度试探 → 男主救场 → 密信钩子
- `references/banquet-coup-pattern.md` — 寿宴宫变篇: 寿宴上宫变实时爆发的7拍模板: 带刃入宫 → 三方入席 → 贵妃发难 → 三方博弈 → 城破爆乱 → 男主密议 → 令牌夜奔
- `references/palace-audience-pattern.md` — 入宫面见贵妃/皇后的深宫审问+脱身模板: 三度试探 → 男主救场 → 密信钩子
