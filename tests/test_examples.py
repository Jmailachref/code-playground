"""Every sample question is valid and its reference solution passes all its test cases."""
import json

import pytest

from api.check_examples import ROOT, check, question_files

FILES = question_files()


def test_slugs_are_unique():
    slugs = [json.loads(p.read_text())["slug"] for p in FILES]
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT / "examples")))
def test_question(path):
    assert check(path) == []
