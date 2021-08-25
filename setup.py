from pathlib import Path
from typing import List

from setuptools import setup


VERSION = 0.1


def get_requirements(req_file: str) -> List[str]:
    """
    Extract requirements from provided file.
    """
    req_path = Path(req_file)
    requirements = req_path.read_text().split("\n") if req_path.exists() else []
    return requirements


def get_long_description(readme_file: str) -> str:
    """
    Extract README from provided file.
    """
    readme_path = Path(readme_file)
    long_description = (
        readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    )
    return long_description


setup(
    name='crypto_rpc',
    version=VERSION,
    packages=['crypto_rpc'],
    url='',
    license='',
    author='DCx7C5',
    author_email='',
    description=''
)
