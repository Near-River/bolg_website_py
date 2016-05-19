#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Nate_River'

'''
async web application: URL handlers
'''

import time, logging, hashlib, json, asyncio
import www.markdown2 as markdown
from www.coreweb import get, post
from www.models import User, Blog, Comment, next_id, Page, get_page_index
from conf.config import configs
from www.apis import *
from aiohttp import web
from www.models import User

COOKIE_NAME = 'DRAGON'
_COOKIE_KEY = configs.session.secret


def check_admin(request):
    if request.__user__ is None or request.__user__.admin == False:
        raise APIPermissionError()


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


def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


@get(path='/')
def index(*, page='1'):
    page_index = get_page_index(page)
    num = yield from find_number(model='blog', selectField='id')
    page = Page(num, page_index)
    if num == 0:
        blogs = []
    else:
        blogs = yield from find_models(model='blog', orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        '__template__': 'blogs.html',
        'page': page,
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
    """authenticate the login user"""
    if not email or not email.strip():
        raise APIValueError(field='email', message='Invalid email.')
    if not password or not password.strip():
        raise APIValueError(field='password', message='Invalid password.')
    # check email
    users = yield from find_models(model='user', where='email=?', args=[email])
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
    """checking the information of the register user"""
    if not email or not email.strip():
        raise APIValueError(field='email', message='Empty field.')
    if not password or not password.strip():
        raise APIValueError(field='password', message='Empty field.')
    if not name or not name.strip():
        raise APIValueError(field='name', message='Empty field.')
    # check email
    # users = (User.findall(where='email=?', args=[email]))
    users = yield from find_models(model='user', where='email=?', args=[email])
    if len(users) > 0:
        raise APIError(error='register:failed', data='email', message='Email is already exist.')
    uid = next_id()
    sha1_pwd = '%s:%s' % (uid, password)
    user = User(id=uid, name=name, email=email, password=hashlib.sha1(sha1_pwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from save_model(user)
    # make the session cookie
    r = web.Response()
    r.set_cookie(name=COOKIE_NAME, value=user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '********'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get(path='/blog/{id}')
def get_blog(id):
    blog = yield from find_model(model='blog', id=id)
    comments = yield from find_models(model='comment', where='blog_id=?', args=[id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }


@get(path='/manage/')
def manage():
    return 'redirect:/manage/blogs'


@get(path='/manage/users')
def manage_users(*, page='1'):
    return {
        '__template__': 'users_manage.html',
        'page_index': get_page_index(page)
    }


@get(path='/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'comments_manage.html',
        'page_index': get_page_index(page)
    }


@get(path='/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'blogs_manage.html',
        'page_index': get_page_index(page)
    }


@get(path='/manage/blogs/create')
def create_blog():
    return {
        '__template__': 'blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }


@get(path='/manage/blogs/edit')
def create_blog(*, id):
    return {
        '__template__': 'blog_edit.html',
        'id': id,
        'action': '/api/blogs'
    }


@get(path='/api/blogs')
def api_blogs(*, page='1'):
    """loading blogs by page"""
    page_index = get_page_index(page)
    num = yield from find_number(model='blog', selectField='id')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=[])
    blogs = yield from find_models(model='blog', orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


@post(path='/api/blogs')
def api_create_blog(request, *, id, name, summary, content):
    """edit the blog:
        if exist id:    update the blog
        else:           save the blog
    """
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'blog name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'blog summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'blog content cannot be empty.')
    # save the blog
    if id == '':
        blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,
                    name=name.strip(), summary=summary.strip(), content=content.strip())
        yield from save_model(blog)
    # update the blog
    else:
        blog = yield from find_model(model='blog', id=id)
        blog.name = name
        blog.summary = summary
        blog.content = content
        yield from update_model(blog)
    return blog


@get(path='/api/blogs/{id}')
def api_get_blog(*, id):
    """find a blog by it's id"""
    blog = yield from find_model('blog', id)
    return blog


@post(path='/api/blogs/{id}/delete')
def api_delete_blog(*, id):
    """delete a specify blog"""
    blog = yield from find_model(model='blog', id=id)
    yield from delete_model(blog)
    return {}


@get(path='/api/users')
def api_get_users(*, page='1'):
    """loading users by page"""
    page_index = get_page_index(page)
    num = yield from find_number(model='user', selectField='id')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = yield from find_models(model='user', orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.password = '********'
    return dict(page=p, users=users)


@get(path='/api/comments')
def api_get_comments(*, page='1'):
    """loading comments by page"""
    page_index = get_page_index(page)
    num = yield from find_number(model='comment', selectField='id')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    comments = yield from find_models(model='comment', orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)


@post('/api/blogs/{id}/comments')
def api_create_comment(id, request, *, content):
    """save the comment with the associated blog"""
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please login first.')
    if not content or not content.strip():
        raise APIValueError(field='content', message='content can\'t be empty.')
    blog = yield from find_model(model='blog', id=id)
    if blog is None:
        raise APIResourceNotFoundError(field='Blog', message='can\'t load the responding blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image,
                      content=content.strip())
    yield from save_model(comment)
    return comment


@post(path='/api/comments/{id}/delete')
def api_delete_comment(*, id):
    """delete a specify comment"""
    comment = yield from find_model(model='comment', id=id)
    yield from delete_model(comment)
    return {}


"""Patch for Incompatible versions: async <--> yield from"""


@asyncio.coroutine
def find_number(model, selectField, where=None, args=None):
    if model == 'blog':
        count = yield from Blog.findnumber(selectField=selectField, where=where, args=args)
        return count
    if model == 'user':
        count = yield from User.findnumber(selectField=selectField, where=where, args=args)
        return count
    if model == 'comment':
        count = yield from Comment.findnumber(selectField=selectField, where=where, args=args)
        return count


@asyncio.coroutine
def find_model(model, id):
    if model == 'blog':
        blog = yield from Blog.find(id)
        return blog
    if model == 'user':
        user = yield from User.find(id)
        return user
    if model == 'comment':
        comment = yield from Comment.find(id)
        return comment


@asyncio.coroutine
def find_models(model, where=None, args=None, **kw):
    if model == 'user':
        users = yield from User.findall(where=where, args=args, **kw)
        return users
    if model == 'blog':
        blogs = yield from Blog.findall(where=where, args=args, **kw)
        return blogs
    if model == 'comment':
        comments = yield from Comment.findall(where=where, args=args, **kw)
        return comments


@asyncio.coroutine
def save_model(model):
    yield from model.save()


@asyncio.coroutine
def update_model(model):
    yield from model.update()


@asyncio.coroutine
def delete_model(model):
    yield from model.delete()


"""Patch for Incompatible versions"""
