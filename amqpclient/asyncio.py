""" Asyncio support
"""
import asyncio
import tornado.platform.asyncio

from .concurrent import (AsyncConnection, 
                         AsyncConnectionJob as _AsyncConnectionJob,
                         AsyncRPCWorker as _AsyncRPCWorker, 
                         AsyncRPCClient as _AsyncRPCClient,
                         AsyncSubscriber as _AsyncSubscriber, 
                         AsyncPublisher as _AsyncPublisher)


class AIOConnectionMixin:
    """ Wrap the connect call to 'connect'
        and return an asyncio future
    """

    @asyncio.coroutine
    def connect( self, *args, **kwargs):
        tornado_future = super(AIOConnectionMixin, self).connect(*args, **kwargs)
        yield from tornado.platform.asyncio.to_asyncio_future(tornado_future)
        

class AsyncConnectionJob(AIOConnectionMixin, _AsyncConnectionJob):
    pass


class AsyncRPCWorker(AIOConnectionMixin, _AsyncRPCWorker):
    pass


class AsyncRPCClient(AIOConnectionMixin, _AsyncRPCClient):
    
    @asyncio.coroutine
    def call(self, *args, **kwargs):
        tornado_future = super(AIOConnectionMixin, self).call(*args, **kwargs)
        return (yield from tornado.platform.asyncio.to_asyncio_future(tornado_future))
 

class AsyncSubscriber(AIOConnectionMixin, _AsyncSubscriber):
    pass


class AsyncPublisher(AIOConnectionMixin, _AsyncPublisher):
    pass

