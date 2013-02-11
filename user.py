

class Restriction(object):
    def __init__(self, attrs):
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
    def allows(self, attr, change, user=None, *args, **kwargs):
        try:
            return user.account[self.account_item] - \
                    (self.quantity_change * change) > 0
        except (KeyError):
            return False

    def did(self, attr, change, user=None, *args, **kwargs):
        user.account[self.account_item] -= (self.quantity_change * change)

class JerryUser(object):

    PROVIDER_CLASS = None
    RESTRICTIONS = {
        "BinaryRestriction": BinaryRestriction,
        "PerTimeRestriction": PerTimeRestriction,
        "TotalAmountRestriction": TotalAmountRestriction,
        "AccountAmountRestriction": AccountAmountRestriction,
    }

    def __init__(self, profile_state=None):
        if profile_state:
            self._load_state(profile_state)

    def _load_state(self, profile_state):
        self.profile_name = profile_state.get("profile", None)
        self.default = profile_state['default'] == 'allow'
        self.restrictions = self._compile_restrictions(profile_state["states"])
        self.account = profile_state["account"]

    def _compile_restrictions(self, states):
        return dict([(key, [self.RESTRICTIONS[item['class_']](item) \
                                for item in values])
                        for key, values in states.iteritems()])

    def can(self, action, change=1, *args, **kwargs):
        restrictions = self.restrictions.get(action, "")
        if not restrictions:
            return self.default

        for restriction in restrictions:
            if not restriction.allows(action, change, user=self, *args, **kwargs):
                return False

        return not self.default

    def did(self, action, change=1, *args, **kwargs):
        restrictions = self.restrictions.get(action, "")
        if restrictions:
            for restriction in restrictions:
                restriction.did(action, change, user=self, *args, **kwargs)


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
                        'account_item': "credtis"}   # typop
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

    user = JerryUser(profile_state=profile_state)

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

    ## do we have credits to share photos privately?
    user.did("share_photo_private", 1)
    user.can("share_photo_private").should.be.ok
    user.did("share_photo_private", 2)
    user.can("share_photo_private").should.be.false

    # not defined: default is deny
    user.can("view_photo").should_not.be.ok
    user.can("view_photo", 10).should_not.be.ok

    ## lets modify and play again:
    user.did("upload_photo")
    user.can("upload_photo").should.be.ok
    user.can("upload_photo", 2).should.be.ok
    user.did("upload_photo", 2)
    user.can("upload_photo").should_not.be.ok


