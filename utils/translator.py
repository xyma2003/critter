import re


class Translator:
    @staticmethod
    def has_english(text: str) -> bool:
        return bool(re.search(r'[a-zA-Z]', text))

    @staticmethod
    def translate_to_chinese(text: str) -> str:
        # 简单实现：如果需要真实翻译，可以接入百度翻译API或Google翻译API
        # 这里仅作占位，返回原文
        # TODO: 实现真实的翻译功能
        return text
