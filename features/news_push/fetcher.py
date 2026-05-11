from bs4 import BeautifulSoup
from typing import List, Dict
from utils.network import NetworkUtils


class NewsFetcher:
    @staticmethod
    def fetch_baidu_hot() -> List[Dict[str, str]]:
        url = "https://top.baidu.com/board?tab=realtime"
        html = NetworkUtils.get(url)
        if not html:
            return []

        try:
            soup = BeautifulSoup(html, 'lxml')
            items = []
            # 百度热搜的DOM结构可能变化，这里是示例
            for item in soup.select('.category-wrap_iQLoo .c-single-text-ellipsis')[:10]:
                title = item.get_text(strip=True)
                link = item.get('href', '')
                if title:
                    items.append({'title': title, 'link': link, 'source': '百度热搜'})
            return items
        except Exception as e:
            print(f"解析百度热搜失败: {e}")
            return []

    @staticmethod
    def fetch_weibo_hot() -> List[Dict[str, str]]:
        url = "https://s.weibo.com/top/summary"
        html = NetworkUtils.get(url)
        if not html:
            return []

        try:
            soup = BeautifulSoup(html, 'lxml')
            items = []
            # 微博热搜的DOM结构示例
            for item in soup.select('tbody tr')[:10]:
                title_tag = item.select_one('.td-02 a')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    link = 'https://s.weibo.com' + title_tag.get('href', '')
                    items.append({'title': title, 'link': link, 'source': '微博热搜'})
            return items
        except Exception as e:
            print(f"解析微博热搜失败: {e}")
            return []

    @staticmethod
    def fetch_google_trends() -> List[Dict[str, str]]:
        # Google Trends需要特殊处理，这里返回空列表作为占位
        # TODO: 实现Google Trends爬取
        return []

    @staticmethod
    def fetch_all() -> List[Dict[str, str]]:
        results = []
        results.extend(NewsFetcher.fetch_baidu_hot())
        results.extend(NewsFetcher.fetch_weibo_hot())
        results.extend(NewsFetcher.fetch_google_trends())
        return results
