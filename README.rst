=========
bibupdate
=========

**Usage**: 

bibupdate [-a] [-c] [-f] [-i IGNORE] [-l LOG] [-m | -M] [-q] [-r] <bibtexfile> [ouptut]

This is a command line tool for updating the entries in a BibTeX_ file using
mrlookup_. By default bibupdate_ tries to update the entry for each paper
in the BibTeX_ file unless the entry already has an **mrnumber** field (you can
disable future checking of an entry by giving it an empty **mrnumber** field).

**Options**::

  -a, --all             update or validate ALL BibTeX entries
  -c, --check_all       check all bibtex entries against a database
  -f, --font_replace    do NOT replace fonts \Bbb, \germ and \scr
  -h, --help            show this help message and exit
  -i IGNORE, --ignored-fields IGNORE
                        a string of bibtex fields to ignore
  -l LOG, --log LOG     log output to file (defaults to stdout)
  -q, --quietness         print fewer messages
  -r  --replace         replace existing bibtex file

  -m, --mrlookup        use mrlookup to update bibtex entries (default)
  -M, --mathscinet      use mathscinet to update bibtex entries (less flexible)

**Note:** 
As described below, you should check the new file for errors before deleting the
original version of your BibTeX_ file.

By default, bibupdate_ does not change your original database file. Instead, it creates a
new file with the name *updated_file.bib*, if your original file was *file.bib*.
It is also possible to have it replace your current file (use carefully!), or to
specify a new file name.

BibTeX_ is widely used by the LaTeX_ community to maintain publication databases.
This script attempts to add missing fields to the papers in a BibTeX_ database
file by querying mrlookup_ and getting the missing information from there. This
is not completely routine because to search on mrlookup_ you need either the
authors or the title of the article and both of these can have non-standard
representations. If the article is already published then it is also possible to
use the publication year and its page numbers. To search on mrlookup_ we::

- use the authors (can be problematic because of accents and names with von etc)
- use the page numbers, if they exist
- use the year only if there are no page numbers and this is NOT a preprint
- use the title if there are no page numbers (or this is a book)

If there is a unique match from mrlookup_ then bibupdate_ replaces all of the
current entries with those from mrlookup_, except for the citation key. The
values of any fields that are not specified by mrlookup_, such as eprint fields,
are retained. By default, a message is printed whenever existing fields in the
database are changed. If the title of the retrieved paper does not (fuzzily)
match that of the original article then the entry is NOT updated and a warning
message is printed.

Although some care is taken to make sure that the new BibTeX_ entries correspond
to the same paper that the original entry referred to there is always a (very
small) chance the new entry corresponds to an entirely different paper.  In my
experience this happens rarely, and mostly with unpublished manuscripts. In any
case, before you delete you original BibTeX_ file *you are strongly advised to
check the updated file BibTeX_ file carefully for errors!*

To help with comparing the updated entries the program prints a detailed list of
all changes that are made to existing BibTeX_ entries (the new fields added to
an entry are not printed). Once bibupdate_ has finished it is recommended that
you compare the old and new versions of your database with programs like *diff*
and *tkdiff*.

I wrote this script because I wanted to automatically add links to journals, the
arXiv_ and DOIs to the bibliographies of my papers using hyperref_. This script
allowed me to add the missing urls and DOI fields to my BibTeX_ database. As a
bonus the script helped me to correct many minor errors that had crept into my
BibTeX_ file over the years (for example, incorrect page numbers and years). Now
I use the program to automatically update the preprint entries in my database
when the papers appear in MathSciNet_ after they are published.

As bibupdate_ calls mrlookup_ this program will only be useful if you have
papers in your database that are listed in MathSciNet_. As described below it is
also possible to call MathSciNet_ directly, however, this is less flexible
because the *mrnumber* field for each paper is required.

Options and their defaults
--------------------------

Most of the options are described above. Here is a little extra detail when it
is not so obvious.

-a, --all  Update or validate ALL BibTeX entries

  By default bibupdate_ only checks each BibTeX_ entry with the mrlookup
  database if the entry does *not* have an **mrnumber** field. With this switch
  all entries are checked and updated.

-c --check_all  Check all bibtex entries against a database

  Prints a list of entries in the BibTeX file that have entries different from
  those given by the corresponding database. The original BibTeX file is not
  changed.

-f, --font_replace  Do not replace fonts \\germ and \\scr

  The BibTeX_ entries generated by mrlookup_ use \\Bbb, \\germ and \\scr for the \\mathbb,
  \\mathfrak and \\mathscr fonts. By default, these fonts specifications are automatically
  changed to the following more LaTeX_ friendly font specifications:

        - \\Bbb X  --> \\mathbb{X}
        - \\scr X  --> \\mathscr{X}
        - \\germ X --> \\mathfrak{X}

  The -f option *disables* these substitutions.

-i IGNORE, --ignored-fields=IGNORE  A string of BibTeX_ fields to ignore when writing the updated file

  By default bibupdate_ removes the following fields from each BibTeX_ entry::

  - coden
  - mrreviewer
  - fjournal
  - issn

  This list can be changed using the -i command line option::

  .. bibupdate -i "coden fjournal" file.bib   # ignore coden and fjournal
  .. bibupdate -i coden -i fjournal file.bib  # ignore coden and fjournal
  .. bibupdate -i "" file.bib                 # do not ignore any fields

-l LOG, --log LOG  Log output to file (defaults to stdout)

  Specify a log filename to use for output.

-m --mrlookup     Use mrlookup to update bibtex entries (default)

