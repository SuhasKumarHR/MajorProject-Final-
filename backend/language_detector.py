from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# Directories that should not be scanned
IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    "coverage",
}


LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".kt": "kotlin",
    ".kts": "kotlin",
}


LANGUAGE_NAMES = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "java": "Java",
    "c": "C",
    "cpp": "C++",
    "csharp": "C#",
    "go": "Go",
    "rust": "Rust",
    "php": "PHP",
    "kotlin": "Kotlin",
}


def _should_ignore(path: Path) -> bool:
    """
    Returns True if any path component belongs to an ignored directory.
    """
    return any(part in IGNORED_DIRECTORIES for part in path.parts)


def _iter_files(root: Path):
    """
    Safely iterate through project files while ignoring dependency/build folders.
    """
    if not root.exists():
        return

    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)

        # Modify dirs in-place so os.walk does not enter ignored directories.
        dirs[:] = [
            d for d in dirs
            if d not in IGNORED_DIRECTORIES
        ]

        for filename in files:
            path = current_path / filename

            if _should_ignore(path):
                continue

            yield path


def _find_file(root: Path, filename: str) -> Path | None:
    """
    Find a file by exact filename.
    """
    for path in _iter_files(root):
        if path.name.lower() == filename.lower():
            return path

    return None


def _find_extension(root: Path, extension: str) -> Path | None:
    """
    Find the first file matching an extension.
    """
    extension = extension.lower()

    for path in _iter_files(root):
        if path.suffix.lower() == extension:
            return path

    return None


def _has_extension(root: Path, extension: str) -> bool:
    return _find_extension(root, extension) is not None


def _count_languages(root: Path) -> dict[str, int]:
    """
    Count source files by programming language.
    """
    counts: dict[str, int] = {}

    for path in _iter_files(root):
        language = LANGUAGE_EXTENSIONS.get(path.suffix.lower())

        if language:
            counts[language] = counts.get(language, 0) + 1

    return counts


def _detect_framework(root: Path, language_id: str) -> str:
    """
    Detect common frameworks from project configuration files.
    """

    # -------------------------
    # Python
    # -------------------------
    if language_id == "python":
        requirements = _find_file(root, "requirements.txt")

        if requirements:
            try:
                content = requirements.read_text(
                    encoding="utf-8",
                    errors="ignore"
                ).lower()

                if "fastapi" in content:
                    return "FastAPI"

                if "flask" in content:
                    return "Flask"

                if "django" in content:
                    return "Django"

                if "streamlit" in content:
                    return "Streamlit"

            except Exception:
                pass

        pyproject = _find_file(root, "pyproject.toml")

        if pyproject:
            try:
                content = pyproject.read_text(
                    encoding="utf-8",
                    errors="ignore"
                ).lower()

                if "fastapi" in content:
                    return "FastAPI"

                if "django" in content:
                    return "Django"

                if "flask" in content:
                    return "Flask"

            except Exception:
                pass

        return "Python"

    # -------------------------
    # JavaScript / TypeScript
    # -------------------------
    if language_id in {"javascript", "typescript"}:
        package_json = _find_file(root, "package.json")

        if package_json:
            try:
                content = package_json.read_text(
                    encoding="utf-8",
                    errors="ignore"
                ).lower()

                if '"next"' in content:
                    return "Next.js"

                if '"@nestjs/core"' in content or '"nestjs"' in content:
                    return "NestJS"

                if '"express"' in content:
                    return "Express"

                if '"react"' in content:
                    return "React"

                if '"vue"' in content:
                    return "Vue"

                if '"angular"' in content or '"@angular/core"' in content:
                    return "Angular"

            except Exception:
                pass

        if language_id == "typescript":
            return "TypeScript"

        return "JavaScript"

    # -------------------------
    # Java
    # -------------------------
    if language_id == "java":
        pom = _find_file(root, "pom.xml")

        if pom:
            try:
                content = pom.read_text(
                    encoding="utf-8",
                    errors="ignore"
                ).lower()

                if "spring-boot" in content:
                    return "Spring Boot"

                if "springframework" in content:
                    return "Spring"

                if "quarkus" in content:
                    return "Quarkus"

            except Exception:
                pass

        return "Java"

    # -------------------------
    # C#
    # -------------------------
    if language_id == "csharp":
        for path in _iter_files(root):
            if path.suffix.lower() in {".csproj", ".sln"}:
                try:
                    content = path.read_text(
                        encoding="utf-8",
                        errors="ignore"
                    ).lower()

                    if "microsoft.aspnetcore" in content:
                        return "ASP.NET Core"

                except Exception:
                    pass

        return "C#"

    # -------------------------
    # Go
    # -------------------------
    if language_id == "go":
        return "Go"

    # -------------------------
    # Rust
    # -------------------------
    if language_id == "rust":
        return "Rust"

    # -------------------------
    # PHP
    # -------------------------
    if language_id == "php":
        composer = _find_file(root, "composer.json")

        if composer:
            try:
                content = composer.read_text(
                    encoding="utf-8",
                    errors="ignore"
                ).lower()

                if "laravel" in content:
                    return "Laravel"

                if "symfony" in content:
                    return "Symfony"

            except Exception:
                pass

        return "PHP"

    # -------------------------
    # Kotlin
    # -------------------------
    if language_id == "kotlin":
        return "Kotlin"

    # -------------------------
    # C / C++
    # -------------------------
    if language_id == "cpp":
        return "C++"

    if language_id == "c":
        return "C"

    return LANGUAGE_NAMES.get(language_id, "Unknown")


