from features.base_feature import BaseFeature
from .fetcher import NewsFetcher
from .formatter import NewsFormatter
from PyQt6.QtCore import QThread, pyqtSignal


class NewsFetchThread(QThread):
    finished = pyqtSignal(list)

    def run(self):
        news_list = NewsFetcher.fetch_all()
        self.finished.emit(news_list)


class NewsFeature(BaseFeature):
    def __init__(self):
        self.fetch_thread = None

    def get_name(self) -> str:
        return "news_push"

    def get_button_text(self) -> str:
        return "推送今天的新闻"

    def execute(self) -> dict:
        from core.state_manager import load_news_cache, save_news_cache

        # 优先使用缓存
        cached_items, is_fresh = load_news_cache()
        if is_fresh and cached_items:
            return {
                'success': True,
                'message': NewsFormatter.format_news_list(cached_items),
                'data': cached_items,
            }

        # 缓存过期或不存在，重新获取
        news_list = NewsFetcher.fetch_all()
        if news_list:
            save_news_cache(news_list)
            return {
                'success': True,
                'message': NewsFormatter.format_news_list(news_list),
                'data': news_list,
            }

        # 网络失败但有旧缓存，降级返回
        if cached_items:
            return {
                'success': True,
                'message': f"(网络异常，显示缓存数据)\n{NewsFormatter.format_news_list(cached_items)}",
                'data': cached_items,
            }

        return {
            'success': False,
            'message': '获取新闻失败，请检查网络连接。',
            'data': [],
        }
