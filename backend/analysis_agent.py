import subprocess
import shutil
import time
import os
from pathlib import Path


class AnalysisAgent:
    """
    ACR_AGENT Analysis Agent

    Responsibilities:
    - Read the structured environment returned by language_detector.py
    - Resolve the actual project directory
    - Detect/normalize the project language
    - Detect framework and package manager
    - Install dependencies when required
    - Run build / compile / syntax checks
    - Return structured analysis results for the KNN + healing pipeline
    """

    def __init__(self, repo_path, environment, deadline=None):
        self.repo_path = Path(repo_path)

        # RepoPrepAgent now returns a dictionary.
        # Keep compatibility with the old string-based format as well.
        self.environment = environment
        self.deadline = deadline

    # =========================================================
    # MAIN EXECUTION
    # =========================================================

    def execute(self):
        print("--- [AGENT START]: AnalysisAgent ---")

        print(
            f"[LOG] Repository path: {self.repo_path}"
        )

        print(
            f"[LOG] Analyzing environment: "
            f"{self.environment}"
        )

        language_id = self._detect_language_id()
        project_path = self._resolve_project_path()
        framework = self._get_framework()
        package_manager = self._get_package_manager()

        print(f"[LOG] Detected language: {language_id}")
        print(f"[LOG] Project path: {project_path}")
        print(f"[LOG] Framework: {framework}")
        print(f"[LOG] Package manager: {package_manager}")

        # -----------------------------------------------------
        # TYPESCRIPT / JAVASCRIPT
        # -----------------------------------------------------

        if language_id in ("typescript", "javascript"):
            result = self._check_js_build(
                project_path=project_path,
                language_id=language_id,
                package_manager=package_manager,
            )

        # -----------------------------------------------------
        # PYTHON
        # -----------------------------------------------------

        elif language_id == "python":
            result = self._check_python_compilation(project_path)

        # -----------------------------------------------------
        # JAVA
        # -----------------------------------------------------

        elif language_id == "java":
            result = self._check_java_build(project_path)

        elif language_id == "kotlin":
            result = self._check_kotlin_build(project_path)

        # -----------------------------------------------------
        # C / C++
        # -----------------------------------------------------

        elif language_id in ("c", "cpp"):
            result = self._check_c_cpp(project_path, language_id)

        # -----------------------------------------------------
        # GO
        # -----------------------------------------------------

        elif language_id == "go":
            result = self._check_go(project_path)

        # -----------------------------------------------------
        # RUST
        # -----------------------------------------------------

        elif language_id == "rust":
            result = self._check_rust(project_path)

        # -----------------------------------------------------
        # PHP
        # -----------------------------------------------------

        elif language_id == "php":
            result = self._check_php(project_path)

        # -----------------------------------------------------
        # C#
        # -----------------------------------------------------

        elif language_id in ("csharp", "c#"):
            result = self._check_csharp(project_path)

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        else:
            result = self._check_simple_project(
                project_path,
                language_id
            )

        # Add common metadata.
        if isinstance(result, dict):
            result.setdefault("language_id", language_id)
            result.setdefault("project_path", str(project_path))
            result.setdefault("framework", framework)
            result.setdefault("package_manager", package_manager)

        print(
            f"[LOG] Analysis result: {result}"
        )

        print("--- [AGENT END]: AnalysisAgent ---")

        return result

    # =========================================================
    # LANGUAGE DETECTION
    # =========================================================

    def _detect_language_id(self):
        """
        Extract language_id from the structured environment.

        Example:

        {
            "status": "SUCCESS",
            "language_id": "typescript",
            "language": "TypeScript",
            "framework": "Next.js",
            "package_manager": "npm",
            "project_path": "...",
            "repository_path": "..."
        }
        """

        environment = self.environment

        # New structured format.
        if isinstance(environment, dict):

            language_id = environment.get("language_id")

            if language_id:
                return self._normalize_language(language_id)

            language = environment.get("language")

            if language:
                return self._normalize_language(language)

        # Backward compatibility with old string format.
        if isinstance(environment, str):
            return self._normalize_language(environment)

        return "unknown"

    # =========================================================
    # LANGUAGE NORMALIZATION
    # =========================================================

    def _normalize_language(self, language):
        """
        Convert different language names into stable IDs.
        """

        if not language:
            return "unknown"

        value = str(language).strip().lower()

        # TypeScript
        if value in (
            "typescript",
            "ts",
            "typescript_simple",
            "typescript (npm)",
            "typescript (bun)",
            "typescript (yarn)",
            "typescript (pnpm)",
        ):
            return "typescript"

        # JavaScript
        if value in (
            "javascript",
            "js",
            "javascript_simple",
            "javascript (npm)",
            "javascript (bun)",
            "javascript (yarn)",
            "javascript (pnpm)",
        ):
            return "javascript"

        # Python
        if value in (
            "python",
            "python_simple",
            "python3",
            "py",
        ):
            return "python"

        # Java
        if value.startswith("java"):
            return "java"

        if value in ("kotlin", "kt", "kts"):
            return "kotlin"

        # C++
        if value in (
            "cpp",
            "c++",
            "cxx",
            "cplusplus",
        ):
            return "cpp"

        # C
        if value in (
            "c",
            "c language",
        ):
            return "c"

        # Go
        if value in (
            "go",
            "golang",
        ):
            return "go"

        # Rust
        if value in (
            "rust",
            "rs",
        ):
            return "rust"

        # PHP
        if value in (
            "php",
        ):
            return "php"

        # C#
        if value in (
            "c#",
            "csharp",
            "cs",
            ".net",
            "dotnet",
        ):
            return "csharp"

        return value

    # =========================================================
    # PROJECT PATH
    # =========================================================

    def _resolve_project_path(self):
        """
        Resolve the actual application directory.

        language_detector.py already identifies the correct project
        path, for example:

            repository/
                frontend/
                    package.json
                    package-lock.json

        In that case we must analyze frontend/, not repository/.
        """

        # -----------------------------------------------------
        # Structured environment
        # -----------------------------------------------------

        if isinstance(self.environment, dict):

            project_path = self.environment.get("project_path")

            if project_path:
                path = Path(project_path)

                if path.exists():
                    return path

            relative_project_path = (
                self.environment.get("relative_project_path")
            )

            if relative_project_path:
                path = self.repo_path / relative_project_path

                if path.exists():
                    return path

        # -----------------------------------------------------
        # Look for common project directories
        # -----------------------------------------------------

        candidates = [
            self.repo_path,
            self.repo_path / "frontend",
            self.repo_path / "client",
            self.repo_path / "web",
            self.repo_path / "app",
            self.repo_path / "website",
            self.repo_path / "backend",
            self.repo_path / "server",
        ]

        for candidate in candidates:
            if not candidate.exists():
                continue

            if (
                (candidate / "package.json").exists()
                or (candidate / "requirements.txt").exists()
                or (candidate / "pyproject.toml").exists()
                or (candidate / "pom.xml").exists()
                or (candidate / "build.gradle").exists()
                or (candidate / "build.gradle.kts").exists()
                or (candidate / "go.mod").exists()
                or (candidate / "Cargo.toml").exists()
                or any(candidate.glob("*.csproj"))
                or any(candidate.glob("*.sln"))
                or (candidate / "composer.json").exists()
                or (candidate / "CMakeLists.txt").exists()
                or (candidate / "Makefile").exists()
            ):
                return candidate

        return self.repo_path

    # =========================================================
    # FRAMEWORK
    # =========================================================

    def _get_framework(self):
        """
        Read framework information from the environment.
        """

        if isinstance(self.environment, dict):

            framework = self.environment.get("framework")

            if framework:
                return str(framework)

        project_path = self._resolve_project_path()

        package_json = project_path / "package.json"

        if package_json.exists():
            try:
                import json

                data = json.loads(
                    package_json.read_text(
                        encoding="utf-8"
                    )
                )

                dependencies = {}

                dependencies.update(
                    data.get("dependencies", {})
                )

                dependencies.update(
                    data.get("devDependencies", {})
                )

                if "next" in dependencies:
                    return "Next.js"

                if "vite" in dependencies:
                    return "Vite"

                if "react" in dependencies:
                    return "React"

                if "vue" in dependencies:
                    return "Vue"

                if "angular" in dependencies:
                    return "Angular"

            except Exception:
                pass

        if (project_path / "pom.xml").exists():
            return "Maven"

        if (
            (project_path / "build.gradle").exists()
            or (project_path / "build.gradle.kts").exists()
        ):
            return "Gradle"

        if (project_path / "manage.py").exists():
            return "Django"

        return "Unknown"

    # =========================================================
    # PACKAGE MANAGER
    # =========================================================

    def _get_package_manager(self):
        """
        Determine the package manager for the current project.

        Node.js package managers are detected only for JavaScript
        and TypeScript projects.

        Priority:
            package-lock.json -> npm
            pnpm-lock.yaml   -> pnpm
            yarn.lock        -> yarn
            bun.lock         -> bun
            bun.lockb        -> bun

        Non-Node languages such as Java, Python, C/C++, Go, Rust,
        PHP, and C# return "none" instead of incorrectly detecting
        npm from unrelated files elsewhere in the repository.
        """

        language_id = self._detect_language_id()

        # Package managers in this method are relevant only
        # to JavaScript and TypeScript projects.
        if language_id not in ("javascript", "typescript"):
            return "none"

        if isinstance(self.environment, dict):
            manager = self.environment.get("package_manager")

            if manager:
                manager = str(manager).strip().lower()

                if manager in (
                    "npm",
                    "pnpm",
                    "yarn",
                    "bun",
                ):
                    return manager

        project_path = self._resolve_project_path()

        # npm gets priority when package-lock exists.
        if (project_path / "package-lock.json").exists():
            return "npm"

        if (project_path / "pnpm-lock.yaml").exists():
            return "pnpm"

        if (project_path / "yarn.lock").exists():
            return "yarn"

        if (project_path / "bun.lock").exists():
            return "bun"

        if (project_path / "bun.lockb").exists():
            return "bun"

        if (project_path / "package.json").exists():
            return "npm"

        return "none"

    # =========================================================
    # COMMAND RUNNER
    # =========================================================

    def _run_command(
        self,
        command,
        cwd=None,
        timeout=600,
    ):
        """
        Execute a command and return structured output.
        """

        if cwd is None:
            cwd = self.repo_path

        cwd = Path(cwd)

        print(
            f"[COMMAND] {' '.join(command)}"
        )

        effective_timeout = timeout
        if self.deadline is not None:
            remaining = int(self.deadline - time.time())
            if remaining <= 0:
                return {
                    "returncode": 124,
                    "stdout": "",
                    "stderr": "Pipeline time budget exceeded before command started.",
                    "command": " ".join(command),
                }
            effective_timeout = min(timeout, remaining)

        try:
            process = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                shell=False,
            )

            return {
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "command": " ".join(command),
            }

        except subprocess.TimeoutExpired as exc:

            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode(
                    "utf-8",
                    errors="replace"
                )

            if isinstance(stderr, bytes):
                stderr = stderr.decode(
                    "utf-8",
                    errors="replace"
                )

            return {
                "returncode": 124,
                "stdout": stdout,
                "stderr": (
                    f"{stderr}\n"
                    f"Command timed out after "
                    f"{effective_timeout} seconds."
                ),
                "command": " ".join(command),
            }

        except FileNotFoundError as exc:

            return {
                "returncode": 127,
                "stdout": "",
                "stderr": str(exc),
                "command": " ".join(command),
            }

        except Exception as exc:

            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
                "command": " ".join(command),
            }

    # =========================================================
    # NODE / TYPESCRIPT / JAVASCRIPT BUILD
    # =========================================================

    def _check_js_build(
        self,
        project_path=None,
        language_id="typescript",
        package_manager="npm",
    ):
        """
        Install Node dependencies and execute the appropriate
        build/compile script.

        For the current ACR_AGENT frontend:

            package.json
            package-lock.json
            bun.lockb

        npm is selected because package-lock.json has priority.
        """

        if project_path is None:
            project_path = self._resolve_project_path()

        project_path = Path(project_path)

        package_json = project_path / "package.json"

        if not package_json.exists():

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "missing_package_json",
                "message": (
                    f"package.json not found in "
                    f"{project_path}"
                ),
                "stdout": "",
                "stderr": "",
                "command": "",
            }

        # -----------------------------------------------------
        # Read package.json
        # -----------------------------------------------------

        try:
            import json

            package_data = json.loads(
                package_json.read_text(
                    encoding="utf-8"
                )
            )

        except Exception as exc:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "package_json_parse_error",
                "message": str(exc),
                "stdout": "",
                "stderr": "",
                "command": "",
            }

        scripts = package_data.get(
            "scripts",
            {}
        )

        # -----------------------------------------------------
        # Select package manager
        # -----------------------------------------------------

        package_manager = (
            package_manager or
            self._get_package_manager()
        ).lower()

        # If package-lock exists, force npm.
        if (project_path / "package-lock.json").exists():
            package_manager = "npm"

        # -----------------------------------------------------
        # Install dependencies
        # -----------------------------------------------------

        if package_manager == "npm":

            if (
                project_path / "package-lock.json"
            ).exists():

                install_command = [
                    "npm",
                    "ci",
                ]

            else:

                install_command = [
                    "npm",
                    "install",
                ]

        elif package_manager == "pnpm":

            install_command = [
                "pnpm",
                "install",
                "--frozen-lockfile",
            ]

        elif package_manager == "yarn":

            install_command = [
                "yarn",
                "install",
                "--frozen-lockfile",
            ]

        elif package_manager == "bun":

            if shutil.which("bun") is None:

                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "bun_not_installed",
                    "message": (
                        "bun.lock/bun.lockb was detected, "
                        "but Bun is not installed."
                    ),
                    "stdout": "",
                    "stderr": "",
                    "command": "",
                }

            install_command = [
                "bun",
                "install",
            ]

        else:

            install_command = [
                "npm",
                "install",
            ]

        install_result = self._run_command(
            install_command,
            cwd=project_path,
            timeout=900,
        )

        if install_result["returncode"] != 0:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "dependency_installation_error",
                "message": (
                    "Node dependency installation failed."
                ),
                "stdout": install_result["stdout"],
                "stderr": install_result["stderr"],
                "command": install_result["command"],
                "language_id": language_id,
            }

        # -----------------------------------------------------
        # Determine build command
        # -----------------------------------------------------

        build_script = None

        # Prefer build.
        if "build" in scripts:
            build_script = "build"

        # Otherwise compile.
        elif "compile" in scripts:
            build_script = "compile"

        # Type checking if no build/compile exists.
        elif (
            language_id == "typescript"
            and "typecheck" in scripts
        ):
            build_script = "typecheck"

        # -----------------------------------------------------
        # Run build
        # -----------------------------------------------------

        if build_script:

            if package_manager == "npm":

                build_command = [
                    "npm",
                    "run",
                    build_script,
                ]

            elif package_manager == "pnpm":

                build_command = [
                    "pnpm",
                    "run",
                    build_script,
                ]

            elif package_manager == "yarn":

                build_command = [
                    "yarn",
                    build_script,
                ]

            elif package_manager == "bun":

                build_command = [
                    "bun",
                    "run",
                    build_script,
                ]

            else:

                build_command = [
                    "npm",
                    "run",
                    build_script,
                ]

            build_result = self._run_command(
                build_command,
                cwd=project_path,
                timeout=1200,
            )

            if build_result["returncode"] != 0:

                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "build_error",
                    "message": (
                        f"{language_id} project "
                        f"{build_script} failed."
                    ),
                    "stdout": build_result["stdout"],
                    "stderr": build_result["stderr"],
                    "command": build_result["command"],
                    "language_id": language_id,
                    "build_script": build_script,
                }

            return {
                "status": "SUCCESS",
                "success": True,
                "error_type": None,
                "message": (
                    f"{language_id} project "
                    f"{build_script} completed successfully."
                ),
                "stdout": (
                    install_result["stdout"]
                    + "\n"
                    + build_result["stdout"]
                ),
                "stderr": (
                    install_result["stderr"]
                    + "\n"
                    + build_result["stderr"]
                ),
                "command": build_result["command"],
                "language_id": language_id,
                "build_script": build_script,
            }

        # -----------------------------------------------------
        # No build script
        # -----------------------------------------------------

        if language_id == "typescript":

            tsc_path = shutil.which("tsc")

            if tsc_path:

                tsc_result = self._run_command(
                    [
                        "tsc",
                        "--noEmit",
                    ],
                    cwd=project_path,
                    timeout=600,
                )

                if tsc_result["returncode"] != 0:

                    return {
                        "status": "FAILURE",
                        "success": False,
                        "error_type": "typescript_compile_error",
                        "message": (
                            "TypeScript compilation failed."
                        ),
                        "stdout": tsc_result["stdout"],
                        "stderr": tsc_result["stderr"],
                        "command": tsc_result["command"],
                        "language_id": language_id,
                    }

                return {
                    "status": "SUCCESS",
                    "success": True,
                    "error_type": None,
                    "message": (
                        "TypeScript compilation "
                        "completed successfully."
                    ),
                    "stdout": tsc_result["stdout"],
                    "stderr": tsc_result["stderr"],
                    "command": tsc_result["command"],
                    "language_id": language_id,
                }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                "Dependencies installed successfully. "
                "No build or compile script was found."
            ),
            "stdout": install_result["stdout"],
            "stderr": install_result["stderr"],
            "command": install_result["command"],
            "language_id": language_id,
        }

    # =========================================================
    # PYTHON
    # =========================================================

    def _check_python_compilation(self, project_path=None):

        if project_path is None:
            project_path = self._resolve_project_path()

        project_path = Path(project_path)

        dependency_file = project_path / "requirements.txt"
        if dependency_file.exists():
            install = self._run_command(
                [
                    "python",
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-cache-dir",
                    "-r",
                    str(dependency_file),
                ],
                cwd=project_path,
                timeout=180,
            )
            if install["returncode"] != 0:
                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "python_dependency_error",
                    "message": "Python dependency installation failed.",
                    "stdout": install["stdout"],
                    "stderr": install["stderr"],
                    "command": install["command"],
                }

        python_files = list(
            project_path.rglob("*.py")
        )

        if not python_files:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "no_python_files",
                "message": (
                    "No Python files found."
                ),
                "stdout": "",
                "stderr": "",
                "command": "",
            }

        failures = []

        for python_file in python_files:

            result = self._run_command(
                [
                    "python",
                    "-m",
                    "py_compile",
                    str(python_file),
                ],
                cwd=project_path,
                timeout=120,
            )

            if result["returncode"] != 0:

                failures.append(
                    {
                        "file": str(python_file),
                        "stdout": result["stdout"],
                        "stderr": result["stderr"],
                    }
                )

        if failures:

            combined_stderr = "\n\n".join(
                f"FILE: {item['file']}\n"
                f"{item['stderr']}"
                for item in failures
            )

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "python_syntax_error",
                "message": (
                    f"{len(failures)} Python file(s) "
                    f"failed compilation."
                ),
                "stdout": "",
                "stderr": combined_stderr,
                "command": "python -m py_compile",
                "failures": failures,
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                f"Successfully compiled "
                f"{len(python_files)} Python file(s)."
            ),
            "stdout": "",
            "stderr": "",
            "command": "python -m py_compile",
        }

    # =========================================================
    # JAVA
    # =========================================================

    def _check_java_build(self, project_path=None):

        if project_path is None:
            project_path = self._resolve_project_path()

        project_path = Path(project_path)

        if (project_path / "pom.xml").exists():

            command = [
                "mvn",
                "-B",
                "test",
            ]

        elif (
            (project_path / "build.gradle").exists()
            or
            (project_path / "build.gradle.kts").exists()
        ):

            if (project_path / "gradlew").exists():

                command = [
                    "./gradlew",
                    "build",
                ]

            elif shutil.which("gradle"):

                command = [
                    "gradle",
                    "build",
                ]

            else:

                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "gradle_not_installed",
                    "message": (
                        "Gradle project detected but "
                        "Gradle is not installed."
                    ),
                    "stdout": "",
                    "stderr": "",
                    "command": "",
                }

        else:

            java_files = list(
                project_path.rglob("*.java")
            )

            if not java_files:

                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "no_java_files",
                    "message": (
                        "No Java files found."
                    ),
                    "stdout": "",
                    "stderr": "",
                    "command": "",
                }

            command = [
                "javac"
            ] + [
                str(file)
                for file in java_files
            ]

        result = self._run_command(
            command,
            cwd=project_path,
            timeout=1200,
        )

        if result["returncode"] != 0:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "java_build_error",
                "message": (
                    "Java build/compilation failed."
                ),
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": result["command"],
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                "Java build/compilation succeeded."
            ),
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "command": result["command"],
        }

    # =========================================================
    # KOTLIN
    # =========================================================

    def _check_kotlin_build(self, project_path=None):
        """Build Gradle Kotlin projects or compile standalone Kotlin files."""
        project_path = Path(project_path or self._resolve_project_path())

        if (
            (project_path / "build.gradle").exists()
            or (project_path / "build.gradle.kts").exists()
        ):
            command = (
                ["./gradlew", "build"]
                if (project_path / "gradlew").exists()
                else ["gradle", "build"]
            )
        else:
            kotlin_files = list(project_path.rglob("*.kt"))
            if not kotlin_files:
                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "no_kotlin_files",
                    "message": "No Kotlin source files found.",
                    "stdout": "",
                    "stderr": "",
                    "command": "",
                }
            command = ["kotlinc", *map(str, kotlin_files), "-d", "acr-kotlin-check.jar"]

        result = self._run_command(command, cwd=project_path, timeout=1200)
        output = project_path / "acr-kotlin-check.jar"
        if output.exists():
            try:
                output.unlink()
            except OSError:
                pass

        if result["returncode"] != 0:
            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "kotlin_build_error",
                "message": "Kotlin build/compilation failed.",
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": result["command"],
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": "Kotlin build/compilation succeeded.",
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "command": result["command"],
        }

    # =========================================================
    # C / C++
    # =========================================================

    def _check_c_cpp(
        self,
        project_path,
        language_id,
    ):

        project_path = Path(project_path)

        if (project_path / "Makefile").exists():
            result = self._run_command(
                ["make"],
                cwd=project_path,
                timeout=300,
            )
            if result["returncode"] != 0:
                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": f"{language_id}_make_error",
                    "message": f"{language_id} Makefile build failed.",
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "command": result["command"],
                }
            return {
                "status": "SUCCESS",
                "success": True,
                "error_type": None,
                "message": f"{language_id} Makefile build succeeded.",
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": result["command"],
            }

        if (
            (project_path / "CMakeLists.txt").exists()
        ):

            build_dir = project_path / "build"

            build_dir.mkdir(
                exist_ok=True
            )

            configure = self._run_command(
                [
                    "cmake",
                    "-S",
                    ".",
                    "-B",
                    "build",
                ],
                cwd=project_path,
                timeout=600,
            )

            if configure["returncode"] != 0:

                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "cmake_configuration_error",
                    "message": (
                        "CMake configuration failed."
                    ),
                    "stdout": configure["stdout"],
                    "stderr": configure["stderr"],
                    "command": configure["command"],
                }

            build = self._run_command(
                [
                    "cmake",
                    "--build",
                    "build",
                ],
                cwd=project_path,
                timeout=1200,
            )

            if build["returncode"] != 0:

                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "cpp_build_error",
                    "message": (
                        "C/C++ build failed."
                    ),
                    "stdout": build["stdout"],
                    "stderr": build["stderr"],
                    "command": build["command"],
                }

            return {
                "status": "SUCCESS",
                "success": True,
                "error_type": None,
                "message": (
                    "C/C++ CMake build succeeded."
                ),
                "stdout": build["stdout"],
                "stderr": build["stderr"],
                "command": build["command"],
            }

        source_extensions = (
            {"*.cpp", "*.cc", "*.cxx"}
            if language_id == "cpp"
            else {"*.c"}
        )
        source_files = [
            source_file
            for extension in source_extensions
            for source_file in project_path.rglob(extension)
        ]

        if not source_files:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "no_source_files",
                "message": (
                    f"No {language_id} source files found."
                ),
                "stdout": "",
                "stderr": "",
                "command": "",
            }

        compiler = (
            "g++"
            if language_id == "cpp"
            else "gcc"
        )

        # The worker runs on Linux, while local development may run on
        # Windows.  Use the actual host platform instead of Path().anchor
        # (which is empty on both relative and POSIX paths).
        output_file = project_path / (
            "acr_test_build.exe"
            if os.name == "nt"
            else "acr_test_build"
        )

        command = [
            compiler
        ] + [
            str(file)
            for file in source_files
        ] + [
            "-o",
            str(output_file),
        ]

        result = self._run_command(
            command,
            cwd=project_path,
            timeout=600,
        )

        if result["returncode"] != 0:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": f"{language_id}_compile_error",
                "message": (
                    f"{language_id} compilation failed."
                ),
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": result["command"],
            }

        try:
            if output_file.exists():
                output_file.unlink()
        except Exception:
            pass

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                f"{language_id} compilation succeeded."
            ),
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "command": result["command"],
        }

    # =========================================================
    # GO
    # =========================================================

    def _check_go(self, project_path):

        project_path = Path(project_path)
        go_mod = project_path / "go.mod"
        go_files: list[Path] = []

        if not go_mod.exists():

            go_files = list(
                project_path.rglob("*.go")
            )

            if not go_files:

                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "no_go_files",
                    "message": (
                        "No Go files found."
                    ),
                    "stdout": "",
                    "stderr": "",
                    "command": "",
                }

        command = (
            ["go", "test", "./..."]
            if go_mod.exists()
            else ["go", "build", *map(str, go_files)]
        )

        result = self._run_command(
            command,
            cwd=project_path,
            timeout=1200,
        )

        if result["returncode"] != 0:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "go_build_error",
                "message": (
                    "Go build/test failed."
                ),
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": result["command"],
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                "Go build/test succeeded."
            ),
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "command": result["command"],
        }

    # =========================================================
    # RUST
    # =========================================================

    def _check_rust(self, project_path):

        project_path = Path(project_path)

        if not (project_path / "Cargo.toml").exists():

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "missing_cargo_toml",
                "message": (
                    "Cargo.toml not found."
                ),
                "stdout": "",
                "stderr": "",
                "command": "",
            }

        result = self._run_command(
            [
                "cargo",
                "check",
            ],
            cwd=project_path,
            timeout=1200,
        )

        if result["returncode"] != 0:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "rust_build_error",
                "message": (
                    "Rust cargo check failed."
                ),
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": result["command"],
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                "Rust cargo check succeeded."
            ),
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "command": result["command"],
        }

    # =========================================================
    # PHP
    # =========================================================

    def _check_php(self, project_path):

        project_path = Path(project_path)

        # A missing PHP executable must be reported as an environment
        # problem, not as a syntax error for every source file.  This makes a
        # stale/incomplete worker image immediately actionable (rebuild
        # Dockerfile.worker) instead of sending misleading compiler context
        # to KNN and Gemini.
        if shutil.which("php") is None:
            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "php_toolchain_missing",
                "message": (
                    "PHP CLI is not installed in the worker image. "
                    "Rebuild Dockerfile.worker and run the pipeline again."
                ),
                "stdout": "",
                "stderr": "php executable was not found on PATH.",
                "command": "php -l",
            }

        if (project_path / "composer.json").exists():
            if shutil.which("composer") is None:
                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "composer_toolchain_missing",
                    "message": (
                        "composer.json is present but Composer is not "
                        "installed in the worker image."
                    ),
                    "stdout": "",
                    "stderr": "composer executable was not found on PATH.",
                    "command": "composer install",
                }
            install = self._run_command(
                [
                    "composer",
                    "install",
                    "--no-interaction",
                    "--prefer-dist",
                    "--no-progress",
                ],
                cwd=project_path,
                timeout=180,
            )
            if install["returncode"] != 0:
                return {
                    "status": "FAILURE",
                    "success": False,
                    "error_type": "composer_installation_error",
                    "message": "PHP dependency installation failed.",
                    "stdout": install["stdout"],
                    "stderr": install["stderr"],
                    "command": install["command"],
                }

        php_files = list(
            project_path.rglob("*.php")
        )

        if not php_files:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "no_php_files",
                "message": (
                    "No PHP files found."
                ),
                "stdout": "",
                "stderr": "",
                "command": "",
            }

        failures = []

        for php_file in php_files:

            result = self._run_command(
                [
                    "php",
                    "-l",
                    str(php_file),
                ],
                cwd=project_path,
                timeout=120,
            )

            if result["returncode"] != 0:

                failures.append(
                    {
                        "file": str(php_file),
                        "stderr": result["stderr"],
                    }
                )

        if failures:

            diagnostics = []
            for item in failures:
                diagnostics.append(
                    f"FILE: {item['file']}\n"
                    f"{item.get('stderr', '')}".strip()
                )

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "php_syntax_error",
                "message": (
                    "PHP syntax validation failed."
                ),
                "stdout": "",
                "stderr": "\n\n".join(diagnostics),
                "command": "php -l",
                "failures": failures,
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                "PHP syntax validation succeeded."
            ),
            "stdout": "",
            "stderr": "",
            "command": "php -l",
        }

    # =========================================================
    # C#
    # =========================================================

    def _check_csharp(self, project_path):

        project_path = Path(project_path)

        csproj_files = list(
            project_path.rglob("*.csproj")
        )

        if csproj_files:

            result = self._run_command(
                [
                    "dotnet",
                    "build",
                    str(csproj_files[0]),
                ],
                cwd=project_path,
                timeout=1200,
            )

        else:

            sln_files = list(
                project_path.rglob("*.sln")
            )

            if sln_files:

                result = self._run_command(
                    [
                        "dotnet",
                        "build",
                        str(sln_files[0]),
                    ],
                    cwd=project_path,
                    timeout=1200,
                )

            else:

                cs_files = list(
                    project_path.rglob("*.cs")
                )

                if not cs_files:

                    return {
                        "status": "FAILURE",
                        "success": False,
                        "error_type": "no_csharp_files",
                        "message": (
                            "No C# project or source files found."
                        ),
                        "stdout": "",
                        "stderr": "",
                        "command": "",
                    }

                # A source-only C# repository still needs a real compiler
                # check. Create a disposable SDK project inside the cloned
                # sandbox so source errors cannot be reported as success.
                check_dir = project_path / ".acr-csharp-check"
                output_dir = check_dir / "out"
                try:
                    if check_dir.exists():
                        shutil.rmtree(check_dir)
                    check_dir.mkdir(parents=True)
                    for source_file in cs_files:
                        shutil.copy2(source_file, check_dir / source_file.name)
                    (check_dir / "check.csproj").write_text(
                        "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
                        "  <PropertyGroup>\n"
                        "    <TargetFramework>net8.0</TargetFramework>\n"
                        "    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>\n"
                        "    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>\n"
                        "  </PropertyGroup>\n"
                        "  <ItemGroup><Compile Include=\"*.cs\" /></ItemGroup>\n"
                        "</Project>\n",
                        encoding="utf-8",
                    )
                    result = self._run_command(
                        ["dotnet", "build", "check.csproj", "--nologo", "-o", str(output_dir)],
                        cwd=check_dir,
                        timeout=300,
                    )
                finally:
                    try:
                        if check_dir.exists():
                            shutil.rmtree(check_dir)
                    except OSError:
                        pass

                if result["returncode"] != 0:
                    return {
                        "status": "FAILURE",
                        "success": False,
                        "error_type": "csharp_build_error",
                        "message": "C# source compilation failed.",
                        "stdout": result["stdout"],
                        "stderr": result["stderr"],
                        "command": result["command"],
                    }

                return {
                    "status": "SUCCESS",
                    "success": True,
                    "error_type": None,
                    "message": "C# source compilation succeeded.",
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "command": result["command"],
                }

        if result["returncode"] != 0:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "csharp_build_error",
                "message": (
                    "C#/.NET build failed."
                ),
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "command": result["command"],
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                "C#/.NET build succeeded."
            ),
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "command": result["command"],
        }

    # =========================================================
    # SIMPLE / UNKNOWN PROJECT
    # =========================================================

    def _check_simple_project(
        self,
        project_path,
        language_id,
    ):

        project_path = Path(project_path)

        files = [
            file
            for file in project_path.rglob("*")
            if file.is_file()
        ]

        if not files:

            return {
                "status": "FAILURE",
                "success": False,
                "error_type": "empty_project",
                "message": (
                    "No project files found."
                ),
                "stdout": "",
                "stderr": "",
                "command": "",
                "language_id": language_id,
            }

        return {
            "status": "SUCCESS",
            "success": True,
            "error_type": None,
            "message": (
                f"Project detected as "
                f"{language_id}, but no specific "
                f"build strategy is configured."
            ),
            "stdout": "",
            "stderr": "",
            "command": "",
            "language_id": language_id,
        }

    # =========================================================
    # BACKWARD COMPATIBILITY METHODS
    # =========================================================

    def _check_simple_python(self):
        return self._check_python_compilation(
            self._resolve_project_path()
        )

    def _check_simple_js(self):
        return self._check_js_build(
            project_path=self._resolve_project_path(),
            language_id="javascript",
            package_manager=self._get_package_manager(),
        )

    def _check_simple_ts(self):
        return self._check_js_build(
            project_path=self._resolve_project_path(),
            language_id="typescript",
            package_manager=self._get_package_manager(),
        )

    def _check_simple_java(self):
        return self._check_java_build(
            self._resolve_project_path()
        )
