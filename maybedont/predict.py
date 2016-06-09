from __future__ import absolute_import, division
import logging, random, math
from collections import namedtuple, defaultdict
from six.moves.urllib.parse import urlsplit, parse_qs

from datasketch import MinHashLSH

from .utils import get_too_common_shingles, get_min_hash, canonicalize_url


logger = logging.getLogger(__name__)


class DupePredictor(object):
    """ Learn to predict if the content is duplicate by the URL.
    """
    def __init__(self, texts_sample=None, jaccard_threshold=0.9, num_perm=128):
        """ Initialize DupePredictor.
        :param jaccard_threshold: a minimal jaccard similarity when pages
        are considered duplicates (intersection of content / union of content).
        :param texts_sample: a list of texts to calculate too_common_shingles
        - this allows a more precise duplicate detection, because now
        we know which parts are common to all pages, and which are unique
        for each page.
        """
        self.jaccard_threshold = jaccard_threshold
        self.num_perm = num_perm
        self.lsh = MinHashLSH(
            threshold=self.jaccard_threshold, num_perm=self.num_perm)
        self.too_common_shingles = set()
        if texts_sample:
            self.too_common_shingles = get_too_common_shingles(texts_sample)

        self.seen_urls = {}  # url: URLMeta
        self.urls_by_path = defaultdict(set)  # path: {url}
        self.urls_by_path_q = defaultdict(set)  # (path, q): {url}
        self.urls_by_path_qwp = defaultdict(set)  # (path, param, q): {url}
        self.params_by_path = defaultdict(set)  # path: {param}
        self.param_values = defaultdict(set)  # (path, param): {value}

        # Duplicate hypotheses:
        # (1) All items with same path are duplicates. Key is (path,)
        self.path_dupstats = defaultdict(DupStat)
        # (2) All items with same path that differ only in given param are
        # duplicates. Key is (param,)
        self.param_dupstats = defaultdict(DupStat)
        # (3) Same but conditioned by path, key is (path, param)
        self.path_param_dupstats = defaultdict(DupStat)
        # (4) Same but conditioned by path + the rest of the query
        # Key is (path, query, param)
        self.path_query_param_dupstats = defaultdict(DupStat)
        # (5) All items with same path with only added param=value are duplicates
        # Key is (param, value)
        self.param_value_dupstats = defaultdict(DupStat)
        # (6) Same but conditioned by path, key is (path, param, value)
        self.path_param_value_dupstats = defaultdict(DupStat)
        # TODO - more powerful hypotheses:
        # - param + value without path
        # - more than one get param

    def get_dupe_prob(self, url):
        """ A probability of given url being a duplicate of some content
        that has already been seem.
        """
        path, query = _parse_url(url)
        dupestats = []
        extend_ds = lambda x: dupestats.extend(filter(None, (
            ds_dict.get(key) for ds_dict, key in x)))
        if self.urls_by_path.get(path):
            extend_ds([(self.path_dupstats, path)])
        # If param is in the query
        for param, value in query.items():
            qwp_key = _q_key(_without_key(query, param))
            # Have we seen the query with param changed or removed?
            has_changed = self.urls_by_path_qwp.get((path, param, qwp_key))
            has_removed = self.urls_by_path_q.get((path, qwp_key))
            if has_changed or has_removed:
                extend_ds(self._param_dupstats(path, param, qwp_key))
            if has_removed:
                extend_ds(self._param_value_dupstats(path, param, value))
        # If param is not in the query, but we've crawled a page when it is
        q_key = _q_key(query)
        for param in (self.params_by_path.get(path, set()) - set(query)):
            if self.urls_by_path_qwp.get((path, param, q_key)):
                extend_ds(self._param_dupstats(path, param, q_key))
                # FIXME - this could be a long list of param values,
                # it's better to somehow store only high-probability values?
                for value in self.param_values.get((path, param), set()):
                    extend_ds(self._param_value_dupstats(path, param, value))
        return max(ds.get_prob() for ds in dupestats) if dupestats else 0.

    def update_model(self, url, text):
        """ Update prediction model with a page by given url and text content.
        Return a list of item duplicates (for testing purposes).
        """
        min_hash = get_min_hash(text, self.too_common_shingles, self.num_perm)
        item_url = canonicalize_url(url)
        item_path, item_query = _parse_url(item_url)
        all_duplicates = [
            (url, self.seen_urls[url]) for url in self.lsh.query(min_hash)]
        duplicates = [(url, m.query) for url, m in all_duplicates
                      if m.path == item_path]
        # Hypothesis (1) - just paths
        n_path_nodup = self._nodup_filter(min_hash, (
            self.urls_by_path.get(item_path, set())
            .difference(url for url, _ in duplicates)))
        self.path_dupstats[item_path].update(len(duplicates), n_path_nodup)
        # Other hypotheses, if param is in the query
        for param, value in item_query.items():
            self._update_with_param(
                duplicates, min_hash, item_path, item_query, param, [value])
        # Other hypotheses, if param is not in the query
        for param in (
                self.params_by_path.get(item_path, set()) - set(item_query)):
            self._update_with_param(
                duplicates, min_hash, item_path, item_query, param,
                self.param_values.get((item_path, param), set()))
        # Update indexes
        for param, value in item_query.items():
            self.urls_by_path_q[item_path, _q_key(item_query)].add(item_url)
            item_qwp_key = _q_key(_without_key(item_query, param))
            self.urls_by_path_qwp[item_path, param, item_qwp_key].add(item_url)
            self.params_by_path[item_path].add(param)
            self.param_values[item_path, param].add(value)
        if not item_query:
            self.urls_by_path_q[item_path, ()].add(item_url)
        self.urls_by_path[item_path].add(item_url)
        if item_url in self.lsh:
            self.lsh.remove(item_url)
        self.lsh.insert(item_url, min_hash)
        self.seen_urls[item_url] = URLMeta(item_path, item_query, min_hash)
        if len(self.seen_urls) % 100 == 0:
            self.log_dupstats()
        return all_duplicates

    def _update_with_param(self, duplicates, min_hash, item_path, item_query,
                           param, values):
        # qwp = "query without param"
        item_qwp = _without_key(item_query, param)
        item_qwp_key = _q_key(item_qwp)

        q_dup = {url for url, q in duplicates
                 if _without_key(q, param) == item_qwp}
        n_q_nodup = self._nodup_filter(min_hash, (
            self.urls_by_path_qwp.get((item_path, param, item_qwp_key), set())
            .union(self.urls_by_path_q.get((item_path, item_qwp_key), set()))
            .difference(q_dup)))
        if q_dup or n_q_nodup:
            for ds_dict, key in self._param_dupstats(
                    item_path, param, item_qwp_key):
                ds_dict[key].update(len(q_dup), n_q_nodup)
        if values:
            if param in item_query:
                qv_dup = {url for url, q in duplicates if q == item_qwp}
                n_qv_nodup = self._nodup_filter(min_hash, (
                    self.urls_by_path_q.get((item_path, item_qwp_key), set())
                    .difference(qv_dup)))
            # FIXME - this could be a long list of param values,
            # it's better to somehow store only high-probability values?
            for value in values:
                if param not in item_query:
                    qv_dup = {url for url, q in duplicates
                        if q.get(param) == value and
                        _without_key(q, param) == item_qwp}
                    qap_key = _q_key(_with_key_val(item_query, param, value))
                    n_qv_nodup = self._nodup_filter(min_hash, (
                        self.urls_by_path_q.get((item_path, qap_key), set())
                        .difference(qv_dup)))
                if qv_dup or n_qv_nodup:
                    for ds_dict, key in self._param_value_dupstats(
                            item_path, param, value):
                        ds_dict[key].update(len(qv_dup), n_qv_nodup)

    def _param_dupstats(self, path, param, qwp_key):
        return [
            (self.param_dupstats, param),
            (self.path_param_dupstats, (path, param)),
            (self.path_query_param_dupstats, (path, param, qwp_key)),
            ]

    def _param_value_dupstats(self, path, param, value):
        return [
            (self.param_value_dupstats, (param, value)),
            (self.path_param_value_dupstats, (path, param, value)),
            ]

    def _nodup_filter(self, min_hash, all_urls, max_sample=200):
        """ This filters results that are considered not duplicates.
        But we really need to check that, because lsh.query does not always
        return ALL duplicates, esp. when there are a lot of them, so
        here we double-check and return only urls that are NOT duplicates.
        Return estimated number of not duplicates.
        """
        if not all_urls:
            return 0
        urls = random.sample(all_urls, max_sample) \
               if len(all_urls) > max_sample else all_urls
        filtered = [
            url for url in urls
            if min_hash.jaccard(self.seen_urls[url].min_hash) <
            self.jaccard_threshold]
        return int(len(filtered) / len(urls) * len(all_urls))

    def log_dupstats(self, min_dup=100):
        for ds, name in [
                (self.path_dupstats, 'Path dupstats'),
                (self.param_dupstats, 'Param dupstats'),
                (self.path_param_dupstats, 'Path-param dupstats'),
                (self.path_query_param_dupstats, 'Path-query-param dupstats'),
                (self.param_value_dupstats, 'Param-value dupstats'),
                (self.path_param_value_dupstats, 'Path-param-value dupstats'),
                ]:
            _log_dupstats(ds, name, min_dup=min_dup)


