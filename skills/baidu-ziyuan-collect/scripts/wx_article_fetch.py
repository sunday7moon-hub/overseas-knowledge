"""微信公众号文章采集工具（基于 Browser Bridge）

用法：
    python wx_article_fetch.py <url>

支持：
- 短链接: https://mp.weixin.qq.com/s/xxx
- 长链接: https://mp.weixin.qq.com/s?__biz=xxx&mid=xxx&idx=1&sn=xxx

输出 JSON: {title, publish_time, author, content, related: [{title, url}]}
"""

import json
import sys
import time

sys.path.insert(0, "/Users/yoyo/.workbuddy/skills/baidu-ziyuan-collect/scripts")
from control import Bridge


def fetch_article(url: str) -> dict:
    b = Bridge()
    if not b.is_connected():
        raise RuntimeError("Bridge 未连接，请确认 Chrome 扩展已打开")

    b.navigate(url)
    time.sleep(6)  # 等待页面加载

    # 标题 & 时间
    expr = """
    (() => {
      const title = (document.querySelector('#activity-name') || {}).innerText || '';
      const timeEl = document.querySelector('#publish_time') || document.querySelector('#publish_time_wechat');
      const time = timeEl ? timeEl.innerText : '';
      const author = (document.querySelector('#js_name') || {}).innerText || '';
      const content = (document.querySelector('#js_content') || {}).innerText || '';
      const related = Array.from(document.querySelectorAll('#js_related a, .weui-msg__link a, a[href*="mp.weixin.qq.com/s"]'))
        .map(a => ({t: (a.innerText || '').trim().slice(0, 60), u: a.href}))
        .filter(x => x.t && x.u.includes('/s'));
      // 去重
      const seen = new Set();
      const uniq = related.filter(x => { if (seen.has(x.u)) return false; seen.add(x.u); return true; });
      return JSON.stringify({title: title.trim(), time: time.trim(), author: author.trim(), content: content.trim(), related: uniq.slice(0, 10)});
    })()
    """
    result = b.evaluate(expr)
    data = json.loads(result)
    data["url"] = b.get_url().split("#")[0]
    return data


if __name__ == "__main__":
    url = sys.argv[1]
    data = fetch_article(url)
    print(json.dumps(data, ensure_ascii=False, indent=2))
