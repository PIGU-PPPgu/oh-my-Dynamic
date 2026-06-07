"""Setuptools editable-install shim for older pip versions."""

from setuptools import find_packages, setup


setup(
    name="oh-my-dynamic",
    version="3.4.0",
    description="Multi-agent orchestration engine with DAG execution, dynamic replan, TEA protocol, and model-provider routing.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    license="MIT",
    author="PIGU-PPPgu",
    package_dir={"": "src"},
    packages=find_packages("src", include=["oh_my_dynamic", "oh_my_dynamic.*"]),
    install_requires=["openai>=1.0.0"],
    extras_require={
        "zhipu": ["zhipuai>=2.0.0"],
        "anthropic": ["anthropic>=0.40.0"],
        "google": ["google-generativeai>=0.8.0"],
        "all": [
            "zhipuai>=2.0.0",
            "anthropic>=0.40.0",
            "google-generativeai>=0.8.0",
        ],
        "dev": [
            "bandit>=1.7.10",
            "coverage[toml]>=7.4.0",
            "pytest>=8.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "oh-my-dynamic-gateway=oh_my_dynamic.cli.gateway:main",
            "oh-my-dynamic-codex-swarm=oh_my_dynamic.cli.codex_swarm:main",
            "oh-my-dynamic-dynamic-workflow=oh_my_dynamic.cli.dynamic_workflow:main",
            "oh-my-dynamic-quality-eval=oh_my_dynamic.cli.quality_eval:main",
            "oh-my-dynamic-doctor=oh_my_dynamic.cli.doctor:main",
        ]
    },
)
