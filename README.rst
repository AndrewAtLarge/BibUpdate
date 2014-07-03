=========
bibupdate
=========

This script is a command line tool for updating the entries in a BibTeX_ file
using mrlookup_. By default bibupdate_ tries to find an updated entry for each
paper unless the entry already has an *mrnumber* field (so you can disable
future checking of an entry by giving it an empty *mrnumber* field).

**Usage** bibupdate_ <file.bib>

**Options**::

  -a, --all                   check ALL BibTeX entries against mrlookup
  -h, --help                  show this help message and exit
  -n, --no_warnings           do not print warnings when replacing BibTeX_ entries
  -i IGNORE, --ignore=IGNORE  A string of BibTeX_ fields to ignore when printing
  -q, --quiet                 Do not print a list of changes (default on)
  -v, --version               Print version and exit

\bibupdate_ does not change your origin database file and, instead, it creates a
new file with the name `updated_file.bib`, if your original file was `file.bib`.
As described below, you should check the new file for errors.

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

Although some care is taken to make sure that the new BibTeX_ entries correspond
to the paper that the original entry referred to there is always a chance the
new entry corresponds to an entirely different paper because fuzzy matching is
used to make the comparisons. In my experience this happens only rarely, and
mostly with unpublished manuscripts. In any case, *you are strongly advised to
check the updated file BibTeX_ file carefully for errors!*

To help with comparing the updated entries in *verbose* mode, the default, the
program prints a detailed list of the changes that are being made to  existing
bibtex entries (the new fields added to an entry are not printed). Comparing the
old and new versions of your database with programs like *diff* and *tkdiff* is
highly recommended.

I wrote this class because with the advent of hyperref_ I wanted to be able to
add links to journals, the arXiv_ and DOIs in the bibliographies of my papers.
This script allowed me to add the missing urls and DOI fields to my bibtex
database.  As a bonus the script corrected many minor errors that I had entered
over the years (for example, incorrect page numbers and years). The program is
still useful because it is quite successful in updating the preprint entries in
my database when the papers are published.

As bibupdate_ calls mrlookup_ this program will only be useful if you have
papers in your database that are listed in MathSciNet_.

Options and their defaults
--------------------------

Most of the options are described above. Here is a little extra detail when it
is not so obvious.

-a, --all                   check ALL BibTeX entries against mrlookup

  By default bibupdate_ only checks each BibTeX entry with the mrlookup
  database if the entry does *not* have an **mrnumber** field. With this switch
  all entries are checked.

-n, --no_warnings           do not print warnings when replacing BibTeX_ entries
-q, --quiet                 Do not print a list of changes (default on)

  There are two levels of verbosity in how bibupdate_ describes the changes that
  it is making. By default all additions to the bibtex entry are printed (to stdout).
  In addition, bibupdate_ will tell you when it *is not* able to find the paper
  on mrlookup_ (either because there are no matches or because there are too
  many). If it is not able to find the paper in the mrlookup_ database and
  bibupdate_ thinks that the paper is not a preprint then it will mark the
  missing entry with an exclamation mark. Here is some sample output::

     Missed Webster:CanonicalBasesHigherRep: Canonical bases and higher representatio
    Found updated entry for Weyl
      publisher: Princeton University Press
              -> Princeton University Press, Princeton, NJ
     Missed Williamson:JamesLusztig: Schubert calculus and torsion
    !Missed QSAII: On Quantitative Substitutional Analysis

  Of the three missed entries, bibupdate_ thinks that the first two are
  preprints and that the final one should have been published. With the one
  entry that bibupdate_ found it updated only the publisher entry to include the
  city of the publisher.

  In *quiet* mode you are just "warned" when changes are being made to an entry
  That is, when papers are found (with changes) or when they are missed and
  bibupdate_ thinks that they are not preprints.  If the warnings are turned off
  then you are on your own.

-i IGNORE, --ignore=IGNORE  A string of BibTeX_ fields to ignore when printing

  By default bibupdate_ removes the following fields from each BibTeX_ entry::

  - coden
  - mrreviewer
  - fjournal
  - issn

  This list can be changed using the `-i` command line option::

  .. bibupdate -i "coden fjournal" file.bib  # ignore just coden and fjournal
  .. bibupdate -i "" file.bib                # do not ignore any fields


Installation
============

There are two installation routes.

1. From the command line type::

      pip install http://bitbucket.org/aparticle/bibupdate/downloads/bibupdate-1.0.tar.gz

2. Clone or download this repository, change directory into it and then
   run *pip* or *easy_install*::

      pip setup.py install


ToDo
----
* Find the best match when mrlookup_ returns multiple entries!
* Add an rc file to override the defaults...

History
-------
BibTeX_ is used by the LaTeX_ community to maintain publication databases.

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
