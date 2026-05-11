from typing import List, Dict
from utils.translator import Translator


class NewsFormatter:
    @staticmethod
    def format_news_item(item: Dict[str, str]) -> str:
        title = item.get('title', '')
        link = item.get('link', '')
        source = item.get('source', '未知来源')

        # 检查是否包含英文
        if Translator.has_english(title):
            translation = Translator.translate_to_chinese(title)
            if translation != title:
                formatted = f"[{source}] {title}\n翻译: {translation}\n链接: {link}"
            else:
                formatted = f"[{source}] {title}\n链接: {link}"
        else:
            formatted = f"[{source}] {title}\n链接: {link}"

        return formatted

    @staticmethod
    def format_news_list(news_list: List[Dict[str, str]]) -> str:
        if not news_list:
            return "暂时没有获取到新闻，请稍后再试。"

        formatted_items = []
        for idx, item in enumerate(news_list[:15], 1):  # 最多显示15条
            formatted_items.append(f"{idx}. {NewsFormatter.format_news_item(item)}")

        return "\n\n".join(formatted_items)
