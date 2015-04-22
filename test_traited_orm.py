from __future__ import with_statement

from nose.tools import assert_equal
import sqlalchemy as sql
from sqlalchemy import orm

from traits.api import push_exception_handler, pop_exception_handler

import traited_orm

# Test schema
metadata = sql.MetaData()
foo = sql.Table('foo', metadata,
    sql.Column('id', sql.Integer, primary_key=True),
    sql.Column('int', sql.Integer),
    sql.Column('float', sql.Float),
    sql.Column('string', sql.String(16)),
)
bar = sql.Table('bar', metadata,
    sql.Column('id', sql.Integer, primary_key=True),
    sql.Column('foo_id', None, sql.ForeignKey('foo.id')),
    sql.Column('string', sql.String(16)),
)
baz = sql.Table('baz', metadata,
    sql.Column('id', sql.Integer, primary_key=True),
    sql.Column('string', sql.String(16)),
)
foo_baz = sql.Table('foo_baz', metadata,
    sql.Column('id', sql.Integer, primary_key=True),
    sql.Column('foo_id', None, sql.ForeignKey('foo.id')),
    sql.Column('baz_id', None, sql.ForeignKey('baz.id')),
)

class Bar(traited_orm.ORMapped):
    id = traited_orm.DBIntKey
    string = traited_orm.DBStr

class Baz(traited_orm.ORMapped):
    id = traited_orm.DBIntKey
    string = traited_orm.DBStr

class Foo(traited_orm.ORMapped):
    id = traited_orm.DBIntKey
    int = traited_orm.DBInt
    float = traited_orm.DBFloat
    string = traited_orm.DBStr

    bars = traited_orm.DBList()
    bazzes = traited_orm.DBList()

orm.mapper(Foo, foo)
orm.mapper(Bar, bar)
orm.mapper(Baz, baz)
'''traited_orm.trait_mapper(Foo, foo, properties=dict(
    bars = traited_orm.trait_list_relation(Bar),
    bazzes = traited_orm.trait_list_relation(Baz, secondary=foo_baz),
))
'''
db = None
conn = None
session = None

def setup():
    """ Module-level setup so this only happens once for all of these tests
    rather than once per test.
    """
    global db, conn, session
    def ignore(*args):
        pass
    push_exception_handler(handler=ignore, reraise_exceptions=True)
    db = sql.create_engine('sqlite:///:memory:')
    metadata.bind = db
    metadata.create_all()
    conn = db.connect()
    session = orm.sessionmaker()()

def teardown():
    conn.close()
    metadata.bind = None
    pop_exception_handler()


def test_simple():
    transaction = conn.begin()
    try:
        session.add(Foo(int=10, float=20.0, string='Foo'))
        session.commit()
        session.flush()
        foo = session.query(Foo).first()
        assert_equal(foo.int, 10)
        assert_equal(foo.float, 20.0)
        assert_equal(foo.string, 'Foo')
        
        
    finally:
        transaction.rollback()
'''
def test_create_via_instantiation():
    transaction = conn.begin()
    try:
        session.add(Foo(int=10, float=20.0, string='Foo',
            bars=[Bar(string='bar1'), Bar(string='barnone')],
            bazzes=[Baz(string='baz1'), Baz(string='baz2')])
            )
        session.commit()
        session.flush()
        foo = session.query(Foo).first()
        assert_equal(foo.int, 10)
        assert_equal(foo.float, 20.0)
        assert_equal(foo.string, 'Foo')
        assert_equal(set([b.string for b in foo.bars]), set(['bar1', 'barnone']))
        assert_equal(set([b.string for b in foo.bazzes]), set(['baz1', 'baz2']))
    finally:
        transaction.rollback()

def test_scalars_update():
    transaction = conn.begin()
    try:
        session.add(Foo(int=10, float=20.0, string='Foo'))
        session.commit()
        session.flush()
        foo = session.query(Foo).first()
        foo.int = 20
        foo.float = 30.0
        foo.string = 'Not Foo'
        
        session.commit()
        
        raise ValueError
        #session.flush()
        del foo
        foo2 = session.query(Foo).first()
        yield assert_equal, foo2.int, 20
        yield assert_equal, foo2.float, 30.0
        yield assert_equal, foo2.string, 'Not Foo'
    finally:
        transaction.rollback()

def test_lists_update_via_assignment():
    transaction = conn.begin()
    try:
        session.add(Foo())
        session.commit()
        session.flush()
        foo = session.query(Foo).first()
        foo.bars = [Bar(string='bar1'), Bar(string='barnone')]
        session.flush()
        del foo
        foo2 = session.query(Foo).first()
        yield assert_equal, set([b.string for b in foo2.bars]), set(['bar1', 'barnone'])
        foo2.bazzes = [Baz(string='baz1'), Baz(string='baz2')]
        session.flush()
        del foo2
        foo3 = session.query(Foo).first()
        yield assert_equal, set([b.string for b in foo3.bazzes]), set(['baz1', 'baz2'])
    finally:
        transaction.rollback()

def test_lists_update_via_modification():
    transaction = conn.begin()
    try:
        session.add_all(Foo(
            bars=[Bar(string='bar1'), Bar(string='barnone')],
            bazzes=[Baz(string='baz1'), Baz(string='baz2')],
        ))
        session.commit()
        session.flush()
        foo = session.query(Foo).first()
        foo.bars.append(Bar(string='bar3'))
        foo.bazzes.append(Baz(string='baz3'))
        session.flush()
        del foo
        foo2 = session.query(Foo).first()
        yield assert_equal, set([b.string for b in foo2.bars]), set(['bar1', 'barnone', 'bar3'])
        yield assert_equal, set([b.string for b in foo2.bazzes]), set(['baz1', 'baz2', 'baz3'])
        del foo2.bars[0]
        del foo2.bazzes[0]
        session.flush()
        del foo2
        foo3 = session.query(Foo).first()
        yield assert_equal, set([b.string for b in foo3.bars]), set(['barnone', 'bar3'])
        yield assert_equal, set([b.string for b in foo3.bazzes]), set(['baz2', 'baz3'])
    finally:
        transaction.rollback()

def test_cloning_does_not_clone_sqlalchemy_metadata():
    transaction = conn.begin()
    try:
        session.add(Foo(int=10, float=20.0, string='Foo'))
        session.commit()
        session.flush()
        foo = session.query(Foo).first()
        foo2 = foo.clone_traits()
        assert set(foo.traits(db_storage=True).keys() + ['trait_added', 'trait_modified', '_session']) == set(foo2.traits().keys())
    finally:
        transaction.rollback()
'''
