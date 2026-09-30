"""
政府AI政策收集工具 - 爬虫模块
"""
import re
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse


def normalize_url(url):
    """URL归一化：用于去重，忽略 http/https、www 前缀、尾斜杠、片段差异"""
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
        scheme = "https"  # 统一使用https
        netloc = parsed.netloc.lower()
        path = parsed.path
        # 保留路径，但移除尾斜杠
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]
        # 移除无意义的查询参数（如 utm、tracking），保留其余
        query = ""
        if parsed.query:
            params = [p for p in parsed.query.split("&") if not any(
                t in p.lower() for t in ["utm_", "track", "from", "source="])]
            if params:
                query = "&".join(sorted(params))
        normalized = urlunparse((scheme, netloc, path, "", query, ""))
        return normalized
    except Exception:
        return url

from config import (
    SITES, CORE_KEYWORDS, CORE_PATTERNS, STRONG_KEYWORDS, BROAD_KEYWORDS,
    CORE_SCORE, STRONG_SCORE, BROAD_SCORE, AI_THRESHOLD, TITLE_BONUS,
    BROAD_ONLY_MIN, BROAD_ONLY_CAP,
    DIRECTION_PATTERNS, TIME_PATTERNS, ENTITY_PATTERNS,
)

# 最近一周的起始日期（不含当天）
RECENT_WEEK_START = "2026-07-15"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
# 编译关键词模式
_CORE_PATTERNS_COMPILED = [re.compile(p) for p in CORE_PATTERNS]
_STRONG_PATTERNS = [re.compile(re.escape(kw), re.IGNORECASE) for kw in STRONG_KEYWORDS]
_BROAD_PATTERNS = [re.compile(re.escape(kw), re.IGNORECASE) for kw in BROAD_KEYWORDS]

REMOVE_TAGS = ['script', 'style', 'nav', 'header', 'footer', 'aside',
               'iframe', 'noscript', 'meta', 'link']

# 地域检测：北京来源
BEIJING_SOURCES = ["北京市发改委", "市科委", "市经信局", "人民政府"]

# 用于检测"其他"地区的省份/城市前缀
REGION_PROVINCES = [
    "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃",
    "青海", "台湾", "内蒙古", "广西", "西藏", "宁夏", "新疆",
    "深圳", "广州", "杭州", "成都", "武汉", "南京", "苏州", "宁波",
    "湖州", "温州", "宁德", "泉州", "合肥", "长沙", "福州",
]

CONTENT_SELECTORS = [
    ".TRS_Editor", ".TRS_Editor2", ".Custom_UnionStyle",
    ".article-content", ".article_con", ".article_conten",
    "#content", ".content", ".main-content",
    ".news-content", ".news_text", ".text-content",
    ".article", ".maintext", ".txt_content",
    "#zoom", "#article-content", ".article-box",
]


def generate_page_urls(base_url, site_config):
    """根据站点配置生成分页URL列表
    page_style 说明:
      - index_numbered: / → index_1.html, index_2.html (跳过index.html，因为与/等价)
      - none: 不分页，仅返回基础URL
      - 空/默认: 使用原有猜测逻辑
    """
    max_pages = site_config.get("max_pages", 3)
    page_style = site_config.get("page_style", "")

    if page_style == "none" or max_pages <= 1:
        return [base_url]

    urls = [base_url]

    if page_style == "index_numbered":
        for page in range(1, max_pages):
            if base_url.endswith('/'):
                url = base_url + f'index_{page}.html'
            else:
                url = base_url + f'/index_{page}.html'
            urls.append(url)
        return urls[:max_pages]

    # 原有默认分页猜测逻辑
    for page in range(1, max_pages):
        if base_url.endswith('.html'):
            url = base_url.replace('.html', f'_{page}.html')
        elif base_url.endswith('.htm'):
            url = base_url.replace('.htm', f'_{page}.htm')
        elif base_url.endswith('/'):
            if page == 1:
                url = base_url + 'index.html'
            else:
                url = base_url + f'index_{page}.html'
        else:
            url = base_url + f'/index_{page}.html'
        urls.append(url)
    return urls[:max_pages]


