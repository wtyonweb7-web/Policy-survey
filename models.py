"""
政府AI政策收集工具 - 数据库模型
"""
import sqlite3
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse
from config import DB_PATH, ACTIVE_DAYS


def _normalize_url(url):
    """URL归一化：忽略 http/https、www 前缀、尾斜杠、片段差异"""
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
        scheme = "https"
        netloc = parsed.netloc.lower()
        path = parsed.path
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]
        query = ""
        if parsed.query:
            params = [p for p in parsed.query.split("&") if not any(
                t in p.lower() for t in ["utm_", "track", "from", "source="])]
            if params:
                query = "&".join(sorted(params))
        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:
        return url


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            region TEXT DEFAULT '全国',
            publish_date TEXT DEFAULT '',
            crawl_date TEXT NOT NULL,
            content_text TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            ai_score REAL DEFAULT 0,
            is_ai_related INTEGER DEFAULT 0,
            article_type TEXT DEFAULT '',
            policy_keywords TEXT DEFAULT '',
            policy_direction TEXT DEFAULT '',
            specific_measures TEXT DEFAULT '',
            time_nodes TEXT DEFAULT '',
            responsible_entity TEXT DEFAULT '',
            is_archived INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_policies_source ON policies(source);
        CREATE INDEX IF NOT EXISTS idx_policies_publish_date ON policies(publish_date);
        CREATE INDEX IF NOT EXISTS idx_policies_ai_related ON policies(is_ai_related);
        CREATE INDEX IF NOT EXISTS idx_policies_archived ON policies(is_archived);
        CREATE INDEX IF NOT EXISTS idx_policies_crawl_date ON policies(crawl_date);
    """)
    conn.commit()
    conn.close()


def upsert_policy(policy):
    """插入或更新一条政策记录"""
    # URL归一化，防止 http/https、www 前缀不同导致重复
    policy["url"] = _normalize_url(policy["url"])

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM policies WHERE url = ?", (policy["url"],)
    ).fetchone()

    if existing:
        # 更新已有记录
        conn.execute("""
            UPDATE policies SET
                title = ?, content_text = ?, summary = ?,
                ai_score = ?, is_ai_related = ?,
                article_type = ?, policy_keywords = ?,
                policy_direction = ?, specific_measures = ?,
                time_nodes = ?, responsible_entity = ?,
                publish_date = ?, crawl_date = ?, region = ?
            WHERE url = ?
        """, (
            policy["title"], policy["content_text"], policy["summary"],
            policy["ai_score"], policy["is_ai_related"],
            policy.get("article_type", ""), policy.get("policy_keywords", ""),
            policy["policy_direction"], policy["specific_measures"],
            policy["time_nodes"], policy["responsible_entity"],
            policy["publish_date"], policy["crawl_date"],
            policy.get("region", "全国"),
            policy["url"],
        ))
    else:
        conn.execute("""
            INSERT INTO policies
                (title, url, source, region, publish_date, crawl_date,
                 content_text, summary, ai_score, is_ai_related,
                 article_type, policy_keywords,
                 policy_direction, specific_measures, time_nodes, responsible_entity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            policy["title"], policy["url"], policy["source"],
            policy.get("region", "全国"),
            policy["publish_date"], policy["crawl_date"],
            policy["content_text"], policy["summary"],
            policy["ai_score"], policy["is_ai_related"],
            policy.get("article_type", ""), policy.get("policy_keywords", ""),
            policy["policy_direction"], policy["specific_measures"],
            policy["time_nodes"], policy["responsible_entity"],
        ))

    conn.commit()
    conn.close()


def update_archive_status():
    """将超过7天的数据标记为归档"""
    cutoff = (datetime.now() - timedelta(days=ACTIVE_DAYS)).strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute(
        "UPDATE policies SET is_archived = 1 WHERE publish_date < ? AND publish_date != '' AND is_archived = 0",
        (cutoff,)
    )
    conn.commit()
    conn.close()


def query_policies(source="", keyword="", region="", date_from="", date_to="",
                   is_archived=None, ai_related=None, page=1, limit=50):
    """查询政策列表"""
    conn = get_db()
    conditions = []
    params = []

    if source:
        conditions.append("source = ?")
        params.append(source)

    if region:
        conditions.append("region = ?")
        params.append(region)

    if keyword:
        conditions.append("(title LIKE ? OR content_text LIKE ? OR summary LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw])

    if date_from:
        conditions.append("publish_date >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("publish_date <= ?")
        params.append(date_to)

    if is_archived is not None:
        if is_archived:
            conditions.append("is_archived = 1")
        else:
            conditions.append("is_archived = 0")

    if ai_related is not None and ai_related:
        conditions.append("is_ai_related = 1")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # 总数
    count_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM policies {where}", params
    ).fetchone()
    total = count_row["cnt"] if count_row else 0

    # 分页数据
    offset = (page - 1) * limit
    rows = conn.execute(
        f"SELECT * FROM policies {where} ORDER BY publish_date DESC, id DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()

    conn.close()
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [dict(r) for r in rows],
    }


def get_statistics():
    """获取统计数据"""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    stats = {
        "total": conn.execute("SELECT COUNT(*) as c FROM policies").fetchone()["c"],
        "ai_related": conn.execute("SELECT COUNT(*) as c FROM policies WHERE is_ai_related = 1").fetchone()["c"],
        "active": conn.execute("SELECT COUNT(*) as c FROM policies WHERE is_archived = 0").fetchone()["c"],
        "archived": conn.execute("SELECT COUNT(*) as c FROM policies WHERE is_archived = 1").fetchone()["c"],
        "new_today": conn.execute("SELECT COUNT(*) as c FROM policies WHERE crawl_date = ?", (today,)).fetchone()["c"],
        "ai_this_week": conn.execute(
            "SELECT COUNT(*) as c FROM policies WHERE is_ai_related = 1 AND publish_date >= ?", (week_ago,)
        ).fetchone()["c"],
        "sources": {},
    }

    # 各来源统计
    rows = conn.execute(
        "SELECT source, COUNT(*) as c FROM policies WHERE is_archived = 0 GROUP BY source ORDER BY c DESC"
    ).fetchall()
    for r in rows:
        stats["sources"][r["source"]] = r["c"]

    conn.close()
    return stats


def get_sources():
    """获取所有数据来源"""
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT source FROM policies ORDER BY source").fetchall()
    conn.close()
    return [r["source"] for r in rows]


def get_new_ai_policies(since_crawl=None):
    """获取上次爬取后新增的AI相关政策"""
    conn = get_db()
    if since_crawl:
        rows = conn.execute(
            "SELECT * FROM policies WHERE is_ai_related = 1 AND created_at > ? ORDER BY publish_date DESC",
            (since_crawl,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM policies WHERE is_ai_related = 1 ORDER BY publish_date DESC LIMIT 20"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_crawl_time():
    """获取最近一次爬取时间"""
    conn = get_db()
    row = conn.execute(
        "SELECT crawl_date FROM policies ORDER BY crawl_date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["crawl_date"] if row else None
