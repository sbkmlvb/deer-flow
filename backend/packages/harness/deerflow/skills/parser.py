import re
from pathlib import Path

from .types import Skill


def _parse_yaml_value(value: str):
    """解析 YAML 值，支持字符串、列表和字典"""
    value = value.strip()
    
    if not value:
        return None
    
    if value.startswith("[") and value.endswith("]"):
        items = []
        inner = value[1:-1].strip()
        if inner:
            for item in inner.split(","):
                item = item.strip().strip("'\"")
                if item:
                    items.append(item)
        return items
    
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    
    return value


def _parse_yaml_frontmatter(front_matter: str) -> dict:
    """
    解析 YAML frontmatter，支持嵌套结构和列表
    
    支持的格式：
    - key: value
    - key: [item1, item2]
    - key:
        - item1
        - item2
    - key:
        subkey: value
    """
    result = {}
    current_key = None
    current_list = []
    current_dict = {}
    in_list = False
    in_dict = False
    dict_indent = 0
    
    lines = front_matter.split("\n")
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped:
            i += 1
            continue
        
        if stripped.startswith("#"):
            i += 1
            continue
        
        if ":" in stripped:
            colon_pos = stripped.index(":")
            key = stripped[:colon_pos].strip()
            value = stripped[colon_pos + 1:].strip()
            
            indent = len(line) - len(line.lstrip())
            
            if in_dict and indent > dict_indent:
                if value:
                    current_dict[key] = _parse_yaml_value(value)
                i += 1
                continue
            
            if in_list or in_dict:
                if current_list:
                    result[current_key] = current_list
                    current_list = []
                elif current_dict:
                    result[current_key] = current_dict
                    current_dict = {}
                in_list = False
                in_dict = False
            
            current_key = key
            
            if value:
                if value.startswith("[") and value.endswith("]"):
                    result[key] = _parse_yaml_value(value)
                else:
                    result[key] = _parse_yaml_value(value)
                current_key = None
            else:
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    next_indent = len(next_line) - len(next_line.lstrip())
                    
                    if next_stripped.startswith("- "):
                        in_list = True
                        current_list = []
                    elif ":" in next_stripped and next_indent > indent:
                        in_dict = True
                        dict_indent = next_indent
                        current_dict = {}
        
        elif stripped.startswith("- "):
            item = stripped[2:].strip().strip("'\"")
            if in_list:
                current_list.append(item)
        
        i += 1
    
    if current_list:
        result[current_key] = current_list
    elif current_dict:
        result[current_key] = current_dict
    
    return result


def parse_skill_file(
    skill_file: Path,
    category: str,
    relative_path: Path | None = None,
    source: str = "deer-flow"
) -> Skill | None:
    """
    Parse a SKILL.md file and extract metadata.

    支持两种格式：
    - deer-flow 格式: name, description, license
    - JRAiController 格式: name, summary, category, mcpTools, icon, context, dependencies

    Args:
        skill_file: Path to the SKILL.md file
        category: Category of the skill ('public', 'custom', 'lighting', 'stage', etc.)
        relative_path: Relative path from category root to skill directory
        source: Source system ('deer-flow' or 'jraicontroller')

    Returns:
        Skill object if parsing succeeds, None otherwise
    """
    if not skill_file.exists() or skill_file.name != "SKILL.md":
        return None

    try:
        content = skill_file.read_text(encoding="utf-8")

        front_matter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

        if not front_matter_match:
            return None

        front_matter = front_matter_match.group(1)

        metadata = _parse_yaml_frontmatter(front_matter)

        name = metadata.get("name")
        if not name:
            return None

        description = metadata.get("description") or metadata.get("summary", "")
        if not description:
            return None

        license_text = metadata.get("license")

        skill_category = metadata.get("category") or category

        summary = metadata.get("summary", "")
        if summary and not metadata.get("description"):
            description = summary

        mcp_tools = metadata.get("mcpTools", [])
        if isinstance(mcp_tools, str):
            mcp_tools = [mcp_tools]

        icon = metadata.get("icon", "")
        if isinstance(icon, str):
            icon = icon.strip("'\"")

        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        context = metadata.get("context", {})
        if isinstance(context, str):
            context = {}

        dependencies = metadata.get("dependencies", {})
        if isinstance(dependencies, str):
            dependencies = {}

        return Skill(
            name=name,
            description=description,
            license=license_text,
            skill_dir=skill_file.parent,
            skill_file=skill_file,
            relative_path=relative_path or Path(skill_file.parent.name),
            category=skill_category,
            enabled=True,
            summary=summary,
            mcp_tools=mcp_tools if isinstance(mcp_tools, list) else [],
            icon=icon,
            tags=tags if isinstance(tags, list) else [],
            context=context if isinstance(context, dict) else {},
            dependencies=dependencies if isinstance(dependencies, dict) else {},
            source=source,
        )

    except Exception as e:
        print(f"Error parsing skill file {skill_file}: {e}")
        return None
