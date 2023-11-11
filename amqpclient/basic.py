#
# Copyright 2018-2023 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

""" AMQP blocking Connections

    Define a basic blocking connection as base class
    for other AMQP schemes.

    The BlockingConnection object supports multiple
    hosts and implements reconnection strategy in case of error.
"""

import logging
import os
import traceback

from contextlib import contextmanager
from dataclasses import dataclass
from time import sleep

import pika

from pika.exceptions import AMQPConnectionError
from typing_extensions import Any, Callable, List, Self


class CloseConnection(Exception):
    pass


class ConnectionAttemptExhausted(Exception):
    pass


class BlockingConnection:
    """ Define a basic blocking connection with reconnect fallback
    """

    def __init__(
        self,
        host: str | List[str],
        port: int = 5672,
        reconnect_always: bool = True,
        reconnect_delay: int = 5,
        logger: logging.Logger = None,
        **connection_params,
    ):
        """ Create a new worker instance

            :param str host: Hostname or IP Address to connect to
            :param int port: TCP port to connect to
            :param float reconnect_delay: delay between reconnection attempts (in seconds)
        """

        if reconnect_delay <= 0:
            raise ValueError("reconnect_delay must be positive integer")
        self._reconnect_always = reconnect_always
        self._reconnect_delay = reconnect_delay
        self._closing = False
        self._cnxindex = 0
        self._connection = None

        self.logger = logger or logging.getLogger()

        if not isinstance(host, (tuple, list)):
            host = [host]

        self._cnxparams = [pika.ConnectionParameters(
            host=h,
            port=port,
            **connection_params
        ) for h in host]

    def close(self):
        self._closing = True
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def handle_connection_error(self, error):
        """ Handle connection strategy on connection error
        """
        self._connection = None

        cluster_size = len(self._cnxparams)
        self.logger.error("AMQP connection error {}".format(error))

        # Attempt reconnection
        # Set next connection backend as our failover
        cnxindex = self._cnxindex + 1
        if cnxindex >= cluster_size:
            # All nodes have been tried
            # If we do not mean to reconnect, leave the field
            if not self._reconnect_always:
                raise ConnectionAttemptExhausted()
            else:
                self._cnxindex = 0
                self.logger.error(
                    "AMQP: no nodes responding, waiting %s s before new attempts",
                    self._reconnect_delay,
                )
                sleep(self._reconnect_delay)
        else:
            self._cnxindex = cnxindex % cluster_size

    def connect(self) -> Self:
        """ Open connection
            Call connect() with the new connection as param.
        """
        if not self._connection:
            self._connection = pika.BlockingConnection(self._cnxparams[self._cnxindex])
        return self

    def new_channel(self) -> pika.channel.Channel:
        """ Return a new channel for this connection

            Open the connection if neeeded
        """
        self.connect()
        return self._connection.channel()

    @property
    def closing(self) -> bool:
        return self._closing

    @contextmanager
    def channel(self) -> pika.channel.Channel:
        """ Managed channel
        """
        if self._closing:
            raise RuntimeError("AMQP: Cannot create channel after closing")

        channel = self.new_channel()
        try:
            yield channel
        finally:
            if not channel.is_closed:
                channel.close()

#
# Define request object
#


@dataclass(frozen=True)
class Request:
    body: Any
    props: pika.BasicProperties
    reply: Callable


#
# Basic blocking RPC worker
#
class BasicWorker(BlockingConnection):
    """ Define a basic synchronous RPC  worker
    """

    def on_message(self, chan, method, props, body):
        """ Called when receivisg a message

            Keep same behavior as for the asynchronous case: no return values
            is expected: instead' a 'reply' function is passed to the handler
        """
        def reply(response, content_type=None, content_encoding=None, headers=None):
            """ Define a reply method that will be passed to the handler
            """
            chan.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(
                    correlation_id=props.correlation_id,
                    expiration=props.expiration,
                    content_type=content_type,
                    content_encoding=content_encoding,
                    headers=headers,
                    delivery_mode=1
                ),
                body=response,
            )
        try:
            self._reply_handler(Request(body, props, reply))
        except Exception as err:
            logging.error(
                "Uncaught exception in response_handler %s\n%s",
                str(err),
                traceback.format_exc(),
            )
        finally:
            # Force acknoweldgement
            chan.basic_ack(delivery_tag=method.delivery_tag)

    def run(self, routing_key: str, request_handler: Callable):
        """ Run blocking rpc worker
        """
        self._handler = request_handler
        while not self.closing:
            try:
                with self.channel() as channel:
                    channel.queue_declare(queue=routing_key)
                    # This is required for fair queuing
                    channel.basic_qos(prefetch_count=1)
                    channel.basic_consume(on_message_callback=self.on_message, queue=routing_key)
                    self.logger.info("[%s] RPC worker ready", os.getpid())
                    channel.start_consuming()
            except AMQPConnectionError as err:
                # Retry connection
                self.handle_connection_error(err)
            except CloseConnection:
                self.close()


