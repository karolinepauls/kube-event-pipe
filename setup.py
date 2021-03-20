#!/usr/bin/env python3
"""Write deduplicated events to stdout as JSON."""
from pathlib import Path
from setuptools import setup  # type: ignore


VERSION = '0.0.1'
README_FILE = Path(__file__).resolve().with_name('README.rst')
README = README_FILE.read_text('utf-8')
REQUIREMENTS = [
    'kubernetes==12.0.1',
    'requests==2.25.1',
]
DEV_REQUIREMENTS = [
    'flake8',
    'flake8-docstrings',
    'flake8_tuple',
    'mypy',
    'pytest',
]

if __name__ == '__main__':
    setup(
        name='kube-event-pipe',
        version=VERSION,
        description='Pipes deduplicated Kubernetes events',
        long_description=README,
        classifiers=[
            'Topic :: Utilities',
            'License :: OSI Approved :: BSD License',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
        ],
        keywords='kubernetes event deduplicate',
        author='Karoline Pauls',
        author_email='code@karolinepauls.com',
        url='https://gitlab.com/karolinepauls/kube-event-pipe',
        project_urls={
            "Bug Tracker": 'https://gitlab.com/karolinepauls/kube-event-pipe/issues',
            "Source Code": 'https://gitlab.com/karolinepauls/kube-event-pipe',
        },
        license='MIT',
        packages=['kube_event_pipe'],
        zip_safe=False,
        install_requires=REQUIREMENTS,
        extras_require={
            'dev': DEV_REQUIREMENTS,
        },
        entry_points={
            'console_scripts': 'kube-event-pipe=kube_event_pipe.main:main'
        },
    )
