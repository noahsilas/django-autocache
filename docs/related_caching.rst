======================
Related Object Caching
======================

Introduction
============

Given a model instance, one frequent database query is to get instances of
another model that are related. This is commonly accomplished with the use
of a Foreign Key.

We will be using the following models as examples throughout this document: ::

    from django.db import models
    from autocache.controllers import RelatedCacheController

    class Person(models.Model):
        name = models.CharField(max_length=200)

        cache = RelatedCacheController()

    class Book(models.Model):
        author = models.ForeignKey(Person, related_name='books')
        title = models.CharField(max_length=200)
        published_date = models.DateTimeField()

        class Meta:
            default_ordering = ('-published_date')

Suppose you have an authorship view, displaying all of the books that a
given author has published. The view would typically look something like
this: ::

    def authorship(request, author_id):
        try:
            author = Person.objects.get(pk=author_id)
        except Person.DoesNotExist:
            raise Http404("No such person")
        books = author.books.all()
        return render(
            request,
            {'author': author, 'books': books},
            'authorship.html'
        )

This pattern will invoke two database queries: one to fetch a Person, and
one to fetch the books with a foreign key relationship to the author. We can
use the autocache features to try the cache first. ::

    author = Person.objects.get(pk=author_id)   # database query
    author = Person.cache.get(pk=author_id)     # cached query

    books = author.books.all()                  # database query
    books = author.cache.books                  # cached query


Reading From Cache
==================
Given an instance of an object with a RelatedCacheController, all of the
attributes on the instance to fetch related objects are mirrored on the
controller. If the instance has a ``.thing_set`` and a RelatedCacheManager
assigned to ``cache``, then ``instance.cache.thing_set`` will return the
same values as ``list(instance.thing_set.all())``. 

.. note::
    Related object caches return lists of instances, not querysets. This means
    that you don't need to put the .all() on the end, but also that you can
    not apply django queryset operations like ``.filter()`` or
    ``.select_related()`` on the result.


Cache Keys
==========
A cache key for the instance is obtained by calling the same ``make_key(pk)``
function described in :ref:`instance_cache_keys`. The key for the related
objects is the instance key, appended with the related name of the collection.
::

    author = Person.objects.get(pk=1)   # get an instance of a Person in the sample_app
    author.cache.books                  # cache key is sample_app:Person:1:books


Cache Timeouts and Multicache
=============================
The RelatedCacheController accepts the same :ref:`timeout <cache_timeouts>`
and :ref:`backend <multicache>` arguments as CacheController.

::

    cache = RelatedCacheController(
            timeout=(60 * 60 * 24 * 7),     # timeout in one week
            backend='my_app_cache'),        # use the cache backend named 
                                            # 'my_app_cache' in settings.py
        )