#
# Blocking subscriber
#


@dataclass(frozen=True)
class Message:
    key: str
    body: Any
    props: pika.BasicProperties


class BasicSubscriber(BlockingConnection):
    """ Define a basic synchronous subscriber

        Creating a publisher:

            channel = connection.new_channel()
            channel.exchange_declare(exchange=topic, exchange_type='fanout')
            self._channel = channel

            # publish:
            channel.basic_publish(exchange=topic, routing_key='', body=message)
    """

    def run(self, exchange, handler, exchange_type='fanout', routing_keys=[]):
        while not self.closing:
            try:
                with self.channel() as channel:
                    if exchange_type is not None:
                        channel.exchange_declare(exchange=exchange, exchange_type=exchange_type)

                    result = channel.queue_declare(queue="", exclusive=True)
                    queue_name = result.method.queue

                    if not routing_keys:
                        # No routing keys: support for 'fanout'
                        channel.queue_bind(exchange=exchange, queue=queue_name)
                    else:
                        # Bind onto multiple routing_keys: supports for 'direct' and
                        # 'topic' exchange type
                        if isinstance(routing_keys, str):
                            routing_keys = [routing_keys]
                        for key in routing_keys:
                            channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=key)

                    def _on_message(chan, method, props, body):
                        try:
                            handler(Message(method.routing_key, body, props))
                        except Exception as err:
                            self.logger.error(
                                "Uncaught exception in message_handler %s\n%s",
                                str(err),
                                traceback.format_exc(),
                            )

                    channel.basic_consume(on_message_callback=_on_message, queue=queue_name, auto_ack=True)

                    self.logger.info("AMQP Subscriber ready")
                    channel.start_consuming()
            except AMQPConnectionError as err:
                # Retry connection
                self.handle_connection_error(err)
            except CloseConnection:
                self.close()


#
# Blocking publisher
#


class BasicPublisher:
    """ Define a basic synchronous publisher
    """

    def __init__(self, *args, **kwargs):
        """ Create a new instance of a  publisher
        """
        self._exchange = None
        self._exchange_type = None
        self._channel = None
        connection = kwargs.get('connection')
        if not connection:
            connection = BlockingConnection(*args, **kwargs)
            self._owned_connection = True
        else:
            self._owned_connection = False
        self._connection = connection

    def close(self):
        if self._channel:
            self._channel.close()
            self._channel = None
        if self._owned_connection:
            self._connection.close()

    @property
    def connection(self) -> BlockingConnection:
        return self._connection

    def initialize(self, exchange, exchange_type='fanout'):
        """
        """
        self._exchange = exchange
        self._exchange_type = exchange_type

    def publish(self, message, routing_key='', expiration=None, content_type=None,
                content_encoding=None, headers=None):
        """ Send message to rabbitMQ server
        """
        if self._connection.closing:
            raise Exception("Cannot publish after closing connection")

        if self._exchange is None:
            raise RuntimeError("Bad exchange value: did you forget to call initialize() ?")

        done = False

        if expiration is not None:
            expiration = "{:d}".format(expiration)

        while not done:
            try:
                if self._channel is None:
                    self._channel = self._connection.new_channel()
                    if self._exchange_type != 'none':
                        self._channel.exchange_declare(exchange=self._exchange, exchange_type=self._exchange_type)

                self._channel.basic_publish(
                    exchange=self._exchange,
                    routing_key=routing_key,
                    properties=pika.BasicProperties(
                        expiration=expiration,
                        content_type=content_type,
                        content_encoding=content_encoding,
                        headers=headers),
                    body=message
                )
                done = True
            except AMQPConnectionError as e:
                self._channel = None
                self._connection.handle_connection_error(e)
