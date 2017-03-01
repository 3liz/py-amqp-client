from setuptools import setup, find_packages, Extension
from pip.req import parse_requirements
from imp import load_source
import os

VER = load_source("version", 'liz_amqp/version.py')

kwargs = {}

with open('README.md') as f:
    kwargs['long_description'] = f.read()

# Parse requirement file and transform it to setuptools requirements'''
requirements = 'requirements.txt'
if os.path.exists(requirements):
    kwargs['install_requires']=list(str(ir.req) for ir in parse_requirements(requirements, session=False))

setup(
    name='liz-amqp',
    version=VER.__version__,
    author='3Liz',
    author_email='infos@3liz.org',
    maintainer='David Marteau',
    maintainer_email='dmarteau@3liz.org',
    description=VER.__description__,
    url='',
    packages=find_packages(include="liz_amqp"),
    entry_points={
        'console_scripts': [],
    },
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
    **kwargs
)