class Crawler:
    """爬虫类，管理所有站点的爬取"""

    def __init__(self):
        self.results = []
        self.errors = []
        self.crawl_log = []  # 记录每个站点的爬取过程（用于前端展示运算思维过程）

    def _log(self, site_name, message):
        """记录一条爬取过程日志"""
        self.crawl_log.append({
            "site": site_name,
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message,
        })

    def fetch(self, url, encoding=None, timeout=20, extra_headers=None):
        """获取页面内容"""
        try:
            resp = SESSION.get(url, timeout=timeout, headers=extra_headers or {})
            resp.raise_for_status()
            if encoding:
                resp.encoding = encoding
            else:
                if resp.apparent_encoding and resp.apparent_encoding.lower() in ('gbk', 'gb2312', 'gb18030'):
                    resp.encoding = resp.apparent_encoding
                elif resp.encoding and resp.encoding.lower() == 'iso-8859-1':
                    resp.encoding = 'utf-8'
            return resp.text
        except Exception as e:
            self.errors.append(f"[FETCH ERROR] {url}: {type(e).__name__}: {e}")
            return None

    def extract_content(self, soup):
        """从详情页提取正文内容（完整保留段落结构）"""
        for tag in REMOVE_TAGS:
            for el in soup.find_all(tag):
                el.decompose()

        # 优先使用已知选择器
        for selector in CONTENT_SELECTORS:
            el = soup.select_one(selector)
            if el:
                paragraphs = []
                for p in el.find_all(['p', 'div', 'section', 'article']):
                    t = p.get_text(strip=True)
                    if len(t) > 10:
                        paragraphs.append(t)
                if paragraphs:
                    return '\n\n'.join(paragraphs)[:8000]
                text = el.get_text(strip=True)
                if len(text) > 200:
                    return text[:8000]

        # 备选：找最大文本块
        candidates = []
        for div in soup.find_all("div"):
            cls = " ".join(div.get("class", []))
            if any(kw in cls.lower() for kw in ["nav", "header", "footer", "menu", "sidebar", "toolbar", "crumb"]):
                continue
            text = div.get_text(separator='\n', strip=True)
            if 500 < len(text) < 50000:
                candidates.append((len(text), text))
        candidates.sort(reverse=True)
        return candidates[0][1][:8000] if candidates else ""

    def detect_article_type(self, title, content):
        """识别文章类型：政策文件 / 会议活动 / 通知公告 / 新闻动态 / 信息发布"""
        text = (title + "\n" + content)[:2000]
        if re.search(r"(办法|通知|意见|方案|规定|条例|实施细则|指导意见|措施|行动方案)", title):
            return "政策文件"
        if re.search(r"(召开|主持|出席|讲话|强调|指出|会议要求)", text):
            return "会议活动"
        if re.search(r"(公示|公告|征集|招聘|报名|通知|招标|采购|遴选)", title):
            return "通知公告"
        if re.search(r"(发布|报道|举办|启动|上线|开幕|签约)|\d+家|\d+个", text[:500]):
            return "新闻动态"
        return "信息发布"

    def extract_summary(self, title, content, keywords_hit):
        """提取文章摘要（优先含关键词段落）"""
        if not content:
            return title[:150]
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 20]
        if not paragraphs:
            return content[:300]
        for p in paragraphs:
            for kw in keywords_hit:
                if kw.lower() in p.lower() and len(p) > 30:
                    return p[:300]
        return paragraphs[0][:300] if len(paragraphs[0]) > 30 else " ".join(paragraphs[:3])[:300]

    def calculate_ai_score(self, title, content):
        """三级AI评分：核心(15) / 强相关(8) / 宽泛(2)，阈值6
           宽泛词积累：4+个宽泛词同时命中时可直接判定为AI相关"""
        text_lower = (title + "\n" + content).lower()
        title_lower = title.lower()
        matched = set()
        score = 0
        broad_count = 0
        has_core_or_strong = False

        # 一级：核心词
        for kw in CORE_KEYWORDS:
            if kw.lower() in text_lower:
                score += CORE_SCORE
                matched.add(kw)
                has_core_or_strong = True
        for pattern in _CORE_PATTERNS_COMPILED:
            if pattern.search(text_lower):
                score += CORE_SCORE
                matched.add(pattern.pattern)
                has_core_or_strong = True

        # 二级：强相关词
        for i, pattern in enumerate(_STRONG_PATTERNS):
            if pattern.search(text_lower):
                score += STRONG_SCORE
                matched.add(STRONG_KEYWORDS[i])
                has_core_or_strong = True

        # 三级：宽泛词
        for i, pattern in enumerate(_BROAD_PATTERNS):
            if pattern.search(text_lower):
                broad_count += 1
                matched.add(BROAD_KEYWORDS[i])

        if has_core_or_strong:
            # 有核心/强相关时，宽泛词提供额外加分（上限3个*2=6分）
            score += min(broad_count, 3) * BROAD_SCORE
        elif broad_count >= BROAD_ONLY_MIN:
            # 无核心/强相关但4+个宽泛词命中，宽泛词积累判定
            score = min(broad_count, BROAD_ONLY_CAP) * BROAD_SCORE

        # 标题命中加分
        for kw in list(matched):
            if kw.lower() in title_lower:
                score += TITLE_BONUS

        return score, score >= AI_THRESHOLD, list(matched)

    def extract_policy_info(self, text):
        """提取政策导向性信息"""
        directions = []
        measures = []
        time_nodes = []
        entities = []

        for name, pattern in DIRECTION_PATTERNS:
            if pattern.search(text):
                directions.append(name)

        for pattern in TIME_PATTERNS:
            for m in pattern.finditer(text):
                time_nodes.append(m.group(1))

        for pattern in ENTITY_PATTERNS:
            for m in pattern.finditer(text):
                entities.append(m.group(1))

        measure_patterns = [
            re.compile(r"（[一二三四五六七八九十]+）\s*([^。]{10,}?。)", re.DOTALL),
            re.compile(r"\d+[\.\、]\s*([^。]{10,}?。)", re.DOTALL),
            re.compile(r"[一二三四五六七八九十]+[\.\、]\s*([^。]{10,}?。)", re.DOTALL),
            re.compile(r"（\d+）\s*([^。]{10,}?。)", re.DOTALL),
        ]
        for pattern in measure_patterns:
            for m in pattern.finditer(text):
                content = m.group(1).strip()
                if len(content) > 10 and content not in measures:
                    measures.append(content)
                    if len(measures) >= 5:
                        break
            if measures:
                break

        time_nodes = list(dict.fromkeys(time_nodes))
        entities = list(dict.fromkeys(entities))
        directions = list(dict.fromkeys(directions))
        measures = list(dict.fromkeys(measures))

        return {
            "policy_direction": "、".join(directions[:5]) if directions else "",
            "specific_measures": "\n".join(measures[:5]) if measures else "",
            "time_nodes": "、".join(time_nodes[:10]) if time_nodes else "",
            "responsible_entity": "、".join(entities[:5]) if entities else "",
        }

    def extract_publish_date(self, soup, url):
        """从页面或URL中提取发布日期（多策略）"""
        page_text = soup.get_text() if soup else ''

        # ========== 策略1: 从meta标签提取（最可靠） ==========
        for selector in ['meta[name="publish-date"]', 'meta[name="PubDate"]',
                         'meta[name="dc.date"]', 'meta[itemprop="datePublished"]',
                         'meta[property="article:published_time"]',
                         '#publish_date', '.publish-date', '.pub-date']:
            el = soup.select_one(selector)
            if el:
                content = el.get('content') or el.get('datetime') or el.get_text(strip=True)
                if content:
                    m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', content)
                    if m:
                        return m.group(1).replace('/', '-')

        # ========== 策略2: 从DOM中的时间标签提取 ==========
        for selector in ['.time', '.date', '.article-info', '.info', '.source',
                         '.article-header', '.head-title', '.title-bar',
                         'time', '.news-info', '.article-source',
                         'span:contains(日期)', 'em:contains(日期)',
                         '.article_date', '.article_clock']:
            els = soup.select(selector) if soup else []
            for el in els:
                text = el.get_text(strip=True)
                m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', text)
                if m:
                    return m.group(1).replace('/', '-')

        # ========== 策略3: 从URL中提取日期（政府网站URL路径通常包含日期） ==========
        # 优先匹配 /YYYYMMDD/ 格式
        m = re.search(r'/(20\d{2})(\d{2})(\d{2})/', url)
        if m:
            return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
        # 匹配 tYYYYMMDD_ 或 t20260715 格式（教育部等网站常见）
        m = re.search(r'[t/](\d{4})(\d{2})(\d{2})[\b_/\.]', url)
        if m:
            return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
        # 匹配 /YYYYMM/ 格式（仅年月，默认用01作为日）
        m = re.search(r'/(20\d{2})(\d{2})/', url)
        if m:
            return f'{m.group(1)}-{m.group(2)}-01'

        # ========== 策略4: 从正文找"发布日期：YYYY-MM-DD"等关键词前缀日期 ==========
        date_keyword_patterns = [
            # 中文格式：发布日期：2026年7月20日
            r'(?:发布日期|发布时间|发文日期|成文日期|印发日期|公布日期|生成日期|创建日期)[:：\s]*(\d{4})年(\d{1,2})月(\d{1,2})日',
            # 横杠格式：发布日期：2026-07-20
            r'(?:发布日期|发布时间|发文日期|成文日期|印发日期|公布日期|生成日期|创建日期)[:：\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            # 简短前缀：日期：2026-07-20
            r'(?:日期|时间)[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        ]
        for pat in date_keyword_patterns:
            m = re.search(pat, page_text[:2000])
            if m:
                if m.lastindex == 3:
                    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
                return m.group(1).replace('/', '-')

        return ''

    def detect_region(self, title, source_name, content=''):
        """检测文章地域：全国 / 北京 / 其他"""
        if source_name in BEIJING_SOURCES:
            return "北京"
        title_clean = title.strip()
        # 检查标题是否以省份/城市名开头
        for province in REGION_PROVINCES:
            if title_clean.startswith(province):
                return "其他"

        # 检查正文前300字是否聚焦某个特定地区（针对全国性来源的本地新闻）
        if content and len(content) > 100:
            content_start = content[:500]
            for province in REGION_PROVINCES:
                if province in content_start[:50]:
                    # 如果省份名出现在正文前50字，说明文章主要是关于该地区的
                    return "其他"

        return "全国"

    def parse_articles_from_list(self, html, source_config):
        """从列表页解析文章条目（同时从<span>标签提取日期）"""
        soup = BeautifulSoup(html, "html.parser")
        articles = []
        seen_urls = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 8:
                continue

            base_url = source_config["list_urls"][0]
            if href.startswith("http"):
                full_url = href
            elif href.startswith("./"):
                full_url = urljoin(base_url.rstrip("/") + "/", href[2:])
            elif href.startswith("/"):
                full_url = "https://" + source_config["domain"] + href
            elif href.startswith("//"):
                full_url = "https:" + href
            else:
                continue
            full_url = normalize_url(full_url)

            if full_url in seen_urls:
                continue

            has_date = bool(re.search(r"202\d|20[2-9]\d", full_url))
            is_article = has_date and (
                "/t" in full_url or "/art/" in full_url or "content" in full_url
            )
            # 对于没有日期数字在URL中的站点（如SASAC），跳过日期检查
            if not is_article and source_config.get("skip_date_check") and (
                "content" in full_url
            ):
                is_article = True

            if is_article:
                seen_urls.add(full_url)
                # 尝试从列表页的 <span> 或父元素中提取日期
                list_date = self._extract_date_from_list_item(a_tag)
                articles.append({"url": full_url, "title": title, "list_date": list_date})

        if len(articles) < 3:
            for ul in soup.find_all(["ul", "div"], class_=re.compile(
                r"(list|news|cont|u-list|article|item|main)"
            )):
                for li in ul.find_all("li"):
                    a = li.find("a")
                    if a and a.get_text(strip=True):
                        title = a.get_text(strip=True)
                        if len(title) < 8:
                            continue
                        href = a.get("href", "")
                        if href.startswith("./"):
                            full_url = urljoin(base_url.rstrip("/") + "/", href[2:])
                        elif href.startswith("/"):
                            full_url = "https://" + source_config["domain"] + href
                        elif href.startswith("http"):
                            full_url = href
                        else:
                            full_url = urljoin(base_url, href)
                        full_url = normalize_url(full_url)
                        if full_url not in seen_urls and (re.search(r"20\d{2}", full_url) or source_config.get("skip_date_check")):
                            seen_urls.add(full_url)
                            list_date = self._extract_date_from_list_item(a)
                            articles.append({"url": full_url, "title": title, "list_date": list_date})

        return articles[:50]

    def _extract_date_from_list_item(self, a_tag):
        """从列表页的<a>标签附近提取日期"""
        # 策略1: 检查父级 <li> 中的 <span> 或 <em> 日期文本
        parent = a_tag.parent
        if parent:
            for span in parent.find_all(["span", "em", "time"]):
                text = span.get_text(strip=True)
                m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', text)
                if m:
                    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
        # 策略2: 检查 <li> 的相邻文本节点
        if parent and parent.name == 'li':
            full_text = parent.get_text(strip=True)
            m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', full_text)
            if m:
                return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
        return ''

    def crawl_site(self, site_config):
        """爬取单个站点（支持分页，按列表页日期提前终止翻页避免抓取历史存量文章）"""
        site_name = site_config["name"]
        max_pages = site_config.get("max_pages", 3)
        max_articles = site_config.get("max_articles", 80)
        skip_date_check = site_config.get("skip_date_check", False)
        print(f"  [爬取] {site_name} (最多{max_pages}页/{max_articles}篇)...")
        self._log(site_name, f"开始爬取，目标栏目：{site_config['list_urls'][0]}，最多翻{max_pages}页")
        articles = []
        seen_urls = set()
        extra_headers = site_config.get("headers", {})

        for list_url in site_config["list_urls"]:
            page_urls = generate_page_urls(list_url, site_config)
            for page_url in page_urls:
                html = self.fetch(page_url, site_config.get("encoding"))
                if not html:
                    self._log(site_name, f"页面请求失败，跳过：{page_url}")
                    continue
                found = self.parse_articles_from_list(html, site_config)
                if not found:
                    continue

                page_has_new = False
                page_dates = [a["list_date"] for a in found if a.get("list_date")]

                for a in found:
                    norm_url = normalize_url(a["url"])
                    if norm_url not in seen_urls:
                        seen_urls.add(norm_url)
                        a["url"] = norm_url
                        articles.append(a)
                        page_has_new = True

                # ====== 翻页提前终止：若本页文章日期均早于最近一周起始日，说明已翻出本周范围，停止翻页 ======
                if not skip_date_check and page_dates:
                    if all(d < RECENT_WEEK_START for d in page_dates):
                        self._log(site_name, f"第{page_urls.index(page_url)+1}页文章日期均早于{RECENT_WEEK_START}，判定已超出最近一周范围，提前停止翻页（避免抓取历史存量）")
                        print(f"    -> 第{page_urls.index(page_url)+1}页文章均早于{RECENT_WEEK_START}，提前停止翻页")
                        break

                if len(articles) >= max_articles * 2:  # 收集更多用于去重
                    break
            if len(articles) >= max_articles * 2:
                break

        print(f"    -> 找到 {len(articles)} 篇文章")
        self._log(site_name, f"列表页解析完成，共发现 {len(articles)} 篇候选文章，开始逐篇请求详情页并做AI评分")

        site_results = []
        for article in articles[:max_articles]:
            time.sleep(0.5)
            try:
                detail_html = self.fetch(article["url"], site_config.get("encoding"), extra_headers=extra_headers)
                if not detail_html:
                    continue

                soup = BeautifulSoup(detail_html, "html.parser")
                title = article["title"]
                content = self.extract_content(soup)
                # 优先用列表页日期（更准确），否则从详情页提取
                publish_date = article.get("list_date", "") or self.extract_publish_date(soup, article["url"])
                region = self.detect_region(title, site_name, content)

                # 过滤非北京/全国的地域性文章
                if region == "其他":
                    continue

                if not content:
                    continue

                ai_score, is_ai_related, keywords = self.calculate_ai_score(title, content)
                article_type = self.detect_article_type(title, content) if is_ai_related else ""

                # ====== 日期过滤：最近一周（7/15~7/22）+ 标记归档 ======
                is_recent = False
                if publish_date and publish_date >= RECENT_WEEK_START:
                    is_recent = True

                summary = self.extract_summary(title, content, keywords) if is_ai_related else content[:200]
                policy_info = self.extract_policy_info(content) if is_ai_related else {}

                now = datetime.now().strftime("%Y-%m-%d %H:%M")

                result = {
                    "title": title,
                    "url": article["url"],
                    "source": site_name,
                    "region": region,
                    "publish_date": publish_date,
                    "crawl_date": now,
                    "content_text": content[:8000],
                    "summary": summary,
                    "ai_score": ai_score,
                    "is_ai_related": 1 if is_ai_related else 0,
                    "is_recent": 1 if is_recent else 0,
                    "article_type": article_type,
                    "policy_keywords": "、".join(keywords[:8]) if keywords else "",
                    "policy_direction": policy_info.get("policy_direction", ""),
                    "specific_measures": policy_info.get("specific_measures", ""),
                    "time_nodes": policy_info.get("time_nodes", ""),
                    "responsible_entity": policy_info.get("responsible_entity", ""),
                }
                site_results.append(result)

                if is_ai_related:
                    print(f"    v AI相关: {title[:50]} (分数:{ai_score}) [{article_type}] [{', '.join(keywords[:4])}]")
                else:
                    print(f"    . 非AI: {title[:40]}")

            except Exception as e:
                self.errors.append(f"[PARSE ERROR] {article['url']}: {type(e).__name__}: {e}")
                continue

        return site_results

    def _get_nested_value(self, doc, key_path):
        """从嵌套字典中按点号路径取值"""
        if not key_path:
            return None
        parts = key_path.split(".")
        value = doc
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def crawl_via_search_api(self, site_config):
        """通过搜索API爬取（支持交通运输部、工信部等搜索模式）"""
        site_name = site_config["name"]
        api_conf = site_config["search_api"]
        method = api_conf.get("method", "POST")
        api_url = api_conf["url"]
        base_params = dict(api_conf["params"])
        max_articles = site_config.get("max_articles", 80)

        # 使用配置中的搜索关键词（默认：人工智能）
        search_keywords = api_conf.get("search_keywords", ["人工智能"])
        all_articles = []
        seen_urls = set()

        print(f"  [搜索] {site_name} (关键词: {'/'.join(search_keywords)})...")
        self._log(site_name, f"通过搜索API爬取，关键词组：{'/'.join(search_keywords)}")

        # 部分搜索API（如工信部）有WAF防护，缺少Referer头会返回403
        extra_headers = api_conf.get("headers", {})

        query_param = api_conf.get("query_param", "qt")
        for keyword in search_keywords:
            params = dict(base_params)
            params[query_param] = keyword
            page = 1

            while len(all_articles) < max_articles:
                params[api_conf.get("page_param", "page")] = page
                try:
                    if method == "POST":
                        resp = SESSION.post(api_url, data=params, headers=extra_headers, timeout=20)
                    else:
                        resp = SESSION.get(api_url, params=params, headers=extra_headers, timeout=20)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    self.errors.append(f"[SEARCH API ERROR] {site_name}: {type(e).__name__}: {e}")
                    break

                # 沿 response_path 导航到文档列表
                docs = data
                path_parts = api_conf.get("response_path", [])
                for part in path_parts:
                    if isinstance(docs, dict):
                        docs = docs.get(part, {})
                    else:
                        docs = None
                        break

                if not docs or not isinstance(docs, list):
                    break

                found_new = 0
                for doc in docs:
                    raw_title = self._get_nested_value(doc, api_conf["title_key"])
                    raw_url = self._get_nested_value(doc, api_conf["url_key"])
                    if not raw_title or not raw_url:
                        continue
                    title = raw_title.strip()
                    if len(title) < 8:
                        continue

                    # 构建完整URL
                    if raw_url.startswith("http"):
                        full_url = raw_url
                    else:
                        prefix = api_conf.get("url_prefix", f"https://{site_config['domain']}")
                        full_url = prefix.rstrip("/") + "/" + raw_url.lstrip("/")

                    full_url = normalize_url(full_url)

                    # 域名过滤（如仅保留 mot.gov.cn 域下的结果）
                    domain_filter = api_conf.get("domain_filter")
                    if domain_filter:
                        parsed_url = urlparse(full_url)
                        url_domain = parsed_url.netloc
                        if not any(fd in url_domain for fd in domain_filter):
                            continue

                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    # 提取日期
                    publish_date = ""
                    date_val = self._get_nested_value(doc, api_conf.get("date_key", ""))
                    if date_val:
                        # 尝试不同日期格式
                        if isinstance(date_val, (int, float)):
                            # 毫秒时间戳
                            try:
                                publish_date = datetime.fromtimestamp(date_val / 1000).strftime("%Y-%m-%d")
                            except Exception:
                                pass
                        elif re.search(r"^\d{4}-\d{2}-\d{2}", str(date_val)):
                            publish_date = str(date_val)[:10]
                        elif re.search(r"^\d{4}\d{2}\d{2}", str(date_val)):
                            try:
                                publish_date = datetime.strptime(str(date_val)[:8], "%Y%m%d").strftime("%Y-%m-%d")
                            except Exception:
                                pass

                    all_articles.append({
                        "url": full_url,
                        "title": title,
                        "publish_date": publish_date,
                    })
                    found_new += 1

                page += 1
                if found_new == 0:
                    break  # 没有更多结果
                time.sleep(0.5)

        print(f"    -> 搜索到 {len(all_articles)} 篇文章（去重后）")
        self._log(site_name, f"搜索完成，去重后共 {len(all_articles)} 篇候选文章，开始逐篇请求详情页并做AI评分")

        # 限制文章数量
        articles = all_articles[:max_articles]

        # 爬取详情页并做AI评分（与crawl_site相同的逻辑）
        site_results = []
        for article in articles:
            time.sleep(0.5)
            try:
                detail_html = self.fetch(article["url"], site_config.get("encoding"), extra_headers=extra_headers)
                if not detail_html:
                    continue

                soup = BeautifulSoup(detail_html, "html.parser")
                title = article["title"]
                content = self.extract_content(soup)

                # 如果API已有日期则直接使用，否则从页面提取
                if article.get("publish_date"):
                    publish_date = article["publish_date"]
                else:
                    publish_date = self.extract_publish_date(soup, article["url"])

                region = self.detect_region(title, site_name, content)

                if region == "其他":
                    continue
                if not content:
                    continue

                ai_score, is_ai_related, keywords = self.calculate_ai_score(title, content)
                article_type = self.detect_article_type(title, content) if is_ai_related else ""
                summary = self.extract_summary(title, content, keywords) if is_ai_related else content[:200]
                policy_info = self.extract_policy_info(content) if is_ai_related else {}

                now = datetime.now().strftime("%Y-%m-%d %H:%M")

                result = {
                    "title": title,
                    "url": article["url"],
                    "source": site_name,
                    "region": region,
                    "publish_date": publish_date,
                    "crawl_date": now,
                    "content_text": content[:8000],
                    "summary": summary,
                    "ai_score": ai_score,
                    "is_ai_related": 1 if is_ai_related else 0,
                    "article_type": article_type,
                    "policy_keywords": "、".join(keywords[:8]) if keywords else "",
                    "policy_direction": policy_info.get("policy_direction", ""),
                    "specific_measures": policy_info.get("specific_measures", ""),
                    "time_nodes": policy_info.get("time_nodes", ""),
                    "responsible_entity": policy_info.get("responsible_entity", ""),
                }
                site_results.append(result)

                if is_ai_related:
                    print(f"    v AI相关: {title[:50]} (分数:{ai_score}) [{article_type}] [{', '.join(keywords[:4])}]")
                else:
                    print(f"    . 非AI: {title[:40]}")

            except Exception as e:
                self.errors.append(f"[PARSE ERROR] {article['url']}: {type(e).__name__}: {e}")
                continue

        ai_count = sum(1 for r in site_results if r["is_ai_related"])
        self._log(site_name, f"完成，共入库 {len(site_results)} 篇（AI相关 {ai_count} 篇）")
        return site_results

    def run_all(self):
        """运行所有站点爬虫"""
        from models import upsert_policy, update_archive_status

        all_new_ai = []
        self.results = []
        self.errors = []
        self.crawl_log = []

        print(f"\n{'='*50}")
        print(f"开始全量爬取 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}")

        for site in SITES:
            try:
                if "search_api" in site:
                    results = self.crawl_via_search_api(site)
                else:
                    results = self.crawl_site(site)
                for r in results:
                    upsert_policy(r)
                    if r["is_ai_related"]:
                        all_new_ai.append(r)
                self.results.extend(results)
                ai_count = sum(1 for r in results if r["is_ai_related"])
                print(f"  [{site['name']}] 完成: {len(results)} 篇, {ai_count} 篇AI相关")
            except Exception as e:
                self.errors.append(f"[SITE ERROR] {site['name']}: {type(e).__name__}: {e}")
                self._log(site["name"], f"站点爬取异常终止：{type(e).__name__}: {e}")
                print(f"  [错误] {site['name']}: {e}")

        update_archive_status()
        self._save_crawl_log()

        print(f"\n{'='*50}")
        print(f"爬取完成! 总计: {len(self.results)} 篇, AI相关: {len(all_new_ai)} 篇")
        if self.errors:
            print(f"错误: {len(self.errors)} 个")
            for e in self.errors[-5:]:
                print(f"  {e[:120]}")
        print(f"{'='*50}")

        return all_new_ai

    def _save_crawl_log(self):
        """将本次爬取的过程日志持久化到本地JSON文件，供HTML报告展示"""
        import json
        log_data = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recent_week_start": RECENT_WEEK_START,
            "entries": self.crawl_log,
            "errors": self.errors[-20:],
        }
        try:
            with open("crawl_log.json", "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [警告] 爬取日志保存失败: {e}")


def run_crawl():
    """运行爬虫的便捷函数"""
    crawler = Crawler()
    new_ai = crawler.run_all()
    return new_ai, crawler.errors
