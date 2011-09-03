from django.test import TestCase
from django.core.cache import cache, get_cache

from .models import Person, Book, Volume

other_cache = get_cache('other')

class CacheControllerTests(TestCase):

    def setUp(self):
        cache.clear()
        other_cache.clear()

    def test_save(self):
        """
        Tests that objects which are saved get cached correctly and are retrievable via CacheController.get.
        """
        author = Person(name="Charles Dickens")
        author.save()

        author_id = author.id

        with self.assertNumQueries(0):
            person = Person.cache.get(author_id)

    def test_delete_invalidate(self):
        """
        Tests that objects which are deleted get invalidated in cache.
        """
        author = Person(name="Charles Dickens")
        author.save()

        author_id = author.id

        author.delete()

        with self.assertNumQueries(0):
            with self.assertRaises(Person.DoesNotExist):
                Person.cache.get(author_id)

    def test_save_updated_value(self):
        """
        Tests that objects which are saved update cache correctly.
        """
        author = Person(name="Charles Dickens")
        author.save()
        author_id = author.id

        author.name = "Jane Austin"
        author.save()

        with self.assertNumQueries(0):
            person = Person.cache.get(author_id)

        self.assertEquals(person.name, "Jane Austin")


    def test_save_cache_miss(self):
        """
        Tests that objects which are not in cache are retreived correctly via CacheController.get.
        """
        author = Person(name="Charles Dickens")
        author.save()

        author_id = author.id

        cache_key = Person.cache.make_key(author.id)
        cache.delete(cache_key)

        with self.assertNumQueries(1):
            person = Person.cache.get(author_id)
        self.assertEquals(person.name, author.name)


    def test_delete_cache_miss(self):
        """
        Tests that CacheController.get properly raises a DoesNotExist when an object is neither in cache nor the database.
        """
        author = Person(name="Charles Dickens")
        author.save()

        author_id = author.id

        author.delete()

        cache_key = Person.cache.make_key(author_id)
        cache.delete(cache_key)

        with self.assertNumQueries(1):
            with self.assertRaises(Person.DoesNotExist):
                person = Person.cache.get(author_id)


class RelatedCacheTests(TestCase):

    def setUp(self):
        cache.clear()
        other_cache.clear()

    def test_create_ordering(self):
        """
        Tests that objects created out of order get cached in the correct
        order.
        """

        # save an author
        author = Person(name="Charles Dickens")
        author.save()

        # save some books
        books = [
            Book(author=author, rank=1, title="Our Mutual Friend"),
            Book(author=author, rank=1, title="David Copperfield"),
            Book(author=author, rank=2, title="A Christmas Carol"),
        ]
        for book in books:
            book.save()

        with self.assertNumQueries(0):
            bs = author.cache.book_set

        # Books should be ordered by rank descending, title ascending
        titles = [
            "A Christmas Carol",
            "David Copperfield",
            "Our Mutual Friend"
        ]
        self.assertEqual([b.title for b in bs], titles)


    def test_update_ordering(self):
        """
        Tests that objects updated get cached in the correct order.
        """

        # save an author
        author = Person(name="Charles Dickens")
        author.save()

        # save some books
        books = [
            Book(author=author, rank=2, title="A Christmas Carol"),
            Book(author=author, rank=1, title="David Copperfield"),
            Book(author=author, rank=1, title="Our Mutual Friend"),
        ]
        for book in books:
            book.save()

        # check the current ordering: rank descending, title ascending
        with self.assertNumQueries(0):
            bs = author.cache.book_set
        self.assertEqual([b.title for b in bs], [b.title for b in books])

        # reorder the books: move book[1] to book[0]
        books[1].rank = 3
        books[1].save()
        books[0], books[1] = books[1], books[0]

        # check the current ordering: rank descending, title ascending
        with self.assertNumQueries(0):
            bs = author.cache.book_set
        self.assertEqual([b.title for b in bs], [b.title for b in books])


    def test_invalidations(self):
        """
        Test that changing a foreign key relationship correctly updates
        both the cache it is moving into and the cache it is moving out of.
        """
        # save some authors
        authors = [
            Person(name="Charles Dickens"),
            Person(name="Jane Austin"),
        ]
        for author in authors:
            author.save()

        # save some books
        books = [
            Book(author=authors[0], rank=1, title="Our Mutual Friend"),
            Book(author=authors[0], rank=2, title="A Christmas Carol"),
            Book(author=authors[1], rank=1, title="Sense and Sensibility"),
        ]
        for book in books:
            book.save()

        # change the author on a book.
        books[0].author = authors[1]
        books[0].save()

        with self.assertNumQueries(0):
            charles_books = authors[0].cache.book_set
            jane_books = authors[1].cache.book_set

        titles = ["Our Mutual Friend", "Sense and Sensibility"]
        self.assertEqual([b.title for b in jane_books], titles)

        titles = ["A Christmas Carol"]
        self.assertEqual([b.title for b in charles_books], titles)