def _detect_package_manager(root: Path, language_id: str) -> str:
    """
    Detect package/dependency manager.
    """

    if language_id == "python":
        if _find_file(root, "poetry.lock"):
            return "Poetry"

        if _find_file(root, "Pipfile"):
            return "Pipenv"

        if _find_file(root, "requirements.txt"):
            return "pip"

        if _find_file(root, "pyproject.toml"):
            return "pip"

        return "pip"

    if language_id in {"javascript", "typescript"}:
        if _find_file(root, "bun.lockb") or _find_file(root, "bun.lock"):
            return "bun"

        if _find_file(root, "pnpm-lock.yaml"):
            return "pnpm"

        if _find_file(root, "yarn.lock"):
            return "yarn"

        if _find_file(root, "package-lock.json"):
            return "npm"

        if _find_file(root, "package.json"):
            return "npm"

        return "npm"

    if language_id == "java":
        if _find_file(root, "pom.xml"):
            return "Maven"

        if (
            _find_file(root, "build.gradle")
            or _find_file(root, "build.gradle.kts")
            or _find_file(root, "gradlew")
        ):
            return "Gradle"

        return "None"

    if language_id == "csharp":
        if _find_extension(root, ".sln"):
            return "dotnet"

        if _find_extension(root, ".csproj"):
            return "dotnet"

        return "dotnet"

    if language_id == "go":
        if _find_file(root, "go.mod"):
            return "Go Modules"

        return "Go"

    if language_id == "rust":
        if _find_file(root, "Cargo.toml"):
            return "Cargo"

        return "Cargo"

    if language_id == "php":
        if _find_file(root, "composer.json"):
            return "Composer"

        return "None"

    if language_id == "kotlin":
        if (
            _find_file(root, "build.gradle")
            or _find_file(root, "build.gradle.kts")
            or _find_file(root, "gradlew")
        ):
            return "Gradle"

        return "Kotlin"

    return "None"


def _detect_build_system(root: Path, language_id: str) -> str:
    """
    Detect how the project is built/tested.
    """

    if language_id == "python":
        if _find_file(root, "pyproject.toml"):
            return "Python/pyproject"

        if _find_file(root, "setup.py"):
            return "setuptools"

        return "Python"

    if language_id in {"javascript", "typescript"}:
        if _find_file(root, "package.json"):
            return "npm scripts"

        return "Node.js"

    if language_id == "java":
        if _find_file(root, "pom.xml"):
            return "Maven"

        if (
            _find_file(root, "build.gradle")
            or _find_file(root, "build.gradle.kts")
            or _find_file(root, "gradlew")
        ):
            return "Gradle"

        return "javac"

    if language_id in {"c", "cpp"}:
        if _find_file(root, "CMakeLists.txt"):
            return "CMake"

        if _find_file(root, "Makefile"):
            return "Make"

        return "GCC/G++"

    if language_id == "csharp":
        if _find_extension(root, ".sln"):
            return "dotnet"

        if _find_extension(root, ".csproj"):
            return "dotnet"

        return "dotnet"

    if language_id == "go":
        return "Go"

    if language_id == "rust":
        return "Cargo"

    if language_id == "php":
        return "PHP"

    if language_id == "kotlin":
        if (
            _find_file(root, "build.gradle")
            or _find_file(root, "build.gradle.kts")
            or _find_file(root, "gradlew")
        ):
            return "Gradle"

        return "kotlinc"

    return "Unknown"


def _find_project_path(root: Path, language_id: str) -> str:
    """
    Find the most likely project directory.

    For Node/TypeScript projects, a package.json may exist in a
    frontend/backend subdirectory.
    """

    if language_id in {"javascript", "typescript"}:
        package_json = _find_file(root, "package.json")

        if package_json:
            return str(package_json.parent)

    if language_id == "python":
        requirements = _find_file(root, "requirements.txt")

        if requirements:
            return str(requirements.parent)

        pyproject = _find_file(root, "pyproject.toml")

        if pyproject:
            return str(pyproject.parent)

    if language_id == "java":
        pom = _find_file(root, "pom.xml")

        if pom:
            return str(pom.parent)

        gradle = _find_file(root, "build.gradle")

        if gradle:
            return str(gradle.parent)

        gradle_kts = _find_file(root, "build.gradle.kts")

        if gradle_kts:
            return str(gradle_kts.parent)

    marker_names = {
        "go": ("go.mod",),
        "rust": ("Cargo.toml",),
        "php": ("composer.json",),
        "kotlin": ("build.gradle", "build.gradle.kts", "gradlew"),
        "c": ("CMakeLists.txt", "Makefile"),
        "cpp": ("CMakeLists.txt", "Makefile"),
    }
    for marker_name in marker_names.get(language_id, ()):
        marker = _find_file(root, marker_name)
        if marker:
            return str(marker.parent)

    if language_id == "csharp":
        project = _find_extension(root, ".csproj") or _find_extension(root, ".sln")
        if project:
            return str(project.parent)

    if language_id in {"c", "cpp", "kotlin"}:
        extension = {"c": ".c", "cpp": ".cpp", "kotlin": ".kt"}[language_id]
        source = _find_extension(root, extension)
        if source:
            return str(source.parent)

    return str(root)


