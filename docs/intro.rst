=====================================
Introduction
=====================================

Autocache addresses two of the most common scenarios for caching and cache
invalidation for django models: `instance caching` and `related objects
caching`.


Instance Caching
================
This is the practice of caching individual model instances. Autocache provides
a `CacheController` that you can attach to models to cause automatic caching and
invalidations. ::

    class Model(django.models.Model):
        cache = autocache.CacheController()
        field = django.models.TextField()

    Model.objects.get(pk=27)    # hits the database
    Model.cache.get(27)         # Tries cache first


Related Objects Caching
=======================
Having fetched an instance of a model, a frequent database operation is to
find all the instances of another model that are related to your instance via
foreign keys. You can attach a `RelatedCacheController` to your model to enable
automatic caching and invalidation of these relations. ::

    instance = Model.cache.get(pk=27)
    related_things = instance.things_set.all()  # hits the database
    related_things = instance.cache.things_set  # Tries cache first

The RelatedCacheController will automatically detect and cache objects related
to the model it resides on by ForeignKeys, ManyToManyFields, and
OneToOneFields.


