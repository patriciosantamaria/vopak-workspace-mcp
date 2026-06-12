"""gcp_helpers.py – GCP CLI verb classification, command safety, and formatting.

Provides:
- Verb sets for read/write/destructive classification of gcloud, bq, and gsutil commands
- extract_gcp_verb() for parsing GCP CLI commands to extract the action verb
- sanitize_command() for blocking shell injection patterns
- ensure_json_format() for auto-appending --format=json to gcloud/bq commands
"""

from __future__ import annotations

import re


# ==========================================
# VERB CLASSIFICATION SETS
# ==========================================

READ_VERBS: set[str] = {
    "list", "describe", "get", "show", "info", "cat", "read",
    "access", "ls", "head", "tail", "print",
}

WRITE_VERBS: set[str] = {
    "create", "update", "set", "add", "deploy", "patch", "grant",
    "enable", "bind", "upload", "cp", "mv", "copy", "move", "push",
    "submit", "import", "start", "stop", "resume",
}

DESTRUCTIVE_VERBS: set[str] = {
    "delete", "remove", "destroy", "revoke", "drop", "truncate",
    "purge", "shred", "empty", "disable", "rm",
}

# Combined set for fast lookup
_ALL_VERBS = READ_VERBS | WRITE_VERBS | DESTRUCTIVE_VERBS

# Shell injection patterns to block
_INJECTION_PATTERN = re.compile(r"[|;&`]|\$\(|>>|<<|>{1}|<{1}")


# ==========================================
# VERB EXTRACTION
# ==========================================


def extract_gcp_verb(command: str) -> str:
    """Extract the primary action verb from a GCP CLI command string.

    Handles three CLI families:
    - gcloud: skip 'gcloud' prefix and service tokens, find first recognized verb.
      e.g. 'gcloud run services list' -> 'list'
    - bq: the second token is the verb (ls, show, query, mk, rm, load, cp).
      e.g. 'bq ls' -> 'ls'
    - gsutil / gcloud storage: extract the subcommand.
      e.g. 'gsutil cp file gs://bucket' -> 'cp'
      e.g. 'gcloud storage cp file gs://bucket' -> 'cp'

    Args:
        command: The full GCP CLI command string.

    Returns:
        The extracted verb in lowercase.
    """
    tokens = command.strip().split()
    if not tokens:
        return ""

    first = tokens[0].lower()

    # --- bq commands ---
    if first == "bq":
        if len(tokens) >= 2:
            return tokens[1].lower()
        return ""

    # --- gsutil commands ---
    if first == "gsutil":
        if len(tokens) >= 2:
            return tokens[1].lower()
        return ""

    # --- gcloud commands ---
    if first == "gcloud":
        # Handle 'gcloud storage <verb>' as a gsutil-like command
        if len(tokens) >= 3 and tokens[1].lower() == "storage":
            return tokens[2].lower()

        # For general gcloud commands, skip prefix and service tokens,
        # find the first recognized verb
        for token in tokens[1:]:
            lower = token.lower()
            # Stop at flags
            if lower.startswith("--"):
                break
            if lower in _ALL_VERBS:
                return lower

        # Fallback: last non-flag token after gcloud
        for token in reversed(tokens[1:]):
            if not token.startswith("--"):
                return token.lower()

    # Ultimate fallback: first token
    return tokens[0].lower()


# ==========================================
# COMMAND SANITIZATION
# ==========================================


def sanitize_command(command: str) -> str:
    """Block shell injection patterns in a GCP CLI command string.

    Checks for dangerous characters that could enable command chaining
    or shell escapes: pipe (|), logical AND (&&), semicolon (;),
    backticks (`), subshell ($(...)), and redirects (>, <).

    Args:
        command: The full command string to validate.

    Returns:
        The original command if it passes validation.

    Raises:
        ValueError: If a shell injection pattern is detected.
    """
    # Check for && specifically (since & alone might be in args)
    if "&&" in command:
        raise ValueError(
            "SECURITY GATE: Shell chaining operator '&&' detected. "
            "Submit each command separately."
        )

    # Check for other injection patterns
    match = _INJECTION_PATTERN.search(command)
    if match:
        char = match.group(0)
        raise ValueError(
            f"SECURITY GATE: Dangerous shell character '{char}' detected. "
            "Shell injection is blocked. Submit clean gcloud/bq/gsutil commands only."
        )

    return command


# ==========================================
# JSON FORMAT ENFORCEMENT
# ==========================================


def ensure_json_format(command: str) -> str:
    """Auto-append --format=json to gcloud and bq commands if not present.

    For gcloud commands (not gsutil), appends --format=json.
    For bq commands, appends --format=json.
    gsutil commands are left unchanged (gsutil does not support --format=json).

    Args:
        command: The full command string.

    Returns:
        The command with --format=json appended if applicable.
    """
    tokens = command.strip().split()
    if not tokens:
        return command

    first = tokens[0].lower()

    # gsutil commands don't support --format=json
    if first == "gsutil":
        return command

    # gcloud storage commands also don't support --format=json
    if first == "gcloud" and len(tokens) >= 2 and tokens[1].lower() == "storage":
        return command

    # For gcloud and bq, append --format=json if not already present
    if first in ("gcloud", "bq"):
        if "--format=json" not in command and "--format" not in command:
            return f"{command} --format=json"

    return command
