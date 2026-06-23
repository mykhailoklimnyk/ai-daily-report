"""
Report generator using OpenAI API with prompt_id support.
"""

import asyncio
import os
import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

# Project root for loading templates
PROJECT_ROOT = Path(__file__).parent.parent


class ReportGenerator:
    """
    Generates daily productivity reports using OpenAI API.
    
    Supports both traditional prompts and prompt_id for OpenAI's
    stored prompts feature.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables")

        # Model configuration
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.2-mini")
        
        # Prompt ID for stored prompts (if available)
        self.prompt_id = os.getenv("OPENAI_PROMPT_ID")
        
        # OpenAI client
        self.client = AsyncOpenAI(api_key=self.api_key, timeout=60.0)

    def _load_prompt_template(self) -> tuple[str, str]:
        """Load the prompt and system role templates from markdown files."""
        prompt_path = PROJECT_ROOT / "prompt.md"
        system_role_path = PROJECT_ROOT / "system_role.md"

        prompt = ""
        system_role = ""

        for path, target in [(prompt_path, "prompt"), (system_role_path, "system_role")]:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Remove filepath comments if present
                    if content.startswith("<!-- filepath:"):
                        content = "\n".join(content.split("\n")[1:])
                    if target == "prompt":
                        prompt = content.strip()
                    else:
                        system_role = content.strip()
            else:
                logger.warning(f"Template file not found: {path}")

        return prompt, system_role

    def format_gitlab_data(self, commits: List[Dict[str, Any]]) -> str:
        """Format GitLab commits for the prompt."""
        if not commits:
            return "## GitLab Commits:\nНемає комітів за сьогодні.\n"

        text = "## GitLab Commits:\n\n"
        
        # Group commits by project
        projects: Dict[str, List[Dict[str, Any]]] = {}
        for commit in commits:
            project = commit.get("project", "Unknown")
            if project not in projects:
                projects[project] = []
            projects[project].append(commit)

        for project, project_commits in projects.items():
            text += f"### {project}:\n"
            for commit in project_commits:
                message = commit.get("message", "No message")
                date = commit.get("date", "")[:10] if commit.get("date") else ""
                text += f"- {message} ({date})\n"
            text += "\n"

        return text

    def format_jira_data(self, jira_data: Dict[str, Any]) -> str:
        """Format Jira tasks for the prompt."""
        text = "## Jira Tasks:\n\n"

        # Tasks in progress — reference/context only, NOT proof of work done today
        in_progress = jira_data.get("tasks_in_progress", [])
        if in_progress:
            text += "### В роботі (довідково, НЕ доказ роботи саме сьогодні):\n"
            for task in in_progress:
                key = task.get("key", "")
                summary = task.get("summary", "")
                project = task.get("project", "")
                text += f"- {key} — {summary} (Проект: {project})\n"
            text += "\n"

        # Tasks closed today — real evidence of today's work
        closed = jira_data.get("tasks_closed_today", [])
        if closed:
            text += "### Закриті сьогодні:\n"
            for task in closed:
                key = task.get("key", "")
                summary = task.get("summary", "")
                project = task.get("project", "")
                text += f"- {key} — {summary} (Проект: {project})\n"
            text += "\n"

        # All my tasks — name/key reference only, NOT evidence of today's activity
        all_tasks = jira_data.get("all_my_tasks", [])
        if all_tasks:
            text += f"### Активні задачі (довідник назв/ключів, НЕ доказ роботи сьогодні): {len(all_tasks)}\n"
            for task in all_tasks[:15]:
                key = task.get("key", "")
                summary = task.get("summary", "")
                status = task.get("status", "")
                text += f"- {key} — {summary} ({status})\n"
            if len(all_tasks) > 15:
                text += f"... та ще {len(all_tasks) - 15} задач\n"
            text += "\n"

        if not in_progress and not closed and not all_tasks:
            text += "Немає задач у Jira.\n"

        return text

    def format_clockify_data(self, entries: List[Dict[str, Any]]) -> str:
        """Format Clockify time entries for the prompt."""
        if not entries:
            return "## Clockify Time Tracking:\nНемає записів часу за сьогодні.\n"

        text = "## Clockify Time Tracking:\n\n"
        
        total_minutes = 0
        for entry in entries:
            name = entry.get("name", "No description")
            project = entry.get("project_name", "No project")
            minutes = entry.get("time", 0)
            total_minutes += minutes
            
            hours = minutes // 60
            mins = minutes % 60
            duration = f"{hours}h {mins}m" if hours else f"{mins}m"
            
            text += f"- {name} ({project}) - {duration}\n"

        # Total
        total_hours = total_minutes // 60
        total_mins = total_minutes % 60
        text += f"\n**Загальний час: {total_hours}h {total_mins}m**\n"

        return text

    def _build_jira_index(self, jira_data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Build a {key: {summary, url}} map from all known Jira tasks.

        Used to turn task keys in the generated report into clickable links
        with the real Jira title. URLs come from real data and are never
        invented by the model.
        """
        base = os.getenv("JIRA_URL", "").rstrip("/")
        index: Dict[str, Dict[str, str]] = {}
        for bucket in ("tasks_in_progress", "tasks_closed_today", "all_my_tasks"):
            for task in jira_data.get(bucket, []):
                key = (task.get("key") or "").strip()
                if not key or key in index:
                    continue
                url = (task.get("url") or "").strip() or (f"{base}/browse/{key}" if base else "")
                index[key] = {
                    "summary": (task.get("summary") or "").strip(),
                    "url": url,
                }
        return index

    # Matches Jira-like keys (UA-123, AUTOMOTO-45) not already inside a link/URL/word.
    _JIRA_KEY_RE = re.compile(r"(?<![\w/\-\[])([A-Z][A-Z0-9]+-\d+)(?![\w\-])")

    def _linkify_jira(self, text: str, index: Dict[str, Dict[str, str]]) -> str:
        """Replace bare Jira keys with markdown links '[KEY — Title](url)'.

        The title is the real Jira summary; the URL is built from real data.
        Keys not present in the index are linked by key only (no invented title).
        """
        base = os.getenv("JIRA_URL", "").rstrip("/")

        def repl(match: "re.Match") -> str:
            key = match.group(1)
            info = index.get(key)
            if info and info.get("url"):
                url = info["url"]
                summary = info.get("summary", "")
            elif base:
                url, summary = f"{base}/browse/{key}", ""
            else:
                return key  # no base URL configured — leave as plain text
            label = f"{key} — {summary}" if summary else key
            return f"[{label}]({url})"

        return self._JIRA_KEY_RE.sub(repl, text)

    def _build_data_context(
        self,
        gitlab_commits: List[Dict[str, Any]],
        jira_data: Dict[str, Any],
        clockify_data: List[Dict[str, Any]],
        current_date: str,
    ) -> str:
        """Build a per-run data anchor that grounds the model in actual counts.

        Counting available evidence up-front (and flagging low-signal days)
        is the main guard against the model padding the report with fiction.
        """
        n_commits = len(gitlab_commits)
        n_closed = len(jira_data.get("tasks_closed_today", []))
        n_in_progress = len(jira_data.get("tasks_in_progress", []))
        n_clockify = len(clockify_data)

        lines = [
            f"=== КОНТЕКСТ ДАНИХ за {current_date} ===",
            f"GitLab комітів сьогодні: {n_commits}",
            f"Jira задач закрито сьогодні: {n_closed}",
            f"Jira задач у роботі (довідково): {n_in_progress}",
            f"Записів Clockify сьогодні: {n_clockify}",
        ]

        # Low-signal day: no commits and nothing closed today => Clockify-only mode.
        if n_commits == 0 and n_closed == 0:
            lines += [
                "",
                "УВАГА: сьогодні немає комітів і немає закритих задач — реальних свідчень "
                "роботи мало. Сформуй звіт ВИКЛЮЧНО на основі записів Clockify нижче: "
                "по одному пункту на кожен змістовний запис. Якщо запис лише один — у звіті "
                "має бути РІВНО один пункт. НЕ створюй пункти зі списку задач «у роботі» чи "
                "активних задач — це лише довідник, а не доказ роботи за сьогодні. НЕ вигадуй.",
            ]
        return "\n".join(lines)

    def _build_user_prompt(
        self,
        gitlab_text: str,
        jira_text: str,
        clockify_text: str,
        prompt_template: str,
        data_context: str,
        current_date: str,
    ) -> str:
        """Build the complete user prompt."""
        task_instructions = prompt_template.replace("{date}", current_date)

        return f"""
{data_context}

{gitlab_text}

{jira_text}

{clockify_text}

{task_instructions}
""".strip()

    async def generate_report(
        self,
        gitlab_commits: List[Dict[str, Any]],
        jira_data: Dict[str, Any],
        clockify_data: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a productivity report using OpenAI.

        Args:
            gitlab_commits: List of GitLab commits
            jira_data: Dictionary with Jira tasks data
            clockify_data: List of Clockify time entries

        Returns:
            Generated report as a string
        """
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Format all data sources
        gitlab_text = self.format_gitlab_data(gitlab_commits)
        jira_text = self.format_jira_data(jira_data)
        clockify_text = self.format_clockify_data(clockify_data)

        # Load templates
        prompt_template, system_role = self._load_prompt_template()

        # Ground the model in the actual amount of evidence available today.
        data_context = self._build_data_context(
            gitlab_commits, jira_data, clockify_data, current_date
        )

        # Build user prompt
        user_prompt = self._build_user_prompt(
            gitlab_text, jira_text, clockify_text, prompt_template,
            data_context, current_date
        )

        try:
            logger.info("Sending data to OpenAI for report generation...")
            logger.info(f"Using model: {self.model}")

            # Build request parameters for Responses API
            request_params = {
                "model": self.model,
                "input": user_prompt,
                "store": False
            }
            
            # Reusable prompt objects (OPENAI_PROMPT_ID) are deprecated by OpenAI —
            # announced 2026-06-03, v1/prompts shut down 2026-11-30. Per the official
            # migration guidance the prompt is managed in code and versioned in git:
            # system_role.md is sent as `instructions`, prompt.md is appended to `input`.
            if self.prompt_id:
                logger.warning(
                    "OPENAI_PROMPT_ID is set but no longer used: OpenAI is shutting down "
                    "reusable prompt objects on 2026-11-30. The prompt now lives in "
                    "system_role.md / prompt.md — you can remove OPENAI_PROMPT_ID from .env."
                )
            request_params["instructions"] = (
                system_role
                or "You are an assistant that writes concise, structured daily productivity reports in Ukrainian."
            )
            
            response = await self.client.responses.create(**request_params)

            # Extract generated text
            generated_report = self._extract_response_text(response)

            if not generated_report:
                logger.error("Unable to parse OpenAI response")
                return "Error generating report: Empty response from model"

            logger.info("Successfully generated productivity report")

            # Turn bare Jira keys into clickable links with the real task title.
            jira_index = self._build_jira_index(jira_data)
            generated_report = self._linkify_jira(generated_report, jira_index)

            # Add disclaimer
            disclaimer = (
                f"\n\n---\n*This report was generated using AI based on task statistics and monitoring metrics.*\n"
                f"Model used: OpenAI {self.model}\n"
                f"Source: [github.com/Klimnyk/ai-daily-report](https://github.com/Klimnyk/ai-daily-report)"
            )

            return generated_report + disclaimer

        except Exception as e:
            error_msg = repr(e)
            if "not found" in error_msg.lower() and "prompt" in error_msg.lower():
                logger.error(f"Prompt ID not found. Remove OPENAI_PROMPT_ID secret or create the prompt in OpenAI Dashboard.")
                return "Error: Invalid OPENAI_PROMPT_ID - prompt not found in OpenAI. Remove this secret or create the prompt."
            logger.error(f"Error generating report: {error_msg}")
            return f"Error generating report: {error_msg}"

    def _extract_response_text(self, response: Any) -> str:
        """Extract text from OpenAI response object."""
        # Responses API format - output_text (SDK convenience property)
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text.strip()

        # Responses API format - iterate over output blocks
        if hasattr(response, "output") and response.output:
            for block in response.output:
                if hasattr(block, "content"):
                    for content in block.content:
                        if hasattr(content, "text") and content.text:
                            return content.text.strip()

        # Fallback: chat.completions format (for older models)
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                return choice.message.content.strip()

        return ""


async def main():
    """Test the report generator."""
    from gitlab.client import fetch_gitlab_commits
    from jira.client import fetch_jira_tasks
    from clockify.client import get_formatted_today_time_entries

    try:
        # Fetch all data concurrently
        gitlab_commits, jira_data, clockify_data = await asyncio.gather(
            fetch_gitlab_commits(),
            fetch_jira_tasks(),
            get_formatted_today_time_entries()
        )

        logger.info("Generating report using OpenAI...")
        generator = ReportGenerator()
        report = await generator.generate_report(
            gitlab_commits=gitlab_commits,
            jira_data=jira_data,
            clockify_data=clockify_data
        )
        print(report)

    except Exception as e:
        logger.error(f"Error in main function: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
