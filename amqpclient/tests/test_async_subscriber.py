# -*- coding: utf-8 -*-
""" Tests async subscriber 
"""
import logging
from tornado.ioloop import IOLoop
from tornado import gen
from functools import partial

from ..concurrent import AsyncPublisher, AsyncSubscriber, AsyncConnection

EXCHANGE = "test_pubsub"

@gen.coroutine
def run_test( args  ):
        
    def message_handler( request ):
        logging.info("===> Received {} {}".format(request.key, request.body))
    
    connection = AsyncConnection(host=args.host, reconnect_delay=args.reconnect_delay,
                                                 reconnect_latency=args.latency)

    sub = AsyncSubscriber(connection=connection)
    pub = AsyncPublisher(connection=connection)
 
    yield sub.connect(EXCHANGE, message_handler)
    yield pub.connect(EXCHANGE)

    # run calls
    for i in range(args.requests):
        pub.publish("message {}".format(i)) 

    yield gen.sleep(2)

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
    logger.setLevel(getattr(logging, args.logging.upper()))
    
    IOLoop.instance().run_sync(partial(run_test, args))
 
    print("Done.")
    
