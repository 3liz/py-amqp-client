#
# Copyright 2018 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

""" Asyncronous pub/sub

    Supports for 'fanout', 'direct' and 'topic' exchanges

"""
import os
import pika
import weakref
import traceback
import asyncio
from collections import namedtuple
from .connection import AsyncConnectionJob

#
# Async Subscriber
#

Request = namedtuple("Request",('key','body','props') )

class AsyncSubscriber(AsyncConnectionJob):
    """ Asynchronous subscriber 
    """

    def __init__(self, *args, **kwargs):
        """ Create a new instance of worker subscriber
        """
        self._consumer_tag = None
        self._channel = None
        super(AsyncSubscriber, self).__init__(*args, **kwargs)

    async def initialize( self, connection, exchange, handler, exchange_type='fanout',
                          routing_keys=[]):

        self._channel = None
        self._channel = await connection.channel()

        if exchange_type is not None:
            await self._channel.exchange_declare(exchange=exchange, exchange_type=exchange_type)

        m = await self._channel.queue_declare(exclusive=True)
        if not routing_keys:
            # No routing keys: support for 'fanout'
            await self._channel.queue_bind(exchange=exchange, queue=m.method.queue) 
        else:
            # Bind onto multiple routing_keys: supports for
            # 'direct' and 'topic' exchange type
            if isinstance(routing_keys, str):
                routing_keys = [routing_keys]
            await asyncio.wait([self._channel.queue_bind(exchange=exchange, queue=m.method.queue,
                                            routing_key=k) for k in routing_keys])

        self._message_handler = handler  
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self._consumer_tag = self._channel.basic_consume(self.on_message, no_ack=True, 
                                                         queue=m.method.queue)

    def on_consumer_cancelled(self):
        self._logger.warn("AMQP Consummer cancelled")

    def _stop_consumming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
           Basic.Cancel RPC command.
        """
        if self._channel:
            self.logger.info('AMQP Cancelling RPC operation')
            self._channel.basic_cancel(consumer_tag=self._consumer_tag, nowait=True)

    def close(self):
        self._stop_consumming()
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        super(AsyncSubscriber, self).close()

    def on_message(self, chan, method, props, body):
        """ Called when receiving a message
        """
        try:
            self._message_handler(Request(method.routing_key, body, props))
        except Exception as e:
            self._logger.error("Uncaught exception in response_handler {}".format(e))
            traceback.print_exc()      


#
# Async Publisher client
#


class TimeoutError(Exception):
    pass

class AsyncPublisher(AsyncConnectionJob):

    def __init__(self, *args, **kwargs):
        """ Create a new instance of a  publisher
        """
        self._channel     = None
        self._expiration  = None
        super(AsyncPublisher, self).__init__(*args,**kwargs)

    def set_msg_expiration( self, expiration ):
        """ Set default message expiration time

            :param expiration: expiration delay in ms.  
        """
        if expiration is not None:
            self._expiration = "{:d}".format(expiration)
        else:
            self._expiration = None

    async def initialize( self, connection, exchange, exchange_type='fanout' ):
        """ Initialize the publisher
        """
        self._channel = None
        self._channel = await connection.channel()
        self._exchange = exchange

        if exchange_type is not None:
            await self._channel.exchange_declare(exchange=self._exchange, exchange_type=exchange_type)

    def close(self):
        if self._channel:
            self._channel.close()
            self._channel = None
        super(AsyncPublisher, self).close()

    def publish(self, message, routing_key='', expiration=None, content_type=None, 
                      content_encoding=None, headers=None):
        """ Send message to rabbitMQ server
        """
        if self._closing:
            raise Exception("Cannot publish after closing connection")

        if expiration is not None:
           expiration = "{:d}".format(expiration)
        else:
           expiration = self._expiration

        self._channel.basic_publish(exchange=self._exchange, 
                                    routing_key=routing_key,
                                    properties=pika.BasicProperties(
                                        expiration = expiration,
                                        content_type = content_type,
                                        content_encoding = content_encoding,
                                        headers = headers),
                                    body=message)

