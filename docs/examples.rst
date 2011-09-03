Examples
========

The example model defines a person with a name. ::

    class Person(models.Model):
        name = models.CharField(max_length=64)

        cache = RelatedCacheController()

        def __unicode__(self):
            return self.name

    class Book(models.Model):
        title = models.CharField(max_length=64)
        author = models.ForeignKey(Person)
