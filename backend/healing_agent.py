import os
import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv()


class HealingAgent:
    """
    Agent 3: Autonomous Healing Agent

    Responsibilities:
    1. Receive CI/CD error information.
    2. Receive KNN failure classification.
    3. Identify actual source files responsible for the error.
    4. Read source code.
    5. Ask Gemini to generate a repair.
    6. Validate Gemini response.
    7. Apply the corrected source code.
    8. Preserve backups of original files.
    """

    def __init__(self, repo_path, analysis_result, project_path=None):
        self.repo_path = str(repo_path)
        self.repo_root = Path(repo_path).resolve()
        self.project_root = self._resolve_project_scope(project_path)
        self.analysis_result = analysis_result

        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=self.api_key
        )

        # Keep the model configurable so an unavailable preview name does not
        # stop the recovery pipeline. The stable Flash model is the default.
        self.model_name = os.getenv(
            "ACR_HEAL_MODEL",
            "gemini-3.8-flash",
        )

    def _resolve_project_scope(self, project_path=None):
        """Return the selected language project, never an outside path."""
        if not project_path:
            return self.repo_root
        candidate = Path(str(project_path)).resolve()
        try:
            candidate.relative_to(self.repo_root)
        except ValueError:
            print(
                "[WARN] Analysis project is outside the clone; "
                "healing scope reset to repository root."
            )
            return self.repo_root
        if not candidate.is_dir():
            print(
                "[WARN] Analysis project is not a directory; "
                "healing scope reset to repository root."
            )
            return self.repo_root
        return candidate

    def _within_project_scope(self, path):
        try:
            Path(path).resolve().relative_to(self.project_root)
            return True
        except ValueError:
            return False

    # =========================================================
    # MAIN EXECUTION
    # =========================================================

    def execute(
        self,
        failure_category="UNKNOWN",
        failure_confidence=0.0
    ):
        print("--- [AGENT START]: HealingAgent ---")

        print(
            "[INFO] Error logs received."
        )

        print(
            f"[KNN] Failure Category: "
            f"{failure_category}"
        )

        print(
            f"[KNN] Confidence: "
            f"{failure_confidence}"
        )

        stderr = str(
            self.analysis_result.get(
                "stderr",
                ""
            )
        )

        stdout = str(
            self.analysis_result.get(
                "stdout",
                ""
            )
        )

        error = str(
            self.analysis_result.get(
                "error",
                ""
            )
        )

        combined_error = (
            stderr
            + "\n"
            + stdout
            + "\n"
            + error
        )

        # -----------------------------------------------------
        # IDENTIFY FAILING FILES
        # -----------------------------------------------------

        failing_files = (
            self._identify_files_from_stderr(
                combined_error
            )
        )

        print(
            f"[INFO] Detected failing files: "
            f"{failing_files}"
        )

        if not failing_files:

            print(
                "[WARN] No source files could be "
                "identified from the error."
            )

            return {
                "status": "FAILED",
                "error": (
                    "Could not identify the source "
                    "file responsible for the error."
                ),
                "fixes": [],
                "fixes_count": 0,
                "failure_category": failure_category,
                "failure_confidence": failure_confidence
            }

        # -----------------------------------------------------
        # READ SOURCE FILES
        # -----------------------------------------------------

        source_files = {}

        for file_path in failing_files:

            content = (
                self._read_file_content(
                    file_path
                )
            )

            if content is not None:

                relative_path = (
                    self._normalize_relative_path(
                        file_path
                    )
                )

                if relative_path:

                    source_files[
                        relative_path
                    ] = content

        if not source_files:

            print(
                "[ERROR] Could not read any "
                "identified source files."
            )

            return {
                "status": "FAILED",
                "error": (
                    "Could not read the identified "
                    "source files."
                ),
                "fixes": [],
                "fixes_count": 0,
                "failure_category": failure_category,
                "failure_confidence": failure_confidence
            }

        # -----------------------------------------------------
        # GENERATE GEMINI PROMPT
        # -----------------------------------------------------

        prompt = self._build_prompt(
            combined_error,
            source_files,
            failure_category,
            failure_confidence
        )

        # -----------------------------------------------------
        # CALL GEMINI
        # -----------------------------------------------------

        response_data = (
            self._call_gemini(
                prompt
            )
        )

        if response_data is None:

            return {
                "status": "FAILED",
                "error": (
                    "Gemini returned invalid JSON."
                ),
                "fixes": [],
                "fixes_count": 0,
                "failure_category": failure_category,
                "failure_confidence": failure_confidence
            }

        # -----------------------------------------------------
        # NORMALIZE RESPONSE
        # -----------------------------------------------------

        fixes = self._normalize_fixes(
            response_data
        )

        if not fixes:

            print(
                "[ERROR] Gemini did not provide "
                "any valid fixes."
            )

            return {
                "status": "FAILED",
                "error": (
                    "Gemini did not provide "
                    "any valid fixes."
                ),
                "fixes": [],
                "fixes_count": 0,
                "failure_category": failure_category,
                "failure_confidence": failure_confidence
            }

        # -----------------------------------------------------
        # APPLY FIXES
        # -----------------------------------------------------

        applied_fixes = []

        for fix in fixes:

            if not self._validate_fix_format(
                fix
            ):
                continue

            relative_path = (
                self._normalize_relative_path(
                    fix["file_path"]
                )
            )

            if not relative_path:
                continue

            fix["file_path"] = relative_path

            success = self._apply_fix(
                fix
            )

            if success:

                applied_fixes.append(
                    fix
                )

        if not applied_fixes:

            print(
                "[ERROR] No Gemini fixes "
                "could be applied."
            )

            return {
                "status": "FAILED",
                "error": (
                    "No Gemini fixes could "
                    "be applied."
                ),
                "fixes": [],
                "fixes_count": 0,
                "failure_category": failure_category,
                "failure_confidence": failure_confidence
            }

        print(
            f"[SUCCESS] Applied "
            f"{len(applied_fixes)} fix(es)."
        )

        print(
            "--- [AGENT COMPLETED] ---"
        )

        return {
            "status": "SUCCESS",
            "fixes": applied_fixes,
            "fixes_count": len(
                applied_fixes
            ),
            "failure_category": failure_category,
            "failure_confidence": failure_confidence
        }

    # =========================================================
    # BUILD GEMINI PROMPT
    # =========================================================

    def _build_prompt(
        self,
        error_log,
        source_files,
        failure_category,
        failure_confidence
    ):

        source_text = ""

        for path, content in source_files.items():

            source_text += (
                "\n\n"
                + "=" * 60
                + "\n"
                + f"FILE: {path}\n"
                + "=" * 60
                + "\n"
                + content
            )

        prompt = f"""
You are an autonomous software repair agent.

Analyze the CI/CD failure and repair the source code.

The system uses KNN for failure classification.

Gemini is responsible for source-code analysis
and generating the repair.

KNN failure category:

{failure_category}

KNN confidence:

{failure_confidence}

IMPORTANT:

The KNN category is supporting information.

You must independently inspect the error and source code.

CI/CD ERROR LOG:

{error_log}

SOURCE FILES:

{source_text}

SELECTED PROJECT SCOPE:

{self.project_root.relative_to(self.repo_root).as_posix() if self.project_root != self.repo_root else "."}

Only repair files inside the selected project scope above. Do not modify any
other language directory in the repository.

Return ONLY valid JSON.

The response must contain a JSON array.

Each fix must contain:

{{
    "file_path": "repository-relative/path",
    "bug_type": "TYPE_ERROR",
    "description": "short explanation",
    "fixed_code": "complete corrected source code",
    "commit_message": "fix: short commit message"
}}

Allowed bug_type values:

IMPORT
LINTING
INDENTATION
SYNTAX
LOGIC
TYPE_ERROR
COMPILATION
DEPENDENCY
BUILD
TEST

IMPORTANT RULES:

1. file_path must be repository-relative.

2. Do not use /app/temp/ or other Docker paths.

3. Only modify files that actually exist.

4. fixed_code must contain the complete corrected file.

5. Preserve the existing functionality.

6. Do not invent files.

7. Do not include Markdown.

8. Do not include ```json.

9. Return valid JSON only.

10. Escape all quotation marks and newlines correctly.

"""

        return prompt

    # =========================================================
    # IDENTIFY FILES FROM ERROR
    # =========================================================

    def _identify_files_from_stderr(
        self,
        stderr
    ):
        """
        Identify actual source files mentioned in an error log.

        The detected path is accepted only when the corresponding
        file actually exists inside the cloned repository.

        This prevents words such as:

            Node.js
            Next.js

        from being incorrectly treated as source files.
        """

        files = []

        if not stderr:
            return files

        text = str(stderr)

        # -----------------------------------------------------
        # Python traceback
        #
        # Example:
        #
        # File "/app/temp/main.py", line 10
        # -----------------------------------------------------

        python_matches = re.findall(
            r'File\s+["\']([^"\']+)["\']',
            text
        )

        files.extend(
            python_matches
        )

        # -----------------------------------------------------
        # Custom error format
        #
        # Example:
        #
        # Error in src/main.py:
        # -----------------------------------------------------

        custom_matches = re.findall(
            r"Error in\s+(.+?):",
            text
        )

        files.extend(
            custom_matches
        )

        # -----------------------------------------------------
        # Java compiler
        #
        # Example:
        #
        # Main.java:12: error:
        # -----------------------------------------------------

        java_matches = re.findall(
            r'([A-Za-z0-9_./\\-]+\.java):\d+(?::\d+)?',
            text
        )

        files.extend(
            java_matches
        )

        # -----------------------------------------------------
        # Maven Java
        #
        # Example:
        #
        # /app/temp/src/Main.java:[12,5]
        # -----------------------------------------------------

        maven_matches = re.findall(
            r'([A-Za-z0-9_./\\-]+\.java):\[\d+,\d+\]',
            text
        )

        files.extend(
            maven_matches
        )

        # -----------------------------------------------------
        # JavaScript / TypeScript
        #
        # Examples:
        #
        # frontend/app/page.tsx:10:5
        # src/index.js:12:4
        # -----------------------------------------------------

        js_ts_matches = re.findall(
            r'([A-Za-z0-9_./\\-]+\.(?:js|jsx|ts|tsx)):\d+(?::\d+)?',
            text
        )

        files.extend(
            js_ts_matches
        )

        # -----------------------------------------------------
        # Standalone source paths
        #
        # IMPORTANT:
        # These are only candidates.
        #
        # They are later checked against the actual
        # repository filesystem.
        # -----------------------------------------------------

        standalone_matches = re.findall(
            r'(?<![\w.-])'
            r'([A-Za-z0-9_./\\-]+'
            r'\.(?:js|jsx|ts|tsx|py|java|c|h|cpp|cc|cxx|hpp|cs|go|rs|php|kt|kts|json|toml|xml|gradle))'
            r'(?![\w.-])',
            text,
            flags=re.IGNORECASE,
        )

        files.extend(
            standalone_matches
        )

        # Build tools often report a configuration filename without a line
        # number. It remains only a candidate until filesystem validation
        # below proves it is an existing file inside the cloned repository.
        config_matches = re.findall(
            r'(?<![\w.-])'
            r'([A-Za-z0-9_./\\-]*(?:package\.json|requirements\.txt|pyproject\.toml|pom\.xml|'
            r'build\.gradle(?:\.kts)?|CMakeLists\.txt|Makefile|[^/\\]+\.csproj|go\.mod|'
            r'Cargo\.toml|composer\.json|Dockerfile|tsconfig\.json))'
            r'(?![\w.-])',
            text,
            flags=re.IGNORECASE,
        )

        files.extend(
            config_matches
        )

        # -----------------------------------------------------
        # NORMALIZE + VALIDATE
        # -----------------------------------------------------

        unique_files = []

        repo_root = (
            Path(self.repo_path)
            .resolve()
        )

        for file_path in files:

            file_path = str(
                file_path
            ).strip()

            if not file_path:
                continue

            file_path = (
                file_path
                .strip('"')
                .strip("'")
            )

            # Convert Windows separators
            file_path = file_path.replace(
                "\\",
                "/"
            )

            # Remove ./ prefix
            while file_path.startswith(
                "./"
            ):
                file_path = file_path[2:]

            # -------------------------------------------------
            # NORMALIZE DOCKER / ABSOLUTE PATH
            # -------------------------------------------------

            relative_path = (
                self._normalize_relative_path(
                    file_path
                )
            )

            if not relative_path:
                continue

            # -------------------------------------------------
            # SECURITY CHECK
            # -------------------------------------------------

            candidate_path = (
                repo_root
                / relative_path
            ).resolve()

            try:

                candidate_path.relative_to(
                    repo_root
                )

            except ValueError:

                continue

            if not self._within_project_scope(candidate_path):
                continue

            # -------------------------------------------------
            # CRITICAL VALIDATION
            #
            # Only accept the path if it is an actual file.
            #
            # This prevents:
            #
            # Node.js
            # Next.js
            #
            # from being treated as files.
            # -------------------------------------------------

            if not candidate_path.exists():

                continue

            if not candidate_path.is_file():

                continue

            # -------------------------------------------------
            # REMOVE DUPLICATES
            # -------------------------------------------------

            if relative_path not in unique_files:

                unique_files.append(
                    relative_path
                )

        return unique_files

    # =========================================================
    # READ SOURCE FILE
    # =========================================================

    def _read_file_content(
        self,
        file_path
    ):

        try:

            relative_path = (
                self._normalize_relative_path(
                    file_path
                )
            )

            if not relative_path:
                return None

            full_path = (
                Path(self.repo_path)
                / relative_path
            )

            repo_root = (
                Path(self.repo_path)
                .resolve()
            )

            full_path = (
                full_path.resolve()
            )

            # -------------------------------------------------
            # SECURITY CHECK
            # -------------------------------------------------

            try:

                full_path.relative_to(
                    repo_root
                )

            except ValueError:

                print(
                    f"[WARN] Ignoring unsafe "
                    f"file path: {file_path}"
                )

                return None

            # -------------------------------------------------
            # FILE EXISTENCE
            # -------------------------------------------------

            if not full_path.exists():

                print(
                    f"[WARN] File not found: "
                    f"{relative_path}"
                )

                return None

            if not full_path.is_file():

                return None

            # -------------------------------------------------
            # READ FILE
            # -------------------------------------------------

            return full_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        except Exception as e:

            print(
                f"[WARN] Could not read file "
                f"{file_path}: {e}"
            )

            return None

    # =========================================================
    # NORMALIZE FILE PATH
    # =========================================================

    def _normalize_relative_path(
        self,
        file_path
    ):

        if not file_path:
            return None

        path = str(
            file_path
        ).strip()

        path = (
            path
            .strip('"')
            .strip("'")
        )

        # Convert Windows separators
        path = path.replace(
            "\\",
            "/"
        )

        # Remove ./ prefix
        while path.startswith(
            "./"
        ):

            path = path[2:]

        # -----------------------------------------------------
        # ABSOLUTE PATH
        # -----------------------------------------------------

        try:

            candidate = Path(
                path
            )

            if candidate.is_absolute():

                repo_root = (
                    Path(self.repo_path)
                    .resolve()
                )

                candidate = (
                    candidate.resolve()
                )

                try:

                    relative = (
                        candidate.relative_to(
                            repo_root
                        )
                    )

                    return relative.as_posix()

                except ValueError:

                    normalized = (
                        path.replace(
                            "\\",
                            "/"
                        )
                    )

                    if "/temp/" in normalized:

                        return (
                            normalized.split(
                                "/temp/",
                                1
                            )[1]
                        )

                    return None

        except Exception:

            pass

        # -----------------------------------------------------
        # REMOVE COMMON DOCKER REPOSITORY PREFIXES
        # -----------------------------------------------------

        prefixes = [
            "/app/temp/",
            "app/temp/",
            "/workspace/",
            "workspace/"
        ]

        for prefix in prefixes:

            if path.startswith(prefix):

                path = path[
                    len(prefix):
                ]

                break

        return path

    # =========================================================
    # VALIDATE GEMINI FIX
    # =========================================================

    def _validate_fix_format(
        self,
        fix
    ):

        required_fields = [
            "file_path",
            "bug_type",
            "description",
            "fixed_code"
        ]

        for field in required_fields:

            if field not in fix:

                print(
                    f"[WARN] Missing field: "
                    f"{field}"
                )

                return False

        # -----------------------------------------------------
        # COMMIT MESSAGE IS OPTIONAL
        # -----------------------------------------------------

        fix.setdefault(
            "commit_message",
            f"fix: {fix['bug_type']} "
            f"in {fix['file_path']}"
        )

        # -----------------------------------------------------
        # ALLOWED BUG TYPES
        # -----------------------------------------------------

        allowed_bug_types = {
            "IMPORT",
            "LINTING",
            "INDENTATION",
            "SYNTAX",
            "LOGIC",
            "TYPE_ERROR",
            "COMPILATION",
            "DEPENDENCY",
            "BUILD",
            "TEST"
        }

        bug_type = str(
            fix["bug_type"]
        ).upper()

        if bug_type not in allowed_bug_types:

            print(
                f"[WARN] Unsupported bug type: "
                f"{bug_type}"
            )

            return False

        fix["bug_type"] = bug_type

        # -----------------------------------------------------
        # FIXED CODE VALIDATION
        # -----------------------------------------------------

        if not isinstance(
            fix["fixed_code"],
            str
        ):

            print(
                "[WARN] fixed_code must "
                "be a string."
            )

            return False

        if not fix[
            "fixed_code"
        ].strip():

            print(
                "[WARN] fixed_code is empty."
            )

            return False

        # -----------------------------------------------------
        # FILE PATH VALIDATION
        # -----------------------------------------------------

        if not str(
            fix["file_path"]
        ).strip():

            return False

        return True

    # =========================================================
    # NORMALIZE GEMINI RESPONSE
    # =========================================================

    def _normalize_fixes(
        self,
        response_data
    ):

        if isinstance(
            response_data,
            dict
        ):

            if "fixes" in response_data:

                response_data = (
                    response_data["fixes"]
                )

            else:

                response_data = [
                    response_data
                ]

        if not isinstance(
            response_data,
            list
        ):

            return []

        valid_fixes = []

        for fix in response_data:

            if not isinstance(
                fix,
                dict
            ):

                continue

            valid_fixes.append(
                fix
            )

        return valid_fixes

    # =========================================================
    # GEMINI API
    # =========================================================

    def _call_gemini(
        self,
        prompt
    ):

        primary_model = self.model_name.strip()
        fallback_model = os.getenv(
            "ACR_HEAL_FALLBACK_MODEL",
            os.getenv("ACR_AURA_FALLBACK_MODEL", "gemini-3.7-flash"),
        ).strip()
        models = [primary_model]
        if fallback_model and fallback_model not in models:
            models.append(fallback_model)

        # Keep healing bounded: retry the primary once, then try the fallback
        # once. A provider capacity error must not make every language fail.
        max_attempts = 3
        attempt = 0
        for model_index, model_name in enumerate(models):
            model_attempts = 2 if model_index == 0 else 1
            for _ in range(model_attempts):
                attempt += 1
                if attempt > max_attempts:
                    break

                try:

                    print(
                        f"[INFO] Gemini API "
                        f"attempt {attempt}/"
                        f"{max_attempts} using {model_name}..."
                    )

                    response = (
                        self.client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config={
                                "temperature": 0.1,
                                "response_mime_type":
                                    "application/json"
                            }
                        )
                    )

                    text = (
                        response.text
                        if response
                        else ""
                    )

                    if not text:

                        raise ValueError(
                            "Gemini returned "
                            "an empty response."
                        )

                    parsed = (
                        self._parse_gemini_json(
                            text
                        )
                    )

                    if parsed is not None:

                        print(
                            "[SUCCESS] Gemini response "
                            "parsed successfully."
                        )

                        return parsed

                    print(
                        "[WARN] Gemini returned "
                        "invalid JSON."
                    )

                except Exception as e:

                    formatted_error = (
                        self._format_gemini_error(
                            e
                        )
                    )

                    print(
                        f"[WARN] Gemini attempt "
                        f"{attempt} failed: "
                        f"{formatted_error}"
                    )

                if attempt < max_attempts:

                    time.sleep(
                        2 * attempt
                    )

        print(
            "[ERROR] Gemini healing failed "
            "after all attempts."
        )

        return None

    # =========================================================
    # ROBUST GEMINI JSON PARSER
    # =========================================================

    def _parse_gemini_json(
        self,
        text
    ):

        if not text:
            return None

        text = str(
            text
        ).strip()

        # -----------------------------------------------------
        # ATTEMPT 1: DIRECT JSON
        # -----------------------------------------------------

        try:

            return json.loads(
                text
            )

        except Exception:

            pass

        # -----------------------------------------------------
        # REMOVE MARKDOWN FENCES
        # -----------------------------------------------------

        cleaned = re.sub(
            r"^```(?:json)?",
            "",
            text,
            flags=re.IGNORECASE
        )

        cleaned = re.sub(
            r"```$",
            "",
            cleaned
        )

        cleaned = cleaned.strip()

        try:

            return json.loads(
                cleaned
            )

        except Exception:

            pass

        # -----------------------------------------------------
        # FIND FIRST JSON OBJECT / ARRAY
        # -----------------------------------------------------

        start_positions = []

        object_start = cleaned.find(
            "{"
        )

        array_start = cleaned.find(
            "["
        )

        if object_start >= 0:

            start_positions.append(
                object_start
            )

        if array_start >= 0:

            start_positions.append(
                array_start
            )

        if not start_positions:

            return None

        start = min(
            start_positions
        )

        opening = cleaned[
            start
        ]

        depth = 0

        in_string = False

        escaped = False

        for index in range(
            start,
            len(cleaned)
        ):

            char = cleaned[
                index
            ]

            # -------------------------------------------------
            # ESCAPED CHARACTERS
            # -------------------------------------------------

            if escaped:

                escaped = False

                continue

            if char == "\\" and in_string:

                escaped = True

                continue

            # -------------------------------------------------
            # STRING HANDLING
            # -------------------------------------------------

            if char == '"':

                in_string = (
                    not in_string
                )

                continue

            if in_string:

                continue

            # -------------------------------------------------
            # NESTED OBJECTS / ARRAYS
            # -------------------------------------------------

            if char in "{[":

                depth += 1

            elif char in "}]":

                depth -= 1

                if depth == 0:

                    candidate = (
                        cleaned[
                            start:index + 1
                        ]
                    )

                    try:

                        return json.loads(
                            candidate
                        )

                    except Exception:

                        return None

        return None

    # =========================================================
    # APPLY GEMINI FIX
    # =========================================================

    def _apply_fix(
        self,
        fix_details
    ):

        try:

            relative_path = (
                self._normalize_relative_path(
                    fix_details[
                        "file_path"
                    ]
                )
            )

            if not relative_path:

                print(
                    "[ERROR] Invalid "
                    "file path."
                )

                return False

            repo_root = (
                Path(self.repo_path)
                .resolve()
            )

            target_path = (
                repo_root
                / relative_path
            ).resolve()

            # -------------------------------------------------
            # SECURITY CHECK
            # -------------------------------------------------

            try:

                target_path.relative_to(
                    repo_root
                )

            except ValueError:

                print(
                    "[ERROR] Attempt to modify "
                    "file outside repository."
                )

                return False

            if not self._within_project_scope(target_path):
                print(
                    "[ERROR] Attempt to modify a file outside the "
                    "selected language project."
                )
                return False

            # -------------------------------------------------
            # FILE MUST EXIST
            # -------------------------------------------------

            if not target_path.exists():

                print(
                    f"[ERROR] Cannot apply fix. "
                    f"File does not exist: "
                    f"{relative_path}"
                )

                return False

            if not target_path.is_file():

                return False

            # -------------------------------------------------
            # BACKUP ORIGINAL
            # -------------------------------------------------

            backup_path = (
                target_path.with_suffix(
                    target_path.suffix
                    + ".acr_backup"
                )
            )

            if not backup_path.exists():

                backup_path.write_text(
                    target_path.read_text(
                        encoding="utf-8",
                        errors="ignore"
                    ),
                    encoding="utf-8"
                )

            # -------------------------------------------------
            # WRITE FIXED CODE
            # -------------------------------------------------

            target_path.write_text(
                fix_details[
                    "fixed_code"
                ],
                encoding="utf-8"
            )

            print(
                f"[SUCCESS] Fix applied to: "
                f"{relative_path}"
            )

            return True

        except Exception as e:

            print(
                f"[ERROR] Failed to apply fix: "
                f"{e}"
            )

            return False

    # =========================================================
    # FORMAT GEMINI ERROR
    # =========================================================

    def _format_gemini_error(
        self,
        error_message
    ):

        message = str(
            error_message
        )

        if "503" in message:

            return (
                "Gemini service temporarily "
                "unavailable (503). "
                "Please retry."
            )

        if "429" in message:

            return (
                "Gemini API rate limit reached. "
                "Please retry later."
            )

        if "401" in message:

            return (
                "Gemini API authentication failed. "
                "Check GEMINI_API_KEY."
            )

        if "403" in message:

            return (
                "Gemini API access denied. "
                "Check API key permissions."
            )

        return message
