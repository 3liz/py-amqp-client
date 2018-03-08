# -*- coding: utf-8 -*-
""" Handle asynchronous connections
"""

import logging
import pika
import traceback
import asyncio

from pika.adapters import AsyncioConnection


def Future():
    return asyncio.get_event_loop().create_future()


def _patch_method( obj, method_name, wrapper=lambda x:x ):
    """ Monkey patch bound method """
    real_bound_method = getattr(obj,method_name)
    def patched_method( self, **kwargs ):
        future = Future()
        real_bound_method(lambda rv: future.set_result(wrapper(rv)), **kwargs)
        return future
    setattr(obj,method_name,patched_method.__get__(obj))
               

def _patch_channel( channel ):
    """ Monkey patch async channel method so that channel
        return future
    """
    _patch_method(channel,'queue_declare')
    _patch_method(channel,'exchange_declare')
    _patch_method(channel,'queue_bind')
    return channel


def _patch_connection( conn ):
    """ Monkey patch connection to return future
        on async function
    """
    return _patch_method(conn, 'channel', _patch_channel)


class AsyncConnection(object):
    """ Asynchronous connection 
    """

    def __init__(self, host, port=5672, logger=None,
                 reconnect_delay = 5, reconnect_latency=0.200,
                 **connection_params):
        """ Create a new instance of worker publisher

            :param str host: Hostname or IP Address to connect to
            :param int port: TCP port to connect to
            :param float reconnect_delay: reconnection delay when trying to reconnect all nodes (in seconds)
            :param float reconnect_latency: latency between reconnection attempts (in seconds)
            :param function on_client_ready: callback that will be called on connection ready. Note that
               caller has to test the 'connected' status to check for failure        
        """
        if isinstance(host, str ):
            host = [host]

        self._connection = None
        self._closing = False
        self._logger = logger or logging.getLogger()
        self._reconnect_delay = reconnect_delay
        self._reconnect_latency = reconnect_latency
        self._cnxindex = 0 # Use round-robin strategy for reconnection
        self._cnxparams = [pika.ConnectionParameters(host=h, port=port, **connection_params) for h in host]
        self._io_loop    =  asyncio.get_event_loop()
        self._callbacks = [] 
        self._future = None

    def add_timeout(self, delay, callback, *args, **kwargs):
        return self._ioloop.call_later(delay, callback, *args, **kwargs)

    @property
    def io_loop(self):
        return self._io_loop

    @property
    def logger(self):
        return self._logger

    @property
    def closing(self):
        return self._closing

    def close(self):
        if self._connection:
            self._connection.close()
        self._connection = None
        self._callbacks  = []
        self._closing    = True

    def add_reconnect_callback( self, callback, *args, **kwargs ):
        """ add a callback to the open channel list. 
            If the connection has to be reinitialized,
            then all registered channels will be reinitialized
        """
        self._callbacks.append((callback,args,kwargs))

    def remove_callback( self, callback ):
        self._callbacks = [c for c in self._callbacks if c != callback]

    def _execute_callbacks(self):
        """ Execute all registered callbacks

            Called only when AMPQ connection is opened, this
            occurs on reconnection
        """
        def handle_error( exc ):
            if exc is not None:
                self._logger.error("Callback failed with exception <{}>".format(exc))

        for callback, args, kwargs in self._callbacks:
            try:
                result = callback(self._connection, *args, **kwargs)
                result.add_done_callback( lambda f: handle_error(f.exception()) )
            except Exception as e:
                handle_error(e)
                traceback.print_exc()                        
    
    def connect(self):
        """ Connects to RabbitMQ
           
            When the connection is established, the on_connection_open method
            will be invoked by pika and all registered callbacks will be executed
        """
        if self._closing:
            raise Exception("Cannot connect after closing connection")

        # Handle concurrency in the case we are waiting for connection to be established
        if self._future is not None:
            return self._future

        future = Future()
       
        # Return immediately if the connection is established
        if self._connection is not None:
            future.set_result(self._connection)
            return future

        # keep our future for concurrency
        self._future = future

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
              if self._future:
                  self._future.set_exception(e)
              else:
                  raise

        def open_handler( conn ):
            self._logger.info("AMQP Connection established")
            # Clear our future
            future = self._future 
            self._future = None
            self._connection = conn
            if reconnect:
                # Execute all registered connection callbacks
                self._execute_callbacks()
            if future is not None:
                future.set_result(conn)

        def closed_handler(connection, reply_code, reply_text):
            self.on_connection_close(reply_code, reply_text)

        cnxparams  = self._cnxparams[self._cnxindex]
        connection = AsyncioConnection(cnxparams,
                    on_open_callback       = open_handler,
                    on_open_error_callback = error_handler,
                    on_close_callback      = closed_handler)

        _patch_connection(connection)
  
    def handle_connection_error(self, error):
        """ Invoked if the connection cannot be (re)open 
     
            See the on_connection_close method.
        """
        self._logger.error("AMQP Connection Error: {}".format(error))    
            
        if self._closing:
            return

        self._connection = None

        # Create a new connection on the next node 
        # Set next connection backend as our failover
        self._cnxindex = (self._cnxindex + 1) % len(self._cnxparams)
        if self._cnxindex == 0:
            # All nodes all been tried
            if self._reconnect_delay > 0:
                self._logger.error("AMQP no nodes responding, waiting {} s before new attempts".format(self._reconnect_delay))
                self._ioloop.call_later(self._reconnect_delay, self._reconnect)
            else:
                self._logger.error("AMQP no nodes responding...")
                raise RuntimeError("Aborting AMQP connection")
        else:
            self._logger.error('AMQP Attempting reconnection in {} ms'.format(self._reconnect_latency*1000))
            self._ioloop.call_later(self._reconnect_latency, self._reconnect)

    def on_connection_close(self, reply_code, reply_text):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given

        """
        # XXX Attempt to reconnect only if connection has already  been established
        # This prevents race conditions with handle_connection_error
        if not self._closing and self._connection:
            self._connection = None
            self._logger.warning("AMQP Connection closed unexpectedly:{}:{}".format(reply_code, reply_text))
            self._reconnect()


class AsyncConnectionJob(object): 
    """ 
    """
    def __init__(self,  *args, **kwargs ):
        """ If the named argument 'connection' is given then it 
            will be used as the current connection.
            OtherWise a new connection is created from the passed arguments
        """
        connection = kwargs.pop('connection', None)
        if connection is None:
            connection = AsyncConnection( *args, **kwargs )
            self._own_connection = True
        else:
            self._own_connection = False

        self._connection = connection
        self._closing = False
        self._logger  = connection._logger

    @property
    def io_loop(self):
        return self._connection.io_loop

    @property
    def connection(self):
        return self._connection

    @property
    def logger(self):
        return self._logger

    def close(self):
        self._closing = True
        self._connection.remove_callback(self.initialize)
        if self._own_connection:
            self._connection.close()
        self._connection = None

    async def connect( self, *args, **kwargs):
        """ Open the connection and initialize the channel
        """
        # Set up connection
        conn = await self._connection.connect()

        # Initialize channels
        await self.initialize(conn, *args, **kwargs) 

        # Register are connection callback for reconnecting
        self._connection.add_reconnect_callback(self.initialize, *args, **kwargs)





                
