import hashlib
import hmac
from operator import itemgetter

from core.http import HttpClient
from sockets.client import _BaseClient


class Api:

    def __init__(self, client: _BaseClient, key: str, secret: str):
        self.api: HttpClient = client.http
        self.key, self.secret = key, secret

    def _generate_signature(self, data, secret):

        ordered_data = self._order_params(data)
        query_string = '&'.join(["{}={}".format(d[0], d[1]) for d in ordered_data])
        m = hmac.new(secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def _order_params(self, data):
        """Convert params to list with signature as last element
        :param data:
        :return:
        """
        has_signature = False
        params = []
        for key, value in data.items():
            if key == 'signature':
                has_signature = True
            else:
                params.append((key, value))
        # sort parameters by key
        params.sort(key=itemgetter(0))
        if has_signature:
            params.append(('signature', data['signature']))
        return params

    async def load_markets(
        self,
        client: _BaseClient,

    ):
        pass
