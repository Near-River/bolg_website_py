#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Nate_River'

'''
orm framework.
'''

import logging as log
import aiomysql
import asyncio
from aiomysql import create_pool


async def create_connection_pool(loop, **kwargs):
    """create the connection pool"""
    log.info('create database connection pool...')
    global __pool__
    __pool__ = await create_pool(
        host=kwargs.get('host', 'localhost'),
        port=kwargs.get('port', 3306),
        user=kwargs['user'],
        password=kwargs['password'],
        db=kwargs['db'],
        charset=kwargs.get('charset', 'utf8'),
        autocommit=kwargs.get('autocommit', True),
        maxsize=kwargs.get('maxsize', 10),
        minsize=kwargs.get('minsize', 1),
        loop=loop
    )
    # print(type(__pool__))   # <class 'aiomysql.pool.Pool'>


async def select(sql, args, size=None):
    """execute select instruction
        return the query result set
    """
    log.info('SQL: %s', sql)
    global __pool__
    async with __pool__.get() as conn:
        # print(type(conn))   # <class 'aiomysql.connection.Connection'>
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(sql.replace('?', '%s'), args or ())
            if size:
                if size == 1:
                    rs = await cursor.fetchone()
                else:
                    rs = await cursor.fetchmany(size)
            else:
                rs = await cursor.fetchall()
            log.info('rows returned %s' % len(rs))
            return rs


async def execute(sql, args, autocommit=True):
    """execute insert | update | delete instruction
        return the affected rows number
    """
    log.info('SQL: %s', sql)
    global __pool__
    async with __pool__.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql.replace('?', '%s'), args)
                affected = cursor.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected


class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    def __init__(self, name=None, ddl='varchar(255)', primary_key=False, default=None):
        super(StringField, self).__init__(name, ddl, primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, default=0.0):
        super().__init__(name, 'real', False, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


def create_args_string(num):
    s = '?, ' * num
    return s[:len(s) - 2]


class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # read the table name from the mapping class
        tablename = attrs.get('__table__', None) or name
        log.info('found model: %s (table: %s)' % (name, tablename))

        # save all the object fields name
        fields = list()
        # save the primary key name
        primary_key = None
        # save the mapping from object attributes name to table fields
        mappings = dict()

        for k, v in attrs.items():
            if isinstance(v, Field):
                log.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    if primary_key:
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primary_key = k
                else:
                    fields.append(k)
        if not primary_key:
            raise RuntimeError('Primary key not found.')
        for k in mappings:
            attrs.pop(k)

        attrs['__table__'] = tablename
        attrs['__mappings__'] = mappings
        attrs['__primarykey__'] = primary_key
        attrs['__fields__'] = fields

        # create the default SELECT, INSERT, UPDATE and DELETE statement
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primary_key, ', '.join(escaped_fields), tablename)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (
            tablename, ', '.join(escaped_fields), primary_key, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (
            tablename, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primary_key)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tablename, primary_key)
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kwargs):
        super(Model, self).__init__(**kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getvalue(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                log.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    @classmethod
    async def find(cls, pk):
        """find object by primary key value"""
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primarykey__), args=(pk,), size=1)
        if len(rs) == 0:
            return None
        return cls(**rs)

    @classmethod
    async def findall(cls, where=None, args=None, **kw):
        """find objects by where clause"""
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderby = kw.get('orderBy', None)
        if orderby:
            sql.append('order by')
            sql.append(orderby)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, [tuple, list]) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    async def findnumber(cls, selectField, where=None, args=None):
        sql = ['select count(%s) _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs['_num_']

    async def save(self):
        args = list(map(self.getvalue, self.__fields__))
        args.append(self.getvalue(self.__primarykey__))
        rows = await execute(self.__insert__, args=args)
        if rows != 1:
            log.warning('failed to insert by primary key: affected rows: %s' % rows)

    async def update(self):
        args = list(map(lambda key: getattr(self, key, None), self.__fields__))
        args.append(getattr(self, self.__primarykey__, None))
        rows = await execute(self.__update__, args=args)
        if rows != 1:
            log.warning('failed to update by primary key: affected rows: %s' % rows)

    async def delete(self):
        args = [getattr(self, self.__primarykey__, None)]
        rows = await execute(self.__delete__, args=args)
        if rows != 1:
            log.warning('failed to delete by primary key: affected rows: %s' % rows)

# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(create_connection_pool(loop, user='root', password='123456', db='blog'))
#     loop.run_forever()
