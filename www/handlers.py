#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Nate_River'

'''
async web application: URL handlers
'''

import time, logging, hashlib, json, asyncio
from www.coreweb import get, post
from www.models import User, Blog, Comment, next_id
from conf.config import configs
from www.apis import *
from aiohttp import web
from www.models import User

COOKIE_NAME = 'DRAGON'
_COOKIE_KEY = configs.session.secret


def user2cookie(user, max_age):
    # Generate cookie string by user info
    expires = str(int(time.time()) + max_age)
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


async def cookie2user(cookie_str):
    # Parse cookie and load user if cookie is valid
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if not user:
            return None
        s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('Invalid sha1')
            return None
        user.password = '********'
        return user
    except BaseException as e:
        logging.exception(e)
        return None


@get(path='/')
def index():
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }


@get(path='/register')
def register():
    return {
        '__template__': 'register.html'
    }


@get(path='/login')
def login():
    return {
        '__template__': 'login.html'
    }


@get(path='/logout')
def logout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user log out.')
    return r


@post(path='/api/authenticate')
def authenticate(*, email, password):
    if not email or not email.strip():
        raise APIValueError(field='email', message='Invalid email.')
    if not password or not password.strip():
        raise APIValueError(field='password', message='Invalid password.')
    # check email
    users = yield from find_users(email)
    if len(users) == 0:
        raise APIValueError(field='email', message='Email not exist.')
    user = users[0]
    # check password
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(password.encode('utf-8'))
    if user.password != sha1.hexdigest():
        raise APIValueError(field='password', message='Invalid password.')
    # pass the authenticate, then set cookie for the user
    r = web.Response()
    r.set_cookie(name=COOKIE_NAME, value=user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '********'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@post(path='/api/register_check')
def register_check(*, email, password, name):
    if not email or not email.strip():
        raise APIValueError(field='email', message='Empty field.')
    if not password or not password.strip():
        raise APIValueError(field='password', message='Empty field.')
    if not name or not name.strip():
        raise APIValueError(field='name', message='Empty field.')

    # check email
    users = yield from find_users(email)
    # users = (User.findall(where='email=?', args=[email]))
    if len(users) > 0:
        raise APIError(error='register:failed', data='email', message='Email is already exist.')
    uid = next_id()
    sha1_pwd = '%s:%s' % (uid, password)
    user = User(id=uid, name=name, email=email, password=hashlib.sha1(sha1_pwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from save_user(user)
    # make the session cookie
    r = web.Response()
    r.set_cookie(name=COOKIE_NAME, value=user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '********'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


"""Incompatible versions: async <--> yield from"""


@asyncio.coroutine
def find_users(email):
    user = yield from User.findall(where='email=?', args=[email])
    return user


@asyncio.coroutine
def save_user(user):
    yield from user.save()


"""Incompatible versions"""
