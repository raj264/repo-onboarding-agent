from unittest.mock import MagicMock, patch

from onboarding_agent.tools.test_lint_tools import run_lint, run_tests


def test_run_tests_passes(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok():\n    assert True\n")

    output = run_tests(tmp_path)
    assert "EXIT CODE: 0" in output


def test_run_tests_fails(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_bad():\n    assert False\n")

    output = run_tests(tmp_path)
    assert "EXIT CODE: 1" in output


def test_run_lint_no_config_found(tmp_path):
    assert run_lint(tmp_path) == "No lint config found in target repo."


@patch("onboarding_agent.tools.test_lint_tools.subprocess.run")
def test_run_lint_runs_ruff_when_config_present(mock_run, tmp_path):
    (tmp_path / "ruff.toml").write_text("")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    run_lint(tmp_path)

    args, kwargs = mock_run.call_args
    assert args[0] == ["ruff", "check", "."]
