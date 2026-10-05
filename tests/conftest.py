"""Shared test setup: the tests must give the same result whatever experiment.yaml currently says."""
import os

import pytest
import yaml

from sandbag.config import ROOT


@pytest.fixture(autouse=True, scope="session")
def settings_for_tests(tmp_path_factory):
    """Use a copy of experiment.yaml in reminder mode, so no test ever calls a real repair model."""
    settings = yaml.safe_load((ROOT / "experiment.yaml").read_text())
    settings["unparseable_reply"] = {"mode": "reminder", "repair_model": None}
    path = tmp_path_factory.mktemp("settings") / "experiment.yaml"
    path.write_text(yaml.safe_dump(settings))
    os.environ["SANDBAG_EXPERIMENT"] = str(path)
    yield
    del os.environ["SANDBAG_EXPERIMENT"]
