update_bib
==========

This is a command line tool for updating the entries in a
BibTeX_ file using mrlookup_.

**Usage** updata_bib <bibtex file>

**Options**::

  -h, --help                  show this help message and exit
  -n, --no_warnings           do not print warnings when replacing BibTeX_ entries
  -i IGNORE, --ignore=IGNORE  BibTeX_ fields to ignore
  -k, --keep                  keep all fields (ignore none)
  -v, --verbose

This script tries to use mrlookup_ to update all of the entries in a BibTeX_
file except for the cite key which remains unchanged. Rather than
overwriting the BibTeX_ a new file is created, called new+filename. The user
is advised to check it carefully for any errors in he new file!

On the entries in the BibTeX_ file which do not already have an mrnumber field
are checked.

Although some care is taken to make sure that the new BibTeX_ entries are
correct given the fuzzy nature of the search strings passed to mrlookup_, and
possible errors in the existing BibTeX_ file, there are no guarantees so you
are advised to check the updated file carefully!

Installation
============

There are two installation routes.

1. From the command line type::

      pip install http://bitbucket.org/aparticle/update_bib/downloads/update_bib-1.0.tar.gz

2. Clone or download this repository, change directory into it and then 
   run `pip` or `easy_install`::

      pip setup.py install


TODO
----

 * add a flag so that the script checks all of the BibTeX_ entries using mr-reference or mrlookup_.
 * find the best match when mrlookup_ returns multiple entries!
 * add dependencies
 * reconfigure so that the BibTeX_ entries are printed in the same order to make
   it easier to diff the output. If this works then copy the original file to
   *.bak and put the updated file in its place.

Links
-----

.. _BibTeX: http://www.BibTeX_.org/
.. _LaTeX: http://en.wikipedia.org/wiki/LaTeX
.. _mrlookup: http://www.ams.org/mrlookup

AUTHOR
------
Andrew Mathas
2012

Version 1.0
