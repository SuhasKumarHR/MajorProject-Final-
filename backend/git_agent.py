"""Commit verified recovery changes and create a real GitHub pull request."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

from git import GitCommandError, Repo
from github import Github
from github.GithubException import GithubException


class GitAgent:
    """Publish only explicit, verified HealingAgent changes."""

    def __init__(self, repo_path, repo_url, branch_name, team_name, leader_name, project_path=None):
        self.repo_path = Path(repo_path).resolve()
        self.project_path = self._resolve_project_scope(project_path)
        self.repo_url = str(repo_url)
        self.branch_name = self._sanitize_branch(branch_name)
        self.team_name = str(team_name)
        self.leader_name = str(leader_name)
        self.github_token = os.getenv("GITHUB_TOKEN", "").strip()

    def _resolve_project_scope(self, project_path=None):
        if not project_path:
            return self.repo_path
        candidate = Path(str(project_path)).resolve()
        try:
            candidate.relative_to(self.repo_path)
        except ValueError:
            return self.repo_path
        return candidate if candidate.is_dir() else self.repo_path

    @staticmethod
    def _sanitize_branch(value):
        value = re.sub(r"[^A-Za-z0-9._/-]", "_", str(value or ""))
        value = re.sub(r"_+", "_", value).strip("._-/")
        return value or "ACR_AGENT_AI_Fix"

    def _repository(self):
        if not (self.repo_path / ".git").is_dir():
            raise RuntimeError(f"Git repository not found at: {self.repo_path}")
        return Repo(self.repo_path)

    def _safe_paths(self, fixes):
        paths = []
        for fix in fixes or []:
            if not isinstance(fix, dict):
                continue
            raw_path = str(fix.get("file_path", "")).replace("\\", "/").lstrip("./")
            if not raw_path:
                continue
            candidate = (self.repo_path / raw_path).resolve()
            try:
                relative_path = candidate.relative_to(self.repo_path).as_posix()
            except ValueError:
                continue
            try:
                candidate.relative_to(self.project_path)
            except ValueError:
                # A selected-language run must never commit another language
                # directory, even if an AI response mentions it.
                continue
            if candidate.is_file() and relative_path not in paths:
                paths.append(relative_path)
        return paths

    def _ensure_branch(self, repo):
        if self.branch_name in {branch.name for branch in repo.branches}:
            repo.git.checkout(self.branch_name)
        else:
            repo.create_head(self.branch_name).checkout()

    def _parse_github_repository(self):
        parsed = urlparse(self.repo_url)
        if parsed.hostname != "github.com":
            raise RuntimeError("A GitHub HTTPS repository URL is required to create a pull request.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            raise RuntimeError("Unable to parse the GitHub owner and repository name.")
        return parts[0], parts[1].removesuffix(".git")

    def _push_branch(self, repo):
        if not self.github_token:
            raise RuntimeError("GITHUB_TOKEN is not configured.")
        origin = repo.remotes.origin
        remote_url = origin.url
        def push_and_validate(remote):
            results = remote.push(refspec=f"{self.branch_name}:{self.branch_name}")
            failures = []
            for result in results:
                flags = int(getattr(result, "flags", 0))
                # GitPython PushInfo.ERROR/REJECTED/REMOTE_REJECTED flags.
                if flags & 0x8 or flags & 0x10 or flags & 0x400:
                    failures.append(str(getattr(result, "summary", result)))
            if failures:
                raise RuntimeError(
                    f"GitHub branch push failed for '{self.branch_name}': "
                    + " | ".join(failures)
                )

        if not remote_url.startswith("https://github.com/"):
            push_and_validate(origin)
            return

        authenticated_url = (
            "https://x-access-token:"
            f"{self.github_token}@github.com/"
            f"{remote_url.split('github.com/', 1)[1]}"
        )
        temporary_name = "acr_agent_authenticated_push"
        if temporary_name in {remote.name for remote in repo.remotes}:
            repo.delete_remote(temporary_name)
        temporary_remote = repo.create_remote(temporary_name, authenticated_url)
        try:
            push_and_validate(temporary_remote)
        finally:
            repo.delete_remote(temporary_remote)

    def _create_pull_request(self):
        owner, repository_name = self._parse_github_repository()
        github_repo = Github(self.github_token).get_repo(f"{owner}/{repository_name}")
        base_branch = github_repo.default_branch
        existing = github_repo.get_pulls(
            state="open",
            head=f"{owner}:{self.branch_name}",
            base=base_branch,
        )
        for pull_request in existing:
            return pull_request.html_url
        pull_request = github_repo.create_pull(
            title="ACR_AGENT: verified CI/CD recovery",
            body=(
                "## ACR_AGENT verified recovery\n\n"
                f"- Team: {self.team_name}\n"
                f"- Leader: {self.leader_name}\n"
                f"- Branch: `{self.branch_name}`\n"
                "- Changes were committed only after a fresh build/test verification."
            ),
            head=self.branch_name,
            base=base_branch,
        )
        return pull_request.html_url

    def execute(self, fixes=None):
        """Commit, push, and return a real PR URL only after verified changes exist."""
        if not self.github_token:
            return {"status": "FAILED", "error": "GITHUB_TOKEN is not configured.", "pr_url": None}
        try:
            repo = self._repository()
            paths = self._safe_paths(fixes)
            if not paths:
                return {
                    "status": "FAILED",
                    "error": "No verified repository-relative repair files are available to commit.",
                    "pr_url": None,
                }
            self._ensure_branch(repo)
            if not repo.git.status("--porcelain", "--", *paths).strip():
                return {"status": "FAILED", "error": "No verified changes were detected.", "pr_url": None}
            repo.git.add("--", *paths)
            commit = repo.index.commit(f"fix: ACR_AGENT verified recovery ({len(paths)} file{'s' if len(paths) != 1 else ''})")
            self._push_branch(repo)
            pr_url = self._create_pull_request()
            return {
                "status": "SUCCESS",
                "branch": self.branch_name,
                "commit": commit.hexsha,
                "commit_hash": commit.hexsha,
                "pr_url": pr_url,
                "fixes_committed": len(paths),
            }
        except (GitCommandError, GithubException, OSError, RuntimeError) as exc:
            return {"status": "FAILED", "error": str(exc), "branch": self.branch_name, "pr_url": None}
