.PHONY: test 

BUILDID=$(shell date +"%Y%m%d%H%M")
COMMITID=$(shell git rev-parse --short HEAD)

PYPISERVER:=storage

BUILDDIR=build
DIST=${BUILDDIR}/dist

MANIFEST=factory.manifest

PYTHON:=python3

ifdef REGISTRY_URL
	REGISTRY_PREFIX=$(REGISTRY_URL)/
endif

DOCKER_IMAGE=$(REGISTRY_PREFIX)python-3.6:latest

dirs:
	mkdir -p $(DIST)

manifest:
	echo name=$(shell $(PYTHON) setup.py --name) > $(MANIFEST) && \
		echo version=$(shell $(PYTHON) setup.py --version) >> $(MANIFEST) && \
		echo buildid=$(BUILDID)   >> $(MANIFEST) && \
		echo commitid=$(COMMITID) >> $(MANIFEST)

AMQP_HOST:=localhost

test:
	@echo "INFO: tests requires a running amqp server"
	$(PYTHON) -m amqpclient.tests.test_async_subscriber --host $(AMQP_HOST) --reconnect-delay=0

# Build dependencies
deps: dirs
	pip wheel -w $(DIST) -r requirements.txt

wheel: deps
	mkdir -p $(DIST)
	$(PYTHON) setup.py bdist_wheel --dist-dir=$(DIST)

deliver:
	twine upload -r $(PYPISERVER) $(DIST)/*

dist: dirs manifest
	$(PYTHON) setup.py sdist --dist-dir=$(DIST)

clean:
	rm -rf $(BUILDDIR)




