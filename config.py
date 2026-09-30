"""
政府AI政策收集工具 - 配置模块
"""
import re

# 数据库路径
DB_PATH = "policies.db"

# 爬取间隔（小时）
CRAWL_INTERVAL_HOURS = 2

# 数据保留天数（超过此天数的数据自动归档）
ACTIVE_DAYS = 7

# 服务器配置
HOST = "0.0.0.0"
PORT = 5000

# ===== AI 关键词体系（三级制）=====
# 三级权重 + 评分门槛，确保只有真正AI相关的文章被标记

# 一级：核心词（命中任意一条 → 直接判定为AI相关）
# 权重：15分
CORE_KEYWORDS = [
    "人工智能", "artificial intelligence",
]

# 核心正则（如独立的 AI 单词）
CORE_PATTERNS = [
    r'\bAI\b',
    r'\ba\.i\.\b',
]

# 二级：强相关词（单个命中即可判定为AI相关）
# 权重：8 分，阈值 6 → 单个命中就过线
STRONG_KEYWORDS = [
    # 大模型
    "大模型", "大语言模型", "大模型技术", "通用大模型",
    "基础模型", "预训练模型", "多模态模型",
    "生成式", "AIGC", "ChatGPT", "GPT",
    # 核心AI技术
    "机器学习", "深度学习", "神经网络", "强化学习",
    "自然语言处理", "NLP", "计算机视觉", "语音识别",
    # 机器人
    "机器人", "人形机器人", "具身智能", "工业机器人",
    "服务机器人", "特种机器人", "人形机器人",
    # 自动驾驶/智能汽车
    "自动驾驶", "智能驾驶", "智能网联汽车", "无人驾驶",
    # 前沿
    "通用人工智能", "AGI", "强人工智能",
    "智能体", "AI Agent",
    # AI芯片与算力
    "AI芯片", "智能芯片", "算力芯片", "人工智能芯片",
    "智能算力", "AI算力",
    # AI平台与系统
    "智能平台", "智能系统",
    "人工智能平台", "AI平台", "人工智能基础设施", "AI基础设施",
    # AI技术能力
    "人工智能技术", "AI技术", "人工智能能力", "AI能力",
    # AI装备与传感
    "智能装备", "智能传感", "智能传感器",
    "智能终端", "智能硬件",
    # 无人系统
    "无人系统", "无人机", "无人车",
    # 行业AI应用（扩展）
    "智能教育", "智能医疗", "智慧医疗",
    "智能交通", "智慧交通", "智能能源", "智慧能源",
    "智能网联", "智能电网", "智能安防",
    # 脑机接口
    "脑机接口", "脑机",
    # AI安全
    "AI安全", "人工智能安全",
]

# 三级：宽泛词（需要 ≥2 个同时命中才加分，且不能单独判定）
# 权重：2 分
BROAD_KEYWORDS = [
    # 算力与算法
    "算力", "算法", "智算", "智能计算", "超算",
    "算力中心", "智算中心", "算力基础设施", "算力网络",
    # 数据
    "数据要素", "数据资产", "数据治理", "数据安全",
    "隐私计算", "数据交易", "数据流通", "大数据",
    "数据基础设施", "数据资源", "数据价值",
    # 数字化（宽泛语境）
    "数字化", "智能化", "数智化", "数字化转型",
    "数字技术", "数字经济", "数字孪生",
    "数字政府", "数字政务",
    "智慧城市", "智慧矿山", "智慧农业",
    "智能网联", "车联网", "车路协同", "智能交通",
    # 芯片与半导体
    "芯片", "半导体", "集成电路", "GPU", "NPU",
    # 工业数字化
    "智能制造", "工业互联网", "数字车间", "智能车间",
    "黑灯工厂", "数字工厂",
    # 云计算与通信
    "云计算", "边缘计算", "物联网", "IoT",
    "5G", "6G",
    # 新兴技术
    "区块链", "量子计算", "量子信息",
    "知识图谱", "多模态", "Transformer",
    "语音识别", "人脸识别", "图像识别",
    # AI应用场景
    "智能客服", "智能推荐", "智能搜索",
    "智能运维", "智能质检", "智能调度",
    # 信息化
    "新一代信息技术", "信息技术", "信创",
    "信息系统", "信息化", "软件和信息服务",
    # 智能终端与硬件
    "可穿戴", "智能硬件", "智能终端",
    # AI产业
    "智能产业", "AI产业", "AI应用",
]

