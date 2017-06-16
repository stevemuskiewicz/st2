# Licensed to the StackStorm, Inc ('StackStorm') under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from st2common.exceptions.auth import (TokenNotFoundError, ApiKeyNotFoundError,
                                       UserNotFoundError, AmbiguousUserError,
                                       NoNicknameOriginProvidedError)
from st2common.models.db import MongoDBAccess
from st2common.models.db.auth import UserDB, TokenDB, ApiKeyDB
from st2common.persistence.base import Access
from st2common.util import hash as hash_utils
from oslo_config import cfg
# from st2common.router import Response


class User(Access):
    impl = MongoDBAccess(UserDB)

    @classmethod
    def get(cls, username):
        return cls.get_by_name(username)

    @classmethod
    def get_by_nickname(cls, nickname, origin):
        if not origin:
            raise NoNicknameOriginProvidedError()

        result = cls.query(**{('nicknames__%s' % origin): nickname})

        if not result.first():
            raise UserNotFoundError()
        if result.count() > 1:
            raise AmbiguousUserError()

        return result.first()

    @classmethod
    def _get_impl(cls):
        return cls.impl

    @classmethod
    def _get_by_object(cls, object):
        # For User name is unique.
        name = getattr(object, 'name', '')
        return cls.get_by_name(name)


class Token(Access):
    impl = MongoDBAccess(TokenDB)

    @classmethod
    def _get_impl(cls):
        return cls.impl

    @classmethod
    def add_or_update(cls, model_object, publish=True):
        if not getattr(model_object, 'user', None):
            raise ValueError('User is not provided in the token.')
        if not getattr(model_object, 'token', None):
            raise ValueError('Token value is not set.')
        if not getattr(model_object, 'expiry', None):
            raise ValueError('Token expiry is not provided in the token.')
        return super(Token, cls).add_or_update(model_object, publish=publish)

    @classmethod
    def get(cls, value):
        result = cls.query(token=value).first()

        if not result:
            raise TokenNotFoundError()

        return result


class ApiKey(Access):
    impl = MongoDBAccess(ApiKeyDB)

    # Maximum value of limit which can be specified by user
    @property
    def max_limit(self):
        return cfg.CONF.api.max_page_size

    # Default number of items returned per page if no limit is explicitly provided
    default_limit = 100

    @classmethod
    def _get_impl(cls):
        return cls.impl

    @classmethod
    def get(cls, value, limit=None, offset=0):
        # DB does not contain key but the key_hash.
        value_hash = hash_utils.hash(value)

        # TODO: To protect us from DoS, we need to make max_limit mandatory
        offset = int(offset)

        if limit and int(limit) > cls.max_limit:
            # TODO: We should throw here, I don't like this.
            msg = 'Limit "%s" specified, maximum value is "%s"' % (limit, cls.max_limit)
            raise ValueError(msg)

        instances = cls.query(key_hash=value_hash).first()

        if not instances:
            raise ApiKeyNotFoundError('ApiKey with key_hash=%s not found.' % value_hash)

        if limit == 1:
            # Perform the filtering on the DB side
            instances = instances.limit(limit)

        return instances

    @classmethod
    def get_by_key_or_id(cls, value):
        try:
            return cls.get(value)
        except ApiKeyNotFoundError:
            pass
        try:
            return cls.get_by_id(value)
        except:
            raise ApiKeyNotFoundError('ApiKey with key or id=%s not found.' % value)
