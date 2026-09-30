"""
政府AI政策收集工具 - 如流通知模块
"""
import os
import subprocess
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# infoflow-notify 脚本路径
NOTIFY_SCRIPT = os.path.expanduser(
    "/home/gem/workspace/.claude/skills/infoflow-notify/scripts/infoflow_notify.py"
)


def notify_available():
    """检查通知脚本是否可用"""
    return os.path.exists(NOTIFY_SCRIPT)


def send_self_notification(new_policies):
    """发送AI政策通知给当前用户"""
    if not new_policies:
        return

    if not notify_available():
        logger.warning("[通知] infoflow-notify 脚本不可用，跳过通知")
        return False

    # 构建通知消息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"## 🤖 AI政策更新 - {timestamp}",
        "",
        f"发现 **{len(new_policies)}** 条新的AI相关政策：",
        "",
    ]

    for i, policy in enumerate(new_policies[:10]):  # 最多显示10条
        source = policy.get("source", "未知来源")
        title = policy.get("title", "无标题")[:60]
        direction = policy.get("policy_direction", "")
        time_node = policy.get("time_nodes", "")
        lines.append(f"{i+1}. **[{source}]** {title}")
        if direction:
            lines.append(f"   📋 {direction}")
        if time_node:
            lines.append(f"   🕐 {time_node}")
        lines.append(f"   [查看原文]({policy.get('url', '#')})")
        lines.append("")

    if len(new_policies) > 10:
        lines.append(f"... 还有 {len(new_policies) - 10} 条未显示")
        lines.append("")

    lines.append("---")
    lines.append("> dodo AI政策收集工具 · 自动通知")

    message = "\n".join(lines)

    try:
        result = subprocess.run(
            ["python3", NOTIFY_SCRIPT, "notify-self", message],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"[通知] 成功发送 {len(new_policies)} 条AI政策通知")
            return True
        else:
            logger.warning(f"[通知] 发送失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        logger.warning(f"[通知] 发送异常: {type(e).__name__}: {e}")
        return False


def send_simple_notify(text):
    """发送简单文本通知"""
    if not notify_available():
        return False

    try:
        result = subprocess.run(
            ["python3", NOTIFY_SCRIPT, "notify-self", text],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False