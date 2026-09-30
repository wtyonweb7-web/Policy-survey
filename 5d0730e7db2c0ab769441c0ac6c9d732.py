"""
政府AI政策收集工具 - Flask 应用
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# 确保在项目目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    init_db, query_policies, get_statistics, get_sources,
    get_new_ai_policies, get_latest_crawl_time, update_archive_status,
)
from crawler import run_crawl
from notifier import notify_available, send_simple_notify
from config import CRAWL_INTERVAL_HOURS, HOST, PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# 爬取状态
crawl_lock = Lock()
crawl_status = {
    "running": False,
    "last_crawl": None,
    "next_crawl": None,
    "last_count": 0,
    "last_ai_count": 0,
    "errors": [],
}


def crawl_job():
    """定时爬取任务"""
    global crawl_status
    if not crawl_lock.acquire(blocking=False):
        logger.warning("[调度] 上次爬取尚未完成，跳过本次调度")
        return

    try:
        crawl_status["running"] = True
        logger.info("[调度] 开始定时爬取...")

        new_ai_policies, errors = run_crawl()

        crawl_status["last_crawl"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        crawl_status["total_count"] = (crawl_status.get("total_count", 0) or 0) + 1
        crawl_status["last_ai_count"] = len(new_ai_policies)
        crawl_status["errors"] = errors[-10:] if errors else []

        # 发送如流通知（如果可用）
        if new_ai_policies and notify_available():
            try:
                from notifier import send_self_notification
                send_self_notification(new_ai_policies)
            except Exception as e:
                logger.warning(f"[通知] 发送失败: {e}")

        logger.info(f"[调度] 爬取完成，新增 {len(new_ai_policies)} 条AI相关政策")
    except Exception as e:
        logger.error(f"[调度] 爬取出错: {e}")
    finally:
        crawl_status["running"] = False
        crawl_status["next_crawl"] = (
            datetime.now() + timedelta(hours=CRAWL_INTERVAL_HOURS)
        ).strftime("%Y-%m-%d %H:%M:%S")
        crawl_lock.release()


# 初始化调度器
scheduler = BackgroundScheduler()


def start_scheduler():
    """启动定时调度器"""
    # 延迟第一次爬取，让Web服务先启动
    scheduler.add_job(
        crawl_job,
        "interval",
        hours=CRAWL_INTERVAL_HOURS,
        id="crawl_policies",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(seconds=60),
    )
    scheduler.start()
    logger.info(f"[调度] 已启动，每 {CRAWL_INTERVAL_HOURS} 小时爬取一次（首次爬取将在60秒后开始）")


# ========== API 路由 ==========

@app.route("/")
def index():
    """前端首页"""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/policies", methods=["GET"])
def api_policies():
    """获取政策列表"""
    source = request.args.get("source", "")
    keyword = request.args.get("keyword", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    show_archived = request.args.get("show_archived", "0")
    ai_only = request.args.get("ai_only", "1")
    page = int(request.args.get("page", 1))
    limit = min(int(request.args.get("limit", 50)), 200)

    # 默认近7天
    if not date_from and not show_archived == "1":
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    is_archived = None
    if show_archived == "1":
        is_archived = 1  # 只看归档
    elif show_archived == "0":
        is_archived = 0  # 只看非归档

    result = query_policies(
        source=source,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        is_archived=is_archived,
        ai_related=True if ai_only == "1" else None,
        page=page,
        limit=limit,
    )

    return jsonify({
        "success": True,
        "data": result["data"],
        "total": result["total"],
        "page": result["page"],
        "limit": result["limit"],
    })


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """获取统计数据"""
    stats = get_statistics()
    return jsonify({"success": True, "data": stats})


@app.route("/api/sources", methods=["GET"])
def api_sources():
    """获取来源列表"""
    sources = get_sources()
    return jsonify({"success": True, "data": sources})


@app.route("/api/status", methods=["GET"])
def api_status():
    """获取爬取状态"""
    last_crawl_time = get_latest_crawl_time()
    return jsonify({
        "success": True,
        "data": {
            **crawl_status,
            "last_crawl_time": last_crawl_time,
            "notify_available": notify_available(),
        },
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """手动触发爬取"""
    global crawl_status
    if crawl_status["running"]:
        return jsonify({
            "success": False,
            "message": "正在爬取中，请稍后再试",
        })

    # 在后台线程中运行
    import threading
    thread = threading.Thread(target=crawl_job, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "message": "已开始爬取，请稍后刷新查看结果",
    })


@app.route("/api/policies/<int:policy_id>", methods=["GET"])
def api_policy_detail(policy_id):
    """获取政策详情"""
    from models import get_db
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM policies WHERE id = ?", (policy_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "message": "未找到"}), 404

    return jsonify({"success": True, "data": dict(row)})


@app.route("/api/archive/update", methods=["POST"])
def api_update_archive():
    """更新归档状态"""
    update_archive_status()
    return jsonify({"success": True, "message": "归档状态已更新"})


# ========== 启动 ==========

if __name__ == "__main__":
    # 初始化数据库
    logger.info("初始化数据库...")
    init_db()

    # 启动调度器
    start_scheduler()

    # 启动Web服务
    logger.info(f"启动Web服务: http://{HOST}:{PORT}")
    print(f"\n{'='*50}")
    print(f"  🤖 AI政策收集工具已启动!")
    print(f"  🌐 访问地址: http://localhost:{PORT}")
    print(f"  ⏰ 自动爬取: 每 {CRAWL_INTERVAL_HOURS} 小时")
    print(f"  📋 数据保留: 近7天活跃，历史数据可搜")
    print(f"{'='*50}\n")

    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)