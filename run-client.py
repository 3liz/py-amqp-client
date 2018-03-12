#!/usr/bin/env python
import asyncio
import logging

from amqpclient.concurrent import AsyncSubscriber, AsyncConnection

EXCHANGE = "test_sub_reconnect"

if __name__ == "__main__":
    
    import sys
    import argparse
    parser = argparse.ArgumentParser(description='Test Tornado async ampq pub/sub')
    parser.add_argument('--host', metavar='address', nargs='?', default='localhost', help="server address")
    parser.add_argument('--logging'  , choices=['debug', 'info', 'warning', 'error'], default='info', help="set log level")
    parser.add_argument('--latency'  , type=float, default=0.200, help="set reconnection latency")
    parser.add_argument('--reconnect-delay',  type=float, default=5, help="Reconnect delay")

    args = parser.parse_args(sys.argv[1:])
    
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(getattr(logging, args.logging.upper()))
   
    ioloop = asyncio.get_event_loop()

    def message_handler( request ):
        logging.info("===> Received {} {}".format(request.key, request.body))

    connection = AsyncConnection(host=args.host, reconnect_delay=args.reconnect_delay,
                                                 reconnect_latency=args.latency, logger=logger)

    sub = AsyncSubscriber(connection=connection)
    asyncio.ensure_future( sub.connect(EXCHANGE, message_handler)  )

    ioloop.run_forever()
 
    print("Done.")
 
