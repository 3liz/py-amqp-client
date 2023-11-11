#
# Copyright 2018 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Define a logger based on amqp
"""

import asyncio
import logging
import os
import sys
import traceback

from .pub import AsyncPublisher


class Handler(logging.Handler):
    """ A logging handler that push notifications to RabbitMQ
    """

    def __init__(self,
                 exchange, routing_key,
                 connection=None,
                 host=None,
                 level=logging.NOTSET,
                 formatstr='%(asctime)s\t%(levelname)s\t%(hostname)s\t[%(process)d]\t%(message)s',
                 content_type='text/plain',
                 message_ttl=3000):

        self._content_type = content_type
        self._routing_key = routing_key
        self._client = AsyncPublisher(connection=connection, host=host)
        self._hostname = os.uname()[1]
        self._client.set_msg_expiration(message_ttl)

        # Catche exception in connection
        async def connect():
            # TODO TEST ME ON FAILURE
            try:
                await self._client.connect(exchange=exchange, exchange_type='topic')
                print("AMQP logger initialized.", file=sys.stderr)
            except Exception:
                traceback.print_exc()
                print("Failed to initialize AMQP logger.", file=sys.stderr)

        asyncio.ensure_future(connect())

        super(Handler, self).__init__(level)
        # Set formatter
        if formatstr is not None:
            self.setFormatter(logging.Formatter(formatstr))

    def createlock(self):
        pass

    def acquire(self):
        pass

    def release(self):
        pass

    def flush(self):
        pass

    def close(self):
        pass

    def emit(self, record):
        """ Publish log message
        """
        record.__dict__.update(hostname=self._hostname)
        self._client.publish(self.format(record),
                             routing_key=self._routing_key % record.__dict__,
                             content_type=self._content_type,
                             content_encoding='utf-8')
