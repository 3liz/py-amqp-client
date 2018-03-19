# -*- coding: utf-8 -*-
"""
Define rpc client/server library 

    - fair queuing
    - Asynchronous send/receipt message
    
    The client declare a transient exclusive queue

"""
import asyncio
import sys
import os
import pika
import uuid
import traceback
from collections import namedtuple

from .connection import AsyncConnectionJob


#
# Async RPC worker
#

Request = namedtuple('Request', ('body','props','reply'))

class AsyncRPCWorker(AsyncConnectionJob):
    """ Asynchronous worker 
    """

    def __init__(self, *args, **kwargs):
        """ Create a new instance of worker publisher
        """
        self._reply_handler = None
        self._routing_key   = None
        self._consumer_tag  = None
        self._channel       = None

        super(AsyncRPCWorker, self).__init__(*args, **kwargs)

    async def initialize( self, connection, handler, routing_key ):
        """ Connect to queue 'routing_key'
        
            This method sets up the consumer by first calling
            add_on_cancel_callback so that the object is notified if RabbitMQ
            cancels the consumer. It then issues the Basic.Consume RPC command
            which returns the consumer tag that is used to uniquely identify the
            consumer with RabbitMQ. We keep the value to use it when we want to
            cancel consuming. The on_message method is passed in as a callback pika
            will invoke when a message is fully received.
        
            :param handler: handler function
                Will be called as (body, cid, reply_fun)
                IMPORTANT: handler must be *reentrant*            
        """

        self._channel = None
        self._routing_key = routing_key
        self._channel = await connection.channel()

        await self._channel.queue_declare(queue=self._routing_key)

        self._reply_handler = handler
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)
        # Required for fair queuing
        self._channel.basic_qos(prefetch_count=1)
        self._consumer_tag  = self._channel.basic_consume(self.on_message, queue=self._routing_key)

    def on_consumer_cancelled(self):
        self.logger.warn("AMQP Consummer cancelled")

    def _stop_consumming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
           Basic.Cancel RPC command.
        """
        if self._channel:
            self.logger.info('AMQP Cancelling RPC operation')
            self._channel.basic_cancel(consumer_tag=self._consumer_tag, nowait=True)

    def close(self):
        self._stop_consumming()
        if self._channel:
            self._channel.close()
            self._channel = None
        super(AsyncRPCWorker, self).close()

    def on_message(self, chan, method, props, body):
        """ Called when receivisg a message

            The handler is assumed to be asynchronous and thus no return values
            is expected: instead' a 'reply' function is passed to the handler 
        """
        def reply( response, content_type=None, content_encoding=None, headers=None ):
            chan.basic_publish(exchange='',
                               routing_key=props.reply_to,
                               properties=pika.BasicProperties(correlation_id = props.correlation_id,
                                                               expiration = props.expiration,
                                                               content_type = content_type,
                                                               content_encoding = content_encoding,
                                                               headers = headers,
                                                               delivery_mode=1),
                               body=response)
            chan.basic_ack(delivery_tag = method.delivery_tag)            

        try:
            self._reply_handler(Request(body,props,reply))
        except Exception as e:
            self.logger.error("Uncaught exception in response_handler {}".format(e))
            # Force acknoweldgement
            chan.basic_ack(delivery_tag = method.delivery_tag)
            traceback.print_exc()      

#
# Async RPC client
#

AsyncRPCResponse = namedtuple("AsyncRPCResponse", ('body', 'props'))

class TimeoutError(Exception):
    pass

class ReturnError(Exception):
    pass

class ConnectionClosed(Exception):
    pass


class AsyncRPCClient(AsyncConnectionJob):

    ReturnError      = ReturnError
    TimeoutError     = TimeoutError
    ConnectionClosed = ConnectionClosed

    def __init__(self, *args, **kwargs):
        """ Create a new instance of worker publisher
        """

        # Default message expiration
        self._expiration     = None
        self._callback_queue = None
        self._consumer_tag   = None
        self._channel        = None
        self._callbacks = {}
                        
        super(AsyncRPCClient, self).__init__(*args, **kwargs)

    def set_msg_expiration( self, expiration ):
        """ Set message expiration time

            :param expiration: expiration delay in ms.  
        """
        if expiration is not None:
            self._expiration = "{:d}".format(expiration)
        else:
            self._expiration = None

    async def initialize( self, connection ):
        """ Create channel for rpc messaging
        """
        self._channel = None
        self._channel = await connection.channel()
        method_frame  = await self._channel.queue_declare(exclusive=True)

        # Since the channel is now open we declare exclusive reply queue and 
        # start a consummer on it 
        self._callback_queue = method_frame.method.queue
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self._channel.add_on_return_callback(self.on_return)
        self._consumer_tag = self._channel.basic_consume(self.on_response, no_ack=True, 
                                                         queue=self._callback_queue)

    def on_consumer_cancelled(self):
        self.logger.warn("AMQP Consummer cancelled")

    def _stop_consumming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
           Basic.Cancel RPC command.
        """
        if self._channel:
            self.logger.info('AMQP Cancelling RPC operation')
            self._channel.basic_cancel(consumer_tag=self._consumer_tag, nowait=True)

    def close(self):
        self._stop_consumming()
        self._callback_queue = None
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        super(AsyncRPCClient, self).close()
        # Resolve pending message
        for cid, future in self._callbacks.items():
            future.set_exception( self.ConnectionClosed() )

    async def call(self, body, routing_key, timeout=5, content_type=None, content_encoding=None, 
             headers=None):
        """ Send message to rabbitMQ server
       
            :param routing key
            :param body: body of the message
            :param timeout: timeout for requests 
            
            The callback must take a AsyncRPCResponse as unique argument
            
        """    
        if self._closing:
            raise Exception("Cannot publish after closing")
        
        assert self._channel, "AMQP no connection !"

        future = self.io_loop.create_future()
        
        # Generate a cid
        cid = str(uuid.uuid4())
        # register the future with the cid
        self._callbacks[cid] = future
        # send message
        self._channel.basic_publish(exchange='',
                                   routing_key=routing_key,
                                   properties=pika.BasicProperties(
                                         reply_to = self._callback_queue,
                                         correlation_id = cid,
                                         content_type = content_type,
                                         content_encoding = content_encoding,
                                         headers = headers,
                                         expiration = self._expiration,
                                         delivery_mode=1),
                                   body=body,
                                   mandatory=True)

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self._callbacks.pop(cid)
            self.logger.error("Caught Timeout for RPC message %s" % cid)
            raise self.TimeoutError()

 
    # handlers

    def on_return( self, ch, method, props, body ):
        """ Called when a message is 'returned'
        """
        # fetch a callback for the returned cid
        cid = props.correlation_id
        try:
            future = self._callbacks.pop(cid)
            future.set_exception(self.ReturnError(method))
        except KeyError:
            self._logger.error('AMQP no handler found for request id {}'.format(cid)) 

    def on_response( self, ch, method, props, body):
        """ Handle rpc response
        """
        # fetch a callback for the returned cid
        cid = props.correlation_id
        try:
            future = self._callbacks.pop(cid)
            future.set_result(AsyncRPCResponse(body, props))
        except KeyError:
            self._logger.error('AMQP no handler found for request id {}'.format(cid)) 


