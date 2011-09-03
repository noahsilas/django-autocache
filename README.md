Django-Autocache
================

Autocache addresses two common scenarios for caching and cache invalidation
for django models: *instance caching* and *related objects caching*.

Instance caching: Storing instances of objects in your cache layer
as well as your database.

Related objects caching: Storing a collection of objects related to another
object referenced by relational constraints (ForeignKey, ManyToMany, etc.)

Installing
----------
    pip install -e "git+git://github.com/noah256/django-autocache.git#egg=autocache"

Usage
-----
To start autocaching model instances, add a CacheController to your model:

    from django.db import models
    from autocache import CacheController

    class myModel(models.Model):
        f1 = models.IntegerField()
        f2 = models.TextField()

        cache = CacheController()

    myModel.cache.get(pk=27)

When using autocache, you should avoid django operations that update multiple
rows at once, since these operations typically don't emit the signals that
autocache relies on for cache invalidation. This includes methods like
[`Queryset.update`](https://docs.djangoproject.com/en/1.3/ref/models/querysets/#update),
[`Queryset.delete`](https://docs.djangoproject.com/en/1.3/ref/models/querysets/#delete),
and
[`RelatedManager.clear`](https://docs.djangoproject.com/en/1.3/ref/models/relations/#django.db.models.fields.related.RelatedManager.clear)

Find the complete documentation at [django-autocache.readthedocs.org](http://django-autocache.readthedocs.org/).

Running the tests
-----------------
Django-Autocache has a sample django application that tests the caching
machinery. To run tests, start by cloning the autocache repository and
entering the `tests` directory.

The tests run using memcached and pylibmc. You can change the backend by
editing `autocache/tests/settings.py`. (TODO: get the test suite to run
multiple times with different backends)

- Start two memcached servers (testing multicache)
    - `memcached -p 11211 -U 0`
    - `memcached -p 11212 -U 0`
- Change into the `autocache/tests/` directory and run `manage.py test`

