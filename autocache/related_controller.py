"""
.. module:cm
   :platform: Django
   :synopsis: Provides a RelatedCacheController object which does automatic caching of 'related fields' on Django models.

.. moduleauthor:: Noah Silas
"""
from operator import attrgetter

from django.db import models
from django.db.models.fields.related import RelatedField
from django.db.models.manager import ManagerDescriptor
from django.utils.functional import curry

from .relation import Relation
from .controller import CacheController, no_arg

### Module level variable used to track lazy relations during
### model initialization.
pending_lookups = {}


def _sort(objects, ordering):
    """ Given an ordering for a model, sort a list of instances of the model.
    """
    for order_by in reversed(ordering):
        reverse = False
        if order_by[0] == '-':
            order_by = order_by[1:]
            reverse = True
        objects.sort(key=attrgetter(order_by), reverse=reverse)



class FieldCachingDescriptor(object):
    def __init__(self, name):
        self.name = '_' + name
        self.cache = self.cachename(name)

    def __get__(self, instance, owner):
        return getattr(instance, self.name)

    def __set__(self, instance, value):
        if not hasattr(instance, self.cache):
            setattr(instance, self.cache, value)
        setattr(instance, self.name, value)

    @staticmethod
    def cachename(name):
        return '_original_' + name + '_cache'


class InstanceCacheManager(object):

    def __init__(self, instance, manager):
        self.instance = instance
        self.manager = manager

    def __getattr__(self, name):
        relation = None
        manager = self.manager

        names = dict((rel.get_accessor_name(), rel) for rel in manager.relations)
        for rel in manager.m2m_relations:
            if rel.model == self.manager.model:
                names[rel.field.name] = rel
            else:
                names[rel.get_accessor_name()] = rel

        if name not in names:
            raise AttributeError("Attempting to access an unknown relation (%s)" % name)

        relation = names[name]

        key = '%s:%s' % (manager.make_key(self.instance.pk), name)
        objects = self.manager.cache.get(key)

        prepare = lambda x: list(x.all())
        if isinstance(relation.field, models.OneToOneField):
            prepare = lambda x: x
            if objects == self.manager.DNE:
                raise relation.model.DoesNotExist()

        if objects is None:
            objects = prepare(getattr(self.instance, name))
            self.manager.cache.set(key, objects, self.manager.timeout)

        return objects


