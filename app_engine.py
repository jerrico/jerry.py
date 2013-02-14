
#from google.appengine.ext import ndb
from jerry.user import Provider as BaseProvider
from google.appengine.api import memcache

from google.appengine.api import urlfetch

import json


class Provider(BaseProvider):

    def _request(self, method, url, data=None):
        return urlfetch.fetch(url, method=method, payload=data, deadline=10)

    def _signin(self, user):
        url = self.end_point + "permission_state"
        url += '?' + self._sign('GET', url, {
            'user_id': user.user_id,
            'device_id': user.device_id})
        req = self._request('GET', url)
        if req.status_code != 200:
            raise ValueError("Can't fetch external profile:%s" % req.status_code)
        user.load_state(json.loads(req.content))
