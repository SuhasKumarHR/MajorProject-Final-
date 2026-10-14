"""
ACR_AGENT Worker Entrypoint

Runs inside the Docker worker container.

Pipeline:

    Stage 1 -> Repository Preparation
    Stage 2 -> Project Analysis
    Stage 3 -> KNN Failure Classification + AI Healing
    Stage 4 -> Git Branch / Commit / Pull Request

The final line printed to stdout is ALWAYS a JSON result.
This is required by container_manager.py.
"""

from __future__ import annotations

import json
import os
import sys
import time
import hashlib
from pathlib import Path
from typing import Any, NoReturn

from analysis_agent import AnalysisAgent
from failure_classifier import FailureClassifier
from git_agent import GitAgent
from healing_agent import HealingAgent
from repo_prep_agent import RepoPrepAgent


def _read_positive_int(
    value: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Safely parse a bounded integer before module configuration is read."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(number, maximum))


# ============================================================
# CONFIGURATION
# ============================================================

MAX_RETRIES = _read_positive_int(
    os.getenv("MAX_RETRIES", "5"),
    default=5,
    minimum=1,
    maximum=50,
)

PIPELINE_TIME_LIMIT_SECONDS = _read_positive_int(
    os.getenv("PIPELINE_TIME_LIMIT_SECONDS", "270"),
    default=270,
    minimum=60,
    maximum=300,
)


# ============================================================
# MAIN PIPELINE
# ============================================================

def main() -> None:
    """
    Execute the complete ACR_AGENT worker pipeline.
    """

    start_time = time.time()
    deadline = start_time + PIPELINE_TIME_LIMIT_SECONDS

    # --------------------------------------------------------
    # Read environment variables.
    # --------------------------------------------------------

    repo_url = os.getenv(
        "REPO_URL",
        "",
    ).strip()

    team_name = os.getenv(
        "TEAM_NAME",
        "",
    ).strip()

    leader_name = os.getenv(
        "LEADER_NAME",
        "",
    ).strip()

    language_hint = os.getenv(
        "LANGUAGE_HINT",
        "auto",
    ).strip().lower() or "auto"

    gemini_api_key = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    github_token = os.getenv(
        "GITHUB_TOKEN",
        "",
    ).strip()

    # --------------------------------------------------------
    # Print configuration without exposing secrets.
    # --------------------------------------------------------

    print("\n" + "=" * 80)
    print("ACR_AGENT - AUTONOMOUS CI/CD HEALING WORKER")
    print("=" * 80)

    print(
        f"[CONFIG] Repository : "
        f"{repo_url or 'NOT SET'}"
    )

    print(
        f"[CONFIG] Team       : "
        f"{team_name or 'NOT SET'}"
    )

    print(
        f"[CONFIG] Leader     : "
        f"{leader_name or 'NOT SET'}"
    )

    print(
        f"[CONFIG] Language   : "
        f"{language_hint}"
    )

    print(
        f"[CONFIG] Max Retries: "
        f"{MAX_RETRIES}"
    )

    print(
        f"[CONFIG] Time Limit : "
        f"{PIPELINE_TIME_LIMIT_SECONDS} seconds"
    )

    print(
        f"[CONFIG] Gemini Key : "
        f"{'SET' if gemini_api_key else 'NOT SET'}"
    )

    print(
        f"[CONFIG] GitHub Token: "
        f"{'SET' if github_token else 'NOT SET'}"
    )

    # --------------------------------------------------------
    # Validate required environment variables.
    # --------------------------------------------------------

    missing = []

    if not repo_url:
        missing.append("REPO_URL")

    if not team_name:
        missing.append("TEAM_NAME")

    if not leader_name:
        missing.append("LEADER_NAME")

    if missing:
        _fail(
            "Missing required environment variables: "
            + ", ".join(missing)
        )

    if not gemini_api_key:
        _fail(
            "GEMINI_API_KEY is not set."
        )

    if not github_token:
        _fail(
            "GITHUB_TOKEN is not set."
        )

    # ========================================================
    # STAGE 1 - REPOSITORY PREPARATION
    # ========================================================

    print("\n")
    print("#" * 80)
    print("# STAGE 1 - REPOSITORY PREPARATION")
    print("#" * 80)

    prep_result: dict[str, Any] = {}
    try:
        prep_agent = RepoPrepAgent(
            repo_url=repo_url,
            team_name=team_name,
            leader_name=leader_name,
            language_hint=language_hint,
        )

        prep_result = prep_agent.execute()

    except Exception as exc:
        _fail(
            f"Stage 1 initialization failed: {exc}"
        )

    if not isinstance(prep_result, dict):
        _fail(
            "Stage 1 returned an invalid result."
        )

    if prep_result.get("status") != "SUCCESS":
        _fail(
            "Stage 1 (Repository Preparation) failed: "
            + str(
                prep_result.get(
                    "error",
                    "Unknown preparation error.",
                )
            )
        )

    repo_path = PathLikeString(
        prep_result.get(
            "repo_path",
            "",
        )
    )

    raw_environment = prep_result.get(
        "environment",
        {},
    )

    target_branch = str(
        prep_result.get(
            "branch_name",
            "",
        )
    ).strip()

    if not repo_path:
        _fail(
            "Stage 1 succeeded but did not return repo_path."
        )

    if not target_branch:
        _fail(
            "Stage 1 succeeded but did not return branch_name."
        )

    if not isinstance(raw_environment, dict):
        _fail(
            "Stage 1 returned invalid environment metadata."
        )
    environment: dict[str, Any] = raw_environment

    print(
        "\n[SUCCESS] Stage 1 completed."
    )

    print(
        f"[INFO] Repository path: {repo_path}"
    )

    print(
        f"[INFO] Branch target: {target_branch}"
    )

    print(
        "[INFO] Environment metadata:"
    )

    print(
        json.dumps(
            environment,
            indent=2,
        )
    )

    # ========================================================
    # INITIALIZE KNN CLASSIFIER
    # ========================================================

    print("\n")
    print("#" * 80)
    print("# KNN FAILURE CLASSIFIER INITIALIZATION")
    print("#" * 80)

    classifier: FailureClassifier | None = None
    try:
        classifier = FailureClassifier(
            n_neighbors=3
        )

        print(
            "[SUCCESS] KNN Failure Classifier initialized."
        )

    except Exception as exc:
        _fail(
            f"KNN classifier initialization failed: {exc}"
        )

    if classifier is None:
        _fail("KNN classifier initialization did not return a classifier.")

    # ========================================================
    # STAGE 2 + STAGE 3 - ANALYSIS / HEALING LOOP
    # ========================================================

    print("\n")
    print("#" * 80)
    print("# STAGE 2 + STAGE 3 - ANALYSIS / AI HEALING LOOP")
    print("#" * 80)

    iteration = 0
    total_failures = 0

    all_fixes: list[dict[str, Any]] = []

    # Fixes remain pending until the next analysis succeeds. This prevents an
    # unverified Gemini patch from being committed or included in final output.
    pending_fixes: list[dict[str, Any]] = []
    rejected_fix_signatures: set[str] = set()
    rollback_events: list[dict[str, Any]] = []

    failure_history: list[dict[str, Any]] = []

    final_success = False

    last_error = None

    last_analysis_result: dict[str, Any] = {}
    last_knn_result: dict[str, Any] = {}
    last_healing_result: dict[str, Any] = {}

    # --------------------------------------------------------
    # Retry loop.
    # --------------------------------------------------------

    while iteration < MAX_RETRIES:

        if time.time() >= deadline:
            last_error = (
                f"Pipeline time limit reached ({PIPELINE_TIME_LIMIT_SECONDS} seconds)."
            )
            break

        iteration += 1

        print("\n")
        print("=" * 80)
        print(
            f"ITERATION {iteration} / {MAX_RETRIES}"
        )
        print("=" * 80)

        # ----------------------------------------------------
        # STAGE 2 - Analysis
        # ----------------------------------------------------

        print(
            "\n[STAGE 2] Running project analysis..."
        )

        try:
            analysis_agent = AnalysisAgent(
                repo_path=repo_path,
                environment=environment,
                deadline=deadline,
            )

            analysis_result = (
                analysis_agent.execute()
            )

        except Exception as exc:
            analysis_result = {
                "status": "FAILED",
                "language": environment.get(
                    "language",
                    "Unknown",
                ),
                "language_id": environment.get(
                    "language_id",
                    "unknown",
                ),
                "framework": environment.get(
                    "framework",
                    "Unknown",
                ),
                "package_manager": environment.get(
                    "package_manager"
                ),
                "build_system": environment.get(
                    "build_system"
                ),
                "project_path": environment.get(
                    "project_path",
                    repo_path,
                ),
                "command": [],
                "stdout": "",
                "stderr": "",
                "error": (
                    "AnalysisAgent exception: "
                    f"{exc}"
                ),
                "returncode": 1,
            }

        last_analysis_result = analysis_result

        if time.time() >= deadline:
            last_error = (
                f"Pipeline time limit reached ({PIPELINE_TIME_LIMIT_SECONDS} seconds) during analysis."
            )
            break

        # ----------------------------------------------------
        # Analysis succeeded.
        # ----------------------------------------------------

        if str(analysis_result.get("status", "")).upper() in {
            "SUCCESS",
            "PASSED",
        }:

            print(
                "\n[SUCCESS] Project analysis PASSED."
            )

            if pending_fixes:
                all_fixes.extend(pending_fixes)
                _discard_backups(repo_path, pending_fixes)
                print("[SUCCESS] Pending AI patch passed fresh verification.")
            else:
                print("[SUCCESS] No healing is required.")

            final_success = True

            break

        # ----------------------------------------------------
        # Analysis failed.
        # ----------------------------------------------------

        total_failures += 1

        # A prior patch has just failed its required rebuild/retest. Preserve
        # that output for the next Gemini request, then restore every file
        # from its recovery backup before another attempt is allowed.
        if pending_fixes:
            verification_context = _build_error_text(analysis_result)
            rollback = _rollback_fixes(repo_path, pending_fixes)
            rejected_fix_signatures.update(
                _fix_signature(fix) for fix in pending_fixes
            )
            rollback_events.append({
                "iteration": iteration,
                "restored_files": rollback["restored_files"],
                "status": rollback["status"],
                "verification_context": verification_context,
            })
            analysis_result["stderr"] = (
                str(analysis_result.get("stderr", ""))
                + "\n[ACR_AGENT] Previous patch failed verification and was rolled back. "
                + "Restored files: "
                + ", ".join(rollback["restored_files"])
            ).strip()
            pending_fixes = []

        print(
            "\n[ERROR] Project analysis FAILED."
        )

        # ----------------------------------------------------
        # Build combined error text.
        #
        # KNN uses this text to classify the failure.
        # ----------------------------------------------------

        error_text = _build_error_text(
            analysis_result
        )

        if not error_text.strip():
            error_text = (
                "Unknown build or analysis failure."
            )

        # Keep failure history for final reporting.
        failure_history.append(
            {
                "iteration": iteration,
                "error": error_text,
                "command": analysis_result.get(
                    "command",
                    [],
                ),
            }
        )

        # ----------------------------------------------------
        # STAGE 3A - KNN CLASSIFICATION
        # ----------------------------------------------------

        print(
            "\n[STAGE 3A] KNN failure classification..."
        )

        try:
            classification = (
                classifier.classify_with_confidence(
                    error_text
                )
            )

            failure_category = str(
                classification.get(
                    "category",
                    "UNKNOWN",
                )
            )

            failure_confidence = float(
                classification.get(
                    "confidence",
                    0.0,
                )
            )

            print(
                f"[KNN] Category   : "
                f"{failure_category}"
            )

            print(
                f"[KNN] Confidence : "
                f"{failure_confidence:.3f}"
            )

        except Exception as exc:

            print(
                f"[WARN] KNN classification failed: "
                f"{exc}"
            )

            failure_category = "UNKNOWN"
            failure_confidence = 0.0

        last_knn_result = {
            "category": failure_category,
            "confidence": failure_confidence,
        }

        # ----------------------------------------------------
        # STAGE 3B - AI HEALING
        # ----------------------------------------------------

        print(
            "\n[STAGE 3B] Starting AI healing..."
        )

        if time.time() >= deadline:
            last_error = (
                f"Pipeline time limit reached ({PIPELINE_TIME_LIMIT_SECONDS} seconds) before AI healing."
            )
            break

        try:
            healing_agent = HealingAgent(
                repo_path=repo_path,
                analysis_result=analysis_result,
            )

            heal_result = healing_agent.execute(
                failure_category=failure_category,
                failure_confidence=failure_confidence,
            )

        except Exception as exc:

            heal_result = {
                "status": "FAILED",
                "error": (
                    "HealingAgent exception: "
                    f"{exc}"
                ),
                "fixes": [],
            }

        last_healing_result = heal_result

        # ----------------------------------------------------
        # Healing succeeded.
        # ----------------------------------------------------

        if heal_result.get("status") == "SUCCESS":

            new_fixes = heal_result.get(
                "fixes",
                [],
            )

            if not isinstance(
                new_fixes,
                list,
            ):
                new_fixes = []

            new_fixes = [
                fix for fix in new_fixes
                if _fix_signature(fix) not in rejected_fix_signatures
            ]

            print(
                "\n[SUCCESS] AI healing completed."
            )

            print(
                f"[SUCCESS] Fixes returned: "
                f"{len(new_fixes)}"
            )

            # ------------------------------------------------
            # If no actual fixes were generated, continuing
            # retries would just repeat the same failure.
            # ------------------------------------------------

            if not new_fixes:

                last_error = (
                    "AI healing completed but "
                    "returned no fixes."
                )

                print(
                    f"[ERROR] {last_error}"
                )

                break

            # Keep the patch outside all_fixes until a fresh AnalysisAgent
            # run passes. This is the verification gate before Git actions.
            pending_fixes = new_fixes

            # Continue loop so AnalysisAgent verifies the generated fix.

            continue

        # ----------------------------------------------------
        # Healing failed.
        # ----------------------------------------------------

        last_error = str(
            heal_result.get(
                "error",
                "AI healing failed.",
            )
        )

        print(
            "\n[ERROR] AI healing FAILED."
        )

        print(
            f"[ERROR] {last_error}"
        )

        break

    # ========================================================
    # RETRY LIMIT RESULT
    # ========================================================

    if pending_fixes:
        rollback = _rollback_fixes(repo_path, pending_fixes)
        rollback_events.append({
            "iteration": iteration,
            "restored_files": rollback["restored_files"],
            "status": rollback["status"],
            "verification_context": "Retry limit reached before patch verification.",
        })
        pending_fixes = []

    if not final_success:

        if (
            iteration >= MAX_RETRIES
            and not last_error
        ):
            last_error = (
                f"Maximum retry limit reached "
                f"({MAX_RETRIES})."
            )

        if not last_error:
            last_error = (
                "Pipeline failed during analysis "
                "or healing."
            )

    # ========================================================
    # STAGE 4 - GIT OPERATIONS
    # ========================================================

    pr_link = "N/A"
    commit_hash = None
    git_status = "SKIPPED"
    git_error = None

    # --------------------------------------------------------
    # Only perform Git operations when:
    #
    # 1. Final analysis passed.
    # 2. At least one fix was applied.
    #
    # If the original project was already healthy and no
    # changes were needed, GitAgent is skipped.
    # --------------------------------------------------------

    if final_success and all_fixes:

        print("\n")
        print("#" * 80)
        print("# STAGE 4 - GIT OPERATIONS")
        print("#" * 80)

        try:

            git_agent = GitAgent(
                repo_path=repo_path,
                repo_url=repo_url,
                branch_name=target_branch,
                team_name=team_name,
                leader_name=leader_name,
            )

            git_result = git_agent.execute(
                fixes=all_fixes
            )

            if git_result.get("status") == "SUCCESS":

                git_status = "SUCCESS"

                pr_url = git_result.get(
                    "pr_url"
                )

                if pr_url:
                    pr_link = str(
                        pr_url
                    )

                commit_hash = git_result.get(
                    "commit_hash"
                )

                print(
                    "\n[SUCCESS] Git operations completed."
                )

                if pr_link != "N/A":
                    print(
                        f"[SUCCESS] Pull Request: "
                        f"{pr_link}"
                    )

            else:

                git_status = "FAILED"

                git_error = str(
                    git_result.get(
                        "error",
                        "Git operations failed.",
                    )
                )

                git_error = "Stage 4 (Git) failed: " + git_error
                last_error = git_error
                print(f"[WARN] {git_error}")

        except Exception as exc:

            git_status = "FAILED"

            git_error = "Stage 4 (Git) exception: " + str(exc)
            last_error = git_error
            print(f"[WARN] {git_error}")

    elif final_success and not all_fixes:

        print("\n")
        print(
            "[INFO] Stage 4 skipped."
        )

        print(
            "[INFO] No fixes were applied, so there "
            "are no changes to commit."
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    elapsed_seconds = (
        time.time() - start_time
    )

    elapsed_minutes = (
        elapsed_seconds / 60
    )

    pipeline_status = (
            "SUCCESS"
            if final_success and git_status != "FAILED"
            else "RECOVERED_GIT_BLOCKED"
            if final_success and git_status == "FAILED"
            else "FAILED"
        )
    verified = final_success
    changed_files = sorted({
        str(fix.get("file_path", ""))
        for fix in all_fixes
        if isinstance(fix, dict) and fix.get("file_path")
    })
    result = {
        "status": pipeline_status,
        "final_status": pipeline_status,
        "repository": repo_url,
        "repository_branch": "main",
        "environment": environment,
        "language_selection": {
            "requested": environment.get("requested_language", "auto"),
            "detected": environment.get("language_id", "unknown"),
            "matches": environment.get("language_match", False),
        },
        "total_time_minutes": round(
            elapsed_minutes,
            2,
        ),
        "total_time_seconds": round(elapsed_seconds, 1),
        "time_limit_seconds": PIPELINE_TIME_LIMIT_SECONDS,
        "fixes_applied": len(
            all_fixes
        ),
        "branch": target_branch,
        "pr_link": pr_link,
        "commit_hash": commit_hash,
        "git_status": git_status,
        "git_error": git_error,
        "speed_bonus_eligible": (
            final_success
            and elapsed_minutes < 5
        ),
        "fixes": all_fixes,
        "iterations_used": iteration,
        "max_retries": MAX_RETRIES,
        "total_failures": total_failures,
        "healing_attempt": iteration,
        "failure_history": failure_history,
        "rollback_events": rollback_events,
        "rollback": (
            rollback_events[-1]
            if rollback_events
            else {"status": "NOT_NEEDED", "restored_files": []}
        ),
        "last_analysis": last_analysis_result,
        "verification": {
            "status": "SUCCESS" if verified else "FAILED",
            "passed": verified,
            "message": (
                "Fresh build/test verification passed."
                if verified
                else "Build/test verification did not pass."
            ),
        },
        "knn": last_knn_result,
        "gemini_diagnosis": (
            last_healing_result.get("diagnosis")
            or last_healing_result.get("message")
            or "; ".join(
                str(fix.get("description", ""))
                for fix in all_fixes
                if isinstance(fix, dict) and fix.get("description")
            )
            or None
        ),
        "files_changed": changed_files,
        "project": {
            "language_id": environment.get(
                "language_id",
                "unknown",
            ),
            "language": environment.get(
                "language",
                "Unknown",
            ),
            "framework": environment.get(
                "framework",
                "Unknown",
            ),
            "package_manager": environment.get(
                "package_manager"
            ),
            "build_system": environment.get(
                "build_system"
            ),
            "project_path": environment.get(
                "project_path",
                repo_path,
            ),
        },
    }

    if not final_success or git_status == "FAILED":
        result["error"] = (
            last_error
            or "GitHub publishing failed after verification."
        )

    # --------------------------------------------------------
    # Print human-readable summary.
    # --------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("ACR_AGENT - FINAL PIPELINE RESULT")
    print("=" * 80)

    print(
        f"[RESULT] Status          : "
        f"{result['status']}"
    )

    print(
        f"[RESULT] Iterations      : "
        f"{result['iterations_used']}"
    )

    print(
        f"[RESULT] Failures        : "
        f"{result['total_failures']}"
    )

    print(
        f"[RESULT] Fixes Applied   : "
        f"{result['fixes_applied']}"
    )

    print(
        f"[RESULT] Branch          : "
        f"{result['branch']}"
    )

    print(
        f"[RESULT] Git Status      : "
        f"{result['git_status']}"
    )

    print(
        f"[RESULT] Pull Request    : "
        f"{result['pr_link']}"
    )

    print(
        f"[RESULT] Time            : "
        f"{result['total_time_minutes']} minutes"
    )

    if result["status"] == "FAILED":
        print(
            f"[RESULT] Error           : "
            f"{result['error']}"
        )

    # ========================================================
    # CRITICAL:
    #
    # container_manager.py reads the LAST stdout line and
    # parses it using json.loads().
    #
    # Therefore this must remain ONE valid JSON line.
    # ========================================================

    print(
        json.dumps(
            result,
            ensure_ascii=False,
        )
    )

    # --------------------------------------------------------
    # Normal process exit.
    #
    # Even a pipeline failure is represented by:
    #
    #     {"status": "FAILED", ...}
    #
    # in the final JSON.
    #
    # container_manager.py can therefore parse the result.
    # --------------------------------------------------------

    sys.exit(0)


def PathLikeString(
    value: Any,
) -> str:
    """
    Convert a repository path value to a clean string.

    This helper intentionally returns a string because all
    downstream agents accept filesystem paths as strings.
    """

    if value is None:
        return ""

    return str(value).strip()


def _build_error_text(
    analysis_result: dict[str, Any],
) -> str:
    """
    Combine all relevant analysis output.

    KNN and HealingAgent both need the actual build error,
    including stderr, stdout and the high-level error.
    """

    parts = []

    error = analysis_result.get(
        "error",
        "",
    )

    stderr = analysis_result.get(
        "stderr",
        "",
    )

    stdout = analysis_result.get(
        "stdout",
        "",
    )

    command = analysis_result.get(
        "command",
        [],
    )

    if error:
        parts.append(
            "ANALYSIS ERROR:\n"
            + str(error)
        )

    if command:
        if isinstance(
            command,
            (list, tuple),
        ):
            command_text = " ".join(
                str(item)
                for item in command
            )
        else:
            command_text = str(
                command
            )

        parts.append(
            "COMMAND:\n"
            + command_text
        )

    if stderr:
        parts.append(
            "STDERR:\n"
            + str(stderr)
        )

    if stdout:
        parts.append(
            "STDOUT:\n"
            + str(stdout)
        )

    return "\n\n".join(
        parts
    ).strip()


def _fix_signature(fix: Any) -> str:
    """Create a stable identity so a rejected patch is not retried unchanged."""
    if not isinstance(fix, dict):
        return "invalid-fix"
    value = (
        str(fix.get("file_path", ""))
        + "\0"
        + str(fix.get("fixed_code", ""))
    )
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _safe_fix_target(repo_path: str, fix: dict[str, Any]) -> Path | None:
    """Resolve a repair path only when it remains inside the cloned repo."""
    raw_path = str(fix.get("file_path", "")).replace("\\", "/").lstrip("./")
    if not raw_path:
        return None
    repo_root = Path(repo_path).resolve()
    target = (repo_root / raw_path).resolve()
    try:
        target.relative_to(repo_root)
    except ValueError:
        return None
    return target


def _rollback_fixes(repo_path: str, fixes: list[dict[str, Any]]) -> dict[str, Any]:
    """Restore on-disk backups for a failed healing attempt, inside the repo only."""
    restored_files: list[str] = []
    failures: list[str] = []
    for fix in reversed(fixes):
        target = _safe_fix_target(repo_path, fix)
        if target is None:
            failures.append(str(fix.get("file_path", "unknown")))
            continue
        backup = target.with_suffix(target.suffix + ".acr_backup")
        if not backup.is_file():
            failures.append(target.relative_to(Path(repo_path).resolve()).as_posix())
            continue
        try:
            target.write_bytes(backup.read_bytes())
            backup.unlink()
            restored_files.append(target.relative_to(Path(repo_path).resolve()).as_posix())
        except OSError:
            failures.append(target.relative_to(Path(repo_path).resolve()).as_posix())
    return {
        "status": "SUCCESS" if not failures else "PARTIAL",
        "restored_files": restored_files,
        "failures": failures,
    }


def _discard_backups(repo_path: str, fixes: list[dict[str, Any]]) -> None:
    """Remove recovery backups only after a patched repository has verified."""
    for fix in fixes:
        target = _safe_fix_target(repo_path, fix)
        if target is None:
            continue
        backup = target.with_suffix(target.suffix + ".acr_backup")
        try:
            if backup.is_file():
                backup.unlink()
        except OSError:
            pass


def _fail(
    message: str,
) -> NoReturn:
    """
    Print a final JSON failure and exit.

    This is used for failures that prevent the normal pipeline
    from continuing.
    """

    result = {
        "status": "FAILED",
        "error": str(message),
    }

    print(
        "\n[PIPELINE ERROR] "
        + str(message)
    )

    # Must be the final stdout line.
    print(
        json.dumps(
            result,
            ensure_ascii=False,
        )
    )

    sys.exit(1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
