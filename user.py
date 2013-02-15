import urllib
import hashlib
import hmac
import binascii
import json


class Restriction(object):
    def __init__(self, user, attrs):
        self.user = user
        for key, value in attrs.iteritems():
            setattr(self, key, value)

    def allows(self, attr, change, *args, **kwargs):
        return False

    def did(self, attr, change, *args, **kwargs):
        pass


class BinaryRestriction(Restriction):

    def allows(self, attr, change, *args, **kwargs):
        return self.allow


class TotalAmountRestriction(Restriction):

    def allows(self, attr, change, *args, **kwargs):
        if not self.left:
            return False

        return self.left - change >= 0

    def did(self, attr, change, *args, **kwargs):
        self.left -= change


class PerTimeRestriction(TotalAmountRestriction):
    pass


class AccountAmountRestriction(Restriction):
    # FIME: needs to be implemented
    def allows(self, attr, change, *args, **kwargs):
        try:
            return self.user.account[self.account_item] - \
                    (self.quantity_change * change) > 0
        except (KeyError):
            return False

    def did(self, attr, change, *args, **kwargs):
        self.user.account[self.account_item] -= (self.quantity_change * change)


class Provider(object):

    def __init__(self, key=None, secret=None,
                end_point="http://api.jerri.co/api/v1/"):
        self.key = key
        self.secret = secret
        self.end_point = end_point

    def _sign(self, method, url, params):
        params["_key"] = self.key
        encoded = urllib.urlencode(params)
        query = "&".join((method.upper(), url, encoded))
        encoded += "&_signature=" + urllib.quote(binascii.b2a_base64(
                hmac.new(self.secret, query, hashlib.sha256).digest()))
        return encoded

    def did(self, user, action, quantity, *args, **kwargs):
        return self.log(self, user, action, quantity)

    def log(self, user, action, quantity=None, unit=None):
        entry = {'action': action}
        if quantity is not None:
            entry['quantity'] = quantity
        if unit is not None:
            entry['unit'] = unit

        params = {
            'user_id': user.user_id,
            'device_id': user.device_id,
            'entries': json.dumps([entry])
        }

        url = self.end_point + "logger"
        data = self._sign(url, "POST", params)
        return self._request("POST", url, data)

    def signin(self, user_id=None, device_id=None):
        user = JerryUser(user_id=user_id, device_id=device_id, provider=self)
        self._signin(user)
        return user


class JerryUser(object):

    RESTRICTIONS = {
        "BinaryRestriction": BinaryRestriction,
        "PerTimeRestriction": PerTimeRestriction,
        "TotalAmountRestriction": TotalAmountRestriction,
        "AccountAmountRestriction": AccountAmountRestriction,
    }

    def __init__(self, user_id, device_id=None, provider=None, profile_state=None):
        self.provider = provider
        self.user_id = user_id
        self.device_id = device_id
        self.profile_name = ""
        self.default = False
        self.restrictions = {}
        self.profile_state = {}

        if profile_state:
            self.load_state(profile_state)

    def load_state(self, profile_state):
        self.profile_state = profile_state
        self.profile_name = profile_state.get("profile", None)
        self.default = profile_state['default'] == 'allow'
        self.restrictions = self._compile_restrictions(profile_state["states"])
        self.account = profile_state["account"]

    def _compile_restrictions(self, states):
        return dict([(key, [self.RESTRICTIONS[item['class_']](self, item) \
                                for item in values])
                        for key, values in states.iteritems()])

    def can(self, action, change=1, *args, **kwargs):
        restrictions = self.restrictions.get(action, "")
        if not restrictions:
            return self.default

        for restriction in restrictions:
            if not restriction.allows(action, change, *args, **kwargs):
                return False

        return not self.default

    def did(self, action, change=1, *args, **kwargs):
        self.dirty = True
        restrictions = self.restrictions.get(action, "")
        if restrictions:
            for restriction in restrictions:
                restriction.did(action, change, *args, **kwargs)

        self.provider.did(self, action, change, *args, **kwargs)

    def log(self, *args, **kwargs):
        return self.provider.log(*args, **kwargs)


if __name__ == "__main__":
    import sure

    profile_state = {
        'profile': 'free',
        'default': 'deny',
        'account': {
            'credits': 100
        },
        'states': {
            'take_photo': [
                {'class_': 'BinaryRestriction', 'allow': True}
            ],
            'take_photo_private': [
                {'class_': 'AccountAmountRestriction',
                        'account_item': "credtis"}   # typo
            ],
            'upload_photo': [
                {'class_': 'PerTimeRestriction', 'limit_to': 100,
                        'duration': 24 * 60 * 60, 'left': 3}
            ],
            'share_photo': [
                {'class_': 'PerTimeRestriction', 'limit_to': 100,
                        'duration': 24 * 60 * 60, 'left': 20},
                {'class_': 'TotalAmountRestriction', 'total_max': 100,
                        'left': 10}
            ],
            'share_photo_private': [
                {'class_': 'AccountAmountRestriction',
                        'account_item': "credits", "quantity_change": 35}
            ],
        }
    }

    class MockProvider:
        def __init__(self):
            self.calls = []

        def did(self, *args, **kwargs):
            self.calls.append(('did', args, kwargs))

    mocky = MockProvider()

    user = JerryUser('Mr.T', provider=mocky, profile_state=profile_state)

    mocky.calls.should.be.empty
    user.can("take_photo").should.be.ok
    user.can("take_photo", 10).should.be.ok

    user.can("upload_photo").should.be.ok
    user.can("upload_photo", 3).should.be.ok
    user.can("upload_photo", 4).should_not.be.ok

    user.can("share_photo").should.be.ok
    user.can("share_photo", 9).should.be.ok
    # total amount kicks in though daily woud allow it
    user.can("share_photo", 12).should_not.be.ok

    ## do we have credits to share photos privately?
    user.can("share_photo_private").should.be.ok
    user.can("share_photo_private", 2).should.be.ok
    user.can("share_photo_private", 3).should.be.false

    # typo
    user.can("take_photo_private").should.be.false

    mocky.calls.should.be.empty

    ## do we have credits to share photos privately?
    user.did("share_photo_private", 1)
    mocky.calls.should.have.length_of(1)
    user.can("share_photo_private").should.be.ok
    user.did("share_photo_private", 2)
    mocky.calls.should.have.length_of(2)
    user.can("share_photo_private").should.be.false

    # not defined: default is deny
    user.can("view_photo").should_not.be.ok
    user.can("view_photo", 10).should_not.be.ok

    ## lets modify and play again:
    user.did("upload_photo")
    mocky.calls.should.have.length_of(3)
    user.can("upload_photo").should.be.ok
    user.can("upload_photo", 2).should.be.ok
    user.did("upload_photo", 2)
    mocky.calls.should.have.length_of(4)
    user.can("upload_photo").should_not.be.ok


