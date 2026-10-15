import os
import shutil
import re
import json
from pathlib import Path
from typing import Any

from git import Repo
from language_detector import detect_project_details


class RepoPrepAgent:

    def __init__(self, repo_url, team_name, leader_name, language_hint="auto", repo_branch="main"):
        self.repo_url = repo_url

        self.team_name = self._sanitize_name(team_name)
        self.leader_name = self._sanitize_name(leader_name)
        self.language_hint = self._normalize_language_hint(language_hint)
        self.repo_branch = str(repo_branch or "main").strip() or "main"

        self.target_dir = os.path.join(os.getcwd(), "temp")

    @staticmethod
    def _normalize_language_hint(language_hint: str) -> str:
        """Normalize UI language labels to the detector's stable IDs."""
        value = str(language_hint or "auto").strip().lower()
        aliases = {
            "auto detect": "auto",
            "autodetect": "auto",
            "js": "javascript",
            "node": "javascript",
            "ts": "typescript",
            "c++": "cpp",
            "cxx": "cpp",
            "c#": "csharp",
            "cs": "csharp",
            "golang": "go",
            "rs": "rust",
            "kt": "kotlin",
        }
        return aliases.get(value, value)

    # =========================================================
    # NAME SANITIZATION
    # =========================================================

    def _sanitize_name(self, name: str) -> str:
        """
        Convert a name into a safe branch-name component.

        Example:
            Suhas Kumar H R
            ->
            SUHAS_KUMAR_H_R
        """

        name = str(name or "").upper()

        name = name.replace(" ", "_")

        name = re.sub(
            r"[^A-Z0-9_]",
            "",
            name
        )

        name = re.sub(
            r"_+",
            "_",
            name
        )

        return name.strip("_")

    # =========================================================
    # MAIN EXECUTION
    # =========================================================

    def execute(self) -> dict[str, Any]:

        print("\n--- [AGENT START]: RepoPrepAgent ---")

        # -----------------------------------------------------
        # Clone repository
        # -----------------------------------------------------

        if not self._clone_repo():

            return {
                "status": "FAILED",
                "error": "Cloning failed"
            }

        # -----------------------------------------------------
        # Detect project environment
        # -----------------------------------------------------

        try:

            environment = self._detect_environment()

        except Exception as e:

            print(
                f"[ERROR] Environment detection failed: {e}"
            )

            return {
                "status": "FAILED",
                "error": f"Environment detection failed: {e}"
            }

        # -----------------------------------------------------
        # Generate branch name
        # -----------------------------------------------------

        branch_name = (
            f"{self.team_name}_"
            f"{self.leader_name}_"
            f"AI_Fix"
        )

        print(
            f"[LOG] Generated branch name: {branch_name}"
        )

        # -----------------------------------------------------
        # Print environment information
        # -----------------------------------------------------

        print(
            "[SUCCESS] Environment detected:"
        )

        print(
            f"    Language      : "
            f"{environment.get('language')}"
        )

        print(
            f"    Framework     : "
            f"{environment.get('framework')}"
        )

        print(
            f"    Package Mgr   : "
            f"{environment.get('package_manager')}"
        )

        print(
            f"    Build System  : "
            f"{environment.get('build_system')}"
        )

        print(
            f"    Project Path  : "
            f"{environment.get('project_path')}"
        )

        print(
            f"    Relative Path : "
            f"{environment.get('relative_project_path')}"
        )

        print(
            f"    Confidence    : "
            f"{environment.get('confidence')}"
        )

        print(
            "--- [AGENT COMPLETED] ---\n"
        )

        return {
            "status": "SUCCESS",
            "repo_path": self.target_dir,
            "environment": environment,
            "branch_name": branch_name
        }

    # =========================================================
    # CLONE REPOSITORY
    # =========================================================

    def _clone_repo(self):

        if os.path.exists(self.target_dir):

            print(
                f"[LOG] Cleaning existing directory: "
                f"{self.target_dir}"
            )

            try:

                shutil.rmtree(
                    self.target_dir
                )

            except Exception as e:

                print(
                    f"[ERROR] Unable to clean directory: "
                    f"{str(e)}"
                )

                return False

        try:

            print(
                f"[LOG] Cloning {self.repo_url}..."
            )

            Repo.clone_from(
                self.repo_url,
                self.target_dir,
                branch=self.repo_branch,
            )

            print(
                "[SUCCESS] Repository cloned successfully."
            )

            return True

        except Exception as e:

            print(
                f"[ERROR] Clone failed: {str(e)}"
            )

            return False

    # =========================================================
    # READ PROJECT CONFIGURATION
    # =========================================================

    def _load_project_config(self, repo_path: Path):
        """
        Read optional acr-project.json from repository root.

        Example:

        {
          "project": "python",
          "language": "python",
          "path": "python"
        }

        The configuration is optional.

        If it does not exist, automatic project detection
        is used.
        """

        config_path = repo_path / "acr-project.json"

        if not config_path.exists():

            print(
                "[LOG] No acr-project.json found."
            )

            print(
                "[LOG] Using automatic project detection."
            )

            return {}

        try:

            print(
                f"[LOG] Reading project configuration: "
                f"{config_path}"
            )

            with open(
                config_path,
                "r",
                encoding="utf-8"
            ) as file:

                config = json.load(file)

            if not isinstance(config, dict):

                raise ValueError(
                    "acr-project.json must contain a JSON object."
                )

            print(
                "[SUCCESS] Project configuration loaded."
            )

            print(
                f"[LOG] Configured project: "
                f"{config.get('project')}"
            )

            print(
                f"[LOG] Configured language: "
                f"{config.get('language')}"
            )

            print(
                f"[LOG] Configured path: "
                f"{config.get('path')}"
            )

            return config

        except Exception as e:

            raise RuntimeError(
                f"Unable to read acr-project.json: {e}"
            )

    # =========================================================
    # RESOLVE CONFIGURED PROJECT PATH
    # =========================================================

    def _resolve_configured_project_path(
        self,
        repo_path: Path,
        config: dict
    ):
        """
        Resolve the selected project path.

        Example:

            "path": "python"

        becomes:

            <cloned_repo>/python
        """

        configured_path = config.get("path")

        if not configured_path:
            return None

        configured_path = str(
            configured_path
        ).strip()

        if not configured_path:
            return None

        project_path = (
            repo_path / configured_path
        ).resolve()

        repo_resolved = repo_path.resolve()

        # -----------------------------------------------------
        # Security check:
        # Project path must remain inside cloned repository.
        # -----------------------------------------------------

        try:

            project_path.relative_to(
                repo_resolved
            )

        except ValueError:

            raise RuntimeError(
                "Configured project path is outside "
                "the cloned repository."
            )

        if not project_path.exists():

            raise RuntimeError(
                f"Configured project path does not exist: "
                f"{configured_path}"
            )

        if not project_path.is_dir():

            raise RuntimeError(
                f"Configured project path is not a directory: "
                f"{configured_path}"
            )

        print(
            f"[SUCCESS] Configured project selected: "
            f"{project_path}"
        )

        return project_path

    def _find_language_project(self, repo_path: Path, language_hint: str):
        """Find a real subproject matching an explicit language selection.

        Multi-language demo repositories commonly contain one directory per
        language and a root ``acr-project.json`` that documents only one of
        them.  The explicit UI selection must win over that documentation;
        otherwise selecting C++ would silently execute the Java directory.
        """
        ignored = {
            ".git", ".next", "node_modules", "venv", ".venv", "env",
            "__pycache__", "dist", "build", "target", "bin", "obj",
            ".idea", ".vscode", "coverage", "temp",
        }
        candidates: list[Path] = [repo_path]
        for current, dirs, _files in os.walk(repo_path):
            current_path = Path(current)
            dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
            try:
                depth = len(current_path.relative_to(repo_path).parts)
            except ValueError:
                continue
            if depth >= 3:
                dirs[:] = []
                continue
            for dirname in dirs:
                candidates.append(current_path / dirname)

        seen: set[str] = set()
        for candidate in candidates:
            candidate = candidate.resolve()
            key = str(candidate).lower()
            if key in seen or not candidate.is_dir():
                continue
            seen.add(key)
            try:
                details = detect_project_details(str(candidate))
            except Exception as exc:
                print(f"[WARN] Could not inspect candidate {candidate}: {exc}")
                continue
            if details.get("language_id") == language_hint:
                return candidate, details
        return None, None

    # =========================================================
    # ENVIRONMENT DETECTION
    # =========================================================

    def _detect_environment(self):

        repo_path = Path(
            self.target_dir
        )

        print(
            "[LOG] Running structured project detection..."
        )

        # -----------------------------------------------------
        # Read optional project configuration
        # -----------------------------------------------------

        config = self._load_project_config(
            repo_path
        )

        # -----------------------------------------------------
        # Select configured subproject if available
        # -----------------------------------------------------

        configured_project_path = (
            self._resolve_configured_project_path(
                repo_path,
                config
            )
        )

        requested_language = self.language_hint
        language_match = True

        if requested_language != "auto":
            configured_details = None
            if configured_project_path:
                configured_details = detect_project_details(str(configured_project_path))
            if configured_details and configured_details.get("language_id") == requested_language:
                detection_path = configured_project_path
                details = configured_details
            else:
                detection_path, details = self._find_language_project(
                    repo_path,
                    requested_language,
                )
                if detection_path is None or details is None:
                    raise RuntimeError(
                        f"Requested language '{requested_language}' was not found in repository. "
                        "Choose Auto detect or a language that has source/configuration files."
                    )
                # The configured path is only a scope for auto-detect (or when
                # it matches the requested language). Do not let its Java path
                # overwrite an explicitly selected C/C++/Go/etc. subproject.
                configured_project_path = None
                language_match = True
        elif configured_project_path:
            detection_path = configured_project_path
            details = None
        else:
            detection_path = repo_path
            details = None

        print(
            f"[LOG] Detection path: "
            f"{detection_path}"
        )

        # -----------------------------------------------------
        # Run language/project detector
        # -----------------------------------------------------

        if details is None:
            details = detect_project_details(str(detection_path))

        if not isinstance(
            details,
            dict
        ):

            raise RuntimeError(
                "detect_project_details() "
                "did not return a dictionary."
            )

        language_id = details.get(
            "language_id",
            "unknown"
        )

        language = details.get(
            "language",
            "Unknown"
        )

        framework = details.get(
            "framework",
            "Unknown"
        )

        package_manager = details.get(
            "package_manager",
            "Unknown"
        )

        build_system = details.get(
            "build_system",
            "Unknown"
        )

        project_path = details.get(
            "project_path"
        )

        confidence = details.get(
            "confidence",
            0.0
        )

        # -----------------------------------------------------
        # If configured project was selected,
        # make sure detector stays inside that project.
        # -----------------------------------------------------

        if configured_project_path:

            if not project_path:

                project_path = str(
                    configured_project_path
                )

            else:

                detected_path = Path(
                    project_path
                ).resolve()

                selected_path = (
                    configured_project_path.resolve()
                )

                try:

                    detected_path.relative_to(
                        selected_path
                    )

                except ValueError:

                    print(
                        "[WARN] Detector returned a path "
                        "outside the configured project."
                    )

                    project_path = str(
                        configured_project_path
                    )

        # -----------------------------------------------------
        # Normalize project path
        # -----------------------------------------------------

        if project_path:

            project_path = os.path.abspath(
                project_path
            )

        else:

            project_path = str(
                detection_path
            )

        # -----------------------------------------------------
        # Make sure detected project belongs to
        # the cloned repository.
        # -----------------------------------------------------

        try:

            Path(
                project_path
            ).resolve().relative_to(
                repo_path.resolve()
            )

        except ValueError:

            print(
                "[WARN] Detector returned a project path "
                "outside repository."
            )

            project_path = str(
                detection_path
            )

        # -----------------------------------------------------
        # Create structured environment
        # -----------------------------------------------------

        environment = {
            "language_id": language_id,
            "language": language,
            "framework": framework,
            "package_manager": package_manager,
            "build_system": build_system,
            "project_path": project_path,
            "confidence": float(confidence),
            "requested_language": requested_language,
            "language_match": language_match and (
                requested_language == "auto" or language_id == requested_language
            ),
        }

        # -----------------------------------------------------
        # Additional metadata
        # -----------------------------------------------------

        environment["relative_project_path"] = (
            os.path.relpath(
                project_path,
                str(repo_path)
            )
        )

        # -----------------------------------------------------
        # Include configured project information
        # -----------------------------------------------------

        if config:

            environment["configured_project"] = (
                config.get("project")
            )

            environment["configured_language"] = (
                config.get("language")
            )

        # -----------------------------------------------------
        # Human-readable logs
        # -----------------------------------------------------

        print(
            f"[LOG] Language detector result: "
            f"{language}"
        )

        print(
            f"[LOG] Framework: "
            f"{framework}"
        )

        print(
            f"[LOG] Package manager: "
            f"{package_manager}"
        )

        print(
            f"[LOG] Build system: "
            f"{build_system}"
        )

        print(
            f"[LOG] Project path: "
            f"{project_path}"
        )

        print(
            f"[LOG] Relative project path: "
            f"{environment.get('relative_project_path')}"
        )

        print(
            f"[LOG] Detection confidence: "
            f"{confidence}"
        )

        return environment


if __name__ == "__main__":

    print(
        "RepoPrepAgent module loaded successfully."
    )
