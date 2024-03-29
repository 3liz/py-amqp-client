#
# Copyright 2018 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

""" Implement pub/sub notifier as cli command
"""
import argparse
import logging
import signal
import sys

from .basic import BasicSubscriber


def subscribe():
    """ Wait for a notification from amqp broker
    """
    parser = argparse.ArgumentParser(description='AMQP subscriber')
    parser.add_argument('-H', '--host', metavar='address', default='localhost',
                        help="server address")
    parser.add_argument('-o', '--output', metavar='path', dest='output', default=None, help='Output message to file')
    parser.add_argument('-t', '--topic', dest='routing_key', default='', help='Message topic')
    parser.add_argument('--reconnect-delay', metavar='seconds', default=3, type=float, help="Reconnection delay")
    parser.add_argument('-x', '--exchange', dest='exchange', metavar='name', help="Exchange name", required=True)
    # Standard exchange type are 'topic','fanout','direct' or 'none' for using the default exchange]
    parser.add_argument('--exchange-type', default='none',
                        help="Exchange type")
    parser.add_argument('-V', '--virtual-host', dest='vhost', default=None)
    parser.add_argument('--credentials', metavar=('user', 'password'),  nargs=2)

    args = parser.parse_args()

    def terminate_handler(signum, frame):
        raise SystemExit("Caught signal {}".format(signum))

    signal.signal(signal.SIGTERM, terminate_handler)
    signal.signal(signal.SIGINT, terminate_handler)

    kwargs = {}

    if args.credentials is not None:
        import pika
        kwargs['credentials'] = pika.PlainCredentials(*args.credentials)

    if args.vhost is not None:
        kwargs['virtual_host'] = args.vhost

    logger = logging.getLogger('subscriber')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel('INFO')

    # Connect
    subscriber = BasicSubscriber(
        args.host,
        reconnect_delay=args.reconnect_delay,
        logger=logger,
        **kwargs,
    )

    exchange_type = args.exchange_type
    if exchange_type == 'none':
        exchange_type = None

    if args.output is not None:
        output = open(args.output, 'w')
    else:
        output = sys.stdout

    def handler(message):
        print(message.body.decode(), file=output)

    try:
        subscriber.run(
            args.exchange,
            handler=handler,
            exchange_type=exchange_type,
            routing_keys=args.routing_key,
        )
    except (KeyboardInterrupt, SystemExit) as e:
        print(e, file=sys.stderr)
        subscriber.close()


if __name__ == "__main__":
    subscribe()
