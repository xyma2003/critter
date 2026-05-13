import json
import urllib.request
from bs4 import BeautifulSoup
from typing import List, Dict
from utils.network import NetworkUtils


class NewsFetcher:
    @staticmethod
    def fetch_baidu_hot() -> List[Dict[str, str]]:
        """百度实时热搜"""
        url = "https://top.baidu.com/board?tab=realtime"
        html = NetworkUtils.get(url)
        if not html:
            return []
        try:
            soup = BeautifulSoup(html, 'lxml')
            items = []
            for wrap in soup.select('.category-wrap_iQLoo')[:10]:
                title_tag = wrap.select_one('.c-single-text-ellipsis')
                link_tag = wrap.select_one('a.img-wrapper_29V76')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                link = link_tag.get('href', '') if link_tag else ''
                if title:
                    items.append({'title': title, 'link': link, 'source': '百度热搜'})
            return items
        except Exception as e:
            print(f"解析百度热搜失败: {e}")
            return []

    @staticmethod
    def fetch_toutiao_hot() -> List[Dict[str, str]]:
        """今日头条热榜（JSON API）"""
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Referer': 'https://www.toutiao.com',
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode('utf-8'))
            items = []
            for entry in data.get('data', [])[:10]:
                title = entry.get('Title', '').strip()
                link = entry.get('Url', '')
                # 链接过长时截取到 topic_id 部分
                if '?' in link:
                    link = link.split('?')[0]
                if title:
                    items.append({'title': title, 'link': link, 'source': '头条热榜'})
            return items
        except Exception as e:
            print(f"解析头条热榜失败: {e}")
            return []

    @staticmethod
    def fetch_all() -> List[Dict[str, str]]:
        results = []
        results.extend(NewsFetcher.fetch_baidu_hot())
        results.extend(NewsFetcher.fetch_toutiao_hot())
        return results
