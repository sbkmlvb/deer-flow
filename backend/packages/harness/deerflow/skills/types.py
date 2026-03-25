from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    """Represents a skill with its metadata and file path

    支持两种格式：
    - deer-flow 格式: name, description, license
    - JRAiController 格式: name, summary, category, mcpTools, icon, context, dependencies
    """

    name: str
    description: str
    license: str | None
    skill_dir: Path
    skill_file: Path
    relative_path: Path
    category: str
    enabled: bool = False

    summary: str = ""
    mcp_tools: list[str] = field(default_factory=list)
    icon: str = ""
    tags: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    dependencies: dict = field(default_factory=dict)

    source: str = "deer-flow"

    @property
    def skill_path(self) -> str:
        """Returns the relative path from the category root (skills/{category}) to this skill's directory"""
        path = self.relative_path.as_posix()
        return "" if path == "." else path

    def get_display_description(self) -> str:
        """获取用于显示的描述（优先使用 summary，其次 description）"""
        return self.summary or self.description

    def get_container_path(self, container_base_path: str = "/mnt/skills") -> str:
        """
        Get the full path to this skill in the container.

        Args:
            container_base_path: Base path where skills are mounted in the container

        Returns:
            Full container path to the skill directory
        """
        category_base = f"{container_base_path}/{self.category}"
        skill_path = self.skill_path
        if skill_path:
            return f"{category_base}/{skill_path}"
        return category_base

    def get_container_file_path(self, container_base_path: str = "/mnt/skills") -> str:
        """
        Get the full path to this skill's main file (SKILL.md) in the container.

        Args:
            container_base_path: Base path where skills are mounted in the container

        Returns:
            Full container path to the skill's SKILL.md file
        """
        return f"{self.get_container_path(container_base_path)}/SKILL.md"

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, description={self.description!r}, category={self.category!r}, source={self.source!r})"
