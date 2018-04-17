from setuptools import setup, find_packages, Extension
import os
import sys

def parse_requirements( filename ):
    with open( filename ) as fp:
        return list(filter(None, (r.strip('\n ').partition('#')[0] for r in fp.readlines())))

if (sys.version_info > (3, 4)):
    def load_source(name, path):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location(name, path)
        mod  = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
else:
    from imp import load_source

VER = load_source("version", 'amqpclient/version.py')

kwargs = {}

with open('README.md') as f:
    kwargs['long_description'] = f.read()

# Parse requirement file and transform it to setuptools requirements'''
requirements = 'requirements.txt'
if os.path.exists(requirements):
    kwargs['install_requires']=parse_requirements(requirements)

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
        "Programming Language :: Python :: 2.7",
        "Operating System :: POSIX",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
    **kwargs
)

