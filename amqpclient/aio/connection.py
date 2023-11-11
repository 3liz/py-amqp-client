#
# Copyright 2018 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

""" Handle asynchronous connections
"""

import asyncio
import logging
import traceback

import pika

from pika.adapters.asyncio_connection import AsyncioConnection
from typing_extensions import Awaitable, Callable, List


class ConnectionAttemptExhausted(Exception):
    pass


def add_timeout(delay, callback, *args, **kwargs):
    return asyncio.get_running_loop().call_later(delay, callback, *args, **kwargs)


def Future():
    """ Shortcut to Future creation
    """
    return asyncio.get_running_loop().create_future()


def _patch_method(obj, method_name):
    """ Monkey patch bound method

        Patch method that use callback so that it returns a future
        The future will be resolved when the callback is
        called.
    """
    real_bound_method = getattr(obj, method_name)

    def patched_method(self, **kwargs):
        future = Future()
        real_bound_method(callback=lambda rv: future.set_result(rv), **kwargs)
        return future
    setattr(obj, method_name, patched_method.__get__(obj))


def _patch_channel(channel):
    """ Monkey patch async channel method so that channel
        callback methods returns futures
    """
    _patch_method(channel, 'queue_declare')
    _patch_method(channel, 'exchange_declare')
    _patch_method(channel, 'queue_bind')
    return channel


def _patch_connection(conn):
    """ Monkey patch connection to return future
        on channel function callback create method.
    """
    real_bound_method = getattr(conn, 'channel')

    def patched_method(self, **kwargs):
        future = Future()
        real_bound_method(on_open_callback=lambda rv: future.set_result(_patch_channel(rv)),
                          **kwargs)
        return future
    setattr(conn, 'channel', patched_method.__get__(conn))


