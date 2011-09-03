class Relation(object):
    """ Wrapper around django.db.models.related.RelatedObject.
        Since the wrapped object isn't a stable public API, we
        want to be able to update this wrapper if RelatedObject
        changes, instead of changing everything else ever.
    """
    def __init__(self, relation):
        self._relation = relation

    @property
    def field(self):
        return self._relation.field

    @property
    def model(self):
        return self._relation.model

    @property
    def related_model(self):
        return self._relation.parent_model

    @property
    def name(self):
        return self._relation.field.name

    @property
    def related_name(self):
        return self._relation.get_accessor_name()