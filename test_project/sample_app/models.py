from django.db import models

from autocache import RelatedCacheController, CachingForeignKey


class Person(models.Model):
    name = models.CharField(max_length=64)

    cache = RelatedCacheController()

    def __unicode__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=64)
    author = CachingForeignKey(Person)
    editors = models.ManyToManyField("Person", related_name='edited')
    rank = models.IntegerField()

    cache = RelatedCacheController(backend='other')

    class Meta:
        # order by rank descending, title alphabetically
        ordering = ('-rank', 'title',)

    def __unicode__(self):
        return self.title


class Volume(models.Model):
    book = models.OneToOneField(Book)
    order_in_series = models.PositiveIntegerField(default=1)

    def __unicode__(self):
        return "%s: %s" % (self.order_in_series, self.book.title)

