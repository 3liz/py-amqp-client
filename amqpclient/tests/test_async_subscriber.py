#
# Copyright 2018 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

""" Tests async subscriber 
"""
import asyncio
import logging

from ..concurrent import AsyncPublisher, AsyncSubscriber, AsyncConnection

EXCHANGE = "test_pubsub"

async def run_test( args  ):
        
    def message_handler( request ):
        logging.info("===> Received {} {}".format(request.key, request.body))
    
    connection = AsyncConnection(host=args.host, 
                                 reconnect_delay=args.reconnect_delay,
                                 reconnect_latency=args.latency)

    sub = AsyncSubscriber(connection=connection)
    pub = AsyncPublisher(connection=connection)
 
    await sub.connect(EXCHANGE, message_handler)
    await pub.connect(EXCHANGE)

    # run calls
    for i in range(args.requests):
        pub.publish("message {}".format(i)) 

    await asyncio.sleep(2)

    sub.close()
    pub.close()
    connection.close()


if __name__ == "__main__":
    
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='Test Tornado async ampq pub/sub')
    parser.add_argument('--host', metavar='address', nargs='?', default='localhost', help="server address")
    parser.add_argument('--requests' , nargs='?', type=int,  default=5, help="numbers of requests")
    parser.add_argument('--logging'  , choices=['debug', 'info', 'warning', 'error'], default='info', help="set log level")
    parser.add_argument('--latency'  , type=float, default=0.200, help="set reconnection latency")
    parser.add_argument('--reconnect-delay',  type=float, default=5, help="Reconnect delay")

    args = parser.parse_args(sys.argv[1:])
    
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(getattr(logging, args.logging.upper()))
    
    asyncio.get_event_loop().run_until_complete(run_test(args))
 
    print("Done.")
    
