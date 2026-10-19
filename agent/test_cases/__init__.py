from typing import Dict, Callable, List
from agent.test_cases.base_case import BaseTestCase
from agent.test_cases.registration_cases import RegistrationTestCases
from agent.test_cases.login_cases import LoginTestCases
from agent.test_cases.profile_cases import ProfileTestCases

TEST_CASE_REGISTRY: Dict[str, Callable[[], BaseTestCase]] = {
    "registration": RegistrationTestCases,
    "login": LoginTestCases,
    "profile": ProfileTestCases,
}

ALL_FLOW_KEYS: List[str] = ["registration", "login", "profile"]

__all__ = [
    "BaseTestCase",
    "RegistrationTestCases",
    "LoginTestCases",
    "ProfileTestCases",
    "TEST_CASE_REGISTRY",
    "ALL_FLOW_KEYS",
]
