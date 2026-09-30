"""
一键刷新：重新爬取所有网站 → 重新生成HTML报告
使用方法：python3 refresh.py
"""
import os
import sys

# 确保在项目目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import get_db, init_db
from crawler import run_crawl
from html_generator import generate

print("=" * 50)
print("  一键刷新：爬取 + 生成HTML")
print("=" * 50)

# 1. 确认数据库存在
init_db()

# 2. 运行爬虫
print("\n[1/2] 开始爬取全部网站...\n")
new_ai, errors = run_crawl()

print(f"\n  爬取完成! AI相关政策: {len(new_ai)} 条")
if errors:
    print(f"  错误: {len(errors)} 个")
    for e in errors[-3:]:
        print(f"    {e[:120]}")

# 3. 重新生成HTML
print(f"\n[2/2] 重新生成HTML报告...")
output_path = generate()

print(f"\n{'=' * 50}")
print(f"  ✅ 刷新完成!")
print(f"  📊 {len(new_ai)} 条AI政策")
print(f"  📄 打开 {output_path} 查看最新数据")
print(f"{'=' * 50}")