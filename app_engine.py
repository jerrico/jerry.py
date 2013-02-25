
#from google.appengine.ext import ndb
from jerry.user import Provider as BaseProvider
from google.appengine.api import memcache

from google.appengine.api import urlfetch

import webapp2
import json


class Provider(BaseProvider):

    def _request(self, method, url, data=None):
        return urlfetch.fetch(url, method=method, payload=data, deadline=10)

    def _set_memcache(self, user, data):
        user_data = json.dumps(data)
        if user.user_id:
            memcache.set("__jerry_u_{}".format(user.user_id), user_data)

        if user.device_id:
            memcache.set("__jerry_d_{}".format(user.device_id), user_data)

        return data

    def _signin(self, user):
        user_data = None
        if user.user_id:
            user_data = memcache.get("__jerry_u_{}".format(user.user_id))
        if not user_data and user.device_id:
            user_data = memcache.get("__jerry_d_{}".format(user.device_id))
        if user_data:
            user_data = json.loads(user_data)
        else:
            url = self.end_point + "permission_state"
            url += '?' + self._sign('GET', url, {
                'user_id': user.user_id,
                'device_id': user.device_id})

            req = self._request('GET', url)
            if req.status_code != 200:
                raise ValueError("Can't fetch external profile:{}".format(
                            req.status_code))

            user_data = json.loads(req.content)["result"]
            self._set_memcache(user, user_data)

        user.load_state(user_data)

    def did(self, user, action, quantity, *args, **kwargs):
        # update memcache
        self._set_memcache(user, user.profile_state)
        return self.log(self, user, action, quantity)


class _ProxyHandler(webapp2.RequestHandler):
    key = None
    secret = None
    end_point = None

    def _get_jerry_provider(self):
        attrs = dict(key=self.key, secret=self.secret)
        if self.end_point:
            attrs["end_point"] = self.end_point
        return Provider(**attrs)

    def get(self):
        provider = self._get_jerry_provider()
        self.response.content_type = "application/json"

        user = provider.signin(self.request.GET.get("user_id"), self.request.GET.get("device_id"))
        self.response.write(json.dumps({"status": "success", "result": user.profile_state}))


def jerry_login_proxy(**config):

    class MyProxy(_ProxyHandler):
        key = config.get("key")
        secret = config.get("secret")
        end_point = config.get("end_point")
    return ('/api/v1/permission_state', MyProxy)
