"""Authorization handlers"""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
from urllib.parse import quote

from oauth2.web.tornado import OAuth2Handler
from tornado import web, gen

from .. import orm
from ..utils import token_authenticated
from .base import BaseHandler, APIHandler


class TokenAPIHandler(APIHandler):
    @token_authenticated
    def get(self, token):
        orm_token = orm.APIToken.find(self.db, token)
        if orm_token is None:
            orm_token = orm.OAuthAccessToken.find(self.db, token)
        if orm_token is None:
            raise web.HTTPError(404)
        if orm_token.user:
            model = self.user_model(self.users[orm_token.user])
        elif orm_token.service:
            model = self.service_model(orm_token.service)
        self.write(json.dumps(model))

    @gen.coroutine
    def post(self):
        user = self.get_current_user()
        if user is None:
            # allow requesting a token with username and password
            # for authenticators where that's possible
            data = self.get_json_body()
            try:
                authenticated = yield self.authenticate(self, data)
            except Exception as e:
                self.log.error("Failure trying to authenticate with form data: %s" % e)
                authenticated = None
            if authenticated is None:
                raise web.HTTPError(403)
            user = self.find_user(authenticated['name'])
        api_token = user.new_api_token()
        self.write(json.dumps({'token': api_token}))


class CookieAPIHandler(APIHandler):
    @token_authenticated
    def get(self, cookie_name, cookie_value=None):
        cookie_name = quote(cookie_name, safe='')
        if cookie_value is None:
            self.log.warning("Cookie values in request body is deprecated, use `/cookie_name/cookie_value`")
            cookie_value = self.request.body
        else:
            cookie_value = cookie_value.encode('utf8')
        user = self._user_for_cookie(cookie_name, cookie_value)
        if user is None:
            raise web.HTTPError(404)
        self.write(json.dumps(self.user_model(user)))


class OAuthHandler(BaseHandler, OAuth2Handler):
    """Implement OAuth provider handlers
    
    OAuth2Handler sets `self.provider` in initialize,
    but we are already passing the Provider object via settings.
    """
    @property
    def provider(self):
        return self.settings['oauth_provider']

    def initialize(self):
        pass


default_handlers = [
    (r"/api/authorizations/cookie/([^/]+)(?:/([^/]+))?", CookieAPIHandler),
    (r"/api/authorizations/token/([^/]+)", TokenAPIHandler),
    (r"/api/authorizations/token", TokenAPIHandler),
    (r"/api/oauth2/authorize", OAuthHandler),
    (r"/api/oauth2/token", OAuthHandler),
]
