"""
Skills 技能模块
每个 Skill 以独立的 .md 文件存放在 agents/skills/ 目录下。
文件格式：YAML frontmatter（元数据） + Markdown 正文（系统提示词）。
当用户消息匹配技能的触发关键词时，自动应用该技能的系统提示词。
"""

import os
import re
from typing import Optional, Dict, Any, List

import yaml

# Skills 文件存放目录
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# 缓存已加载的 Skills
_SKILLS_CACHE: Optional[List[Dict[str, Any]]] = None


# ============================================================
# Skill 文件加载
# ============================================================

def _load_skill_from_md(filepath: str) -> Optional[Dict[str, Any]]:
    """
    从 .md 文件中解析 Skill 配置
    文件格式：YAML frontmatter 包裹在 --- 之间，后续为系统提示词

    Args:
        filepath: .md 文件的绝对路径

    Returns:
        Skill 配置字典，解析失败返回 None
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return None

    # 解析 YAML frontmatter
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)', content, re.DOTALL)
    if not fm_match:
        return None

    try:
        metadata = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError:
        return None

    body = fm_match.group(2).strip()

    skill = {
        "name": metadata.get("name", ""),
        "display_name": metadata.get("display_name", metadata.get("name", "")),
        "description": metadata.get("description", ""),
        "enabled": metadata.get("enabled", False),
        "trigger_keywords": metadata.get("trigger_keywords", []),
        "config": {
            "system_prompt_override": body
        }
    }
    return skill


def _load_all_skills() -> List[Dict[str, Any]]:
    """扫描 skills/ 目录，加载所有 .md 文件"""
    skills = []
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for filename in sorted(os.listdir(SKILLS_DIR)):
        if filename.endswith(".md"):
            filepath = os.path.join(SKILLS_DIR, filename)
            skill = _load_skill_from_md(filepath)
            if skill:
                skills.append(skill)
    return skills


def _get_skills() -> List[Dict[str, Any]]:
    """获取 Skills 列表（带缓存）"""
    global _SKILLS_CACHE
    if _SKILLS_CACHE is None:
        _SKILLS_CACHE = _load_all_skills()
    return _SKILLS_CACHE


def reload_skills() -> List[Dict[str, Any]]:
    """强制重新加载所有 Skills（用于热更新）"""
    global _SKILLS_CACHE
    _SKILLS_CACHE = None
    return _get_skills()


# ============================================================
# Skills 查询 API（保持与原接口兼容）
# ============================================================

def get_all_skills() -> list:
    """返回所有 Skills 列表（供管理界面使用）"""
    return _get_skills()


def get_enabled_skills() -> list:
    """返回所有已启用的 Skills 列表（供前端展示）"""
    return [s for s in _get_skills() if s.get("enabled", False)]


# ============================================================
# Skill 检测与匹配
# ============================================================

def detect_skill(user_message: str) -> Optional[Dict[str, Any]]:
    """
    检测用户消息是否触发了某个已启用的 Skill

    Args:
        user_message: 用户输入的原始消息

    Returns:
        匹配到的 Skill 配置字典，未匹配返回 None
    """
    if not user_message:
        return None

    message_lower = user_message.lower()

    for skill in get_enabled_skills():
        keywords = skill.get("trigger_keywords", [])
        for keyword in keywords:
            if _keyword_match(keyword.lower(), message_lower):
                return skill

    return None


def detect_skill_chain(user_message: str, conversation_context: list = None) -> list:
    """
    识别用户意图并返回应顺序触发的 Skill 链列表
    用于外勤行程核验流水线的自动编排

    Args:
        user_message: 用户输入的原始消息
        conversation_context: 可选的对话上下文

    Returns:
        应顺序触发的 Skill 名称列表
    """
    message_lower = user_message.lower() if user_message else ""

    # 全流程审核关键词 → 触发全部4个技能
    full_pipeline_keywords = ["审核", "审计", "核验报告", "全流程", "一键审核", "audit"]
    if any(kw in message_lower for kw in full_pipeline_keywords):
        return ["document-parser", "geo-verifier", "anomaly-detector", "report-generator"]

    # 上传文件 + 行程关键词 → 先解析再核验
    upload_trip_keywords = ["上传", "文件", "报告", "docx", "xlsx", "文档"]
    trip_keywords = ["外勤", "出差", "行程", "报销", "出车"]
    has_upload = any(kw in message_lower for kw in upload_trip_keywords)
    has_trip = any(kw in message_lower for kw in trip_keywords)
    if has_upload and has_trip:
        return ["document-parser", "geo-verifier"]

    # 仅解析请求
    parse_keywords = ["解析", "提取", "读取", "parse", "extract"]
    if any(kw in message_lower for kw in parse_keywords) and has_trip:
        return ["document-parser"]

    # 地理核验特定请求
    verify_keywords = ["核对", "比对", "核实里程", "验证地址", "检查路线"]
    if any(kw in message_lower for kw in verify_keywords):
        return ["geo-verifier"]

    # 异常检测特定请求
    anomaly_keywords = ["查异常", "检测异常", "风险分析", "可疑"]
    if any(kw in message_lower for kw in anomaly_keywords):
        return ["anomaly-detector"]

    # 报告生成特定请求
    report_keywords = ["出报告", "生成报告", "汇总报告", "审计结论"]
    if any(kw in message_lower for kw in report_keywords):
        return ["report-generator"]

    # 默认：匹配单个技能
    single_skill = detect_skill(user_message)
    if single_skill:
        return [single_skill["name"]]

    return []


def _keyword_match(keyword: str, text: str) -> bool:
    """
    关键词匹配：CJK 关键词使用子串匹配，ASCII 关键词使用词边界匹配
    """
    has_cjk = any('一' <= c <= '鿿' or '぀' <= c <= 'ヿ'
                  or '가' <= c <= '힯' for c in keyword)

    if has_cjk:
        return keyword in text
    else:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))


def get_skill_prompt(skill: Dict[str, Any]) -> str:
    """
    获取 Skill 的系统提示词覆盖

    Args:
        skill: Skill 配置字典

    Returns:
        该 Skill 的系统提示词字符串，若未定义则返回空字符串
    """
    config = skill.get("config", {})
    return config.get("system_prompt_override", "")


def execute_skill(skill_name: str, context: dict) -> dict:
    """
    执行指定的 Skill（供 API 或其他模块调用）

    Args:
        skill_name: Skill 名称
        context: 执行上下文，包含用户输入、会话历史等

    Returns:
        执行结果，包含 skill 信息和提示词
    """
    for skill in get_all_skills():
        if skill["name"] == skill_name:
            if not skill.get("enabled", False):
                return {"success": False, "error": f"Skill '{skill_name}' 未启用"}
            return {
                "success": True,
                "skill": {
                    "name": skill["name"],
                    "display_name": skill["display_name"],
                    "description": skill["description"],
                },
                "system_prompt": get_skill_prompt(skill)
            }

    return {"success": False, "error": f"未找到 Skill '{skill_name}'"}
