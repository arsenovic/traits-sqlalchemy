""" Utilities for mapping HasTraits classes to a relational database using
SQLAlchemy.

These tools are not declarative, like the Elixir extension. Rather, they just
provide the low-level support for mapping an existing schema to traited classes.
Your classes must subclass from HasDBTraits. Each mapped trait should have the
"db_storage=True" metadata. Many of the traits have been subclassed here to
provide this by default, e.g. DBInt, DBInstance, DBStr, etc. Many of these are
also customized to accept None, too, in order to support SQL NULLs.

The only collection trait supported is DBList. One cannot currently map Dict or
Set traits. 

Instead of using sqlalchemy.orm.mapper() to declare mappers, use trait_mapper().
For 1:N and M:N relations that map to a DBList, use trait_list_relation()
instead of sqlalchemy.orm.relation().
"""


import weakref

from sqlalchemy.orm import EXT_CONTINUE, MapperExtension, mapper, relation, session, reconstructor

from sqlalchemy.orm.attributes import set_attribute
from traits.api import (Any, Array, Either, Float, HasTraits,
    Instance, Int, List, Property, Python, Str, TraitListObject, on_trait_change)

__all__ = ['MappedTraitListObject', 'DBList', 'DBAny', 'DBArray', 'DBFloat',
    'DBInstance', 'DBInt', 'DBIntKey', 'DBStr', 'HasDBTraits',
    'trait_list_relation', 'trait_mapper']


# A unique object to act as a dummy object for MappedTraitListObjects so we know
# when they have been constructed outside of Traits. It needs to be a valid
# HasTraits instance, but otherwise, nothing special.
HAS_TRAITS_SENTINEL = HasTraits()

class MappedTraitListObject(TraitListObject):
    """ TraitListObject decorated for SQLAlchemy relations.
    """
    __emulates__ = list

    def __init__(self, *args, **kwds):
        if not args and not kwds:
            args = (DBList(), HAS_TRAITS_SENTINEL, '__fake', [])
        TraitListObject.__init__(self, *args, **kwds)

# FIXME: Fix Traits so we don't need this hack.
class WeirdInt(int):
    """ Work around a missing feature in Traits.

    Traits uses the default_value_type to determine if a trait is a List, Dict,
    etc. through a dict lookup for deciding if it is going to add the *_items
    events. List subclasses need to use a different default_value_type, though,
    so we'll pretend that we look like a list (default_value_type=5). The other
    place where Traits uses the default_value_type is in the C code, where it
    converts it to a C int, so it will get the real value of "8" there.

    Horrible, horrible hack. I am not proud.
    """
    def __hash__(self):
        return hash(5)
    def __eq__(self, other):
        if other == 5:
            return True
        else:
            return int(self) == other

class DBList(List):
    """ Subclass of List traits to use SQLAlchemy mapped lists.
    """

    default_value_type = WeirdInt(8)

    def __init__(self, *args, **kwds):
        kwds['db_storage'] = True
        List.__init__(self, *args, **kwds)

        # Set up the Type-8 initializer.
        self.real_default_value = self.default_value
        def type8_init(obj):
            # Handle the conversion to a MappedTraitListObject in the validator.
            return self.real_default_value
        self.default_value = type8_init

    def validate(self, object, name, value):
        """ Validates that the values is a valid list.
        """
        if (isinstance(value, list) and
           (self.minlen <= len(value) <= self.maxlen)):
            if object is None:
                return value

            if hasattr(object, '_state'):
                # Object has been mapped.
                attr = getattr(object.__class__, name)
                _, list_obj = attr.impl._build_collection(object._state)
                # Add back the Traits-specified information.
                list_obj.__init__(self, object, name, value)
            else:
                # Object has not been mapped, yet.
                list_obj = MappedTraitListObject(self, object, name, value)
            return list_obj

        self.error(object, name, value)

class DBAny(Any):
    def __init__(self, *args, **kwds):
        kwds['db_storage'] = True
        super(DBAny, self).__init__(*args, **kwds)

class DBInstance(Instance):
    def __init__(self, *args, **kwds):
        kwds['db_storage'] = True
        super(DBInstance, self).__init__(*args, **kwds)

class DBArray(Array):
    def __init__(self, *args, **kwds):
        kwds['db_storage'] = True
        super(DBArray, self).__init__(*args, **kwds)

class DBInt(Either):
    def __init__(self, **kwds):
        kwds['db_storage'] = True
        kwds['default'] = 0
        super(DBInt, self).__init__(Int, None, **kwds)

class DBIntKey(Either):
    def __init__(self, **kwds):
        kwds['db_storage'] = True
        super(DBIntKey, self).__init__(None, Int, **kwds)

