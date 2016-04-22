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


How to use
----------



How it works
------------


License
-------

License is MIT
