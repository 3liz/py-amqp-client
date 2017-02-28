# -*- coding: utf-8 -*-
""" Implement pub/sub notifier as cli command
"""
from .basic import BasicPublisher

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
    parser.add_argument('--exchange-type', choices=['topic','fanout','direct','none'],  default='fanout', 
                        help="Exchange type")
    parser.add_argument('-X','--header', metavar=('key','value'), dest='headers', nargs=2, action='append', help="Header")
    parser.add_argument('--expiration', metavar='milliseconds', default=None, type=int, help="Message expiration")
    parser.add_argument('--content-type'    , nargs='?', default=None)
    parser.add_argument('--content-encoding', nargs='?', default=None)
 
    args = parser.parse_args()

    if args.input is not None:
        with open(args.input,'r') as f:
            message = f.read()
    else:
        message = ''
        # Enable reading from pipe
        for line in sys.stdin:
            message += line
  
    # Connect
    publisher = BasicPublisher(args.host, reconnect_delay=args.reconnect_delay, 
                               reconnect_latency=0);

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


