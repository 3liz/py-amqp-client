#!/bin/sh

set -e

pip3 install -U --user setuptools
pip3 install -U --user -r requirements.txt 

pip3 install --user -e ./ 

# Add /.local to path
export PATH=$PATH:/.local/bin

python3 -m amqpclient.tests.test_async_subscriber --host $AMQP_HOST --reconnect-delay=0
python3 -m amqpclient.tests.test_async_rpc_worker --host $AMQP_HOST --reconnect-delay=0
python3 -m amqpclient.tests.test_async_rpc_client --host $AMQP_HOST --reconnect-delay=0

