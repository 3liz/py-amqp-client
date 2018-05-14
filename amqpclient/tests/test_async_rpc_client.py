#
# Copyright 2018 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
    Tests async client
"""

from __future__ import (absolute_import, division, print_function)

import os
import logging
import pika
import multiprocessing as mp
import signal
import asyncio
from time import sleep

from ..concurrent import AsyncRPCClient


ROUTING_KEY='test_rpc'

   
def sig_handler(sig, frame):
   raise SystemExit();


def _run_worker( queue, host, response_delay):
    """
    """
    pid = os.getpid()
    
    logging.info(" [{}] worker started".format(pid))

    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=host))

    channel = connection.channel()
    channel.queue_declare(queue=queue)

    def on_request(ch, method, props, body):
        logging.info(" [{}] request cid={} {}".format(pid,props.correlation_id,body))
        response = "pid={} delay={}".format(pid, response_delay)

        sleep(response_delay)
        ch.basic_publish(exchange='',
                         routing_key=props.reply_to,
                         properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                         body=str(response))
        ch.basic_ack(delivery_tag = method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(on_request, queue=queue)

    # Install signal handler
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        logging.info(" [{}] Awaiting RPC requests".format(pid))
        channel.start_consuming()
    except SystemExit:
        logging.info("Stopping worker {}".format(os.getpid()))
        connection.close()
    

def run_worker(queue = ROUTING_KEY, response_delay = 1, host='localhost'): 
    p = mp.Process(target=_run_worker, args=(queue, host, response_delay))
    p.start()
    return p


async def run_client(args):
    client = AsyncRPCClient(host=args.host, reconnect_delay=args.reconnect_delay,
                                            reconnect_latency=args.latency)
    client.set_msg_expiration(8000)
    await client.connect()
    responses = await asyncio.gather(*[client.call("=> request %s" % i,ROUTING_KEY,timeout=args.timeout) for i in range(args.requests)])  
    for i,rv in enumerate(responses):
        print('***',i,rv)
    client.close()


if __name__ == "__main__":
    
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='Test Tornado async ampq client')
    parser.add_argument('--host', metavar='address', nargs='?', default='localhost', help="server address")
    parser.add_argument('--workers', nargs='?', type=int,  default=1, help="numbers workers")
    parser.add_argument('--requests', nargs='?', type=int,  default=5, help="numbers of requests")
    parser.add_argument('--timeout', nargs='?', type=int,  default=8, help="request timeout")
    parser.add_argument('--delay', nargs='?', type=int,  default=1, help="worker delay")
    parser.add_argument('--logging', choices=['debug', 'info', 'warning', 'error'], default='info', help="set log level")
    parser.add_argument('--latency'  , type=float, default=0.200, help="set reconnection latency")
    parser.add_argument('--reconnect-delay',  type=float, default=5, help="Reconnect delay")

    args = parser.parse_args(sys.argv[1:])
    
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(getattr(logging, args.logging.upper()))
    
    procs = [run_worker(response_delay=args.delay, host=args.host) for _ in range(args.workers)]

    try:
        asyncio.get_event_loop().run_until_complete(run_client(args))
    finally:
        for p in procs:
            p.terminate()
 
    print("Done.")
    
