
traits-sqlalchemy 
--------------------
Utilities for mapping [HasTraits](https://github.com/enthought/traits) classes to a relational database using
[SQLAlchemy](http://www.sqlalchemy.org).


*NOTE:* This project is in the process of  being revived. Currently, it only 
works with flat (non-relational) classes, ie no Foreignkey.





These tools are not declarative, like the Elixir extension. Rather, they just
provide the low-level support for mapping an existing schema to traited classes.
Your classes must subclass from `HasDBTraits`. Each mapped trait should have the
"db_storage=True" metadata. Many of the traits have been subclassed here to
provide this by default, e.g. DBInt, DBInstance, DBStr, etc. Many of these are
also customized to accept None, too, in order to support SQL NULLs.

The only collection trait supported is DBList. One cannot currently map Dict or
Set traits. 




