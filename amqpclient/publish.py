#
# Copyright 2018 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

""" Implement pub/sub notifier as cli command
"""
from .basic import pika, BasicPublisher

import sys
import argparse 

def publish():
    """ Publish an amqp message notification
    """
    parser = argparse.ArgumentParser(description='AMQP publisher')
    parser.add_argument('-H','--host' , metavar='address', default='localhost',
                         help="server address")
    parser.add_argument('-i','--input', dest='input', metavar='path', help='Read message content from input file')
    parser.add_argument('-t','--topic', dest='routing_key', default='', help='Message topic')
    parser.add_argument('--reconnect-delay', metavar='seconds', default=3, type=float, help="Reconnection delay")
    parser.add_argument('-x','--exchange', dest='exchange', metavar='name', help="Exchange name", required=True)
    # Standard exchange type are 'topic','fanout','direct' or 'none' for using the default exchange] 
    parser.add_argument('--exchange-type', default='none', help="Exchange type")
    parser.add_argument('-X','--header', metavar=('key','value'), dest='headers', nargs=2, action='append', help="Header")
    parser.add_argument('--expiration', metavar='milliseconds', default=None, type=int, help="Message expiration")
    parser.add_argument('--content-type'    , default=None)
    parser.add_argument('--content-encoding' , default=None)
    parser.add_argument('-V','--virtual-host', dest='vhost', default=None)
    parser.add_argument('--credentials', metavar=('user', 'password'),  nargs=2)
 
    args = parser.parse_args()

    if args.input is not None:
        with open(args.input,'r') as f:
            message = f.read()
    else:
        message = ''
        # Enable reading from pipe
        for line in sys.stdin:
            message += line
 
    kwargs = {}

    if args.credentials is not None:
        kwargs['credentials'] = pika.PlainCredentials(*args.credentials)

    if args.vhost is not None:
        kwargs['virtual_host'] = args.vhost

    # Connect
    publisher = BasicPublisher(args.host, reconnect_delay=args.reconnect_delay, 
                               reconnect_latency=0, **kwargs);

    exchange_type = args.exchange_type
    if exchange_type == 'none':
        exchange_type = None

    if args.headers is not None:
        headers = dict(args.headers)
    else:
        headers = None

    publisher.initialize(args.exchange, args.exchange_type)
    publisher.publish(message, routing_key      = args.routing_key,
                               expiration       = args.expiration, 
                               content_type     = args.content_type,
                               content_encoding = args.content_encoding, 
                               headers = args.headers)
    publisher.close()


if __name__ == "__main__":
    publish()


