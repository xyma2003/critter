---
quick_id: 260423-fma
type: execute
wave: 1
depends_on: []
files_modified:
  - data/pet/__init__.py
  - ui/panel.py
autonomous: true
must_haves:
  truths:
    - "App restart restores mood to last saved value (not reset to default)"
    - "After 10 minutes, mood progress bar visibly decreases"
    - "Clicking 抚摸 increases mood bar"
    - "When mood < 40, welcome greeting uses bored/low-energy wording"
    - "When mood >= 70, welcome greeting uses happy/energetic wording"
  artifacts:
    - path: "data/pet/__init__.py"
      provides: "mood persistence, mood decay, pet() method, PET_LINES dict"
    - path: "ui/panel.py"
      provides: "mood-tiered GREETINGS, _mood_greeting(), _pet() handler, 抚摸 button"
  key_links:
    - from: "PetStats.__init__"
      to: "pet_stats.json"
      via: "data.get('mood', 70.0)"
    - from: "PetStats.decay()"
      to: "self.mood"
      via: "self.mood - 3 per tick (floor 20)"
    - from: "MainPanel._mood_greeting()"
      to: "self.stats.mood"
      via: "tier check >= 70 / >= 40 / < 40"
    - from: "MainPanel._pet()"
      to: "self.stats.pet()"
      via: "calls pet(), logs PET_LINES, flashes 😻"
---

<objective>
Implement MOOD-01 through MOOD-07: make mood an independent, persistent stat with its own
decay, add a 抚摸 button that nudges mood up, and replace flat greeting list with
mood-tiered greetings so the pet's personality shifts with its emotional state.

Purpose: mood currently resets on restart and is just a derivative of hunger+energy;
after this change mood has its own lifecycle — persisted across restarts, decaying
independently, lifted by interactions, and reflected in the greeting text.
Output: updated data/pet/__init__.py and ui/panel.py
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
</context>

<interfaces>
<!-- Key contracts the executor needs. No codebase exploration required. -->

From data/pet/__init__.py (current state):

```python
class PetStats:
    DECAY_INTERVAL_MS = 10 * 60 * 1000

    def __init__(self):
        data = load_json(PET_STATS_FILE, {})
        self.hunger = float(data.get('hunger', 80))
        self.energy = float(data.get('energy', 80))
        self._compute_mood()       # <-- REMOVE this call

    def _compute_mood(self):
        self.mood = (self.hunger * 0.5 + self.energy * 0.5)   # keep as fallback only

    def feed(self):    # calls _compute_mood() at end  <-- REMOVE that call
    def rest(self):    # calls _compute_mood() at end  <-- REMOVE that call
    def decay(self):   # calls _compute_mood() at end  <-- REMOVE that call; add mood decay here

    def _save(self):
        save_json(PET_STATS_FILE, {
            'hunger': round(self.hunger, 1),
            'energy': round(self.energy, 1),
            'mood':   round(self.mood, 1),    # already saved — just preserved
        })
```

From ui/panel.py (current state):

```python
GREETINGS = [('今天还开心吗？', '不管怎样，我在这里陪着你 🐱'), ...]   # flat list

# Two call sites:
q, sub = random.choice(self.GREETINGS)   # line ~392 in _build_home_tab
q, sub = random.choice(self.GREETINGS)   # line ~635 in _back_to_welcome

# Button list in _build_pet_tab (line ~1686):
[('🐟 喂食', self._feed), ('🎾 逗猫', self._play), ('💤 休息', self._sleep)]

# Imports already present:
from data.pet import PetStats, FEED_LINES, PLAY_LINES, REST_LINES
# After task 1 adds PET_LINES, update import to include it.

# _flash_emoji(flash_em, duration_ms) already exists — reuse for 😻
# _log_pet(msg) already exists — reuse for pet action log
# self.stats.pet() will be the new PetStats method (added in task 1)
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: data/pet/__init__.py — mood persistence, decay, pet() method</name>
  <files>data/pet/__init__.py</files>
  <action>
Make four targeted changes:

**MOOD-01 — Load mood from JSON in __init__, remove _compute_mood() calls:**
Replace the `__init__` body so mood is loaded from JSON:
```python
def __init__(self):
    data = load_json(PET_STATS_FILE, {})
    self.hunger = float(data.get('hunger', 80))
    self.energy = float(data.get('energy', 80))
    if 'mood' in data:
        self.mood = float(data['mood'])
    else:
        self._compute_mood()   # one-time fallback only if no saved mood
```
Remove `_compute_mood()` calls from `feed()` and `rest()` — those methods nudge
hunger/energy but should no longer overwrite mood. Keep `_compute_mood()` method
itself (it's still needed as the one-time initializer fallback above).

**MOOD-02 — mood decay in decay():**
In `decay()`, replace `self._compute_mood()` with an independent mood decay step:
```python
def decay(self):
    self.hunger = self._clamp(self.hunger - self.HUNGER_DECAY)
    self.energy = self._clamp(self.energy - self.ENERGY_DECAY)
    self.mood   = self._clamp(max(20.0, self.mood - 3))
    self._save()
