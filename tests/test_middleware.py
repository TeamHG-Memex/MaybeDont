import pytest
import scrapy
from scrapy import Request
from scrapy.http.response.html import HtmlResponse
from scrapy.utils.log import configure_logging
from scrapy.exceptions import IgnoreRequest

from maybedont.scrapy_middleware import AvoidDupContentMiddleware


configure_logging()


class Spider(scrapy.Spider):
    name = 'spider'

    def parse(self, response):
        assert response


def test_middleware():
    Rq = lambda path: Request(
        'http://example.com{}'.format(path),
        meta={'avoid_dup_content': True})
    Rs = lambda req, body: HtmlResponse(
        req.url, body=body.encode(), request=req)
    mw = AvoidDupContentMiddleware(
        initial_queue_limit=1, threshold=0.5, exploration=0.00)
    spider = Spider()
    req = Rq('/')
    mw.process_request(req, spider)
    mw.process_response(req, Rs(req, ''), spider)
    assert mw.dupe_predictor
    n_dropped = 0
    for i in range(10):
        req = Rq('/viewtopic.php?topic_id={}'.format(i))
        mw.process_request(req, spider)
        mw.process_response(req, Rs(req, 'Topic {}'.format(i)), spider)
        req = Rq('/viewtopic.php?topic_id={}&start=0'.format(i))
        try:
            mw.process_request(req, spider)
        except IgnoreRequest:
            n_dropped += 1
        else:
            mw.process_response(req, Rs(req, 'Topic {}'.format(i)), spider)
        mw.dupe_predictor.log_dupstats(min_dup=0)
    assert n_dropped == 5
    # one request in different order
    req = Rq('/viewtopic.php?topic_id=100&start=0')
    mw.process_request(req, spider)
    mw.process_response(req, Rs(req, ''), spider)
    mw.process_request(Rq('/viewtopic.php?topic_id=200'), spider)
    with pytest.raises(IgnoreRequest):
        mw.process_request(Rq('/viewtopic.php?topic_id=100'), spider)
    # test exploration
    mw.exploration = 0.5
    n_dropped = 0
    n_requests = 0
    for i in range(150, 170):
        req = Rq('/viewtopic.php?topic_id={}'.format(i))
        mw.process_request(req, spider)
        mw.process_response(req, Rs(req, 'Topic {}'.format(i)), spider)
        req = Rq('/viewtopic.php?topic_id={}&start=0'.format(i))
        n_requests += 1
        try:
            mw.process_request(req, spider)
        except IgnoreRequest:
            n_dropped += 1
        else:
            mw.process_response(req, Rs(req, 'Topic {}'.format(i)), spider)
    assert n_dropped > 0
    assert n_dropped < n_requests


def test_skip():
    mw = AvoidDupContentMiddleware(
        initial_queue_limit=300, threshold=0.98, exploration=0.05)
    spider = Spider()
    mw.process_request(Request('http://example.com'), spider)
    assert len(mw.initial_queue) == 0
    req = Request('http://example.com', meta={'avoid_dup_content': True})
    mw.process_request(req, spider)
    mw.process_response(
        req, HtmlResponse(req.url, body=b'a', request=req), spider)
    assert len(mw.initial_queue) == 1
