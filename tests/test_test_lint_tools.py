from unittest.mock import MagicMock, patch

from onboarding_agent.tools.test_lint_tools import run_lint, run_tests


def test_run_tests_passes(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok():\n    assert True\n")

    output = run_tests(tmp_path)
    assert "EXIT CODE: 0" in output


def test_run_tests_fails(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest\n")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_bad():\n    assert False\n")

    output = run_tests(tmp_path)
    assert "EXIT CODE: 1" in output


def test_run_tests_no_runner_detected(tmp_path):
    output = run_tests(tmp_path)
    assert "No recognized test runner found" in output


@patch("onboarding_agent.tools.test_lint_tools.subprocess.run")
def test_run_tests_detects_npm(mock_run, tmp_path):
    (tmp_path / "package.json").write_text("{}")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    run_tests(tmp_path)

    assert mock_run.call_args.args[0] == ["npm", "test"]


@patch("onboarding_agent.tools.test_lint_tools.subprocess.run")
def test_run_tests_detects_go(mock_run, tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/foo\n")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    run_tests(tmp_path)

    assert mock_run.call_args.args[0] == ["go", "test", "./..."]


@patch("onboarding_agent.tools.test_lint_tools.subprocess.run")
def test_run_tests_detects_cargo(mock_run, tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "foo"\n')
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    run_tests(tmp_path)

    assert mock_run.call_args.args[0] == ["cargo", "test"]


def test_run_lint_no_config_found(tmp_path):
    assert run_lint(tmp_path) == "No lint config found in target repo."


@patch("onboarding_agent.tools.test_lint_tools.subprocess.run")
def test_run_lint_runs_ruff_when_config_present(mock_run, tmp_path):
    (tmp_path / "ruff.toml").write_text("")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    run_lint(tmp_path)

    assert mock_run.call_args.args[0] == ["ruff", "check", "."]


@patch("onboarding_agent.tools.test_lint_tools.subprocess.run")
def test_run_lint_runs_eslint_when_config_present(mock_run, tmp_path):
    (tmp_path / "package.json").write_text('{"eslintConfig": {}}')
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    run_lint(tmp_path)

    assert mock_run.call_args.args[0] == ["npx", "eslint", "."]


@patch("onboarding_agent.tools.test_lint_tools.subprocess.run")
def test_run_lint_detects_eslint_flat_config(mock_run, tmp_path):
    (tmp_path / "eslint.config.js").write_text("export default [];\n")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    run_lint(tmp_path)

    assert mock_run.call_args.args[0] == ["npx", "eslint", "."]