```
(Remove the `self._compute_mood()` call that was at the end.)

**MOOD-04 — Add pet() method and PET_LINES:**
Add after the `on_chat` method:
```python
def pet(self):
    """抚摸：心情 +10，饱食 -5（消耗一点注意力）。"""
    self.mood   = self._clamp(self.mood + 10)
    self.hunger = self._clamp(self.hunger - 5)
    self._save()
```

Add `PET_LINES` dict after the existing `REST_LINES` dict at the bottom of the file:
```python
PET_LINES = {
    'happy': [
        '呜呜被摸摸了！好开心好开心！😻',
        '喵～ 再摸一下嘛！尾巴都翘起来了 😸',
        '最喜欢铲屎官了！摸摸超舒服！😻✨',
    ],
    'normal': [
        '嗯……摸摸，舒服~ 😌',
        '喵。被摸到了最喜欢的地方 🐾',
        '轻轻的，再来一下 😸',
    ],
    'bored': [
        '……摸摸也没什么精神 😔',
        '嗯……谢谢你，好一丢丢了 😐',
        '虽然没精神，但摸摸还是喜欢的 😿',
    ],
}
```
  </action>
  <verify>
    <automated>cd /Users/maxinyue09/.openclaw/workspace/desktop-pet && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -c "from data.pet import PetStats, PET_LINES; s = PetStats(); print('mood loaded:', s.mood); s.pet(); print('after pet():', s.mood); s.decay(); print('after decay():', s.mood); print('PET_LINES keys:', list(PET_LINES.keys()))"</automated>
  </verify>
  <done>
    - `from data.pet import PetStats, PET_LINES` succeeds
    - PetStats() loads mood from JSON (prints a float, not crash)
    - pet() raises mood by 10 (clamped to 100)
    - decay() lowers mood by 3 (floor 20)
    - PET_LINES has 'happy', 'normal', 'bored' keys each with 3 strings
  </done>
</task>

<task type="auto">
  <name>Task 2: ui/panel.py — mood-tiered greetings + 抚摸 button + _pet() handler</name>
  <files>ui/panel.py</files>
  <action>
Make three targeted changes:

**MOOD-05 — Replace flat GREETINGS with tiered dict and add _mood_greeting():**

Replace the `GREETINGS` class attribute (currently a flat list of 15 tuples) with:
```python
GREETINGS = {
    'happy': [
        ('今天也是元气满满的一天！', '有我陪着你，什么都能搞定 😸✨'),
        ('嘿！你来了，我好开心！', '今天有什么有趣的事要分享吗 🎉'),
        ('好久不见，想死你了！', '快来陪我聊天嘛 😻'),
        ('今天天气怎么样？', '不管晴雨，有我在就够啦 🌤'),
        ('有没有让你开心的事？', '快说快说，我也想跟着高兴 🎊'),
    ],
    'neutral': [
        ('今天还开心吗？', '不管怎样，我在这里陪着你 🐱'),
        ('嘿，你回来啦！', '我一直在等你呢 ✨'),
        ('今天吃了什么好吃的？', '记得好好吃饭，不然我要担心了 🍜'),
        ('工作顺利吗？', '休息一下，摸摸我也许会好一点 😸'),
        ('最近睡得好吗？', '睡眠很重要哦，我晚上都在守护你 🌙'),
        ('今天有没有喝够水？', '记得补充水分，身体是最重要的 💧'),
        ('有没有做让自己骄傲的事？', '你已经很棒了，继续加油！⭐'),
        ('今天学到什么新东西了吗？', '每天进步一点点就很好了 📚'),
        ('最近有什么小确幸？', '生活里的小美好值得被记录 🌸'),
        ('今天有没有笑一笑？', '笑一个嘛，你笑起来很好看的 😄'),
    ],
    'bored': [
        ('……你来了啊。', '没什么精神，但还是想陪着你 😔'),
        ('今天有点累了，', '不过有你在好一点了 😐'),
        ('有没有什么烦恼？', '说出来也许会轻松一些，我在听 👂'),
        ('压力大吗？', '深呼吸……一切都会好起来的 🌿'),
        ('今天……感觉怎么样？', '我也不太好，我们互相陪伴吧 😿'),
    ],
}
```

Add a `_mood_greeting()` method after the `__init__` method (or alongside other small
helper methods near the top of the class — place it just before `_fix_panel_window_level`):
```python
def _mood_greeting(self):
    """根据当前心情选择问候语 tier。"""
    mood = self.stats.mood
    if mood >= 70:
        tier = 'happy'
    elif mood >= 40:
        tier = 'neutral'
    else:
        tier = 'bored'
    return random.choice(self.GREETINGS[tier])
