#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Nate_River'

'''
user class.
'''

from www.orm import Model, StringField, IntegerField, create_connection_pool
import asyncio


class User(Model):
    __table__ = 'user'

    id = IntegerField(primary_key=True)
    name = StringField(ddl='varchar(20)')

    def __str__(self):
        return 'Id: %s  Name: %s' % (self.id, self.name)


async def add():
    await asyncio.sleep(1)
    user = User(id=1, name='Jack')
    await user.save()


async def delete():
    await asyncio.sleep(1)
    user = User(id=1)
    await user.delete()


async def update():
    await asyncio.sleep(1)
    user = User(id=1, name='King')
    await user.update()


async def select():
    await asyncio.sleep(1)
    print('select one')
    user = await User.find(1)
    print(user)
    print('select all')
    users = await User.findall()
    for u in users:
        print(u)
    print('select number')
    count = await User.findnumber(selectField='id')
    print(count)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    tasks = [create_connection_pool(loop, user='root', password='123456', db='blog'), select()]
    loop.run_until_complete(asyncio.wait(tasks))
    loop.run_forever()
