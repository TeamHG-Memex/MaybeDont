import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name = 'MaybeDont',
    version = '0.1.0',
    author = "Konstantin Lopuhin",
    author_email = "kostia.lopuhin@gmail.com",
    description = 'A component that tried to avoid downloading duplite content',
    license = 'MIT',
    url = 'https://github.com/TeamHG-Memex/MaybeDont',
    packages = ['maybedont'],
    long_description=read('README.rst'),
    install_requires = [
        'six',
        'datasketch>=0.2.0',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)