class RelatedCacheController(CacheController):

    def __init__(self, backend='default', timeout=no_arg):
        super(RelatedCacheController, self).__init__(backend, timeout)
        self.relations = []
        self.m2m_relations = []

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return InstanceCacheManager(instance, self)

    def contribute_to_class(self, model, name):
        super(RelatedCacheController, self).contribute_to_class(model, name)
        # Remember the name that we're binding to
        self.manager_name = name

        # add listener for built models; we will check models as they finish
        # being constructed to see if they relate to our model
        models.signals.class_prepared.connect(self._check_relations)

        # we want to use self as our manager descriptor, so we will replace
        # the one that django put there for us
        setattr(model, name, self)

    def _check_relations(self, sender, **kwargs):
        """ Checks newly registered models for relations to self.model.
        """
        if sender is self.model:
            self._setup_initial_relations()
            return

        for field in sender._meta.fields:
            if isinstance(field, RelatedField):
                if field.rel.to is self.model:
                    if hasattr(field, 'related'):
                        self._setup_relation(field.related)
                    else:
                        # This is a lazy relation
                        # Look for an "app.Model" relation
                        try:
                            app_label, model_name = field.rel.to.split(".")
                        except ValueError:
                            # If we can't split, assume a model in current app
                            app_label = self.model._meta.app_label
                            model_name = relation
                        except AttributeError:
                            # If it doesn't have a split it's actually a model class
                            app_label = field.rel.to._meta.app_label
                            model_name = field.rel.to._meta.object_name

                        key = (app_label, model_name)
                        value = (self.model, field)
                        pending_lookups.setdefault(key, []).append(value)

        for field in sender._meta.many_to_many:
            if field.rel.to is self.model:
                self._setup_m2m_relation(field)

    def _setup_initial_relations(self):
        """ Called when self.model is fully initialized; registers all
            known relations for cache handling.
        """
        for relation in self.model._meta.get_all_related_objects():
            self._setup_relation(relation)

        for field in self.model._meta.many_to_many:
            if isinstance(field, models.ManyToManyField):
                self._setup_m2m_relation(field)

        # check if there are lazy relations waiting
        key = (self.model._meta.app_label, self.model._meta.object_name)
        for model, field in pending_lookups.pop(key, ()):
            if isinstance(field, models.ManyToManyField):
                self._setup_m2m_relation(field)
            else:
                self._setup_relation(field.related)

    def _setup_relation(self, relation):
        """ Given a relation to this model, hooks up cache invalidation functions
        """
        self.relations.append(relation)
        setattr(relation.model, relation.field.name + '_id', FieldCachingDescriptor(relation.field.name + '_id'))

        f = curry(self.related_post_save_invalidate, relation)
        models.signals.post_save.connect(f, sender=relation.model, weak=False)

        f = curry(self.related_post_delete_invalidate, relation)
        models.signals.post_delete.connect(f, sender=relation.model, weak=False)

    def _invalidate_delete(self, relation, pk, instance_pk):
        key = ':'.join((self.make_key(pk), relation.get_accessor_name()))

        if isinstance(relation.field, models.OneToOneField):
            self.cache.set(key, self.DNE, self.timeout)
            return

        objects = self.cache.get(key)
        if objects is None:
            filters = {relation.field.name: pk}
            objects = relation.model.objects.filter(**filters)
            self.cache.set(key, list(objects), self.timeout)

        else:
            try:
                # try to remove the object in the cache list
                pks = [o.pk for o in objects]
                index = pks.index(instance_pk)
                del objects[index]
            except ValueError:
                pass
            self.cache.set(key, objects, self.timeout)

    def _invalidate(self, relation, instance):
        field_name = relation.field.name + '_id'
        pk_cache_name = FieldCachingDescriptor.cachename(field_name)
        pk = getattr(instance, field_name)
        pk_cache = getattr(instance, pk_cache_name)

        if pk != pk_cache:
            if pk_cache or relation.field.null:
                # if the former pk is None on a non_nullable field, then it means
                # that an object has been created, and we don't have to worry
                # about removing it from an existing cache key. Unfortunately,
                # nullable fields don't give us that option.
                self._invalidate_delete(relation, pk_cache, instance.pk)

        key = ':'.join((self.make_key(pk), relation.get_accessor_name()))

        objects = self.cache.get(key)

        if objects is None:
            if isinstance(relation.field, models.OneToOneField):
                filters = {relation.field.name: pk}
                try:
                    obj = relation.model.objects.get(**filters)
                except relation.model.DoesNotExist:
                    self.cache.set(key, self.DNE, self.timeout)
                    raise

                self.cache.set(key, obj, self.timeout)
            else:
                filters = {relation.field.name: pk}
                objects = relation.model.objects.filter(**filters)
                self.cache.set(key, list(objects), self.timeout)
        else:
            if isinstance(relation.field, models.OneToOneField):
                self.cache.set(key, instance, self.timeout)

            else:
                try:
                    # try to replace the object in the cache list
                    pks = [o.pk for o in objects]
                    index = pks.index(instance.pk)
                    objects[index] = instance
                except ValueError:
                    # the object isn't in the list; add it
                    objects.append(instance)
                if relation.model._meta.ordering:
                    _sort(objects, relation.model._meta.ordering)

                self.cache.set(key, objects, self.timeout)

        # update the cached relation value so another .save() won't try
        # to do cache invalidations again
        setattr(instance, pk_cache_name, pk)

    def related_post_save_invalidate(self, relation, instance, **kwargs):
        self._invalidate(relation, instance)

    def related_post_delete_invalidate(self, relation, instance, **kwargs):
        field_name = relation.field.name + '_id'
        pk = getattr(instance, field_name)
        self._invalidate_delete(relation, pk, instance.pk)


    ###
    ### Many To Many Invalidation Routines
    ###

    def _setup_m2m_relation(self, field):
        """ Sets up cache invalidation functions for a m2m field related to self.model
        """

        if field.model is self.model:
            self.m2m_relations.append(field.related)
        else:
            self.relations.append(field.related)

        f = curry(self.post_m2m_invalidate, field.related)
        models.signals.m2m_changed.connect(f, sender=field.rel.through, weak=False)

        remote = field.related.model is self.model
        sender = field.related.parent_model if remote else field.related.model
        f = curry(self.m2m_post_save_invalidate, field.related)
        models.signals.post_save.connect(f, sender=sender, weak=False)

    def post_m2m_invalidate(self, relation, sender, instance, action, reverse, model, pk_set, **kwargs):
        """ Signal handler for django.db.models.signals.m2m_changed
        """

        funcs = {
            'post_add': {
                True: self._m2m_add_local,
                False: self._m2m_add_remote,
            },
            'post_remove': {
                True: self._m2m_remove_local,
                False: self._m2m_remove_remote,
            },
        }

        local = self.model is instance.__class__
        try:
            f = funcs[action][local]
        except KeyError:
            return

        attribute_name = relation.field.name
        accessor_name = relation.get_accessor_name()
        if local ^ reverse:
            # The reverse end of the relation is being accessed. Swap the
            # accessor and attribute names to represent the other end or the
            # relationship.
            attribute_name, accessor_name = accessor_name, attribute_name

        f(relation, instance, pk_set, accessor_name, attribute_name)

    def _m2m_add_local(self, relation, instance, pk_set, attribute_name, accessor_name):
        """ add the model instances matching pk_set to instance's cache set """
        key = ':'.join((self.make_key(instance.pk), attribute_name))
        objects = self.cache.get(key)
        if objects is None:
            objects = getattr(instance, attribute_name).all()
            self.cache.set(key, list(objects), self.timeout)
        else:
            pks = [o.pk for o in objects]
            instances = relation.parent_model._default_manager.filter(pk__in=pk_set)
            for instance in instances:
                if instance.pk not in pks:
                    objects.append(instance)
            if relation.parent_model._meta.ordering:
                _sort(objects, relation.parent_model._meta.ordering)
            self.cache.set(key, objects, self.timeout)

    def _m2m_add_remote(self, relation, instance, pk_set, attribute_name, accessor_name):
        """add instance to the cache set for each object in pk_set """
        model = instance.__class__

        for pk in pk_set:
            key = ':'.join((self.make_key(pk), accessor_name))
            objects = self.cache.get(key)
            if objects is None:
                filters = {accessor_name: pk}
                objects = model._default_manager.filter(**filters)
                self.cache.set(key, list(objects), self.timeout)
            else:
                pks = [o.pk for o in objects]
                if pk not in pks:
                    objects.append(instance)
                if model._meta.ordering:
                    _sort(objects, model._meta.ordering)
                self.cache.set(key, objects, self.timeout)


    def _m2m_remove_local(self, relation, instance, pk_set, attribute_name, accessor_name):
        """ remove the model instances matching pk_set from instance's cache set """
        key = ':'.join((self.make_key(instance.pk), attribute_name))
        objects = self.cache.get(key)
        if objects is None:
            objects = getattr(instance, attribute_name).all()
            self.cache.set(key, list(objects), self.timeout)
        else:
            pks = [o.pk for o in objects]
            for pk in pk_set:
                try:
                    index = pks.index(pk)
                    del objects[index]
                    del pks[index]
                except ValueError:
                    pass
            self.cache.set(key, objects, self.timeout)

    def _m2m_remove_remote(self, relation, instance, pk_set, attribute_name, accessor_name):
        """remove instance from the cache set for each object in pk_set """
        model = instance.__class__

        for pk in pk_set:
            key = ':'.join((self.make_key(pk), accessor_name))
            objects = self.cache.get(key)
            if objects is None:
                filters = {accessor_name: pk}
                objects = model._default_manager.filter(**filters)
                self.cache.set(key, list(objects), self.timeout)
            else:
                pks = [o.pk for o in objects]
                for pk in pk_set:
                    try:
                        index = pks.index(pk)
                        del objects[index]
                        del pks[index]
                    except ValueError:
                        pass
                self.cache.set(key, objects, self.timeout)

    def m2m_post_save_invalidate(self, relation, instance, **kwargs):
        assert self.model is not instance.__class__

        reverse = instance.__class__ is relation.parent_model

        field_name = relation.field.name
        accessor_name = relation.get_accessor_name()
        model = relation.parent_model
        if not reverse:
            accessor_name, field_name = field_name, accessor_name
            model = relation.model

        related_objects = getattr(instance, accessor_name).all()


        for object in related_objects:
            key = ':'.join((self.make_key(object.pk), field_name))
            objects = self.cache.get(key)
            objects = None
            if objects is None:
                filters = {accessor_name: object.pk}
                objects = model._default_manager.filter(**filters)
                self.cache.set(key, list(objects), self.timeout)
