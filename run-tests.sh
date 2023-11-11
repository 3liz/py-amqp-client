#!/bin/sh

set -e

AMQP_HOST=${AMQP_HOST:-localhost}

python3 -m amqpclient.tests.test_async_subscriber --host $AMQP_HOST
python3 -m amqpclient.tests.test_async_rpc_worker --host $AMQP_HOST
python3 -m amqpclient.tests.test_async_rpc_client --host $AMQP_HOST

