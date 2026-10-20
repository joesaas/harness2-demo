"""测试共用组装：执行器 / 评估器 / 探测器各一份，语料与出厂驾驭层现造。"""

import pytest

from harness2_demo.contrast import BehaviorEvaluator, ProbeRunner
from harness2_demo.executor import RuleExecutor
from harness2_demo.tasks import build_corpus_1, build_corpus_2, build_factory_harness


@pytest.fixture
def executor():
    return RuleExecutor()


@pytest.fixture
def evaluator():
    return BehaviorEvaluator()


@pytest.fixture
def probe(executor, evaluator):
    return ProbeRunner(executor, evaluator)


@pytest.fixture
def corpus1():
    return build_corpus_1()


@pytest.fixture
def corpus2():
    return build_corpus_2()


@pytest.fixture
def factory():
    return build_factory_harness()
