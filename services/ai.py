"""
services/ai.py — Claude CLI 辅助函数
"""
import re
import subprocess


def translate_titles_with_claude(titles):
    """用 Claude CLI 把英文标题批量翻译成「中文（原文）」格式。失败时返回原标题。"""
    if not titles:
        return titles
    numbered = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(titles))
    prompt = (
        '把下面的英文热搜词条翻译成中文，格式为「中文译名（原文）」，'
        '每行一条，保持编号，只输出翻译结果，不要解释：\n' + numbered
    )
    try:
        result = subprocess.run(
            ['/opt/homebrew/bin/claude', '--print', prompt],
            capture_output=True, text=True, timeout=30
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        translated = []
        for line in lines:
            line = re.sub(r'^\d+\.\s*', '', line)
            translated.append(line)
        if len(translated) == len(titles):
            return translated
    except Exception:
        pass
    return titles
