#
# Copyright 2017 3liz
# Author David Marteau
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
AMQP RPC handler dispatcher

Implements handler dispatcher: associate function to command.

"""

import json
import logging
import traceback


class MSGException(Exception):
    def __init__( self, code, message, exc=None):
        super(Exception, self).__init__(code, message, exc)


def parse_message(body):
    """ Parse message body as json

        :param str body: A valid json message

            {
                'command': 'name',
                'args'     : {
                }
            }

        :return: A tuple (name, args)
        :raises: MSGException: with code 400 if the parsing fail
    """
    try:
        data=json.loads(body)
        name = data['command']
        args = data['args']
        return name, args
    except Exception as e:
        traceback.print_exc()
        raise MSGException(400,"Invalid message",exc=e)


class RPCHandler(object):
    """ Basic commands handler
    """
    def __init__(self, logger=None):
        self._registry = {}
        self.logger = logger or logging.getLogger()

    def command(self,  name):
        """ Decorator for registering function as a
            command
        """
        def wrapper( fun ):
            self._registry[name] = fun
            return fun

        return wrapper

    def log_error( self, e ):
        """ handle messge error """
        if not isinstance(e, MSGException):
            code, msg, exc = 500,"Internal Error",e
        else:
            code, msg, exc = e.args

        self.logger.error("{} {} {}".format(code, msg, exc))
        return code, msg, exc

    def handle_error(self, request, e):
        """ handle rpc message error

            Return an error reply
            to the client
        """
        code, msg, exc = self.log_error(e)
        error_msg = dict( code=code, message=msg, error=str(exc) )
        self.reply_json(request, data=error_msg,  code=code)
        return code, msg, exc

    def __call__( self, request ):
        """ Handle command

            Pass request arguments as arguments keywords
        """
        try:
            name, args = parse_message(request.body)
            fun = self._registry.get(name)
            if fun is None:
                raise MSGException(400,"invalid_command")

            fun( request, **args )

        except Exception as e:
            if not isinstance(e, MSGException):
                traceback.print_exc()
            self.handle_error(request, e)

    def reply_json(self, request, data, code=200,  headers={}):
        """ Reply with json data
        """
        headers = dict(headers)
        headers['return-code'] = code
        request.reply( json.dumps(data),
                       content_type="application/json",
                       content_encoding="utf-8",
                       headers=headers)
 

