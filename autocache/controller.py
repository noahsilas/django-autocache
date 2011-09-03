
import django.core.cache
from django.db import models
from django.db.models.manager import ManagerDescriptor

no_arg = object()

class CacheController(object):
    """ Automatically caches model instances on saves
    """
    DNE = 'DOES_NOT_EXIST'
    DEFAULT_TIMEOUT = 60 * 60

    def __init__(self, backend='default', timeout=no_arg):
        if backend is 'default':
            self.cache = django.core.cache.cache
        else:
            self.cache = django.core.cache.get_cache(backend)

        if timeout is no_arg:
            self.timeout = self.DEFAULT_TIMEOUT
        else:
            self.timeout = timeout

    def make_key(self, pk):
        key = "%(app_label)s:%(model)s:%(pk)s" % {
            'app_label': self.model._meta.app_label,
            'model': self.model.__name__,
            'pk': pk,
        }
        return key

    def get(self, pk):
        key = self.make_key(pk)
        obj = self.cache.get(key)
        if obj is None:
            try:
                obj = self.model._default_manager.get(pk=pk)
            except self.model.DoesNotExist:
                self.cache.set(key, self.DNE, self.timeout)
                raise
            self.cache.set(key, obj, self.timeout)
        elif obj == self.DNE:
            raise self.model.DoesNotExist()
        return obj

    def contribute_to_class(self, model, name):
        self.model = model

        # The ManagerDescriptor attribute prevents this controller from being accessed via model instances.
        setattr(model, name, ManagerDescriptor(self))

        models.signals.post_save.connect(self.post_save, sender=model)
        models.signals.post_delete.connect(self.post_delete, sender=model)

    def post_save(self, instance, **kwargs):
        key = self.make_key(instance.pk)
        self.cache.set(key, instance, self.timeout)

    def post_delete(self, instance, **kwargs):
        key = self.make_key(instance.pk)
        self.cache.set(key, self.DNE, self.timeout)


