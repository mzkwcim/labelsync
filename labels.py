#!/usr/bin/env python3

"""
sync_labels.py

Synchronizes GitHub labels using the GitHub CLI (`gh`) and a TOML label file.

Features:
- Optional deletion of all existing labels
- Label creation from a TOML definition
- Automatic backup of current labels
- Dry-run mode
- Interactive confirmation
- Full structured logging with loguru

Author: Jakub Hajduga
"""

import subprocess
import argparse
import tomllib  # Python 3.11+
import tomli_w  # pip install tomli-w
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

from logger_setup import configure_console_logger


def run_gh_command(cmd, repo, dry_run=False):
    """
    Executes a GitHub CLI command.

    Args:
        cmd (list): Base GitHub CLI command, e.g. ['label', 'list'].
        repo (str): GitHub repository name in owner/repo format.
        dry_run (bool): If True, runs the function in simulation mode.
    """
    full_cmd = ["gh"] + cmd + ["--repo", repo]
    if dry_run:
        logger.debug(f"[DRY-RUN] Would run: {' '.join(full_cmd)}")
        return ""

    try:
        result = subprocess.run(full_cmd, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(full_cmd)}")
        logger.error(e.stderr)
        return None


def backup_labels(repo, dry_run=False):
    """
    Creates a TOML file backup of the current labels in the specified GitHub repository.

    Args:
        repo (str): GitHub repository name in owner/repo format.
        dry_run (bool): If True, runs the function in simulation mode.
    """
    if dry_run:
        logger.info("[DRY-RUN] Skipping label backup.")
        return

    logger.info(f"📦 Backing up current labels from {repo}...")
    output = run_gh_command(["label", "list"], repo)
    if not output:
        logger.warning("Could not fetch label list.")
        return

    labels = []
    for line in output.splitlines():
        parts = line.split("\t")
        name = parts[0]
        color = parts[1]
        description = parts[2] if len(parts) > 2 else ""
        labels.append({
            "name": name,
            "color": color,
            "description": description
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_labels_{repo.replace('/', '_')}_{timestamp}.toml"

    with open(backup_file, "wb") as f:
        tomli_w.dump({"label": labels}, f)

    logger.success(f"Labels backed up to {backup_file}")


def delete_all_labels(repo, dry_run=False):
    """
    Deletes all labels in the specified repository.

    Args:
        repo (str): GitHub repository name in owner/repo format.
        dry_run (bool): If True, runs the function in simulation mode.
    """
    logger.info(f"🗑️  Fetching existing labels from {repo}...")
    output = run_gh_command(["label", "list"], repo, dry_run)
    if not output:
        logger.warning("Could not retrieve label list.")
        return

    for line in output.splitlines():
        label = line.split("\t")[0]
        logger.info(f"❌ Deleting: {label}")
        run_gh_command(["label", "delete", label, "--yes"], repo, dry_run)


def create_labels_from_toml(file_path, repo, dry_run=False):
    """
    Reads a TOML labels configuration file and uses the GitHub CLI to create labels in the specified repository.

    Args:
        file_path (str): TOML file path containing label definitions, which can be relative or absolute.
        repo (str): GitHub repository name in owner/repo format.
        dry_run (bool): If True, runs the function in simulation mode.
    """
    logger.info(f"📄 Reading labels from: {file_path}")
    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    labels = data.get("label", [])
    for label in labels:
        name = label["name"]
        description = label.get("description", "")
        color = label.get("color", "ffffff")

        logger.info(f"✅ Creating label: {name}")
        run_gh_command([
            "label", "create", name,
            "--description", description,
            "--color", color
        ], repo, dry_run)


def confirm_operation(repo, file_path):
    """
    Prompts the user before executing the GitHub CLI command for modifying labels.

    Args:
        repo (str): GitHub repository name in owner/repo format.
        file_path (str): TOML file path containing label definitions, which can be relative or absolute.

    Returns:
        bool: Whether the user confirms the action.
    """
    logger.warning(f"You are about to modify labels in: {repo}")
    logger.info(f"Using label definitions from: {file_path}")
    response = input("❓ Are you sure you want to proceed? (y/N): ").strip().lower()
    return response in ("y", "yes")


def main():
    """
    CLI entry point for synchronizing GitHub labels from a TOML file.

    Parses command-line arguments, configures logging and applies label changes
    to the specified repository.
    """
    parser = argparse.ArgumentParser(description="Sync GitHub labels from a TOML file.")

    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository in the format owner/repo"
    )

    parser.add_argument(
        "--file",
        default="labels.toml",
        help="Path to TOML label file (default: labels.toml)"
    )

    parser.add_argument(
        "--skip-delete",
        action="store_true",
        help="Skip deleting existing labels before applying new ones"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying anything"
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Set up console logging
    configure_console_logger(args.log_level)

    # Confirmation prompt
    if not args.dry_run and not confirm_operation(args.repo, args.file):
        logger.warning("Operation cancelled by user.")
        return

    backup_labels(args.repo, dry_run=args.dry_run)

    if not args.skip_delete:
        delete_all_labels(args.repo, dry_run=args.dry_run)
    else:
        logger.info("⏭️  Skipping label deletion (--skip-delete enabled)")

    create_labels_from_toml(args.file, args.repo, dry_run=args.dry_run)

    logger.success("🎉 Label sync complete.")


if __name__ == "__main__":
    main()
