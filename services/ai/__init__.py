"""
services/ai — Claude CLI 辅助函数
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
        # 按编号匹配，忽略空行和多余文字，容忍 Claude 输出格式不稳定
        translated = [None] * len(titles)
        for line in result.stdout.split('\n'):
            m = re.match(r'^(\d+)\.\s+(.+)', line.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(titles):
                    translated[idx] = m.group(2).strip()
        # 只要所有条目都匹配到了就返回翻译结果，否则回退原文
        if all(t is not None for t in translated):
            return translated
    except Exception:
        pass
    return titles
