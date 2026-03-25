import os
from pathlib import Path

from .parser import parse_skill_file
from .types import Skill


def get_skills_root_path() -> Path:
    """
    Get the root path of the skills directory.

    Returns:
        Path to the skills directory (deer-flow/skills)
    """
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    skills_dir = backend_dir.parent / "skills"
    return skills_dir


def get_jrai_skills_path() -> Path | None:
    """
    Get the path to JRAiController skills directory.

    JRAiController 技能目录位于 deer-flow 同级的 assets/skills/ 目录下。

    Returns:
        Path to JRAiController skills directory, or None if not found
    """
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    jrai_skills_dir = backend_dir.parent.parent / "assets" / "skills"
    if jrai_skills_dir.exists():
        return jrai_skills_dir
    return None


def _scan_skills_directory_recursive(
    skills_path: Path,
    category: str,
    source: str = "deer-flow",
    max_depth: int = 3
) -> list[Skill]:
    """
    递归扫描技能目录，返回找到的所有技能

    Args:
        skills_path: 技能目录路径
        category: 分类名称
        source: 来源系统
        max_depth: 最大递归深度（从 skills_path 开始计算）

    Returns:
        技能列表
    """
    skills = []

    if not skills_path.exists() or not skills_path.is_dir():
        return skills

    def scan_dir(current_path: Path, relative_path: Path, depth: int):
        """递归扫描目录"""
        if depth > max_depth:
            return

        try:
            items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return

        for item in items:
            if item.name.startswith("."):
                continue

            if item.is_file() and item.name == "SKILL.md":
                skill = parse_skill_file(
                    item,
                    category=category,
                    relative_path=relative_path,
                    source=source
                )
                if skill:
                    skills.append(skill)

            elif item.is_dir():
                new_relative = relative_path / item.name if relative_path != Path(".") else Path(item.name)
                scan_dir(item, new_relative, depth + 1)

    scan_dir(skills_path, Path("."), 0)

    return skills


def _scan_jrai_skills_directory(
    skills_path: Path,
    max_depth: int = 3
) -> list[Skill]:
    """
    递归扫描 JRAiController 技能目录

    目录结构：
    assets/skills/
    ├── lighting/           <- 第一层：分类
    │   ├── lighting-control/   <- 第二层：技能
    │   │   └── SKILL.md
    │   └── lighting-cue/
    │       └── SKILL.md
    └── stage/
        └── stage-create/
            └── SKILL.md

    Args:
        skills_path: JRAiController 技能根目录
        max_depth: 最大递归深度（从 skills_path 开始计算）

    Returns:
        技能列表
    """
    skills = []

    if not skills_path.exists() or not skills_path.is_dir():
        return skills

    try:
        first_level_dirs = sorted(
            [item for item in skills_path.iterdir() if item.is_dir() and not item.name.startswith(".")],
            key=lambda x: x.name.lower()
        )
    except PermissionError:
        return skills

    for category_dir in first_level_dirs:
        category = category_dir.name

        def scan_dir(current_path: Path, relative_path: Path, depth: int):
            """递归扫描目录"""
            if depth > max_depth:
                return

            try:
                items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                return

            for item in items:
                if item.name.startswith("."):
                    continue

                if item.is_file() and item.name == "SKILL.md":
                    skill = parse_skill_file(
                        item,
                        category=category,
                        relative_path=relative_path,
                        source="jraicontroller"
                    )
                    if skill:
                        skills.append(skill)

                elif item.is_dir():
                    new_relative = relative_path / item.name if relative_path != Path(".") else Path(item.name)
                    scan_dir(item, new_relative, depth + 1)

        scan_dir(category_dir, Path("."), 0)

    return skills


def load_skills(skills_path: Path | None = None, use_config: bool = True, enabled_only: bool = False) -> list[Skill]:
    """
    Load all skills from multiple directories.

    扫描以下目录：
    1. deer-flow/skills/public/  - deer-flow 公共技能
    2. deer-flow/skills/custom/  - deer-flow 自定义技能
    3. assets/skills/            - JRAiController 技能（递归扫描所有分类）

    Args:
        skills_path: Optional custom path to skills directory.
                     If not provided and use_config is True, uses path from config.
                     Otherwise defaults to deer-flow/skills
        use_config: Whether to load skills path from config (default: True)
        enabled_only: If True, only return enabled skills (default: False)

    Returns:
        List of Skill objects, sorted by name
    """
    if skills_path is None:
        if use_config:
            try:
                from deerflow.config import get_app_config

                config = get_app_config()
                skills_path = config.skills.get_skills_path()
            except Exception:
                skills_path = get_skills_root_path()
        else:
            skills_path = get_skills_root_path()

    skills = []

    for category in ["public", "custom"]:
        category_path = skills_path / category
        found_skills = _scan_skills_directory_recursive(
            category_path,
            category=category,
            source="deer-flow",
            max_depth=3
        )
        skills.extend(found_skills)

    jrai_skills_path = get_jrai_skills_path()
    if jrai_skills_path:
        found_skills = _scan_jrai_skills_directory(jrai_skills_path, max_depth=3)
        skills.extend(found_skills)

    try:
        from deerflow.config.extensions_config import ExtensionsConfig

        extensions_config = ExtensionsConfig.from_file()
        for skill in skills:
            skill.enabled = extensions_config.is_skill_enabled(skill.name, skill.category)
    except Exception as e:
        print(f"Warning: Failed to load extensions config: {e}")

    if enabled_only:
        skills = [skill for skill in skills if skill.enabled]

    skills.sort(key=lambda s: s.name)

    return skills


def load_jrai_skills_only(enabled_only: bool = False) -> list[Skill]:
    """
    仅加载 JRAiController 的技能

    Args:
        enabled_only: If True, only return enabled skills (default: False)

    Returns:
        List of JRAiController Skill objects, sorted by name
    """
    skills = []

    jrai_skills_path = get_jrai_skills_path()
    if not jrai_skills_path:
        return skills

    skills = _scan_jrai_skills_directory(jrai_skills_path, max_depth=3)

    if enabled_only:
        skills = [skill for skill in skills if skill.enabled]

    skills.sort(key=lambda s: s.name)

    return skills
