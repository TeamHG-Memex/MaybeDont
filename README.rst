MaybeDont
=========

.. image:: https://img.shields.io/travis/TeamHG-Memex/MaybeDont/master.svg
   :target: http://travis-ci.org/TeamHG-Memex/MaybeDont
   :alt: Build Status

.. image:: https://codecov.io/github/TeamHG-Memex/MaybeDont/coverage.svg?branch=master
   :target: https://codecov.io/github/TeamHG-Memex/MaybeDont?branch=master
   :alt: Code Coverage

.. contents::

MaybeDont is a library that helps avoid downloading pages with duplicate
content during crawling. It learns which URL components are important and
which are not important during crawling, and tries to predict if the page
will be duplicate based on it's URL.

The idea is that if you have a crawler that just
follows all links, it might download a lot of duplicate pages: for example,
for a forum there might be pages like ``/view.php?topicId=10`` and
``/view.php?topicId=10&start=0`` - the only difference is added ``start=0``,
and the content of this pages is likely duplicate. If we knew that adding
``start=0`` does not change content, then we would avoid downloading the page
``/view.php?topicId=10&start=0`` if we have already fetched
``/view.php?topicId=10``, and thus save time and bandwidth.


Duplicate detector
------------------

``maybedont.DupePredictor`` collects statistics about page URLs and contents, and
is able to predict if the new URL will bring any new content.

First, initialize a ``DupePredictor``::

    from maybedont import DupePredictor
    dp = DupePredictor(
        texts_sample=[page_1, page_2, page_3],
        jaccard_threshold=0.9)  # default value

``texts_sample`` is a list of page contents. It can be ommited, but it is
recommended to provide it: it is used to learn which parts of the page are
common for a lot of site's pages, and excludes this parts from duplicate
comparison. This helps with pages where the content is small relative to
the site chrome (footer, header, etc.): without removing chrome all such
pages would be considered duplicates, as only a tiny fraction of the content
changes.

Next, we can update ``DupePredictor`` model with downloaded pages::

    dp.update_model(url_4, text_4)
    dp.update_model(url_5, text_5)

After a while, ``DupePredictor`` will learn which arguments in URLs
are important, and which can be safely ignored.
``DupePredictor.get_dupe_prob`` returns the probability of url being
a duplicate of some content that has already been seem::

    dp.get_dupe_prob(url_6)

Runtime overhead should be not too large: on a crawl with < 100k pages,
expected time to update the model is 1-5 ms, and below 1 ms
to get the probability. All visited urls and hashes of content are stored
in memory, along with some indexing structures.


Install
-------

::

    pip install MaybeDont


Spider middleware
-----------------

If you have a `Scrapy <http://scrapy.org>`_ spider,
or are looking for an inspiration for a spider
middleware, check out ``maybedont.scrapy_middleware.AvoidDupContentMiddleware``.
First, it collects an queue of documents to know better which page elements
are common on the site, in order to exclude them from content comparison.
After that it builds it's ``DupePredictor``, updates it with crawled pages
(only textual pages are taken into account), and starts dropping requests
for duplicate content once it gets confident enough. Not all requests for
duplicates are dropped: with a small probability (currenty 5%) requests
are carried anyway. This makes duplicate detection more robust against
changes in site URL or content structure as the crawl progresses.

To enable the middleware, the following settings are required::

    AVOID_DUP_CONTENT_ENABLED = True
    DOWNLOADER_MIDDLEWARES['maybedont.scrapy_middleware.AvoidDupContentMiddleware'] = 200

Middleware is only applied to requests with ``avoid_dup_content`` in
``request.meta``.

Optional settings:

- ``AVOID_DUP_CONTENT_THRESHOLD = 0.98`` - minimal probability when requests
  are skipped.
- ``AVOID_DUP_CONTENT_EXPLORATION = 0.05`` - probability of still making a
  request that should be dropped
- ``AVOID_DUP_CONTENT_INITIAL_QUEUE_LIMIT = 300`` - number of pages that
  should be downloaded before DupePredictor is initialized


How it works
------------

Duplicate detection is based on ``MinHashLSH`` from the
`datasketch <https://github.com/ekzhu/datasketch>`_ library. Text
4-shingles of words are used for hashing,
not spanning line breaks in the extracted text.

Several hypotheses about duplicates are tested:

1. All URLs with a given URL path are the same (have the same content),
   regardless of query parameters;
2. All URLs which only differ in a given URL query parameter are the same
   (e.g. session tokens can be detected this way);
3. All URLs which have a given path and only differ in a given URL
   query parameter are the same;
4. All URLs which have a given path and query string and only differ
   in a single given query parameter are the same;
5. URLs are the same if they have same path and only differ
   in that some of them have a given param=value query argument added;
6. URLs are the same if they have a given path and only differ
   in a given param=value query argument;

Bernoulli distribution is fit for each hypothesis.


License
-------

License is MIT