-M --mathscinet   Use mathscinet to update bibtex entries

  By default mrlookup_ is used to update the BibTeX_ entries in the database.
  This has he advantage of being a free service provided by the American
  Mathematical Society. A second advantage is the more flexible searching is
  possible when \mrlookup_ is used. It is also possible to update BibTeX_
  entries using MathSciNet_, however, these searches are currently only possible
  using the **mrnumber** field (so this option only does something if combined
  with the -all option).

-q, --quietness  Print fewer messages

  There are three levels of verbosity in how bibupdate_ describes the changes that
  it is making. These are determined by the `q` option as follows::

  .. bibupdate     bibfile.bib    Report all changes (default)
  .. bibupdate -q  bibfile.bib    Only print entries that are changed
  .. bibupdate -qq bibfile.bib    Only printer error messages

  By default all changes are printed (to stdout, although a log file can be
  specified by the -l option). In the default mode bibupdate_ will tell you what
  entries it changes and when it *is not* able to find the paper on the database
  (either because there are no matches or because there are too many). If it is
  not able to find the paper and bibupdate_ thinks that the paper is not a
  preprint then it will mark the missing entry with an exclamation mark, to
  highlight that it thinks that it should have found the entry in mrlookup_ but
  failed. Here is some sample output::

    ------------------------------
    ? did not find Webster:CanonicalBasesHigherRep=Canonical bases and higher representatio
    ++++++++++++++++++++++++++++++
    + updating Weyl=
    + publisher: Princeton University Press
    +         -> Princeton University Press, Princeton, NJ
    ------------------------------
    ? did not find Williamson:JamesLusztig=Schubert calculus and torsion
    ------------------------------
    ! did not find QSAII=On Quantitative Substitutional Analysis

  Each bibtex_ entry is identified by the citation key and the document title,
  as specified by your database. Of the three missed entries above, bibupdate_
  thinks that the first two are preprints (they are not marked with an !), that
  the final one should already have been published. With the entry that
  bibupdate_ found, only the publisher entry was changed so that it includes the
  city of the publisher.

  In *warning mode*, with the -w option,  you are just "warned" when changes are
  being made to an entry. That is, when papers are found (with changes) or when
  they are missed and bibupdate_ thinks that they are not preprints. In *quiet
  mode*, with the -qq option, the program only reports when something goes wrong.

-r  --replace  Replace the existing bibtex file with the updated version

  Replace the existing BibTeX_ file with the updated file. A backup version of
  the original BibTeX_ is made with a .bak extension. it is also possible to
  specify the output filename as the last argument to bibupdate.

BibTeX fields
-------------

bibupdate_ reads the entries in a BibTeX_ using a series of python regular
expressions. To do this bibupdate_ only supports a more restrictive format for
specifying the values of fields: they must always be enclosed in braces.
(BibTeX_ is slightly more flexible as it will also accepts "words").  For
example, bibupdate_ will correctly recognise the YEAR from::

    YEAR = {1991},

however, it will fail to determine the YEAR when the braces are omitted::

    YEAR = 1991,

If you maintain your BibTeX_ database "by hand" then this might be a problem for
you. If, however, you use a program like JabRef this should not be an issue.

There are a small number of cases that I know of where bibupdate_ fails to
correctly identify papers that are listed in MathSciNet_. These failure occur 
for the following reasons:

* Apostrophes: Searching for a title containing, for example, "James's Conjecture" 
  confuses mrlookup_.
* Accents in authors: Generally accents are not a problem because the AMs is
  LaTeX_ aware, however, issues arise when there are multiple versions of authors
  names.
* Pages numbers: electronic journals, in particular, often have strange page
  numbers (for example "Art. ID rnm032, 24"). Occassionally MathReviews for
  closely related articles are combined.

Installation
============

You need to have Python_ installed. In principle, this program should work on
any system that supports Python_, however, I only promise that it will work
on an up-to-date mac or Linux system. In the event that it does not install I
may not be able to help you as I will not have access to your system.

There are two installation routes.

1. From the command line type::

      pip install http://bitbucket.org/AndrewsBucket/bibupdate/downloads/bibupdate-1.1.tar.gz

2. Clone or download_ this repository, change directory into it and then
   run *pip* or *easy_install*::

      pip setup.py install

Instead of pip, you should also be able to use easy_install. The program should
run on python 2.7 and 2.8...I haven't tried python3.

Support
=======

This program is being made available primarily on the basis that it might be
useful to others. I wrote the program in my spare time and I will support it in
my spare time, to the extent that I will fix what I consider to be serious
problems and I may implement feature requests. Ultimately, however, my family,
research, teaching and administrative duties will have priority.

To do
=====

- Implement more intelligent searches using MathSciNet_.
- Interface to the arXiv_? In principle, this is easy to do although,
  ultimately, it would probably not work because the arXiv_ blocks frequent
  requests from the same IP address in order to discourage robots.

AUTHOR
======

`Andrew Mathas`_

bibupdate_ Version 1.1. Copyright (C) 2012-14 

GNU General Public License, Version 3, 29 June 2007

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU_General Public License (GPL_) as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

.. _`Andrew Mathas`: http://www.maths.usyd.edu.au/u/mathas/
.. _arXiv: http://arxiv.org/
.. _BibTeX: http://www.bibtex.org/
.. _bibupdate: https://bitbucket.org/aparticle/bibupdate
.. _download: http://bitbucket.org/AndrewsBucket/bibupdate/downloads/
.. _GPL: http://www.gnu.org/licenses/gpl.html
.. _hyperref: http://www.ctan.org/pkg/hyperref
.. _LaTeX: http://en.wikipedia.org/wiki/LaTeX
.. _MathSciNet: http://www.ams.org/mathscinet/
.. _mrlookup: http://www.ams.org/mrlookup
.. _Python: https://www.python.org/