def _without_key(dict_, key):
    return {k: v for k, v in dict_.items() if k != key}


def _with_key_val(dict_, key, value):
    dict_ = dict(dict_)
    dict_[key] = value
    return dict_


def _parse_url(url):
    p = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(p.query).items() if len(v) == 1}
    return ''.join([p.netloc, p.path]), query


def _q_key(query):
    return tuple(sorted(query.items()))


def _log_dupstats(dupstats, name, min_dup):
    dupstats_items = [
        (url, dupstat) for url, dupstat in sorted(
            dupstats.items(), key=lambda x: x[1].total, reverse=True)
        if dupstat.dup > min_dup]
    if dupstats_items:
        logger.debug('%s:', name)
        for url, dupstat in dupstats_items:
            logger.debug('%s %s', url, dupstat)


URLMeta = namedtuple('URLMeta', ['path', 'query', 'min_hash'])


class DupStat(object):
    def __init__(self):
        self.dup = 0
        self.nodup = 0

    @property
    def total(self):
        return self.dup + self.nodup

    def update(self, dup, nodup):
        self.dup += dup
        self.nodup += nodup

    def get_prob(self):
        if self.total < 5:
            return 0.
        a, b = self.dup + 1, self.nodup + 1
        n = a + b
        p = a / n
        q = b / n
        # Lower edge of the 95% confidence interval, binomial distribution
        return p - 1.96 * math.sqrt(p * q / n)

    def __repr__(self):
        return '<DupStat: {:.0%} ({} of {})>'.format(
            self.get_prob(), self.dup, self.total)
