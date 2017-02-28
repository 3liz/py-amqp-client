# -*- coding: utf-8 -*-
"""
    Tests async client
"""
import logging
from tornado.ioloop import IOLoop
from tornado import gen
from functools import partial
from ..concurrent import  AsyncRPCClient, AsyncRPCWorker, AsyncConnection

ROUTE_KEY = "test_rpc"


@gen.coroutine
def run_test( args  ):
        
    def worker_handler( request ):
        cid = request.props.correlation_id
        logging.info(" [{}] request {}".format(cid, request.body))
        response = "cid={}".format(cid)
        request.reply(response)

    connection = AsyncConnection(host=args.host)

    client = AsyncRPCClient(connection=connection)
    worker = AsyncRPCWorker(connection=connection)
    
    yield client.connect()
    yield worker.connect(worker_handler, routing_key=ROUTE_KEY)

    responses = yield { i: client.call("=> request %s" % i, ROUTE_KEY, timeout=args.timeout) for i in range(args.requests) }    
    for i,rv in responses.items():
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
        
    args = parser.parse_args(sys.argv[1:])
    
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, args.logging.upper()))
    
    IOLoop.current().run_sync(partial(run_test,args))
 
    print("Done.")
    
