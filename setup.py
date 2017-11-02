from setuptools import setup, find_packages, Extension
from pip.req import parse_requirements
import os

def load_source(name, path):
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location(name, path)
    mod  = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

VER = load_source("version", 'amqpclient/version.py')

kwargs = {}

with open('README.md') as f:
    kwargs['long_description'] = f.read()

# Parse requirement file and transform it to setuptools requirements'''
requirements = 'requirements.txt'
if os.path.exists(requirements):
    kwargs['install_requires']=list(str(ir.req) for ir in parse_requirements(requirements, session=False))

setup(
    name='py-amqp-client',
    version=VER.__version__,
    author='3Liz',
    author_email='infos@3liz.org',
    maintainer='David Marteau',
    maintainer_email='dmarteau@3liz.org',
    description=VER.__description__,
    url='',
    packages=find_packages(include=['amqpclient','amqpclient.*']),
    entry_points={
        'console_scripts': [],
    },
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
    **kwargs
)

