from setuptools import setup, find_packages

setup(
    name="nuzantara_mcp_browser",
    version="0.1.0",
    description="Headless browser sidecar for Nuzantara UI verification",
    author="Nuzantara Team",
    author_email="zero@balizero.com",
    packages=find_packages(),
    install_requires=[
        "fastmcp",
        "playwright",
    ],
    entry_points={
        "console_scripts": [
            "nuzantara-mcp-browser=nuzantara_mcp_browser.server:main",
        ],
    },
    python_requires=">=3.8",
)