# ===== 评分参数 =====
CORE_SCORE = 15       # 一级：核心词
STRONG_SCORE = 8      # 二级：强相关词
BROAD_SCORE = 2       # 三级：宽泛词
AI_THRESHOLD = 6      # 判定为AI相关的分数门槛
TITLE_BONUS = 3       # 标题命中额外加分（不限级别）
BROAD_ONLY_MIN = 4    # 宽泛词积累判定阈值：4+个宽泛词同时命中时，即可判定为AI相关
BROAD_ONLY_CAP = 5    # 宽泛词积累上限（最多计入5个）


# ===== 政策导向性提取模式 =====
DIRECTION_PATTERNS = [
    ("鼓励发展", re.compile(
        r"(鼓励|大力发展|积极发展|重点发展|加快发展|支持|推动|促进|培育|"
        r"壮大|提升[^质].*水平|加大.*力度|扶持|优先|引导.*发展|加快推进|大力推进)"
    )),
    ("资金支持", re.compile(
        r"(补贴|资助|奖励|奖金|专项资金|财政.*支持|税收.*优惠|"
        r"融资|信贷|资金.*支持|经费|基金|投资|减免|贴息|补助|奖补)"
    )),
    ("试点示范", re.compile(
        r"(试点|示范|试验区|先行区|标杆|典型场景|示范区|示范基地|"
        r"先导区|试验区|试运行|试点项目)"
    )),
    ("规范管理", re.compile(
        r"(规范|管理|监管|监督|安全|治理|引导.*健康|"
        r"合规|准入|备案|许可|审核|评估|监测|检查|考核)"
    )),
    ("规划布局", re.compile(
        r"(规划|布局|总体要求|指导思想|发展目标|顶层设计|"
        r"体系建设|标准|指标体系|统筹|总体布局|中长期|纲要愿景)"
    )),
    ("限制禁止", re.compile(
        r"(禁止|不得|严禁|限制|惩戒|处罚|违规|违法|"
        r"追责|问责|整治|淘汰|关闭|取缔|严查)"
    )),
]

# 时间节点提取（日期格式）
TIME_PATTERNS = [
    re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日)"),
    re.compile(r"(到\d{4}年)"),
    re.compile(r"(\d{4}年\d{1,2}月)"),
    re.compile(r"(\d{4}年底)"),
    re.compile(r"(\d{4}年前)"),
    re.compile(r"(\d{4}年末)"),
    re.compile(r"(\d{4}年上半年)"),
    re.compile(r"(\d{4}年下半年)"),
    re.compile(r"(\d{4}年\d{1,2}季度)"),
    re.compile(r"(截至\d{4}年)"),
    re.compile(r"(\d{4}/\d{1,2}/\d{1,2})"),
]

# 责任主体
ENTITY_PATTERNS = [
    re.compile(r"(国家发展改革委|发改委|发展改革委)"),
    re.compile(r"(工业和信息化部|工信部)"),
    re.compile(r"(科学技术部|科技部)"),
    re.compile(r"(交通运输部)"),
    re.compile(r"(教育部)"),
    re.compile(r"(国务院国资委|国资委)"),
    re.compile(r"(北京市发展改革委|北京市发改委|市发改委)"),
    re.compile(r"(北京市科委|市科委|中关村管委会)"),
    re.compile(r"(北京市经济和信息化局|市经信局|经信局)"),
    re.compile(r"(北京市人民政府|市政府)"),
    re.compile(r"(各省|各地区|各地方|各地)"),
    re.compile(r"(国务院[^。]*?[办委部局])"),
    re.compile(r"(中央[^。]*?[办委部局])"),
    re.compile(r"(全国[^。]*?[办委部局])"),
]

# 内容正文中的无用标签（不参与AI评分）
EXCLUDE_SECTIONS = [
    "header", "footer", "nav", ".sidebar", ".toolbar",
    ".breadcrumb", ".topbar", ".bottom-bar",
]

