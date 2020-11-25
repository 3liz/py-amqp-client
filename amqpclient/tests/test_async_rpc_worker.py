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

import asyncio
import logging
from ..concurrent import  AsyncRPCClient, AsyncRPCWorker, AsyncConnection

ROUTE_KEY = "test_rpc"


async def run_test( args  ):
        
    def worker_handler( request ):
        cid = request.props.correlation_id
        logging.info(" [{}] request {}".format(cid, request.body))
        response = "cid={}".format(cid)
        request.reply(response)

    connection = AsyncConnection(host=args.host, 
                                 reconnect_delay=args.reconnect_delay,
                                 reconnect_latency=args.latency)

    client = AsyncRPCClient(connection=connection)
    worker = AsyncRPCWorker(connection=connection)
    
    await client.connect()
    await worker.connect(worker_handler, routing_key=ROUTE_KEY)

    responses = await asyncio.gather(*[client.call("=> request %s" % i, ROUTE_KEY, timeout=args.timeout) for i in range(args.requests)] )
    for i,rv in enumerate(responses):
        print('***',i,rv)

    worker.close()
    client.close()
    connection.close()


if __name__ == "__main__":
    
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='Test Tornado async ampq client')
    parser.add_argument('--host', metavar='address', nargs='?', default='localhost', help="server address")
    parser.add_argument('--requests', nargs='?', type=int,  default=5, help="numbers of requests")
    parser.add_argument('--timeout', nargs='?', type=int,  default=5, help="request timeout")
    parser.add_argument('--delay', nargs='?', type=int,  default=1, help="worker delay")
    parser.add_argument('--logging', choices=['debug', 'info', 'warning', 'error'], default='info', help="set log level")
    parser.add_argument('--latency'  , type=float, default=0.200, help="set reconnection latency")
    parser.add_argument('--reconnect-delay',  type=float, default=5, help="Reconnect delay")

    args = parser.parse_args(sys.argv[1:])
    
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(getattr(logging, args.logging.upper()))
   
    asyncio.get_event_loop().run_until_complete(run_test(args))
 
    print("Done.")
    