class OneToOneTests(TestCase):

    def setUp(self):
        cache.clear()
        other_cache.clear()

    def test_create(self):

        author = Person(name="J. K. Rowling")

        author.save()

        book = Book(author=author, rank=1, title="Harry Potter and the Philosopher's Stone")

        book.save()

        volume = Volume(book=book, order_in_series=1)
        volume.save()

        # get related book from database.
        db_volume = book.volume

        # get related book from cache.
        with self.assertNumQueries(0):
            cache_volume = book.cache.volume

        self.assertEquals(db_volume, cache_volume)

    def test_delete(self):
        author = Person(name="J. K. Rowling")

        author.save()

        book = Book(author=author, rank=1, title="Harry Potter and the Philosopher's Stone")

        book.save()

        volume = Volume(book=book, order_in_series=1)
        volume.save()

        volume.delete()

        with self.assertRaises(Volume.DoesNotExist):
            cache_volume = book.cache.volume

    def test_save_update_value(self):
        author = Person(name="J. K. Rowling")

        author.save()

        book = Book(author=author, rank=1, title="Harry Potter and the Philosopher's Stone")

        book.save()

        volume = Volume(book=book, order_in_series=1)
        volume.save()

        volume.order_in_series = 2
        volume.save()

        with self.assertNumQueries(1):
            db_volume = book.volume

        with self.assertNumQueries(0):
            cache_volume = book.cache.volume

        self.assertEquals(cache_volume, db_volume)
        self.assertEquals(cache_volume.order_in_series, 2)


    def test_save_cache_miss(self):
        """
        Tests that objects which are not in cache are retreived correctly.
        """
        author = Person(name="J. K. Rowling")
        author.save()

        book = Book(author=author, rank=1, title="Harry Potter and the Philosopher's Stone")
        book.save()

        volume = Volume(book=book, order_in_series=1)
        volume.save()

        cache_key = ':'.join((Book.cache.make_key(book.id), 'volume'))
        other_cache.delete(cache_key)

        with self.assertNumQueries(1):
            cache_volume = book.cache.volume
            self.assertEquals(volume, cache_volume)


    def test_delete_cache_miss(self):
        """
        Tests that CacheController.get properly raises a DoesNotExist when an object is neither in cache nor the database.
        """
        """
        Tests that objects which are not in cache are retreived correctly.
        """
        author = Person(name="J. K. Rowling")
        author.save()

        book = Book(author=author, rank=1, title="Harry Potter and the Philosopher's Stone")
        book.save()

        volume = Volume(book=book, order_in_series=1)
        volume.save()

        volume.delete()

        cache_key = ':'.join((Book.cache.make_key(book.id), 'volume'))
        other_cache.delete(cache_key)

        with self.assertNumQueries(1):
            with self.assertRaises(Volume.DoesNotExist):
                cache_volume = book.cache.volume


    def test_move_volume(self):
        author = Person(name="J. K. Rowling")
        author.save()

        books = [
            Book(author=author, rank=1, title="Harry Potter and the Philosopher's Stone"),
            Book(author=author, rank=2, title="Harry Potter and the Deathly Hallows")
        ]

        for book in books:
            book.save()

        volume = Volume(book=books[0], order_in_series=1)
        volume.save()

        with self.assertNumQueries(0):
            book0_cache_vol = books[0].cache.volume

        with self.assertRaises(Volume.DoesNotExist):
            book1_cache_vol = books[1].cache.volume

        volume.book = books[1]
        volume.save()

        with self.assertNumQueries(0):
            book1_cache_vol = books[1].cache.volume

        with self.assertNumQueries(0):
            with self.assertRaises(Volume.DoesNotExist):
                book0_cache_vol = books[0].cache.volume

        self.assertEquals(book0_cache_vol, book1_cache_vol)