# ===== 站点配置 =====
# 两种模式：
#   1. search_api: 通过搜索API获取政策列表（交通运输部、工信部）
#   2. list_urls: 通过静态列表页获取政策链接（其余站点）
SITES = [
    {
        "name": "国家发改委",
        "domain": "www.ndrc.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "https://www.ndrc.gov.cn/xxgk/",
        ],
        "max_pages": 1,
        "page_style": "none",
    },
{
    "name": "工信部",
    "domain": "www.miit.gov.cn",
    "encoding": "utf-8",
    "page_url": "https://www.miit.gov.cn/search/zcwjk.html?websiteid=110000000000000&pg=&p=&tpl=14&category=183&q=",
    "search_api": {
        "method": "GET",
        "url": "https://www.miit.gov.cn/search-front-server/api/search/info",
        "params": {
            "websiteid": "110000000000000",
            "scope": "basic",
            "pg": 20,
            "cateid": "196",
            "category": "yyss",
            "pos": "title_text,infocontent,titlepy",
            "dateField": "deploytime",
            "level": 6,
            "sortFields": '[{"name":"deploytime","type":"desc"}]',
        },
        "response_path": ["data", "searchResult", "dataResults"],
        "title_key": "data.title_text",
        "url_key": "data.url",
        "date_key": "data.jsearch_date",
        "date_value_ts": "data.cdate",
        "page_param": "p",
        "query_param": "q",
        "url_prefix": "https://www.miit.gov.cn",
        "search_keywords": [""],
        "headers": {
            "Referer": "https://www.miit.gov.cn/search/zcwjk.html?websiteid=110000000000000&pg=&p=&tpl=14&category=183&q="
        },
    },
    "max_articles": 100,
},
    {
        "name": "科技部",
        "domain": "www.most.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "https://www.most.gov.cn/satp/kjzc/zh/",
        ],
        "link_prefix": "https://www.most.gov.cn",
        "date_from_url": True,
        "url_date_pattern": r"/(\d{6})/t\d{8}_",
        "content_selectors": [".content", ".TRS_Editor", ".article-content", "#content"],
        "max_pages": 10,
        "page_style": "index_numbered",
    },
    {
        "name": "交通运输部",
        "domain": "www.mot.gov.cn",
        "encoding": "utf-8",
        "search_api": {
            "method": "POST",
            "url": "https://api.so-gov.cn/query/s",
            "params": {
                "siteCode": "bm19000004_zck",
                "tab": "fbf1585095712506bbcb4de6bb559559",
                "pageSize": 20,
                "ie": "undefined",
            },
            "response_path": ["data", "result", "search", "docs"],
            "title_key": "titleO",
            "url_key": "url",
            "date_key": "formatRows",
            "page_param": "page",
            "domain_filter": ["mot.gov.cn"],  # 仅保留交通运输部本级政策
            "search_keywords": ["人工智能", "AI", "智能", "数据安全", "数字化", "智慧交通", "大数据", "自动驾驶", "智能网联", "机器人"],
        },
        "max_articles": 80,
    },
    {
        "name": "教育部",
        "domain": "www.moe.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "http://www.moe.gov.cn/jyb_xxgk/xxgk/zhengce/",
        ],
        "link_prefix": "http://www.moe.gov.cn",
        "max_pages": 10,
        "page_style": "index_numbered",
    },
    {
    "name": "国资委",
    "domain": "www.sasac.gov.cn",
    "encoding": "utf-8",
    "list_urls": [
        "http://www.sasac.gov.cn/n2588035/n2588320/n2588335/index.html",
    ],
    "link_prefix": "http://www.sasac.gov.cn",
    "skip_date_check": True,
    "max_pages": 1,
    },
    {
        "name": "北京市发改委",
        "domain": "fgw.beijing.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "https://fgw.beijing.gov.cn/fgwzwgk/2024zcwj/",
        ],
        "link_prefix": "https://fgw.beijing.gov.cn",
        "content_selectors": [".content", ".article-content", "#content", ".TRS_Editor"],
        "max_pages": 1,
        "page_style": "none",
    },
    {
        "name": "市科委",
        "domain": "kw.beijing.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "https://kw.beijing.gov.cn/zwgk/zcwj/",
        ],
        "link_prefix": "https://kw.beijing.gov.cn",
        "content_selectors": [".content", ".article-content", "#content", ".TRS_Editor"],
        "max_pages": 20,
        "page_style": "index_numbered",
    },
    {
        "name": "市经信局",
        "domain": "jxj.beijing.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "https://jxj.beijing.gov.cn/zwgk/2024zcwj/",
        ],
        "link_prefix": "https://jxj.beijing.gov.cn",
        "content_selectors": [".content", ".article-content", "#content", ".TRS_Editor"],
        "max_pages": 10,
        "page_style": "index_numbered",
    },
    {
        "name": "人民政府",
        "domain": "beijing.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "https://www.beijing.gov.cn/zhengce/zhengcefagui/",
            "https://www.beijing.gov.cn/gongkai/ldhd/",
        ],
        "link_prefix": "https://www.beijing.gov.cn",
        "max_pages": 10,
        "page_style": "index_numbered",
    },
    {
        "name": "人民政府(经开区)",
        "domain": "kfqgw.beijing.gov.cn",
        "encoding": "utf-8",
        "list_urls": [
            "https://kfqgw.beijing.gov.cn/zwgkkfq/2024zcwj/",
        ],
        "link_prefix": "https://kfqgw.beijing.gov.cn",
        "content_selectors": [".content", ".article-content", "#content", ".TRS_Editor"],
        "max_pages": 10,
        "page_style": "index_numbered",
    },
]
