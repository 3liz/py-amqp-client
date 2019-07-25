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

DOCKER_IMAGE=$(REGISTRY_PREFIX)python:3.7-alpine

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
	$(PYTHON) -m amqpclient.tests.test_async_rpc_worker --host $(AMQP_HOST) --reconnect-delay=0
	$(PYTHON) -m amqpclient.tests.test_async_rpc_client --host $(AMQP_HOST) --reconnect-delay=0

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


BECOME_USER:=$(shell id -u)

LOCAL_HOME ?= $(shell pwd)

docker-test-run:
	mkdir -p $$(pwd)/.local $(LOCAL_HOME)/.cache
	docker network create net_$(COMMITID)
	docker run -d --rm --name amqp-rabbit-test-$(COMMITID) --net net_$(COMMITID)  $(REGISTRY_PREFIX)rabbitmq:3
	docker run --rm --name py-amqp-test-$(COMMITID) -w /src \
		-u $(BECOME_USER) \
		-v $$(pwd):/src \
		-v $$(pwd)/.local:/.local \
		-v $(LOCAL_HOME)/.cache:/.cache \
		-e PIP_CACHE_DIR=/.cache \
		-e AMQP_HOST=amqp-rabbit-test-$(COMMITID) \
		--net net_$(COMMITID) \
		$(DOCKER_IMAGE) ./run_tests.sh
	@echo "TESTS SUCCEEDED"

docker-test-cleanup:
	@docker stop amqp-rabbit-test-$(COMMITID)|| echo "Failed to remove container amqp-rabbit-test-$(COMMITID)"
	@docker network rm net_$(COMMITID) || echo "Failed to remove network net_$(COMMITID)"

# Clean up things if test fail
docker-test-failed: docker-test-cleanup
	@echo "TESTS FAILED !"
	@false

docker-test:
	$(MAKE) docker-test-run docker-test-cleanup || $(MAKE) docker-test-failed

