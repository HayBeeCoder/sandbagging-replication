import pytest
import yaml

from sandbag.config import ROOT, load_experiment


def write(tmp_path, **changes):
    """Copy the real experiment.yaml into a temp folder with some values changed."""
    settings = yaml.safe_load((ROOT / "experiment.yaml").read_text())
    settings.update(changes)
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(settings))
    return path


def test_real_file_loads_with_paper_values():
    s = load_experiment()
    assert s["runs_per_condition"] == 50
    assert s["alpha"] == 0.01
    assert s["max_tokens"] == 4096
    assert s["conditions"] == ["sandbag", "counterfactual"]


def test_missing_setting_is_refused(tmp_path):
    settings = yaml.safe_load((ROOT / "experiment.yaml").read_text())
    del settings["seed"]
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(settings))
    with pytest.raises(ValueError, match="missing 'seed'"):
        load_experiment(path)


def test_wrong_type_is_refused(tmp_path):
    with pytest.raises(ValueError, match="runs_per_condition"):
        load_experiment(write(tmp_path, runs_per_condition="fifty"))


def test_unknown_sandbox_is_refused(tmp_path):
    with pytest.raises(ValueError, match="sandbox"):
        load_experiment(write(tmp_path, sandbox="laptop"))


def test_repair_mode_needs_a_repair_model(tmp_path):
    bad = {"mode": "repair", "repair_model": None}
    with pytest.raises(ValueError, match="repair_model"):
        load_experiment(write(tmp_path, unparseable_reply=bad))
    good = {"mode": "repair", "repair_model": "llama31_8b_runpod"}
    assert load_experiment(write(tmp_path, unparseable_reply=good))["unparseable_reply"]["mode"] == "repair"