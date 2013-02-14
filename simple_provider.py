
from jerry.user import Provider
import requests
import json


class SimpleHTTPProvider(Provider):
    def _request(self, method, url, data):
        func = method == "POST" and requests.post or requests.get
        return func(url, data=data)

    def _signin(self, user):
        url = self.end_point + "permission_state"
        url += '?' + self._sign('GET', url, {
            'user_id': user.user_id,
            'device_id': user.device_id})
        req = self._request('GET', url)
        user.load_state(json.loads(req.content))
