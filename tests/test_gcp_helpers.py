"""Tests for GCP CLI helpers (extract_gcp_verb, sanitize_command, ensure_json_format).

Validates:
- Verb extraction across gcloud, bq, and gsutil command families
- Shell injection blocking for dangerous characters
- JSON format auto-appending for gcloud and bq commands
"""

from __future__ import annotations

import pytest

from src.shared.gcp_helpers import (
    extract_gcp_verb,
    sanitize_command,
    ensure_json_format,
)


# ==========================================
# extract_gcp_verb — gcloud commands
# ==========================================


class TestExtractGcpVerbGcloud:
    """extract_gcp_verb should correctly identify verbs in gcloud commands."""

    @pytest.mark.parametrize(
        "command, expected",
        [
            ("gcloud run services list", "list"),
            ("gcloud run services describe my-service", "describe"),
            ("gcloud compute instances list --project=my-project", "list"),
            ("gcloud iam service-accounts create my-sa --display-name=SA", "create"),
            ("gcloud run deploy my-service --image=gcr.io/proj/img", "deploy"),
            ("gcloud projects delete my-project", "delete"),
            ("gcloud secrets versions access 1 --secret=my-secret", "access"),
            ("gcloud compute addresses list --project=my-project", "list"),
            ("gcloud services enable compute.googleapis.com", "enable"),
            ("gcloud iam roles update my-role --project=proj", "update"),
        ],
    )
    def test_gcloud_verb_extraction(self, command: str, expected: str):
        assert extract_gcp_verb(command) == expected


# ==========================================
# extract_gcp_verb — bq commands
# ==========================================


class TestExtractGcpVerbBq:
    """extract_gcp_verb should correctly identify verbs in bq commands."""

    @pytest.mark.parametrize(
        "command, expected",
        [
            ("bq ls", "ls"),
            ("bq show dataset.table", "show"),
            ("bq rm dataset.table", "rm"),
            ("bq query --use_legacy_sql=false 'SELECT 1'", "query"),
            ("bq mk --table dataset.table schema.json", "mk"),
            ("bq cp dataset.src dataset.dst", "cp"),
            ("bq load dataset.table gs://bucket/file.csv", "load"),
        ],
    )
    def test_bq_verb_extraction(self, command: str, expected: str):
        assert extract_gcp_verb(command) == expected


# ==========================================
# extract_gcp_verb — gsutil / gcloud storage commands
# ==========================================


class TestExtractGcpVerbGsutil:
    """extract_gcp_verb should correctly identify verbs in gsutil and gcloud storage commands."""

    @pytest.mark.parametrize(
        "command, expected",
        [
            ("gsutil ls gs://my-bucket", "ls"),
            ("gsutil cp file.txt gs://bucket/file.txt", "cp"),
            ("gsutil rm gs://bucket/file.txt", "rm"),
            ("gsutil mv gs://src/a gs://dst/a", "mv"),
            ("gsutil cat gs://bucket/file.txt", "cat"),
            ("gcloud storage cp file gs://bucket", "cp"),
            ("gcloud storage ls gs://my-bucket", "ls"),
            ("gcloud storage rm gs://bucket/file.txt", "rm"),
        ],
    )
    def test_gsutil_verb_extraction(self, command: str, expected: str):
        assert extract_gcp_verb(command) == expected


# ==========================================
# extract_gcp_verb — edge cases
# ==========================================


class TestExtractGcpVerbEdgeCases:
    """extract_gcp_verb should handle edge cases gracefully."""

    def test_empty_command(self):
        assert extract_gcp_verb("") == ""

    def test_single_token(self):
        assert extract_gcp_verb("gcloud") == "gcloud"

    def test_bq_single_token(self):
        assert extract_gcp_verb("bq") == ""

    def test_gsutil_single_token(self):
        assert extract_gcp_verb("gsutil") == ""


# ==========================================
# sanitize_command — injection blocking
# ==========================================


class TestSanitizeCommandBlocks:
    """sanitize_command must block shell injection patterns."""

    @pytest.mark.parametrize(
        "command, pattern_name",
        [
            ("gcloud run services list | grep something", "pipe"),
            ("gcloud run services list && rm -rf /", "double-ampersand"),
            ("gcloud run services list; echo pwned", "semicolon"),
            ("gcloud run services list `whoami`", "backtick"),
            ("gcloud run services list $(whoami)", "subshell"),
            ("gcloud run services list > /tmp/out", "redirect-out"),
            ("gcloud run services list < /etc/passwd", "redirect-in"),
        ],
    )
    def test_blocks_injection(self, command: str, pattern_name: str):
        with pytest.raises(ValueError, match="SECURITY GATE"):
            sanitize_command(command)


class TestSanitizeCommandAllows:
    """sanitize_command must allow clean commands."""

    @pytest.mark.parametrize(
        "command",
        [
            "gcloud run services list --project=my-project",
            "bq ls --project_id=my-project",
            "gsutil cp file.txt gs://bucket/file.txt",
            "gcloud iam service-accounts create my-sa --display-name=My SA",
            "gcloud compute instances describe my-vm --zone=us-central1-a",
        ],
    )
    def test_allows_clean_commands(self, command: str):
        result = sanitize_command(command)
        assert result == command


# ==========================================
# ensure_json_format — auto-appending
# ==========================================


class TestEnsureJsonFormatGcloud:
    """ensure_json_format should append --format=json to gcloud commands."""

    def test_appends_to_gcloud(self):
        result = ensure_json_format("gcloud run services list")
        assert result == "gcloud run services list --format=json"

    def test_no_duplicate_format(self):
        result = ensure_json_format("gcloud run services list --format=json")
        assert result == "gcloud run services list --format=json"

    def test_no_override_custom_format(self):
        result = ensure_json_format("gcloud run services list --format=table")
        assert result == "gcloud run services list --format=table"


class TestEnsureJsonFormatBq:
    """ensure_json_format should append --format=json to bq commands."""

    def test_appends_to_bq(self):
        result = ensure_json_format("bq ls")
        assert result == "bq ls --format=json"

    def test_no_duplicate_bq(self):
        result = ensure_json_format("bq ls --format=json")
        assert result == "bq ls --format=json"


class TestEnsureJsonFormatGsutil:
    """ensure_json_format should NOT append --format=json to gsutil commands."""

    def test_no_append_to_gsutil(self):
        result = ensure_json_format("gsutil ls gs://my-bucket")
        assert result == "gsutil ls gs://my-bucket"

    def test_no_append_to_gcloud_storage(self):
        result = ensure_json_format("gcloud storage ls gs://my-bucket")
        assert result == "gcloud storage ls gs://my-bucket"


class TestEnsureJsonFormatEdgeCases:
    """ensure_json_format should handle edge cases."""

    def test_empty_command(self):
        result = ensure_json_format("")
        assert result == ""

    def test_unknown_binary(self):
        result = ensure_json_format("kubectl get pods")
        assert result == "kubectl get pods"
