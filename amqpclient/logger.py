# -*- encoding=utf-8 -*-
#
# Copyrights 2016-2017 3Liz
# Author: David Marteau (dmarteau@3liz.com)
#
"""
Define a logger based on amqp
"""
# Keep python 2 compat
from __future__ import (absolute_import, division, print_function)

import os
import sys
import logging
from .basic import BasicPublisher

class Handler(logging.Handler):
    """ A logging handler that push notifications to RabbitMQ
    """
    
    def __init__(self, 
                exchange, routing_key,
                level=logging.NOTSET,
                formatstr='%(asctime)s\t%(levelname)s\t%(hostname)s\t[%(process)d]\t%(message)s',
                content_type='text/plain',
                exchange_type='topic',
                message_ttl=3000,
                **kwargs):

        self._content_type = content_type
        self._routing_key  = routing_key
        self._client       = BasicPublisher(**kwargs)
        self._hostname     = os.uname()[1]
        self._expiration   = message_ttl

        self._client.initialize(exchange, exchange_type=exchange_type) 

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
                routing_key = self._routing_key % record.__dict__,
                expiration = self._expiration,
                content_type = self._content_type,
                content_encoding ='utf-8')


