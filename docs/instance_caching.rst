================
Instance Caching
================

The CacheController works by listening for the post_save and post_delete
signals that the model it is attached to will emit when you alter an instance.
This allows it to automatically keep cached instances up to date! ::

    from django.db import models
    from autocache.controller import CacheController

    class Model(models.Model):
        field1 = IntegerField()
        field2 = TextField()

        cache = CacheController()


Reading From Cache
==================
You can use the cache controller like a very simple manager: currently only
the ``.get(pk)`` operation is supported. This will try to get and return the
model instance from cache. In the event that the key does not have a cache
entry, the value is read from the database using the model's default manager.
The result is placed into the cache before being returned to the caller. ::

    obj = Model.cache.get(pk=933)

Just like objects.get(), cache.get() may raise a Model.DoesNotExist exception.
A DoesNotExist marker is placed in cache when an instance is deleted or an
attempt to fetch a non-existent row is made, preventing subsequent requests
against the cache from hitting DB or returning stale data.


.. _instance_cache_keys:

Instance Cache Keys
===================

The default CacheController creates keys based on your model's app, name and
primary key, separated by colons:
``app_label:model_name:primary_key``. This should present you with a unique
key for each object. 

.. note::
    This can be problematic if your model uses a primary key that can contain
    whitespace and you are using memcached as your cache backend. One possible
    solution is to provide a key generation function that hashes the key (see
    example below). You can also use a cache backend like `Django NewCache`_
    that automatically hashes the key.

.. _Django NewCache: https://github.com/ericflo/django-newcache


Overriding Cache Key Generation
-------------------------------
You can subclass CacheController and override the make_key function to
customize your cache keys.

CacheController.make_key(`self, pk`)
    Called to generate all cache keys for this controller. You can access the
    model class that this controller is attached to through ``self.model``.

Examples
^^^^^^^^
::

    import hashlib

    class HashCacheController(CacheController):
        """ Hashes the cache key. This creates keys that are difficult to type
            by hand, but can avoid problems related to key content and length.
        """
        def make_key(self, pk):
            key = super(HashCacheController, self).make_key(pk)
            return hashlib.sha256(key).hexdigest()

    class ModelVersionCacheController(CacheController):
        """ Versions each cache key with the model's CACHE_VERSION attribute.
            Updating the model's version when altering it's schema will
            effectively invalidate all cached instances.
        """
        def make_key(self, pk):
            model_version = getattr(self.model, 'CACHE_VERSION', 0)
            key = ':'.join([super(HashCacheController, self), model_version])
            return key


.. _cache_timeouts:

Cache Timeouts
==============
The default cache timeout is one hour. You can specify a number of seconds
to timeout as the ``timeout`` parameter in the CacheController constructor. : ::

    cache = CacheController(timeout=(60 * 60 * 24 * 7)) # timeout in one week


Overriding the default timeout
------------------------------

If you find yourself frequently overriding the default timeout, you can
subclass the CacheController and set a ``DEFAULT_TIMEOUT`` attribute: ::

    class LongCacheController(CacheController):
        # timeouts longer than 30 days are treated as absolute timestamps by
        # memcached; that makes 30 days the largest naive value we can use.
        DEFAULT_TIMEOUT = 60 * 60 * 24 * 30


.. _multicache:

Multicache
----------

Starting in Django 1.3 you could define multiple cache backends. If you want
to tie the instance cache for a model to a backend other than 'default', you
can pass the name of the backend you want to use into the controller
constructor as the keyword argument ``backend``.


Caveats
=======

Autocache relies on the post_save and post_delete signals to keep your cache
up to date. Performing operations that alter the database state without
sending these signals will result in your cache becoming out of sync with your
database.

.. note::
    Do not use queryset.update() with models that have a CacheController
    attached! Your cache will **not** be updated.

