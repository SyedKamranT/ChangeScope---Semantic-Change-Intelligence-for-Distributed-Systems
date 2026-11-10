#!/usr/bin/env python3
"""ChangeScope Unified Cross-Platform Task Runner."""

import argparse
import subprocess
import sys


def run_command(cmd: list[str], use_shell: bool = False) -> None:
    """Executes a command and exits on failure."""
    cmd_str = " ".join(cmd)
    print(f"\n[RUNNING] {cmd_str}")
    result = subprocess.run(cmd, shell=use_shell)
    if result.returncode != 0:
        print(f"\n[FAILED] Command exited with code {result.returncode}: {cmd_str}")
        sys.exit(result.returncode)
    print(f"[PASSED] {cmd_str}")


def lint() -> None:
    run_command([sys.executable, "-m", "ruff", "check", "."])
    run_command([sys.executable, "-m", "ruff", "format", "--check", "."])


def format_code() -> None:
    run_command([sys.executable, "-m", "ruff", "format", "."])
    run_command([sys.executable, "-m", "ruff", "check", "--fix", "."])


def typecheck() -> None:
    run_command([sys.executable, "-m", "mypy", "packages/", "apps/"])


def test() -> None:
    run_command([sys.executable, "-m", "pytest", "-v", "tests/"])


def build_web() -> None:
    run_command(["pnpm", "--filter", "@changescope/web", "build"], use_shell=True)


def check_all() -> None:
    print("=== ChangeScope Foundation Quality Invariants Verification ===")
    lint()
    typecheck()
    test()
    build_web()
    print("\n✅ ALL QUALITY INVARIANTS PASSED SUCCESSFULLY!")


def main() -> None:
    parser = argparse.ArgumentParser(description="ChangeScope Development Tasks")
    parser.add_argument(
        "task",
        choices=["lint", "format", "typecheck", "test", "build", "check-all"],
        default="check-all",
        nargs="?",
        help="Task to execute",
    )
    args = parser.parse_args()

    if args.task == "lint":
        lint()
    elif args.task == "format":
        format_code()
    elif args.task == "typecheck":
        typecheck()
    elif args.task == "test":
        test()
    elif args.task == "build":
        build_web()
    elif args.task == "check-all":
        check_all()


if __name__ == "__main__":
    main()
