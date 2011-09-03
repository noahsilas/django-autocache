import django.core.cache
from django.db.models import ForeignKey
from django.db.models.fields.related import ReverseSingleRelatedObjectDescriptor, ManyToOneRel

def key_factory(model, to):
    try:
        app_label, model_name = to.split(".")
    except ValueError:
        # If we can't split, assume a model in current app
        app_label = model._meta.app_label
        model_name = to
    except AttributeError:
        # If it doesn't have a split it's actually a model class
        app_label = to._meta.app_label
        model_name = to._meta.object_name

    def make_key(pk):
        key = "%(app_label)s:%(model)s:%(pk)s" % {
            'app_label': app_label,
            'model': model_name,
            'pk': pk,
        }
        return key
    return make_key


class CachingReverseSingleRelatedObjectDescriptor(ReverseSingleRelatedObjectDescriptor):

    def __get__(self, instance, instance_type=None):
        if instance is None:
            return self

        cache_name = self.field.get_cache_name()
        try:
            return getattr(instance, cache_name)
        except AttributeError:
            val = getattr(instance, self.field.attname)
            if val is None:
                # If NULL is an allowed value, return it.
                if self.field.null:
                    return None
                raise self.field.rel.to.DoesNotExist

            # try to get the object from cache
            key = self.field.make_key(val)
            rel_obj = self.field.cache.get(key)
            if rel_obj is self.field.DNE:
                raise self.field.rel.to.DoesNotExist
            if rel_obj is None:
                try:
                    other_field = self.field.rel.get_related_field()
                    if other_field.rel:
                        params = {'%s__pk' % self.field.rel.field_name: val}
                    else:
                        params = {'%s__exact' % self.field.rel.field_name: val}

                    # If the related manager indicates that it should be used for
                    # related fields, respect that.
                    rel_mgr = self.field.rel.to._default_manager
                    db = router.db_for_read(self.field.rel.to, instance=instance)
                    if getattr(rel_mgr, 'use_for_related_fields', False):
                        rel_obj = rel_mgr.using(db).get(**params)
                    else:
                        rel_obj = QuerySet(self.field.rel.to).using(db).get(**params)
                except self.field.rel.to.DoesNotExist:
                    self.field.cache.set(key, self.field.DNE, self.field.TIMEOUT)
                    raise

            self.field.cache.set(key, rel_obj, self.field.TIMEOUT)
            setattr(instance, cache_name, rel_obj)
            return rel_obj


class CachingForeignKey(ForeignKey):

    DNE = 'DOES_NOT_EXIST'
    TIMEOUT = 60 * 60

    def __init__(self, to, to_field=None, rel_class=ManyToOneRel, **kwargs):
        # pop kwargs super.__init__ can't handle
        backend = kwargs.pop('backend', 'default')
        self.make_key = kwargs.pop('make_key', None)

        super(CachingForeignKey, self).__init__(to, to_field, rel_class, **kwargs)

        if backend is 'default':
            self.cache = django.core.cache.cache
        else:
            self.cache = django.core.cache.get_cache(backend)

    def contribute_to_class(self, cls, name):
        super(CachingForeignKey, self).contribute_to_class(cls, name)
        setattr(cls, self.name, CachingReverseSingleRelatedObjectDescriptor(self))

        if self.make_key is None:
            self.make_key = key_factory(self.model, self.rel.to)
