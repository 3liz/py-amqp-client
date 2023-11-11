.PHONY: test 

BUILDID=$(shell date +"%Y%m%d%H%M")
COMMITID=$(shell git rev-parse --short HEAD)

PYPISERVER:=storage

PYTHON_PKG=amqpclient

SDIST=build

MANIFEST=factory.manifest

PYTHON:=python3

manifest:
	echo name=$(shell $(PYTHON) setup.py --name) > $(MANIFEST) && \
		echo version=$(shell $(PYTHON) setup.py --version) >> $(MANIFEST) && \
		echo buildid=$(BUILDID)   >> $(MANIFEST) && \
		echo commitid=$(COMMITID) >> $(MANIFEST)

lint: 
	@flake8 $(PYTHON_PKG) 

autopep8:
	@autopep8 -v --in-place -r --max-line-length=120 $(AUTOPEP8_EXTRA_ARGS) $(PYTHON_PKG)

test: lint
	@echo "INFO: tests requires a running amqp server"
	$(PYTHON) -m amqpclient.tests.test_async_subscriber --host $(AMQP_HOST) --reconnect-delay=0
	$(PYTHON) -m amqpclient.tests.test_async_rpc_worker --host $(AMQP_HOST) --reconnect-delay=0
	$(PYTHON) -m amqpclient.tests.test_async_rpc_client --host $(AMQP_HOST) --reconnect-delay=0

deliver:
	twine upload -r $(PYPISERVER) $(DIST)/*

dist: manifest
	mkdir -p $(SDIST)
	rm -rf *.egg-info
	$(PYTHON) setup.py sdist --dist-dir=$(DIST)

clean:
	rm -rf $(SDIST) *.egg-info
