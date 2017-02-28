.PHONY: qgis python manifest dockerfile


ifndef FABRIC
FABRIC:=$(shell [ -e .fabricrc ] && echo "fab -c .fabricrc" || echo "fab")
endif

BUILDDIR=${shell pwd}/build

DIST=${BUILDDIR}/dist

default: setup

build: manifest
	mkdir -p $(DIST)
	python setup.py sdist --dist-dir=$(DIST)

manifest:
	mkdir -p $(DIST)
	$(FABRIC) create_manifest:$(shell python setup.py --name),versiontag=$(shell python setup.py --version),directory=$(DIST)



