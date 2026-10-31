"""Tests for the base CLI options: help, --config, and --completions."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from chopper.cli import main


def combined_output(result: object) -> str:
    """Return stdout and stderr together for assertions."""
    output = getattr(result, "output", "")
    stderr = getattr(result, "stderr", "")
    return str(output) + str(stderr)


def test_short_help() -> None:
    result = CliRunner().invoke(main, ["-h"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "--config" in result.output
    assert "--completions" in result.output


def test_long_help() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "SOURCE" in result.output
    assert "--config" in result.output
    assert "--completions" in result.output


def test_config_prints_path(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / ".env"
    config.write_text("CHOPPER_DEBUG=true\n", encoding="utf-8")
    monkeypatch.setattr(
        "chopper.cli.find_file_upwards",
        lambda *_args, **_kwargs: config,
    )

    result = CliRunner().invoke(main, ["--config"])

    assert result.exit_code == 0
    assert result.output.strip() == str(config)


def test_config_missing_exits_with_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "chopper.cli.find_file_upwards",
        lambda *_args, **_kwargs: None,
    )

    result = CliRunner().invoke(main, ["--config"])

    assert result.exit_code == 1
    assert "No configuration file found" in combined_output(result)


def test_completions_writes_xdg_script(monkeypatch, tmp_path: Path) -> None:
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    result = CliRunner().invoke(main, ["--completions"])

    script = data_home / "bash-completion" / "completions" / "chopper"
    assert result.exit_code == 0
    assert script.exists()

    content = script.read_text(encoding="utf-8")
    assert "--script-dir" in content
    assert "-s)" in content
    assert "--comments" in content
    assert "server client none" in content
    assert "_chopper_filedir -d" in content
    assert "complete -o nosort -F _chopper_completion chopper" in content

    assert str(script) in result.output
    assert f"source {script}" in result.output


def test_completions_falls_back_to_local_share(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    result = CliRunner().invoke(main, ["--completions"])

    script = (
        tmp_path / ".local" / "share" / "bash-completion" / "completions" / "chopper"
    )
    assert result.exit_code == 0
    assert script.exists()
    assert str(script) in result.output


def test_completions_warns_for_old_bash(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(
        "chopper.completions.get_bash_version",
        lambda: (3, 2),
    )

    result = CliRunner().invoke(main, ["--completions"])

    assert result.exit_code == 0
    assert "bash 3.2" in combined_output(result)
    assert "bash 4.4 or newer" in combined_output(result)


def test_new_flags_do_not_require_source(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(
        "chopper.cli.find_file_upwards",
        lambda *_args, **_kwargs: None,
    )

    completions = CliRunner().invoke(main, ["--completions"])
    config = CliRunner().invoke(main, ["--config"])

    assert completions.exit_code == 0
    # --config exits 1 here only because no config file exists, not because
    # SOURCE is missing.
    assert config.exit_code == 1
    assert "Missing argument" not in combined_output(config)
