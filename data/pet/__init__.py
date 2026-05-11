"""
data/pet — PetStats：心情 / 饱食 / 精力数值管理
"""
from core.state_manager import save_pet_stats, load_pet_stats


class PetStats:
    """
    三个数值各 0-100，随时间自然衰减，互动可回复。
    数值持久化到 ~/.desktop-pet-state.json，重启后继续。
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
        data = load_pet_stats() or {}
        self.hunger = float(data.get('hunger', 80))
        self.energy = float(data.get('energy', 80))
        if 'mood' in data:
            self.mood = float(data['mood'])
        else:
            self._compute_mood()

    def _compute_mood(self):
        self.mood = (self.hunger * 0.5 + self.energy * 0.5)

    def _clamp(self, v):
        return max(0.0, min(100.0, v))

    def feed(self):
        self.hunger = self._clamp(self.hunger + 35)
        self.energy = self._clamp(self.energy + 10)
        self._save()

    def play(self):
        self.hunger = self._clamp(self.hunger - 10)
        self.energy = self._clamp(self.energy - 15)
        self.mood   = self._clamp(self.mood + 20)   # 玩耍直接拉心情
        self._save()

    def rest(self):
        self.energy = self._clamp(self.energy + 40)
        self._save()

    def on_chat(self):
        """每次对话结束后调用，心情小幅提升。"""
        self.mood = self._clamp(self.mood + 8)
        self._save()

    def pet(self):
        """抚摸：心情 +10，饱食 -5（消耗一点注意力）。"""
        self.mood   = self._clamp(self.mood + 10)
        self.hunger = self._clamp(self.hunger - 5)
        self._save()

    def decay(self):
        """定时衰减，由 win.after 调用。"""
        self.hunger = self._clamp(self.hunger - self.HUNGER_DECAY)
        self.energy = self._clamp(self.energy - self.ENERGY_DECAY)
        self.mood   = self._clamp(max(20.0, self.mood - 3))
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
        save_pet_stats(
            round(self.hunger, 1),
            round(self.energy, 1),
            round(self.mood, 1),
        )


# ── 互动台词池（按状态分支）──────────────────────────

FEED_LINES = {
    'starving': [
        '终于等到你了！我都快饿晕了 😭🐟',
        '呜呜好饿好饿，谢谢你救了我！🐟',
        '肚子咕咕叫超久了……好香啊！😋',
    ],
    'hungry': [
        '正好有点饿，吃得好满足~ 🐟',
        '嗯嗯嗯，鱼鱼最好吃了！😸',
        '哇，鱼！我最喜欢的！🐟✨',
        '谢谢铲屎官，吃饱了好开心~ 😊',
    ],
    'full': [
        '其实我还不太饿……但鱼鱼不吃白不吃 😏',
        '刚吃过呢，不过再吃一点也没关系啦 😅🐟',
        '撑死我了，你太宠我了吧 🤣',
    ],
}

PLAY_LINES = {
    'bored': [
        '终于有人陪我玩了！冲啊！🎾💨',
        '我等这一刻好久了！！🎾🎉',
        '无聊死了，快来快来！😆',
    ],
    'normal': [
        '耶！逗猫棒！！扑过去！🎾',
        '哈哈抓到了！再来再来！😹',
        '嗖——！我好厉害！🐾🎾',
        '玩得好开心，尾巴都竖起来了~ 😸',
    ],
    'tired': [
        '有点累了，但还是想玩……🥱🎾',
        '玩一下下就好，我有点困 😴',
        '嗯……勉强陪你玩一会儿吧 😪',
    ],
}

REST_LINES = {
    'exhausted': [
        '累坏了……zzz 好舒服好舒服 💤',
        '终于可以睡了，不要叫我……💤😴',
        '眼皮好重……立刻进入梦乡 💤',
    ],
    'normal': [
        '小憩一下，充个电~ 💤',
        '闭上眼睛，很快就好了 😌',
        '嗯……睡一觉什么都好了 💤✨',
        '躺平！休息是最重要的事！😴',
    ],
    'energetic': [
        '其实我不困，但既然你让我休息……💤',
        '勉强躺一会儿吧，反正也没事做 😏',
        '好吧好吧，补个觉也不错 😌',
    ],
}

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
