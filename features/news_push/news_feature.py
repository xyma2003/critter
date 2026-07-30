from features.base_feature import BaseFeature
from .fetcher import NewsFetcher
from .formatter import NewsFormatter
from PyQt6.QtCore import QThread, pyqtSignal


class NewsFetchWorker(QThread):
    """QThread worker for fetching news without blocking the UI.

    Uses pyqtSignal to communicate results back to the main thread.
    Never use threading.Thread + QTimer.singleShot — the timer gets
    created in the bg thread (no event loop) and the callback never fires.
    """
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, news_feature):
        super().__init__()
        self._news_feature = news_feature

    def run(self):
        try:
            result = self._news_feature.execute()
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))


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
