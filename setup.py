from pathlib import Path

from setuptools import find_packages, setup

requirements = Path("requirements.txt").read_text().splitlines()

setup(
    name="repo-onboarding-agent",
    version="0.1.0",
    description="Clone-and-run CLI that gives any codebase an AI onboarding assistant (LLM + RAG + MCP + Agent).",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[r for r in requirements if r.strip() and not r.startswith("#")],
    entry_points={
        "console_scripts": [
            "onboarding-agent=onboarding_agent.cli:main",
        ],
    },
    python_requires=">=3.10",
)
