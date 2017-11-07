# -*- coding: utf-8 -*-
""" Implement pub/sub notifier as cli command
"""

# XXX Keep python2 compatibility 
from __future__ import (absolute_import, division, print_function)

from .basic import BasicSubscriber

import signal
import sys
import argparse 


def subscribe():
    """ Wait for a notification from amqp broker
    """
    parser = argparse.ArgumentParser(description='AMQP subscriber')
    parser.add_argument('-H','--host' , metavar='address', default='localhost',
                         help="server address")
    parser.add_argument('-o','--output', metavar='path', dest='output', default=None, help='Output message to file')
    parser.add_argument('-t','--topic', dest='routing_key', default='', help='Message topic')
    parser.add_argument('--reconnect-delay', metavar='seconds', default=3, type=float, help="Reconnection delay")
    parser.add_argument('-x','--exchange', dest='exchange', metavar='name', help="Exchange name", required=True)
    parser.add_argument('--exchange-type', choices=['topic','fanout','direct','none'],  default='fanout', 
                        help="Exchange type")
    parser.add_argument('-V','--virtual-host', dest='vhost', default=None)
    parser.add_argument('--credentials', metavar=('user', 'password'),  nargs=2)

    args = parser.parse_args()

    def terminate_handler(signum, frame):
        raise SystemExit("Caught signal {}".format(signum))

    signal.signal(signal.SIGTERM, terminate_handler)
    signal.signal(signal.SIGINT , terminate_handler)

    kwargs = {}

    if args.credentials is not None:
        kwargs['credentials'] = pika.PlainCredentials(*args.credentials)

    if args.vhost is not None:
        kwargs['virtual_host'] = args.vhost

    # Connect
    subscriber = BasicSubscriber(args.host, reconnect_delay=args.reconnect_delay, 
                                 reconnect_latency=0, **kwargs);

    exchange_type = args.exchange_type
    if exchange_type == 'none':
        exchange_type = None

    if args.output is not None:
        output = open(args.output,'w')
    else:
        output = sys.stdout

    def handler( message ):
        print( message.body, file=output)
        subscriber.close()

    try:
       subscriber.run(args.exchange, 
                      handler = handler, 
                      exchange_type=exchange_type,
                      routing_keys=args.routing_key)
    except SystemExit as e:
        print(e, file=sys.stderr)
        subscriber.close() 

if __name__ == "__main__":
    subscribe()


