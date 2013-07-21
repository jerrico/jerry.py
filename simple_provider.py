
from jerry.user import Provider
import requests
import json


class SimpleHTTPProvider(Provider):
    def _request(self, method, url, data):
        func = method == "POST" and requests.post or requests.get
        return func(url, data=data)

    def _signin(self, user):
        url = self.end_point + "permission_state"
        params = {}
        if user.user_id is not None:
            params['user_id'] = user.user_id
        if user.device_id is not None:
            params['device_id'] = user.device_id

        if not params:
            raise ValueError("Either user_id or device_id must be give ")
        url += '?' + self._sign('GET', url, params)
        req = self._request('GET', url)
        user.load_state(json.loads(req.content))

if __name__ == "__main__":
    import sure

    provider = SimpleHTTPProvider("key1234", "secret1455")
    provider._sign("get", provider.end_point + "permission_state",
            {'user_id': "asdfa",
            'device_id': "asdfadsf"}).should.equal(r"_key=key1234&user_id=asdfa&device_id=asdfadsf&_signature=nSDAnCS1lmbCbCKToGedEvEEjYvt8gvJ2EzSpFWxzcw%3D%0A")


    provider._sign("post", provider.end_point + "logger",
            {'device_id': None, 'user_id': "231499435803498513425",
            'entries': json.dumps([{"action": "take_photo"}])
            }).should.equal(r"_key=key1234&entries=%5B%7B%22action%22%3A+%22take_photo%22%7D%5D&user_id=231499435803498513425&device_id=None&_signature=B%2B%2BsEUCoqFfALoBcKNFdeWBkD745O549T2mYQNXEhEA%3D%0A")