class ManyToManyTest(TestCase):

    def setUp(self):
        cache.clear()
        other_cache.clear()

    def test_create(self):

        # save some authors
        authors = [
            Person(name="Charles Dickens"),
            Person(name="Jane Austin"),
        ]
        for author in authors:
            author.save()

        # save some books
        books = [
            Book(author=authors[0], rank=1, title="Our Mutual Friend"),
            Book(author=authors[0], rank=2, title="A Christmas Carol"),
            Book(author=authors[1], rank=1, title="Sense and Sensibility"),
        ]
        for book in books:
            book.save()

        # hook up a many to many relationship
        books[0].editors.add(authors[0])

        # try to get it out of cache
        with self.assertNumQueries(0):
            books[0].cache.editors

        # add a new author, remove the original
        books[0].editors.add(authors[1])
        books[0].editors.remove(authors[0])

        # get the list of the editors of book 0 from db
        db_b0_editors = list(books[0].editors.all())

        # get the list of the editors of book 0 from cache
        with self.assertNumQueries(0):
            cache_b0_editors = books[0].cache.editors

        # the cache and the db should match
        self.assertEquals(db_b0_editors, cache_b0_editors)


    def test_create_reverse(self):

        # save some authors
        authors = [
            Person(name="Charles Dickens"),
            Person(name="Jane Austin"),
        ]
        for author in authors:
            author.save()

        # save some books
        books = [
            Book(author=authors[0], rank=1, title="Our Mutual Friend"),
            Book(author=authors[0], rank=2, title="A Christmas Carol"),
            Book(author=authors[1], rank=1, title="Sense and Sensibility"),
        ]
        for book in books:
            book.save()

        # hook up some many to manys
        authors[0].edited.add(books[0])
        authors[0].edited.add(books[1])
        authors[0].edited.remove(books[1])

        # get the list of the editors of book 0 from db
        db_a0_edited = list(authors[0].edited.all())

        # get the list of the editors of book 0 from cache
        with self.assertNumQueries(0):
            cache_a0_edited = authors[0].cache.edited

        # the cache and the db should match
        self.assertEquals(db_a0_edited, cache_a0_edited)

    def test_update(self):

        # save some authors
        authors = [
            Person(name="Charles Dickens"),
            Person(name="Jane Austin"),
        ]
        for author in authors:
            author.save()

        # save some books
        books = [
            Book(author=authors[0], rank=1, title="Our Mutual Friend"),
            Book(author=authors[0], rank=2, title="A Christmas Carol"),
            Book(author=authors[1], rank=1, title="Sense and Sensibility"),
        ]
        for book in books:
            book.save()

        # hook up a many to many relationship
        authors[0].edited.add(books[0])

        with self.assertNumQueries(0):
            authors[0].cache.edited

        # update the book in the m2m
        books[0].rank = 3
        books[0].save()

        with self.assertNumQueries(0):
            self.assertEquals(authors[0].cache.edited[0].rank, 3)

    def test_update_reverse(self):

        # save some authors
        authors = [
            Person(name="Charles Dickens"),
            Person(name="Jane Austin"),
        ]
        for author in authors:
            author.save()

        # save some books
        books = [
            Book(author=authors[0], rank=1, title="Our Mutual Friend"),
            Book(author=authors[0], rank=2, title="A Christmas Carol"),
            Book(author=authors[1], rank=1, title="Sense and Sensibility"),
        ]
        for book in books:
            book.save()

        # hook up a many to many relationship
        authors[0].edited.add(books[0])

        with self.assertNumQueries(0):
            authors[0].cache.edited

        # update the author in the m2m
        authors[0].name = 'Kelly Clarkson'
        authors[0].save()

        books[0].cache.editors[0].name

        with self.assertNumQueries(0):
            self.assertEquals(books[0].cache.editors[0].name, 'Kelly Clarkson')


class RelatedForeignKeyTests(TestCase):

    def setUp(self):
        cache.clear()
        other_cache.clear()

    def test_foreign_key_fetches_from_cache(self):
        # save an author
        p = Person(name="Charles Dickens")
        p.save()

        # save a book
        b = Book(author_id=p.id, rank=1, title="Our Mutual Friend")
        b.save()

        # get the books author
        with self.assertNumQueries(0):
            b.author

