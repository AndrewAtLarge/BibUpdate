=========
bibupdate
=========

This script is a command line tool for updating the entries in a BibTeX_ file
using mrlookup_. By default bibupdate_ tries to find an updated entry unless
unless it already has an *mrnumber* field. BibTeX_ is commonly used by the
LaTeX_ community to maintain publication databases.

**Usage** updata_bib <bibtex file>

**Options**::

  -a, --all                   check ALL BibTeX entries against mrlookup
  -h, --help                  show this help message and exit
  -n, --no_warnings           do not print warnings when replacing BibTeX_ entries
  -i IGNORE, --ignore=IGNORE  A string of BibTeX_ fields to ignore when printing
  -v, --verbose

This script attempts to add missing fields to the papers in a BibTeX_ database
file by querying mrlookup_ and getting the missing information from there. This
is not completely routine because to search on mrlookup_ you need either the
authors or the title of the article and both of these can have non-standard
representations. If the article is already published then it is also possible to
use the articles publication year and its page numbers but bibupdate_ does NOT
do this because in my own files I found that these were not always reliable. In
addition, preprints do not have such information (and the publication year of an
article is rarely the same year that it appeared on a preprint archive).  For
these reasons, bibupdate_ uses *fuzzy* matching on the list of authors and the
title to when it tries to find an article using mrlookup_. 

Although some care is taken to make sure that the new BibTeX_ entries does
correspond to the original ones because of the fuzzy nature of the matching it
possible that updated entries can be for completely different papers. *For this
reason you are advised to check the updated file BibTeX_ file carefully!*

To help with comparing the updated entries in *verbose* mode the program prints
a detailed list of the changes to existing bibtex entries (new entries are not
printed). Comparing the old and new versions of your database with programs like
*diff* and *tkdiff* is highly recommended.

I wrote this class because with the advent of hyperref_ I wanted to be able to
links to journals, the arXiv_ and DOIs in my bibliographies of my papers. This
script allowed me to painless add the missing urls and DOIs to my bibtex file.
As a bonus the script corrected many minor errors in my database and it is now
very success in updating the preprints in my database when they are published.
As bibupdate_ calls mrlookup_ it will only be useful if the papers in your
database are listed in MathSciNet_.

Options and their defaults
--------------------------

TBA

Installation
============

There are two installation routes.

1. From the command line type::

      pip install http://bitbucket.org/aparticle/bibupdate/downloads/bibupdate-1.0.tar.gz

2. Clone or download this repository, change directory into it and then 
   run *pip* or *easy_install*::

      pip setup.py install


TODO
----

* find the best match when mrlookup_ returns multiple entries!
* reconfigure so that the BibTeX_ entries are printed in the same order to make
  it easier to diff the output. If this works then copy the original file to
  *.bak and put the updated file in its place.
* Add a (yaml?) rc file to override the defaults...

Links
-----

.. _BibTeX: http://www.BibTeX_.org/
.. _hyperref: http://www.ctan.org/pkg/hyperref
.. _LaTeX: http://en.wikipedia.org/wiki/LaTeX
.. _MthSciNet: http://www.ams.org/mathscinet/
.. _mrlookup: http://www.ams.org/mrlookup
.. _bibupdate: https://bitbucket.org/aparticle/bibupdate
.. _arXiv: http://arxiv.org/

AUTHOR
------
Andrew Mathas
