from hashlib import sha1
from collections import defaultdict

from datasketch import MinHash


def shingle_hashes(text):
    n = 4
    for line in text.split('\n'):
        words = line.strip().split()
        if words:
            for idx in range(min(len(words), n), len(words) + 1):
                yield sha1(' '.join(
                    words[max(0, idx - n) : idx]).encode('utf-8'))


def get_too_common_shingles(texts, threshold=0.05):
    shingle_counts = defaultdict(int)
    n_items = 0
    for text in texts:
        n_items += 1
        hashes = set(shingle_h.digest() for shingle_h in shingle_hashes(text))
        for h in hashes:
            shingle_counts[h] += 1
    if shingle_counts:
        return set(h for h, count in shingle_counts.items()
                   if count > max(1, threshold * n_items))
    return set()


def get_min_hash(text, too_common, num_perm=128):
    min_hash = MinHash(num_perm=num_perm)
    for shingle_h in shingle_hashes(text):
        digest = shingle_h.digest()
        if digest not in too_common:
            min_hash.update(digest)
    return min_hash


try:
    from scrapy.utils.url import canonicalize_url as _canonicalize_url
    def canonicalize_url(url):
        return _canonicalize_url(url, keep_fragments=True)
except ImportError:
    def canonicalize_url(url):
        return url
