import logging, random

import pytest

from maybedont import DupePredictor


logging.basicConfig(level=logging.DEBUG)


def test_path():
    dupe_predictor = DupePredictor()
    def gen_urls():
        return ['http://foo.com/d?p{0}={0}'.format(random.randint(1, 100)),
                'http://foo.com/nd?p{0}={0}'.format(random.randint(1, 100))]
    for _ in range(100):
        url1, url2 = gen_urls()
        dupe_predictor.update_model(url1, 'd')
        dupe_predictor.update_model(
            url2, 'd{}'.format(random.randint(1, 100)))
    dupe_predictor.log_dupstats(min_dup=1)
    url1, url2 = gen_urls()
    assert dupe_predictor.get_dupe_prob(url1) > 0.97
    assert dupe_predictor.get_dupe_prob(url2) < 0.97


@pytest.mark.parametrize('reverse_update', [True, False])
@pytest.mark.parametrize('reverse_test', [True, False])
@pytest.mark.parametrize('is_param', [True, False])
def test_param(reverse_update, reverse_test, is_param):
    dupe_predictor = DupePredictor()
    def gen_urls(page):
        tpls = ['{}/?page={}', '{}/?page={}&start=0'] if is_param else \
               ['{}/{}',       '{}/{}?start=0']
        return [tpl.format('http://foo.com', page) for tpl in tpls]
    for i in range(100):
        urls = gen_urls(i)
        if reverse_update:
            urls.reverse()
        for url in urls:
            dupe_predictor.update_model(url, 'a{}'.format(i))
    dupe_predictor.log_dupstats(min_dup=1)
    url1, url2 = gen_urls('b')
    if reverse_test:
        url1, url2 = url2, url1
    dupe_predictor.update_model(url1, 'b')
    assert dupe_predictor.get_dupe_prob(url2) > 0.97
    for url in gen_urls('c'):
        assert dupe_predictor.get_dupe_prob(url) < 0.1


@pytest.mark.parametrize('reverse_update', [True, False])
@pytest.mark.parametrize('reverse_test', [True, False])
@pytest.mark.parametrize('is_param', [True, False])
def test_param_value(reverse_update, reverse_test, is_param):
    dupe_predictor = DupePredictor()
    random.seed(1)
    def gen_urls(page):
        random_start = random.randint(1, 100)
        if is_param:
            tpls = ['{}/?page={}', '{}/?page={}&start=0',
                    '{}/?page={}&start=%s' % random_start]
        else:
            tpls = ['{}/{}', '{}/{}?start=0', '{}/{}?start=%s' % random_start]
        return [tpl.format('http://foo.com', page) for tpl in tpls]
    for i in range(100):
        urls = gen_urls(i)
        with_contents = list(zip(urls, ['a{}'.format(i)] * 2 +
                                       ['r{}'.format(random.randint(1, 100))]))
        if reverse_update:
            with_contents.reverse()
        for url, content in with_contents:
            dupe_predictor.update_model(url, content)
    dupe_predictor.log_dupstats(min_dup=1)
    url1, url2, url3 = gen_urls('b')
    if reverse_test:
        url1, url2 = url2, url1  # url3 stays the same
    dupe_predictor.update_model(url1, 'b')
    assert dupe_predictor.get_dupe_prob(url2) > 0.97
    assert dupe_predictor.get_dupe_prob(url3) < 0.3
    for url in gen_urls('c'):
        assert dupe_predictor.get_dupe_prob(url) < 0.3