class DBUUID(Any):
    def __init__(self, *args, **kwds):
        kwds['db_storage'] = True
        super(DBUUID, self).__init__(*args, **kwds)

class DBFloat(Either):
    def __init__(self, **kwds):
        kwds['db_storage'] = True
        kwds['default'] = 0.0
        super(DBFloat, self).__init__(Float, None, **kwds)

class DBStr(Either):
    def __init__(self, **kwds):
        kwds['db_storage'] = True
        kwds['default'] = ''
        super(DBStr, self).__init__(Str, None, **kwds)

def _fix_dblist(object, value, trait_name, trait):
    """ Fix MappedTraitListObject values for DBList traits that do not have the
    appropriate metadata.

    No-op for non-DBList traits, so it may be used indiscriminantly.
    """
    if isinstance(trait.handler, DBList):
        if value.object() is HAS_TRAITS_SENTINEL:
            value.object = weakref.ref(object)
            value.name = trait_name
            value.name_items = trait_name + '_items'
            value.trait = trait.handler


class HasDBTraits(HasTraits):
    """ Base class providing the necessary connection to the SQLAlchemy mapper.
    """
    
    @reconstructor
    def init_on_load(self):
        """
        This will make sure that the HasTraits machinery is hooked up so that
        things like @on_trait_change() will work.
        """
        super(HasDBTraits, self).__init__()
        # Check for bad DBList traits.
        for trait_name, trait in self.traits(db_storage=True).items():
            value = self.trait_get(trait_name)[trait_name]
            _fix_dblist(self, value, trait_name, trait)

    # The SQLAlchemy Session this object belongs to.
    _session = Property()

    # Any implicit traits added by SQLAlchemy are transient and should not be
    # copied through .clone_traits(), copy.copy(), or pickling.
    _ = Python(transient=True)

    def _get__session(self):
        return session.object_session(self)

    @on_trait_change('+db_storage')
    def _tell_sqlalchemy(self, object, trait_name, old, new):
        """ If the trait being changed has db_storage metadata, set dirty flag.

        Returns
        -------
        If self is linked to a SQLAlchemy session and the conditions have
        been met then the dirty flag on the SQLAlchemy metadata will be set.

        Description
        -----------
        HasTrait bypasses the default class attribute getter and setter which
        in turn causes SQLAlchemy to fail to detect that a class has data 
        to be flushed.  As a work-around we must manually set the SQLAlchemy
        dirty flag when one of our db_storage traits has been changed.
        """
        
        
        if hasattr(self, '_sa_instance_state'):
            trait = self.trait(trait_name)
            # Use the InstrumentedAttribute descriptor on this class inform
            # SQLAlchemy of the changes.
            instr = getattr(self.__class__, trait_name)
            # SQLAlchemy looks at the __dict__ for information. Fool it.
            self.__dict__[trait_name] = old
            _fix_dblist(self, new, trait_name, trait)
            instr.__set__(self, new)
            # The value may have been replaced. Fix it again.
            new = self.trait_get(trait_name)[trait_name]
            _fix_dblist(self, new, trait_name, trait)
            self.__dict__[trait_name] = new
        return

def trait_list_relation(argument, secondary=None,
    collection_class=MappedTraitListObject, **kwargs):
    """ An eager relation mapped to a List trait.

    The arguments are the same as sqlalchemy.orm.relation().
    """
    kwargs['lazy'] = False
    return relation(argument, secondary=secondary,
        collection_class=collection_class, **kwargs)
    
class TraitMapperExtension(MapperExtension):
    """ Create HasDBTraits instances correctly.
    """

    def create_instance(self, mapper, selectcontext, row, class_):
        """ Create HasDBTraits instances correctly.

        This will make sure that the HasTraits machinery is hooked up so that
        things like @on_trait_change() will work.
        """
        if issubclass(class_, HasTraits):
            obj = mapper.class_manager.new_instance(class_)
            HasTraits.__init__(obj)
            return obj
        else:
            return EXT_CONTINUE

    def populate_instance(self, mapper, selectcontext, row, instance, **flags):
        """ Receive a newly-created instance before that instance has
        its attributes populated.

        This will fix up any MappedTraitListObject values which were created
        without the appropriate metadata.
        """
        if isinstance(instance, HasTraits):
            mapper.populate_instance(selectcontext, instance, row, **flags)
            # Check for bad DBList traits.
            for trait_name, trait in instance.traits(db_storage=True).items():
                value = instance.trait_get(trait_name)[trait_name]
                _fix_dblist(instance, value, trait_name, trait)
        else:
            return EXT_CONTINUE