class AsyncConnection:
    """ Asynchronous connection
    """

    def __init__(
        self,
        host: str | List[str],
        port: int = 5672,
        logger: logging.Logger = None,
        reconnect_always: bool = True,
        reconnect_delay: int = 5,
        **connection_params,
    ):
        """ Create a new instance of worker publisher

            :param str host: Hostname or IP Address to connect to
            :param int port: TCP port to connect to
            :param float reconnect_delay: reconnection delay when trying to reconnect all nodes (in seconds)
            :param float reconnect_always: always attempts reconnection)
        """
        if reconnect_delay <= 0:
            raise ValueError("reconnect_delay must be positive integer")

        if isinstance(host, str):
            host = [host]

        self._connection = None
        self._closing = False
        self._logger = logger or logging.getLogger()
        self._reconnect_always = reconnect_always
        self._reconnect_delay = reconnect_delay
        self._cnxindex = 0  # Use round-robin strategy for reconnection
        self._cnxparams = [pika.ConnectionParameters(host=h, port=port, **connection_params) for h in host]
        self._callbacks = []
        self._connect_future = None

    @property
    def logger(self):
        return self._logger

    @property
    def connected(self):
        return self._connection and self._connection.is_open

    @property
    def closing(self):
        return self._closing

    def close(self):
        if self._connection:
            self._connection.close()
        self._connection = None
        self._callbacks = []
        self._closing = True

    def add_reconnect_callback(self, callback: Callable[[], Awaitable], *args, **kwargs):
        """ Add a callback to run when reconnecting.

            If the connection has to be reinitialized,
            then all registered channels will be reinitialized
        """
        self._callbacks.append((callback, args, kwargs))

    def remove_callback(self, callback: Callable):
        self._callbacks = [c for c in self._callbacks if c != callback]

    async def _execute_callbacks(self):
        """ Execute all registered callbacks

            Called only when AMPQ connection is opened, this
            occurs on reconnection
        """
        for callback, args, kwargs in self._callbacks:
            try:
                await callback(self._connection, *args, **kwargs)
            except Exception as err:
                self._logger.error(
                    "Callback failed with exception <%s>\n%s",
                    err,
                    traceback.format_exc()
                )

    def connect(self) -> Awaitable:
        """ Connects to RabbitMQ

            When the connection is established, the on_connection_open method
            will be invoked by pika and all registered callbacks will be executed
        """
        if self._closing:
            raise Exception("Cannot connect after closing connection")

        # Handle concurrency in the case we are waiting for connection to be established
        if self._connect_future is not None:
            return self._connect_future

        future = Future()

        # Return immediately if the connection is established
        if self._connection is not None:
            future.set_result(self._connection)
            return future

        # keep our future for concurrency
        self._connect_future = future

        self._reconnect(False)
        return future

    def _reconnect(self, reconnect=True):
        """ Handle reconnection
        """

        def error_handler(_unused, message):
            try:
                self.handle_connection_error(message)
            except Exception as e:
                # Handle abort connection exception
                if self._connect_future:
                    self._connect_future.set_exception(e)
                else:
                    raise

        def open_handler(conn):
            self._logger.info("AMQP Connection established")
            # Clear our future
            future = self._connect_future
            self._connect_future = None
            self._connection = conn
            if reconnect:
                # Schedule all registered connection callbacks
                asyncio.create_task(self._execute_callbacks())
            if future is not None:
                future.set_result(conn)

        def closed_handler(_unused_connection, reason):
            self.on_connection_close(reason)

        cnxparams = self._cnxparams[self._cnxindex]
        connection = AsyncioConnection(
            cnxparams,
            on_open_callback=open_handler,
            on_open_error_callback=error_handler,
            on_close_callback=closed_handler,
        )

        _patch_connection(connection)

    def handle_connection_error(self, error):
        """ Invoked if the connection cannot be (re)open

            See the on_connection_close method.
        """
        self._logger.error("AMQP Connection Error: {}".format(error))

        if self._closing:
            return

        self._connection = None

        cluster_size = len(self._cnxparams)

        # Create a new connection on the next node
        # Set next connection backend as our failover

        cnxindex = self._cnxindex + 1
        if cnxindex >= cluster_size:
            # All nodes have been tried
            # If we do not mean to reconnect, leave the field
            if not self._reconnect_always:
                raise ConnectionAttemptExhausted()
            else:
                self._cnxindex = 0
                self._logger.error(
                    "AMQP no nodes responding, waiting %s s before new attempts", self._reconnect_delay)
                add_timeout(self._reconnect_delay, self._reconnect)
        else:
            # Try on next node
            self._cnxindex = cnxindex % cluster_size
            add_timeout(1, self._reconnect)

    def on_connection_close(self, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param str reason: The server provided reason if given

        """
        # XXX Attempt to reconnect only if connection has already  been established
        # This prevents race conditions with handle_connection_error
        if not self._closing and self._connection:
            self._connection = None
            self._logger.warning("AMQP Connection closed unexpectedly: %s", reason)
            self._reconnect()


class AsyncConnectionJob:
    """
    """

    def __init__(self,  *args, **kwargs):
        """ If the named argument 'connection' is given then it
            will be used as the current connection.
            OtherWise a new connection is created from the passed arguments
        """
        connection = kwargs.pop('connection', None)
        if connection is None:
            connection = AsyncConnection(*args, **kwargs)
            self._own_connection = True
        else:
            self._own_connection = False

        self._connection = connection
        self._closing = False
        self._logger = connection._logger

    @property
    def connection(self):
        return self._connection

    @property
    def connected(self):
        return self._connection.connected

    @property
    def logger(self):
        return self._logger

    def close(self):
        self._closing = True
        self._connection.remove_callback(self.initialize)
        if self._own_connection:
            self._connection.close()
        self._connection = None

    async def connect(self, *args, **kwargs):
        """ Open the connection and initialize the channel
        """
        # Set up connection
        conn = await self._connection.connect()

        # Initialize channels
        await self.initialize(conn, *args, **kwargs)

        # Register our initialize callback to use when reconnecting
        self._connection.add_reconnect_callback(self.initialize, *args, **kwargs)

    async def initialize(self, *args, **kwargs):
        ...