def detect_project_language(project_path: str) -> str:
    """
    Backward-compatible function.

    Returns only the detected language name.
    """

    details = detect_project_details(project_path)

    return details["language"]


def detect_project_details(project_path: str) -> dict[str, Any]:
    """
    Main project detector.

    Returns:
        {
            "language_id": "...",
            "language": "...",
            "framework": "...",
            "package_manager": "...",
            "build_system": "...",
            "project_path": "...",
            "confidence": 0.0
        }
    """

    root = Path(project_path).resolve()

    if not root.exists():
        return {
            "language_id": "unknown",
            "language": "Unknown",
            "framework": "Unknown",
            "package_manager": "None",
            "build_system": "Unknown",
            "project_path": str(root),
            "confidence": 0.0,
        }

    counts = _count_languages(root)

    # Strong project markers take priority over raw file counts.
    package_json = _find_file(root, "package.json")
    if package_json is not None:

        try:
            content = package_json.read_text(
                encoding="utf-8",
                errors="ignore"
            ).lower()

            if (
                '"typescript"' in content
                or _has_extension(root, ".ts")
                or _has_extension(root, ".tsx")
            ):
                language_id = "typescript"
            else:
                language_id = "javascript"

        except Exception:
            language_id = (
                "typescript"
                if _has_extension(root, ".ts")
                else "javascript"
            )

    elif _find_file(root, "pom.xml"):
        language_id = "java"

    elif (
        _find_file(root, "Cargo.toml")
        or _has_extension(root, ".rs")
    ):
        language_id = "rust"

    elif _find_file(root, "go.mod"):
        language_id = "go"

    elif (
        _find_extension(root, ".csproj")
        or _find_extension(root, ".sln")
    ):
        language_id = "csharp"

    elif _find_file(root, "composer.json"):
        language_id = "php"

    elif (
        _find_file(root, "build.gradle")
        or _find_file(root, "build.gradle.kts")
        or _find_file(root, "gradlew")
    ):
        if _has_extension(root, ".kt") or _has_extension(root, ".kts"):
            language_id = "kotlin"
        elif _has_extension(root, ".java"):
            language_id = "java"
        else:
            language_id = "kotlin"

    elif _find_file(root, "requirements.txt") or _find_file(root, "pyproject.toml"):
        language_id = "python"

    elif counts:
        # ``counts`` is non-empty here. Indexing makes the value type explicit
        # for both Python and static analyzers.
        language_id = max(counts, key=lambda language: counts[language])

    else:
        language_id = "unknown"

    total_source_files = sum(counts.values())

    if total_source_files > 0:
        language_files = counts.get(language_id, 0)

        confidence = round(
            language_files / total_source_files,
            2
        )
    else:
        confidence = 0.0

    # Strong project markers get a minimum confidence.
    marker_languages = {
        "typescript": _find_file(root, "package.json"),
        "javascript": _find_file(root, "package.json"),
        "java": _find_file(root, "pom.xml"),
        "rust": _find_file(root, "Cargo.toml"),
        "go": _find_file(root, "go.mod"),
        "csharp": (
            _find_extension(root, ".csproj")
            or _find_extension(root, ".sln")
        ),
        "php": _find_file(root, "composer.json"),
        "python": (
            _find_file(root, "requirements.txt")
            or _find_file(root, "pyproject.toml")
        ),
        "kotlin": (
            _find_file(root, "build.gradle")
            or _find_file(root, "build.gradle.kts")
            or _find_file(root, "gradlew")
        ),
    }

    if marker_languages.get(language_id):
        confidence = max(confidence, 0.85)

    language = LANGUAGE_NAMES.get(
        language_id,
        "Unknown"
    )

    framework = _detect_framework(
        root,
        language_id
    )

    package_manager = _detect_package_manager(
        root,
        language_id
    )

    build_system = _detect_build_system(
        root,
        language_id
    )

    project_dir = _find_project_path(
        root,
        language_id
    )

    return {
        "language_id": language_id,
        "language": language,
        "framework": framework,
        "package_manager": package_manager,
        "build_system": build_system,
        "project_path": project_dir,
        "confidence": confidence,
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Detect project language and build environment."
    )

    parser.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project directory"
    )

    args = parser.parse_args()

    result = detect_project_details(
        args.project_path
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )
