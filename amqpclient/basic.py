#
# Copyright 2018 3liz
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

import os
import logging
import pika
import traceback
from collections import namedtuple
from time import sleep
from pika.exceptions import AMQPConnectionError


class CloseConnection(Exception):
    pass


class BlockingConnection(object):
    """ Define a basic blocking connection with reconnect fallback 
    """       
    def __init__( self,  host, port=None, logger=None, 
                  reconnect_delay=5, 
                  reconnect_latency=0.200,
                   **connection_params ):
        """ Create a new worker instance

            :param str host: Hostname or IP Address to connect to
            :param int port: TCP port to connect to
            :param float reconnect_delay: reconnection delay when trying to reconnect all nodes (in seconds)
            :param float reconnect_latency: latency between reconnection attempts (in seconds)
        """
        self._logger = logger or logging.getLogger()
        self._reconnect_delay = reconnect_delay
        self._reconnect_latency = reconnect_latency
        self._closing = False
        self._num_retry = 0
        self._cnxindex = 0
        self._connection = None
        self._channel = None

        if not isinstance(host, (tuple, list)):
            host = [host]
     
        self._cnxparams = [pika.ConnectionParameters(host=h, port=port, **connection_params) for h in host]

    @property
    def logger(self):
        return self._logger

    def close(self):
        self._closing = True
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @property
    def closing(self):
        return self._closing

    def handle_connection_error(self, error):
        """ Handle connection strategy on connection error
        """
        self._connection = None
        self._channel    = None

        cluster_size = len(self._cnxparams)
        logging.error("AMQP connection error {}".format(error))

        # Attempt reconnection
        self._num_retry += 1
        # Create a new connection on the next node 
        # Set next connection backend as our failover
        self._cnxindex = (self._cnxindex + 1) % cluster_size
        if self._num_retry >= cluster_size:
            # All nodes all been tried
            self._num_retry = 0
            if self._reconnect_delay > 0:
                self._logger.error("AMQP no nodes responding, waiting {} s before new attempts".format(self._reconnect_delay))
                sleep(self._reconnect_delay)
            else:
                self._logger.error("AMQP no nodes responding...")
                raise RuntimeError("Aborting AMQP connection")
        else:
            self._logger.error('AMQP Attempting reconnection in {} ms'.format(self._reconnect_latency*1000))
            sleep(self._reconnect_latency)     
        
    def connect(self):
        """ Reconnect 
             
            Call connect() with the new connection as param.
        """
        if self._closing:
            raise Exception("Cannot connect after closing")
        connection = pika.BlockingConnection(self._cnxparams[self._cnxindex]) 
        return connection

#
# Define request object 
#

Request = namedtuple('Request', ('body','props','reply'))

#
# Basic blocking RPC worker
#

class BasicWorker(BlockingConnection):
    """ Define a basic synchronous RPC  worker 
    """
    def on_message(self, method, props, body):
        """ Called when receivisg a message

            The handler is assumed to be asynchronous and thus no return values
            is expected: instead' a 'reply' function is passed to the handler
        """
        def reply( response, content_type=None, content_encoding=None, headers=None):
                    """ Define a reply method that will be passed to the handler
                    """
                    chan.basic_publish(exchange='',
                               routing_key=props.reply_to,
                               properties=pika.BasicProperties(
                                   correlation_id = props.correlation_id,
                                   expiration = props.expiration,
                                   content_type = content_type,
                                   content_encoding = content_encoding,
                                   headers = headers,
                                   delivery_mode=1),
                               body=response)
                    chan.basic_ack(delivery_tag = method.delivery_tag)

        try:
            handler(Request(body,props,reply))
        except Exception as e:
            logging.error("Uncaught exception in response_handler {}".format(e))
            # Force acknoweldgement
            chan.basic_ack(delivery_tag = method.delivery_tag)
            traceback.print_exc()
 

    def run( self, routing_key, request_handler ):
        """ Run blocking rpc worker
        """
        self._handler = request_handler
        while not self.closing:
            try:
                connection = self.connect() 
                
                channel = connection.channel()
                channel.queue_declare(queue=routing_key) 
              
                # This is required for fair queuing
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(self.on_message, queue=routing_key)
               
                self._connection = connection
                self._channel    = channel
                self._logger.info("[{}] RPC worker ready".format(os.getpid()))
                self._channel.start_consuming()
            except AMQPConnectionError as e:
                self.handle_connection_error(e)
            except CloseConnection:
                self.close()

#
# Blocking subscriber
#

Message = namedtuple("Message",('key','body','props') )

class BasicSubscriber(BlockingConnection):
    """ Define a basic synchronous subscriber 
        
        Creating a publisher:

            channel = connection.channel()
            channel.exchange_declare(exchange=topic, exchange_type='fanout')
            self._channel = channel

            # publish:
            channel.basic_publish(exchange=topic, routing_key='', body=message)
    """
    def run(self, exchange, handler, exchange_type='fanout', routing_keys=[]):
        while not self.closing:    
            try:
                connection = self.connect() 
                
                channel = connection.channel()

                if exchange_type is not None:
                    channel.exchange_declare(exchange=exchange, exchange_type=exchange_type)
            
                result = channel.queue_declare(exclusive=True) 
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
                    except Exception as e:
                        self.logger.error("Uncaught exception in message_handler {}".format(e))
                        traceback.print_exc()
                    
                channel.basic_consume(_on_message, queue=queue_name, no_ack=True)
               
                self._connection = connection
                self._channel    = channel
                self._logger.info("[{}] Subscriber ready".format(os.getpid()))
                self._channel.start_consuming()
    
            except AMQPConnectionError as e:
                self.handle_connection_error(e)
            except CloseConnection:
                self.close()

#
# Publisher
#

class BasicPublisher(BlockingConnection):
    """ Define a basic synchronous publisher
    """
    def __init__(self, *args, **kwargs):
        """ Create a new instance of a  publisher
        """
        self._exchange  = None
        self._exchange_type = None
        super(BasicPublisher, self).__init__(*args,**kwargs)

    def initialize(self, exchange, exchange_type='fanout'):
        """
        """
        self._exchange = exchange
        self._exchange_type = exchange_type

    def publish(self, message, routing_key='', expiration=None, content_type=None, 
                      content_encoding=None, headers=None):
        """ Send message to rabbitMQ server
        """
        if self._closing:
            raise Exception("Cannot publish after closing connection")

        if self._exchange is None:
            raise RuntimeError("Bad exchange value: did you forget to call initialize() ?")

        done=False

        while not done:
            try:
                if self._connection is None:
                    connection = self.connect()
                    channel = connection.channel()
                    if self._exchange_type != 'none':
                        channel.exchange_declare(exchange=self._exchange, exchange_type=self._exchange_type)
     
                    self._channel    = channel
                    self._connection = connection

                if expiration is not None:
                   expiration = "{:d}".format(expiration)
                else:
                   expiration = None

                self._channel.basic_publish(exchange=self._exchange, 
                                            routing_key=routing_key,
                                            properties=pika.BasicProperties(
                                                expiration = expiration,
                                                content_type = content_type,
                                                content_encoding = content_encoding,
                                                headers = headers),
                                            body=message)
                done=True
            except AMQPConnectionError as e:
                publisher.handle_connection_error(e)
   

