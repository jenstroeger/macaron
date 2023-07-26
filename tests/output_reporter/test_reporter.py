# Copyright (c) 2022 - 2023, Oracle and/or its affiliates. All rights reserved.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/.

"""
This modules contains tests for the JSON reporter.
"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jinja2 import Environment, FileSystemLoader, select_autoescape

from macaron.config.target_config import Configuration
from macaron.output_reporter.reporter import HTMLReporter, JSONReporter
from macaron.output_reporter.results import Record, Report, SCMStatus

from ..st import JINJA_CONTEXT_DICT


class MockRecord(Record):
    """A mock class for the record."""

    def __init__(self, mock_data: dict) -> None:
        super().__init__(
            record_id="record",
            description="sample_desc",
            pre_config=Configuration({}),
            status=SCMStatus.AVAILABLE,
            context=MagicMock(),
            dependencies=[],
        )
        self.mock_data = mock_data

    def get_dict(self) -> dict:
        return self.mock_data


@pytest.fixture(scope="module", name="custom_jinja_env")
def fixture_custom_jinja_env() -> Environment:
    """Return the custom Jinja2 environment for testing.

    Returns
    -------
    Environment
        The custom Jinja2 environment.
    """
    root_path = Path(__file__).parent.joinpath("resources")
    return Environment(
        loader=FileSystemLoader(root_path),
        autoescape=select_autoescape(enabled_extensions=["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def test_no_html_template_found(custom_jinja_env: Environment) -> None:
    """Test initializing a HTMLReporter instance with a non-existing template."""
    no_template_reporter = HTMLReporter(env=custom_jinja_env, target_template="not_exist_template.html")
    assert not no_template_reporter.template


def test_syntax_err_template(custom_jinja_env: Environment) -> None:
    """Test generating the HTML report from a template with syntax errors."""
    syntax_err = HTMLReporter(env=custom_jinja_env, target_template="syntax_err.html")
    assert not syntax_err.template


def test_runtime_err_template(custom_jinja_env: Environment) -> None:
    """Test generating the HTML report from a template with runtime errors."""
    report = Report(MockRecord({}))
    runtime_err = HTMLReporter(env=custom_jinja_env, target_template="runtime_err.html")
    with patch("builtins.open") as mock_open:
        runtime_err.generate("report_paths", report)
        mock_open.assert_not_called()


@given(mock_data=JINJA_CONTEXT_DICT, num_dep=st.integers(min_value=0, max_value=3))
def test_gen_html_reports(custom_jinja_env: Environment, mock_data: Any, num_dep: int) -> None:
    """Test if HTMLReporter can print HTML files without errors."""
    report = Report(MockRecord(mock_data))
    for _ in range(num_dep):
        report.root_record.dependencies.append(MockRecord(mock_data))

    reporter = HTMLReporter(env=custom_jinja_env, target_template="template.html")
    with patch("builtins.open") as mock_open:
        reporter.generate("report_paths", report)
        mock_open.assert_called()


@pytest.mark.parametrize(
    ("main_status", "has_deps", "gen_empty_main"),
    [
        (SCMStatus.ANALYSIS_FAILED, False, False),
        (SCMStatus.MISSING_SCM, False, False),
        (SCMStatus.DUPLICATED_SCM, False, False),
        (SCMStatus.ANALYSIS_FAILED, True, True),
        (SCMStatus.MISSING_SCM, True, True),
        (SCMStatus.DUPLICATED_SCM, True, True),
        (SCMStatus.AVAILABLE, False, False),
        (SCMStatus.AVAILABLE, True, False),
    ],
)
def test_main_target_status(
    custom_jinja_env: Environment, main_status: SCMStatus, has_deps: bool, gen_empty_main: bool
) -> None:
    """Test the different scenarios for the main target's analysis status."""
    main_record: Record = Record(
        record_id="record",
        description="sample_desc",
        pre_config=Configuration({}),
        status=main_status,
        context=MagicMock(),
        dependencies=[],
        policies_failed=[],
        policies_passed=[],
    )

    report = Report(main_record)

    if has_deps:
        dep_record: Record = Record(
            record_id="dep",
            description="sample_desc",
            pre_config=Configuration({}),
            status=SCMStatus.AVAILABLE,
            context=MagicMock(),
            dependencies=[],
            policies_failed=[],
            policies_passed=[],
        )
        report.root_record.dependencies.append(dep_record)

    reporter = HTMLReporter(env=custom_jinja_env, target_template="template.html")
    empty_main_call = call(os.path.join("report_paths", "index.html"), mode="w", encoding="utf-8")
    with patch("builtins.open") as mock_open:
        reporter.generate("report_paths", report)
        if gen_empty_main:
            mock_open.assert_has_calls([empty_main_call])
        else:
            assert empty_main_call.args not in mock_open.call_args_list


@given(mock_data=JINJA_CONTEXT_DICT, num_dep=st.integers(min_value=0, max_value=3))
def test_gen_json_reports(mock_data: Any, num_dep: int) -> None:
    """Test if JSONReporter can print JSON files without errors."""
    report = Report(MockRecord(mock_data))
    for _ in range(num_dep):
        report.root_record.dependencies.append(MockRecord(mock_data))

    reporter = JSONReporter()

    with patch("builtins.open") as mock_open:
        reporter.generate("report_paths", report)
        calls = [call(os.path.join("report_paths", "dependencies.json"), mode="w", encoding="utf-8")]
        mock_open.assert_has_calls(calls)
