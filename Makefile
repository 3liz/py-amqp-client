.PHONY: qgis python manifest dockerfile

ifndef FABRIC
FABRIC:=$(shell [ -e .fabricrc ] && echo "fab -c .fabricrc" || echo "fab")
endif

PYPISERVER:=local

BUILDDIR=${shell pwd}/build

DIST=${BUILDDIR}/dist

build: manifest
	mkdir -p $(DIST)
	python setup.py bdist_wheel --dist-dir=$(DIST)

wheel:
	mkdir -p $(DIST)
	python setup.py bdist_wheel --dist-dir=$(DIST)

manifest:
	mkdir -p $(DIST)
	$(FABRIC) create_manifest:$(shell python setup.py --name),versiontag=$(shell python setup.py --version),directory=$(DIST)

upload:
	twine upload -r $(PYPISERVER) $(DIST)/*

# Build dependencies
deps:
	mkdir -p $(DIST)
	pip wheel -w=$(DIST) -r=requirements.txt

