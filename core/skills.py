"""Agent skills — procedural knowledge the agent creates, uses, and improves.

Each skill lives in skills/<name>/SKILL.md with optional YAML frontmatter.
Skills are NOT tools — they are instructions, workflows, and patterns the agent
loads into context to perform complex tasks consistently. The agent creates them
autonomously after complex multi-step tasks and improves them during use.
"""

import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_skill(path: str) -> dict | None:
    """Parse a SKILL.md file. Returns {name, description, triggers, body} or None."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return None

    m = _FRONTMATTER_RE.match(raw)
    if not m:
        body = raw.strip()
        meta = {}
    else:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = raw[m.end():].strip()

    name = meta.get("name") or os.path.basename(os.path.dirname(path))
    description = meta.get("description", "")
    triggers = meta.get("triggers", [])

    if isinstance(triggers, str):
        triggers = [triggers]

    return {
        "name": name,
        "description": description,
        "triggers": triggers,
        "body": body,
        "path": path,
    }


def list_skills() -> list[dict]:
    """List all available skills with their metadata."""
    if not os.path.isdir(SKILLS_DIR):
        return []
    skills = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue
        md_path = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(md_path):
            continue
        parsed = _parse_skill(md_path)
        if parsed:
            skills.append(parsed)
    return skills


def get_skill(name: str) -> dict | None:
    """Get a single skill by name."""
    path = os.path.join(SKILLS_DIR, name, "SKILL.md")
    if not os.path.isfile(path):
        return None
    return _parse_skill(path)


def create_skill(name: str, description: str, triggers: list[str], body: str) -> str:
    """Create a new skill. Writes skills/<name>/SKILL.md. Returns result message."""
    if not re.match(r"^[a-z0-9](-?[a-z0-9])*$", name):
        return f"[ERROR] Invalid skill name '{name}'. Use lowercase letters, numbers, and hyphens only. Must not start/end with hyphen or have consecutive hyphens."
    if len(name) > 64:
        return f"[ERROR] Skill name too long (max 64 chars)."
    if len(description) > 1024:
        return f"[ERROR] Description too long (max 1024 chars)."
    skill_dir = os.path.join(SKILLS_DIR, name)
    os.makedirs(skill_dir, exist_ok=True)
    path = os.path.join(skill_dir, "SKILL.md")
    if os.path.exists(path):
        return f"[ERROR] Skill '{name}' already exists. Use skill_improve to update it."
    frontmatter = {
        "name": name,
        "description": description,
        "triggers": triggers,
    }
    content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, default_style=None).strip() + "\n---\n\n" + body.strip() + "\n"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"[ERROR] Failed to write skill: {e}"
    return f"[OK] Skill '{name}' created with {len(triggers)} trigger(s). Load it with the `skill` tool."


def improve_skill(name: str, description: str, triggers: list[str], body: str) -> str:
    """Update an existing skill's content. Returns result message."""
    skill_dir = os.path.join(SKILLS_DIR, name)
    path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(path):
        return f"[ERROR] Skill '{name}' not found. Use skill_create first."
    frontmatter = {
        "name": name,
        "description": description,
        "triggers": triggers,
    }
    content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, default_style=None).strip() + "\n---\n\n" + body.strip() + "\n"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"[ERROR] Failed to update skill: {e}"
    return f"[OK] Skill '{name}' improved."


def find_matching_skills(text: str) -> list[dict]:
    """Find skills whose triggers match the given text. Returns skill dicts."""
    if not text:
        return []
    text_lower = text.lower()
    matches = []
    for skill in list_skills():
        for trigger in skill.get("triggers", []):
            if trigger.lower() in text_lower:
                matches.append(skill)
                break
    return matches


def skills_prompt_block() -> str:
    """Generate the 'Available skills' block for the system prompt."""
    skills = list_skills()
    if not skills:
        return ""
    lines = [
        "## Skills — procedural knowledge you created and own",
        "Skills are NOT tools — they are instructions you wrote for yourself. After a complex multi-step task, you should create a skill so you remember how next time. Skills persist across conversations and you improve them as you get better.\n",
        "Available skills (load with `skill` tool, or they auto-load when triggers match):",
    ]
    for s in skills:
        triggers_str = ", ".join(s["triggers"][:3]) if s["triggers"] else s["description"]
        lines.append(f"- **{s['name']}** ({triggers_str})")
    return "\n".join(lines)
