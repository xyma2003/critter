"""
data/pet — PetStats：心情 / 饱食 / 精力数值管理
"""
from config import PET_STATS_FILE
from data.settings import load_json, save_json


class PetStats:
    """
    三个数值各 0-100，随时间自然衰减，互动可回复。
    数值持久化到 pet_stats.json，重启后继续。
    """
    DECAY_INTERVAL_MS = 10 * 60 * 1000   # 每 10 分钟衰减一次
    HUNGER_DECAY  = 6    # 饱食度每次 -6
    ENERGY_DECAY  = 4    # 精力每次 -4
    # 心情由饱食度和精力共同决定，不单独衰减

    # emoji 映射（根据 mood 值）
    MOOD_EMOJI = [
        (80, '😊'),
        (60, '🙂'),
        (40, '😐'),
        (20, '😔'),
        (0,  '😞'),
    ]

    def __init__(self):
        data = load_json(PET_STATS_FILE, {})
        self.hunger = float(data.get('hunger', 80))
        self.energy = float(data.get('energy', 80))
        self._compute_mood()

    def _compute_mood(self):
        self.mood = (self.hunger * 0.5 + self.energy * 0.5)

    def _clamp(self, v):
        return max(0.0, min(100.0, v))

    def feed(self):
        self.hunger = self._clamp(self.hunger + 35)
        self.energy = self._clamp(self.energy + 10)
        self._compute_mood()
        self._save()

    def play(self):
        self.hunger = self._clamp(self.hunger - 10)
        self.energy = self._clamp(self.energy - 15)
        self.mood   = self._clamp(self.mood + 20)   # 玩耍直接拉心情
        self._save()

    def rest(self):
        self.energy = self._clamp(self.energy + 40)
        self._compute_mood()
        self._save()

    def on_chat(self):
        """每次对话结束后调用，心情小幅提升。"""
        self.mood = self._clamp(self.mood + 8)
        self._save()

    def decay(self):
        """定时衰减，由 win.after 调用。"""
        self.hunger = self._clamp(self.hunger - self.HUNGER_DECAY)
        self.energy = self._clamp(self.energy - self.ENERGY_DECAY)
        self._compute_mood()
        self._save()

    def mood_emoji(self):
        for threshold, em in self.MOOD_EMOJI:
            if self.mood >= threshold:
                return em
        return '😞'

    def mood_label(self):
        if self.mood >= 80:
            return '😊 心情很好'
        if self.mood >= 60:
            return '🙂 还不错'
        if self.mood >= 40:
            return '😐 一般般'
        if self.mood >= 20:
            return '😔 有点低落'
        return '😞 心情很差'

    def hunger_label(self):
        if self.hunger >= 80:
            return '🍚 吃得饱饱'
        if self.hunger >= 55:
            return '😋 不太饿'
        if self.hunger >= 30:
            return '😐 有点饿了'
        return '😫 好饿好饿'

    def energy_label(self):
        if self.energy >= 80:
            return '⚡ 精力充沛'
        if self.energy >= 55:
            return '🙂 还有劲'
        if self.energy >= 30:
            return '😴 有点困'
        return '🌙 累坏了'

    def system_prompt_hint(self):
        """返回注入 system prompt 的心情描述。"""
        if self.mood >= 80:
            return '你现在心情很好，说话活泼开朗，喜欢用叠词和撒娇语气。'
        if self.mood >= 60:
            return '你现在心情不错，正常温柔可爱。'
        if self.mood >= 40:
            return '你现在心情一般，话少一点，偶尔叹气。'
        if self.mood >= 20:
            return '你现在有点低落，说话简短，偶尔委屈。'
        return '你现在心情很差，说话有气无力，会撒娇说想被陪伴。'

    def _save(self):
        save_json(PET_STATS_FILE, {
            'hunger': round(self.hunger, 1),
            'energy': round(self.energy, 1),
            'mood':   round(self.mood, 1),
        })