```

Replace **both** occurrences of `random.choice(self.GREETINGS)` with `self._mood_greeting()`:
- Line ~392 in `_build_home_tab`: `q, sub = self._mood_greeting()`
- Line ~635 in `_back_to_welcome`: `q, sub = self._mood_greeting()`

**Button change + _pet() handler:**

In `_build_pet_tab`, replace the button list:
```python
# OLD:
[('🐟 喂食', self._feed), ('🎾 逗猫', self._play), ('💤 休息', self._sleep)]
# NEW:
[('🐟 喂食', self._feed), ('🎾 玩耍', self._play), ('🤲 抚摸', self._pet)]
```

Add `_pet()` method immediately after `_sleep()` (around line 1873):
```python
def _pet(self):
    mood = self.stats.mood
    if mood >= 70:
        bucket = 'happy'
    elif mood >= 40:
        bucket = 'normal'
    else:
        bucket = 'bored'
    self.stats.pet()
    self._sync_pet_ui()
    self._flash_emoji('😻', 800)
    self._log_pet(random.choice(PET_LINES[bucket]))
    self.pet.trigger_bounce()
```

Update the import line at the top of panel.py to include `PET_LINES`:
```python
from data.pet import PetStats, FEED_LINES, PLAY_LINES, REST_LINES, PET_LINES
```
  </action>
  <verify>
    <automated>cd /Users/maxinyue09/.openclaw/workspace/desktop-pet && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -c "
import sys
# Syntax / import check
import importlib.util, ast
for f in ['ui/panel.py', 'data/pet/__init__.py']:
    with open(f) as fh: src = fh.read()
    ast.parse(src)
    print(f, '— syntax OK')
# Check GREETINGS is a dict
spec = importlib.util.spec_from_file_location('panel', 'ui/panel.py')
# just parse, don't import (avoids tk requirement)
import re
with open('ui/panel.py') as fh: text = fh.read()
assert 'happy' in text and 'neutral' in text and 'bored' in text, 'GREETINGS tiers missing'
assert '_mood_greeting' in text, '_mood_greeting method missing'
assert '🤲 抚摸' in text, '抚摸 button missing'
assert 'def _pet(self)' in text, '_pet method missing'
assert 'PET_LINES' in text, 'PET_LINES import missing'
print('All panel.py checks passed')
"</automated>
  </verify>
  <done>
    - panel.py passes Python syntax check
    - GREETINGS dict has 'happy', 'neutral', 'bored' keys
    - `_mood_greeting()` method present
    - `random.choice(self.GREETINGS)` no longer appears (replaced by `self._mood_greeting()`)
    - Button list shows '🤲 抚摸' (not '💤 休息')
    - `def _pet(self)` method present, calls `self.stats.pet()` and `PET_LINES`
    - Import line includes `PET_LINES`
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Full mood system:
    - mood persisted to / restored from pet_stats.json (MOOD-01)
    - mood decays -3 per 10-min tick with floor 20 (MOOD-02)
    - on_chat() still nudges mood +8 (MOOD-03 confirmed)
    - new pet() method: mood +10, hunger -5 (MOOD-04)
    - mood-tiered GREETINGS dict + _mood_greeting() (MOOD-05)
    - 抚摸 button replaces 休息, _pet() handler wired up
  </what-built>
  <how-to-verify>
    Run the app:
    ```
    cd /Users/maxinyue09/.openclaw/workspace/desktop-pet
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 main.py
    ```

    1. Open pet tab — note the current mood bar value.
    2. Click "🤲 抚摸" — mood bar should visibly increase and 😻 should flash briefly.
    3. Send a chat message — mood bar should increase after response arrives.
    4. Close and relaunch the app — mood bar should show the same value as before restart (not reset to 70).
    5. Home tab greeting: if mood >= 70 the greeting should be upbeat (e.g. "今天也是元气满满"); if mood < 40 it should be subdued (e.g. "……你来了啊").
    6. "🎾 玩耍" button should be visible (not "逗猫"), "🤲 抚摸" visible (not "💤 休息").
    7. (Optional) To test decay: temporarily set DECAY_INTERVAL_MS = 5000 in data/pet/__init__.py, wait 15 seconds, check mood bar drops.
  </how-to-verify>
  <resume-signal>Type "approved" if all checks pass, or describe any issues found.</resume-signal>
</task>

</tasks>

<verification>
- `python3.11 -c "from data.pet import PetStats, PET_LINES"` — no ImportError
- `python3.11 -c "ast.parse(open('ui/panel.py').read())"` — no SyntaxError
- pet_stats.json contains a 'mood' key after any interaction
- App restarts with the last saved mood value
</verification>

<success_criteria>
1. Mood survives app restart (loaded from JSON, not recomputed from hunger/energy)
2. Mood progress bar decreases over time (decay tick subtracts 3, floor 20)
3. Chat and 抚摸 interactions visibly increase the mood bar
4. Home tab greeting text tier matches current mood (happy / neutral / bored)
5. Pet tab shows 🎾 玩耍 and 🤲 抚摸 buttons (not 逗猫 / 休息)
</success_criteria>

<output>
After completion, create `.planning/quick/260423-fma-phase-3-mood-system-implement-mood-01-to/260423-fma-SUMMARY.md`
with what was built, files changed, and any notable decisions made.
</output>
