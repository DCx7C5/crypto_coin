# -*- coding: utf-8 -*-
"""
# ccctrl's exception hierarchy

CCCException
 +-- NoMoreItems
 +-- SubclassingNotAllowed
 +-- ServerError
      +-- # TODO: ...
 +-- ClientError
      +-- SocketException
      +-- HTTPException
           +-- Forbidden                # 403
           +-- NotFound                 # 404
           +--
      +-- RPCException
           +-- ClientException
           +-- ServerException
"""


from aiohttp import ClientResponse


from typing import (
    Union,
)

from core.utils import flatten_error_dict


class CCCException(Exception):
    """Base exception class for crypto_coin
       Ideally speaking, this could be caught to handle any exceptions thrown from this library."""
    pass


class NoMoreItems(CCCException):
    """Exception that is thrown when an async iteration operation has no more items."""
    pass


class SubclassingNotAllowed(CCCException):
    pass


class ClientException(CCCException):
    """Exception that's thrown when an operation in the :class:`Client` fails.

    These are usually for exceptions that happened due to user input.
    """
    pass


class InvalidArgument(CCCException):
    """Exception that's thrown when an argument to a function
    is invalid some way (e.g. wrong value or wrong type).

    This could be considered the analogous of ``ValueError`` and
    ``TypeError`` except inherited from :exc:`ClientException` and thus
    :exc:`DiscordException`.
    """
    pass


class HTTPException(CCCException):
    """Exception that's thrown when an HTTP request operation fails.
    Attributes
    ------------
    response: :class:`aiohttp.ClientResponse`
        The response of the failed HTTP request. This is an
        instance of :class:`CCC.HttpClientResponse`.

    text: :class:`str`
        The text of the error. Could be an empty string.
    status: :class:`int`
        The status code of the HTTP request.
    code: :class:`int`
        The wallet specific error code for the failure.
    """

    def __init__(self, response: ClientResponse,
                 message: Union[str, dict],
                 error_code: int = None, **kwargs) -> None:
        self.response, self.status = response, response.status
        if isinstance(message, dict):
            self.code = message.get('code', 0)
            base = message.get('message', '')
            errors = message.get('errors')
            if errors:
                errors = flatten_error_dict(errors)
                helpful = '\n'.join(f'In %s: %s' % t for t in errors.items())
                self.text = base + '\n' + helpful
            else:
                self.text = base
        else:
            self.text = message
            self.code = 0

        fmt = f'{self.response.status} {self.response.reason} (error code: {self.code})'
        if len(self.text):
            fmt = fmt + f': {self.text}'

        super().__init__(fmt)


class Forbidden(HTTPException):
    """Exception that's thrown for when status code 403 occurs.
    Subclass of :exc:`HTTPException`
    """
    pass


class NotFound(HTTPException):
    """Exception that's thrown for when status code 404 occurs.
    Subclass of :exc:`HTTPException`
    """
    pass


class RPCException(CCCException):
    pass


class InvalidRequestError(RPCException):
    """Invalid request sent to rpc server."""
    code = -32600


class MethodNotFoundError(RPCException):
    """Method not found on rpc server."""
    code = -32601


class InvalidParamsError(RPCException):
    """Invalid rpc parameters provided."""
    code = -32602


class InternalError(RPCException):
    """Internal rpc server error."""
    code = -32603


class ParseError(RPCException):
    """Error while parsing rpc request."""
    code = -32700


class MiscError(RPCException):
    """std::exception thrown in command handling."""
    code = -1


class ForbiddenBySafeMode(RPCException):
    """Server is in safe mode, and command is not allowed in safe mode."""
    code = -2


class RpcTypeError(RPCException):
    """Unexpected type was passed as parameter."""
    code = -3


class InvalidAddressOrKey(RPCException):
    """Invalid address or key."""
    code = -5


class OutOfMemory(RPCException):
    """Ran out of memory during operation."""
    code = -7


class InvalidParameter(RPCException):
    """Invalid, missing or duplicate parameter."""
    code = -8


class DatabaseError(RPCException):
    """Database error."""
    code = -20


class DeserializationError(RPCException):
    """Error parsing or validating structure in raw format."""
    code = -22


class ClientNodeNotAdded(RPCException):
    """Node has not been added before"""
    code = -24


class VerifyError(RPCException):
    """General error during transaction or block submission."""
    code = -25


class VerifyRejected(RPCException):
    """Transaction or block was rejected by network rules."""
    code = -26


class WebsocketException(CCCException):
    pass


class GatewayNotFound(CCCException):
    """An exception that is usually thrown when the gateway hub
    for the :class:`Client` websocket is not found."""
    def __init__(self):
        message = 'The gateway to connect to discord was not found.'
        super(GatewayNotFound, self).__init__(message)


class ConnectionClosed(WebsocketException):
    """Exception that's thrown when the gateway connection is
    closed for reasons that could not be handled internally.
    Attributes
    -----------
    code: :class:`int`
        The close code of the websocket.
    reason: :class:`str`
        The reason provided for the closure.

    """
    def __init__(self, socket, *, code=None):
        # This exception is just the same exception except
        # reconfigured to subclass ClientException for users
        self.code = code or socket.close_code
        # aiohttp doesn't seem to consistently provide close reason
        self.reason = ''
        super().__init__(f'WebSocket closed with {self.code}')


class ReconnectWebSocket(Exception):
    """Signals to safely reconnect the websocket."""
    def __init__(self, *, resume=True):
        self.resume = resume
        self.op = 'RESUME' if resume else 'IDENTIFY'


class WebSocketClosure(Exception):
    """An exception to make up for the fact that aiohttp doesn't signal closure."""
    pass


__rpc_errors__ = (
    InvalidRequestError,
    MethodNotFoundError,
    InvalidParamsError,
    InternalError,
    ParseError,
    MiscError,
    ForbiddenBySafeMode,
    RpcTypeError,
    InvalidAddressOrKey,
    OutOfMemory,
    InvalidParameter,
    DatabaseError,
    DeserializationError,
    ClientNodeNotAdded,
    VerifyError,
    VerifyRejected,
)

__exceptions__ = (
    CCCException,
    NoMoreItems,
    HTTPException,
    Forbidden,
    NotFound,
)

__all_exceptions__ = __exceptions__ + __rpc_errors__

rpc_error_lookup_table = {e.code: e for e in __rpc_errors__}
