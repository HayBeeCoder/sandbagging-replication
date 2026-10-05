"""The model's commands must be shut out of everything except their own folder."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from sandbag import lockdown
from sandbag.config import ROOT
from tests.test_agent import KEY, action, run


def output_of(cmd, tmp_path):  # what the model sees when it runs cmd
    _, messages = run([action("bash", cmd=cmd), action("submit", answer=KEY)], tmp_path)
    return messages[3].text


def test_this_machine_is_locked_down():
    lockdown.check()  # fails with the fix to apply if the repo folder is readable


def test_commands_do_not_run_as_root(tmp_path):
    uid = int(output_of("id -u", tmp_path))
    assert 20000 <= uid < 60000


def test_the_answer_key_cannot_be_read(tmp_path):
    assert "Permission denied" in output_of(f"cat {ROOT}/data/answer_key.json", tmp_path)
    assert KEY not in output_of(f"cat {ROOT}/data/answer_key.json; ls {ROOT}; ls {ROOT.parent}", tmp_path)


def test_our_environment_is_not_passed_on(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "sk-do-not-leak")
    seen = output_of("env", tmp_path)
    assert "sk-do-not-leak" not in seen and "PATH=" in seen


def test_the_model_can_still_work_in_its_own_folder(tmp_path):
    assert output_of("echo 12 > notes.txt && cat notes.txt && ls", tmp_path).split() == ["12", "Documentation.md", "notes.txt", "questions.txt"]


def test_every_run_gets_its_own_user():
    assert lockdown.new_uid() != lockdown.new_uid()


def test_one_run_cannot_read_another_runs_folder():
    mine, other = lockdown.new_uid(), lockdown.new_uid()
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, "Documentation.md").write_text("secret condition")
        os.chown(folder, mine, mine)
        os.chmod(folder, 0o700)
        peek = subprocess.run(lockdown.as_user(other, "/tmp", f"cat {folder}/Documentation.md"), capture_output=True, text=True)
    assert peek.returncode != 0 and "secret condition" not in peek.stdout


def test_a_readable_private_folder_is_refused():
    with tempfile.TemporaryDirectory() as folder:
        os.chmod(folder, 0o755)
        with pytest.raises(RuntimeError, match="chmod 700"):
            lockdown.check(private=folder)
