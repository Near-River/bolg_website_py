#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Nate_River'

'''
test User: CRUD
'''

from www.models import User
import www.orm as orm
import asyncio
import sys


async def testSave(loop):
    await orm.create_connection_pool(loop, user='root', password='123456', db='blog')
    user = User(email='near@gmail.com', password='admin', name='Near', admin=True)
    # user = User(id='1', email='near@gmail.com', password='admin', name='Near', admin=True)
    await user.save()


async def testDelete(loop):
    await orm.create_connection_pool(loop, user='root', password='123456', db='blog')
    user = await User.find('1')
    await user.delete()


async def testUpdate(loop):
    await orm.create_connection_pool(loop, user='root', password='123456', db='blog')
    user = await User.find('1')
    user.password = '123456'
    await user.update()


async def testQuery(loop):
    await orm.create_connection_pool(loop, user='root', password='123456', db='blog')
    print('select all')
    users = await User.findall()
    for u in users:
        print(u.email)
    print('select number')
    count = await User.findnumber(selectField='id')
    print(count)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # loop.run_until_complete(testSave(loop=loop))
    # loop.run_until_complete(testUpdate(loop=loop))
    # loop.run_until_complete(testDelete(loop=loop))
    loop.run_until_complete(testQuery(loop=loop))
    loop.close()
    if loop.is_closed():
        sys.exit(0)
