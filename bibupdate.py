#!/usr/bin/env python

r"""
===============================================
bibupdate - update the entries of a bibtex file
===============================================

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

See https://bitbucket.org/aparticle/bibupdate for more details
about the bibupdate program.

Andrew Mathas andrew.mathas@gmail.com
Copyright (C) 2012-14 
"""

# Metadata - used in setup.py
__author__='Andrew Mathas'
__author_email__='andrew.mathas@gmail.com'
__description__='Automatically update the entries of a bibtex file'
__keywords__='bibtex, mrlookup, MathSciNet, latex'
__license__='GNU General Public License, Version 3, 29 June 2007'
__url__='https://bitbucket.org/AndrewsBucket/bibupdate'
__version__='1.3dev'

# for command line option
bibupdate_version=r'''
%(prog)s version {__version__}: {__description__}
{__license__}
'''.format( **globals() )

######################################################
import argparse, os, re, shutil, sys, textwrap, urllib, __builtin__
from collections import OrderedDict
from fuzzywuzzy import fuzz

# global options, used mainly for printing
global options, verbose, warning, debugging, fix_fonts, wrapped

def bib_print(*args):
    r"""
    Default printing mechanism. Defaults to sys.stdout but can be overridden 
    by the command line options.
    """
    for a in args:
        options.log.write(a+'\n')

def bib_error(*args):
    r"""
    Print errors to sys.stderr and also to the log file if it is not sys.stdout.
    Then exit with an error code of 2.
    """
    if options.log!=sys.stdout:
        bib_print('%s error:' % options.prog)
        for a in args:
            bib_print(a)

    sys.stderr.write('%s error: ' % options.prog)
    for a in args:
        sys.stderr.write(a+'\n')
    sys.exit(2)

def CleanExceptHook(type, value, traceback):
    r"""
    Exit cleanly when program is killed, or jump into pdb if debugging
    """
    if type == KeyboardInterrupt:
        bib_error('program killed. Exiting...')
    elif (options.debugging==0 or hasattr(sys, 'ps1') or not sys.stdin.isatty()
            or not sys.stdout.isatty() or not sys.stderr.isatty() 
            or issubclass(type, bdb.BdbQuit) or issubclass(type, SyntaxError)):
        sys.__excepthook__(type, value, traceback)
    else:
        import traceback, pdb
        # we are NOT in interactive mode, print the exception...
        traceback.print_exception(type, value, tb)
        print
        # ...then start the debugger in post-mortem mode.
        pdb.pm()

# ...and a hook to grab the exception
sys.excepthook = CleanExceptHook

##########################################################

# define a regular expression for extracting papers from BibTeX file
bibtex_entry=re.compile('(@\s*[A-Za-z]*\s*{[^@]*})\s*',re.DOTALL)

# regular expression for cleaning TeX from title etc
remove_tex=re.compile(r'[{}\'"_$]+')
remove_mathematics=re.compile(r'\$[^\$]+\$')  # assume no nesting
# savagely remove all maths from title
clean_title=lambda title: remove_tex.sub('',remove_mathematics.sub('',title))

# to help in checking syntax define recognised/valid types of entries in a bibtex database
bibtex_pub_types=['article', 'book', 'booklet', 'conference', 'inbook', 'incollection', 
                  'inproceedings', 'manual', 'mastersthesis', 'misc', 'phdthesis', 
                  'proceedings', 'techreport', 'unpublished'
]

# need to massage some of the font specifications returned by mrlookup to "standard" latex fonts.
fonts_to_replace={ 'Bbb' :'mathbb', 
                   'scr' :'mathcal', 
                   'germ':'mathfrak' 
}
# a factory regular expression to replace expressions like \scr C and \scr{ Cat} in one hit
font_replacer=re.compile(r'\\(%s)\s*(?:(\w)|\{([\s\w]*)\})' % '|'.join('%s'%f for f in fonts_to_replace.keys()))
def replace_fonts(string):
    r"""
    Return a new version of `string` with various fonts commands replaced with
    their more standard LaTeX variants.

    Currently::

        - \Bbb X   and \BBb {X*}  --> \mathbb{X*}
        - \scr X*  and \scr {X*}  --> \mathcal{X*}
        - \germ X* and \germ{X*}  --> \mathfrak{X*}
    """
    return font_replacer.sub(lambda match : r'\%s{%s}' % (fonts_to_replace[match.group(1)],match.group(2) or match.group(3)), string)

def good_match(one,two):
    r"""
    Returns True or False depending on whether or not the lower cased strings
    `one` and `two` are a good (fuzzy) match for each other.
    """
    return fuzz.ratio(one.lower(), two.lower())>90

# overkill for "type checking" of the wrap length command line option
class NonnegativeIntegers(__builtin__.list):
    r"""
    A class that gives an easy test for positive integers::

        >>> 1 in NonnegativeIntegers()
        True
        >>> -1 in NonnegativeIntegers()
        False
    """
    def __str__(self):
        return 'positive integers'

    def __contains__(self,x):
        r"""
        By implementing containment we can test if `x` is in `NonnegativeIntegers()`.
        """
        return isinstance(x,int) and x>=0

class Bibtex(OrderedDict):
    r"""
    The bibtex class holds all of the data for a bibtex entry for a manuscript.
    It is called with a string <bib_string> that contains a bibtex entry and it
    returns a dictionary with whistles for the bibtex entry together with some
    methods for updating and printing the entry. As the bibtex file is a flat
    text file, to extract the data from it we use a collection of regular
    expressions which pull out the data key by key.

    The class contains mrlookup() and mathscinet() methods that attempt to
    update the bibtex entry by searching on the corresponding AMS databases for
    the paper. If successful this overwrite all of the existing bibtex fields,
    except for the cite key. Any entries not in MathSciNet are retained.

    Most of he hard work is done by a cunning use of regular expressions to
    extract the data from the bibtex file and from mrlookup and
    mathscient...perhaps we should be using pyquery or beautiful soup for the
    latter, but these regular expressions are certainly effective.
    """
    # A regular expression to extract a bibtex entry from a string. We assume that
    # the pub_type is a word in [A-Za-z]* and allow the citation key and the
    # contents of the bibtex entry to be fairly arbitrary and of the form: {cite_key, *}.
    parse_bibtex_entry=re.compile(r'@(?P<pub_type>[A-Za-z]*)\s*\{\s*(?P<cite_key>\S*)\s*,\s*?(?P<keys_and_vals>.*\})[,\s]*\}', re.MULTILINE|re.DOTALL)

    # To extract the keys and values we need to remove all spaces around equals
    # signs because otherwise we are unable to cope with = inside a bibtex field.
    keys_and_vals=re.compile(r'\s*=\s*')

    # A regular expression to extract pairs of keys and values from a bibtex
    # string. The syntax here is very lax: we assume that bibtex fields do not
    # contain the string '={'.  From the AMS the format of a bibtex entry is
    # much more rigid but we cannot assume that an arbitrary bibtex file will
    # respect the AMS conventions.  There is a small complication in that we
    # allow the value of each field to either be enclosed in braces or to be a
    # single word.
    bibtex_keys=re.compile(r'([A-Za-z]+)=(?:\{((?:[^=]|=(?!\{))+)\}|(\w+)),?\s*$', re.MULTILINE|re.DOTALL)

    # A regular expression for extracting page numbers: <first page>-*<last page>
    # or simply <page>.
    page_nums=re.compile('(?P<apage>[0-9]*)-+(?P<zpage>[0-9]*)')

    # For authors we match either "First Last" or "Last, First" with the
    # existence of the comma being the crucial test because we want to allow
    # compound surnames like De Morgan.
    author=re.compile(r'(?P<Au>[\w\s\\\-\'"{}]+),\s[A-Z]|[\w\s\\\-\'"{}]+\s(?P<au>[\w\s\\\-\'"{}]+)',re.DOTALL)

    def __init__(self, bib_string):
        """
        Given a string <bib_string> that contains a bibtex entry return the corresponding Bibtex class.

        EXAMPLE:
        """
        super(Bibtex, self).__init__()   # initialise as an OrderedDict
        entry=self.parse_bibtex_entry.search(bib_string)
        if entry is None:
            self.cite_key=None
            self.bib_string=bib_string
        else:
            self.pub_type=entry.group('pub_type').strip().lower()
            self.cite_key=entry.group('cite_key').strip()
            keys_and_vals=self.keys_and_vals.sub('=',entry.group('keys_and_vals'))   # remove spaces around = 
            for (key,val,word) in self.bibtex_keys.findall(keys_and_vals):
                if val=='': 
                    val=word                  # val matches {value} whereas word matches word
                else:
                    val=' '.join(val.split()) # remove any internal space from val
                lkey=key.lower()              # keys always in lower case
                if lkey=='title':
                    self[lkey]=fix_fonts(val) # only fix fonts in the title, others assumed OK
                else:
                    self[lkey]=val

            # guess whether this entry corresponds to a preprint
            self.is_preprint=( (self.has_key('pages') and self['pages'].lower() in ['preprint', 'to appear', 'in preparation'])
                      or not (self.has_key('pages') and self.has_key('journal')) )

    def __str__(self):
        r"""
        Return a string for printing the bibtex entry.
        """
        if hasattr(self,'pub_type'):
            return '@%s{%s,\n  %s\n}' % (self.pub_type.upper(), self.cite_key,
                    ',\n  '.join('%s = {%s}'%(key,wrapped(self[key]))
                     for key in self.keys() if key not in options.ignored_fields))
        else:
            return self.bib_string

    def __getitem__(self, key, default=''):
        """
        We override `__getitem__` so that `self[key]` returns `default` if the `self[key]`
        does not exist.
        """
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            return default

    def has_valid_pub_type(self):
        r"""
        Return True if the entry has a valid pub_type, as determined by
        bibtex_pub_types, and False otherwise.
        """
        return hasattr(self, 'pub_type') and (self.pub_type in bibtex_pub_types)

    def update_entry(self, url, search):
        """
        Call `url` to search for the bibtex entry as specified by the dictionary
        `search` and then update `self` if there is a unique good match. If
        there is a good match then we update ourself and overwrite all fields
        with those from mrlookup (and keep any other fields).

        The url can (currently) point to mrlookup or to mathscinet.
        """
        # query url with the search string
        try:
            debugging('S %s\n%s' % (url, '\n'.join('S %s=%s'%(s[0],s[1]) for s in search.items())))
            lookup = urllib.urlopen(url, urllib.urlencode(search))
            page=lookup.read()
            lookup.close()   # close the url feed
        except IOError:
            bib_error('unable to connect to %s' % url)

        # attempt to match self with the bibtex entries returned by mrlookup
        matches=[Bibtex(mr.groups(0)[0]) for mr in bibtex_entry.finditer(page)]
        matches=[mr for mr in matches if mr is not None and mr.has_valid_pub_type()]
        debugging('MR number of matches=%d'%len(matches))
        clean_ti=clean_title(self['title'])
        debugging('MR ti=%s.%s' % (clean_ti, ''.join('\nMR -->%s.'%clean_title(mr['title']) for mr in matches)))
        if clean_ti<>'':
            matches=[mr for mr in matches if good_match(clean_ti, clean_title(mr['title']))]
        debugging('MR number of clean matches=%d'%len(matches))

        if len(matches)==1:
            match=matches[0]
            differences=[key for key in match if key not in options.ignored_fields and self[key]<>match[key]]
            if differences!=[] and any(self[key]!='' for k in differences):
                if options.check_all:
                    bib_print('%s\n%s=%s\n%s' % ('='*30, self.cite_key, self['title'][:50],
                                  '\n'.join(' %s: %s\n%s-> %s'%(key,self[key], ' '*len(key), match[key]) 
                                        for key in differences)))
                else:
                    warning('%s\n+ Updating %s=%s' % ('+'*30, self.cite_key, self['title'][:50]))
                    verbose('\n'.join('+  %s: %s\n+%s->  %s'%(key,self[key], ' '*len(key),
                                        match[key]) for key in differences))
                    for key in differences:
                        self[key]=match[key]
            else:
                debugging('No change')

        else:  # no good match, or more than one good match
            if not self.is_preprint:
                verbose("%s\n%s Didn't find %s=%s"%('-'*30, 
                            '!' if self.is_preprint else '!', self.cite_key,
                            self['title'][:40] if self.has_key('title') else '???'))

    def mrlookup(self):
        """
        Use mrlookup to search for a more up-to-date version of this entry. To
        search with mrlookup we look for papers published by the first author in
        the given year with the right page numbers. Most of the work here is in
        finding the correct search parameters.
        """
        # only check mrlookup for books or articles for which we don't already have an mrnumber field
        if not options.all and (self.has_key('mrnumber')
           or self.pub_type not in ['book','article','inproceedings','incollection']):
            return

        debugging('='*30)
        search={'bibtex':'checked'}   # a dictionary that will contain the parameters for the mrlookup search

        if self.has_key('pages') and not self.is_preprint:
            pages=self.page_nums.search(self['pages'])
            if not pages is None:
                search['ipage']=pages.group('apage')  # first page
                search['fpage']=pages.group('zpage')  # last page
            elif self['pages'].isdigit():
                search['ipage']=self['pages']  # first page
                #search['fpage']=self['pages']  # last page

        # the year is reliable only if we also have page numbers
        if self.has_key('year') and (self.pub_type=='book' or search.has_key('ipage')):
            search['year']=self['year']

        # mrlookup requires either an author or a title
        if self.has_key('author'):
            # mrlookup is latex aware and it does a far better job of parsing
            # authors than we ever will, however, it only recognises authors in
            # the form "Last Name" -- and sometimes with a first initial as
            # well. So this is what we need to give it.
            authors=''
            aulist=re.sub(' and ','&',self['author'])
            aulist=aulist.replace('~',' ')
            for au in aulist.split('&'):
                a=self.author.search(au.strip())
                if not a is None:
                    if a.group('au') is not None:
                        authors+=' and '+a.group('au')    # First LAST
                    else:
                        authors+=' and '+a.group('Au')    # LAST, First
            if len(authors)>5:
                search['au']=authors[5:]

        if self.has_key('title') and len(self['title'])>0 and (not search.has_key('ipage') or self.is_preprint):
            search['ti']=clean_title(self['title'])

        self.update_entry('http://www.ams.org/mrlookup', search)

    def mathscinet(self):
        """
        Use MathSciNet to check/update the entry using the mrnumber field, if it exists.
        """
        if options.all or self.has_key('mrnumber'):
            search={'fmt': 'bibtex', 'pg1': 'MR', 's1': self['mrnumber'].split()[0]}
            self.update_entry('http://www.ams.org/mathscinet/search/publications.html', search, False)

def process_options():
    r"""
    Set up and then parse the options to bibupdate using argparse.
    """
    global options, verbose, warning, debugging, fix_fonts, wrapped

    parser = argparse.ArgumentParser(description='Update and validate BibTeX files',
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('bibtexfile',type=argparse.FileType('r'),help='bibtex file to update')
    parser.add_argument('outputfile',nargs='?',type=str,default=None,help='output file')

    parser.add_argument('-a','--all',action='store_true',default=False,
                        help='update or validate ALL BibTeX entries')
    parser.add_argument('-c','--check-all',action='store_true', default=False,
                        help='check all bibtex entries against a database')
    parser.add_argument('-k','--keep_fonts',action='store_true', default=False,
                        help='do NOT replace fonts \Bbb, \germ and \scr in titles')
    parser.add_argument('-i','--ignored-fields',type=str,default=['coden','mrreviewer','fjournal','issn'],
                        metavar='FIELDS', action='append',help='a string of bibtex fields to ignore')
    parser.add_argument('-l','--log', default=sys.stdout, type=argparse.FileType('w'),
                        help='log messages to specified file (defaults to stdout)')

    # add a mutually exclusive switch for choosing between mrlookup and mathscinet
    lookup=parser.add_mutually_exclusive_group()
    lookup.add_argument('-m','--mrlookup',action='store_const',const='mrlookup',dest='lookup',
                        default='mrlookup',help='use mrlookup to update bibtex entries (default)')
    lookup.add_argument('-M','--mathscinet',action='store_const',const='mathscinet',dest='lookup',
                        help='use mathscinet to update bibtex entries (less flexible)')

    parser.add_argument('-o','--overwrite',action='store_true', default=False,
                        help='overwrite existing bibtex file')
    parser.add_argument('-q','--quieter',action='count', default=2,
                        help='printer fewer messages')
    parser.add_argument('-w','--wrap',type=int, default=0, action='store', choices=NonnegativeIntegers(),
                        metavar='LEN', help='wrap bibtex fields to specified width')

    # suppress printing of these two options
    parser.add_argument('--version',action='version', version=bibupdate_version, help=argparse.SUPPRESS)
    parser.add_argument('-d','--debugging',action='count', default=0, help=argparse.SUPPRESS)

    # parse the options
    options = parser.parse_args()
    options.prog=parser.prog
    if len(options.ignored_fields)>4:
        # if any fields were added then don't ignore the first 4 fields.
        options.ignored_fields=list(chain.from_iterable([i.lower().split() for i in options.ignored_fields[4:]]))

    # if check_all==True then we want to check everything
    if options.check_all:
        options.all=True

    # define word wrapping when requested
    if options.wrap!=0:
        wrapped=lambda field: '\n'.join(textwrap.wrap(field,options.wrap,subsequent_indent='\t'))
    else:
        wrapped=lambda field: field

    # define debugging, verbose and warning functions
    if options.debugging>0:
        options.quieter=2
        debugging=bib_print
        if options.debugging==4:
            # start pudb
            import pudb
            pu.db
    else:
        debugging=lambda *arg: None
    verbose=bib_print if options.quieter==2 else lambda *arg: None
    warning=bib_print if options.quieter>=1 else lambda *arg: None

    # a shorthand for fixed the fonts (to avoid an if-statement when calling it)
    fix_fonts=replace_fonts if not options.keep_fonts else lambda title: title 

def main():
    r"""
    Open the files and the delegate all of the hard work to the BibTeX class.
    """
    process_options()

    # now we are ready to open the existing BibTeX file and start working
    try:
        bibfile=open(options.bibtexfile.name,'r')
        papers=bibfile.read()
        bibfile.close()
        asterisk=papers.index('@')
    except IOError:
        bib_error('unable to open bibtex file %s' % options.bibtexfile.name)

    # if we are checking for errors then we check EVERYTHING but, in this case,
    # we don't need to create a new bibtex file
    if options.check_all:
        options.check_all=True
    else:
        if options.overwrite:
            newfile=options.filename.name  # will be backed up below
        elif options.outputfile is None:
            # write updates to 'updated_'+filename
            dir=os.path.dirname(options.bibtexfile.name)
            base=os.path.basename(options.bibtexfile.name)
            newfile='{dir}updated_{base}'.format(dir='' if dir=='' else dir+'/',base=base)
        else:
            newfile=options.outputfile

        # backup the output file by adding .bak if it exists and is non-empty
        if os.path.isfile(newfile) and os.path.getsize(newfile)>0:
            try:
                shutil.copyfile(newfile,newfile+'.bak')
            except IOError:
                biberror('unable to create backup file for %s'%newfile)

        # open newfile
        try:
            newbibfile=open(newfile,'w')
            newbibfile.write(papers[:asterisk]) # copy everything up to the first @
        except IOError:
            bib_error('unable to open new bibtex file %s' % newfile)

    # we are now ready to start processing the papers from the bibtex file
    for bibentry in bibtex_entry.finditer(papers[asterisk:]):
        if not bibentry is None:
            bt=Bibtex(bibentry.group())
            # other pub_types are possible such as @comment{} we first check
            if bt.has_valid_pub_type():
                getattr(bt, options.lookup)()  # call lookup program

        # now write the new (and hopefully) improved entry
        if not options.check_all:
            newbibfile.write('%s\n\n' % bt)

    if not options.check_all:
        newbibfile.close()

##############################################################################
if __name__ == '__main__':
  main()


# By automatically generating the README file as part of setup we don't need to
# hardcode version numbers etc.
readme_text=r'''=========
bibupdate
=========

{__description__}

usage: bibupdate [-h] [-a] [-c] [-f] [-i FIELDS] [-l LOG] [-m | -M] [-q] [-r]
                 [-w LEN] bibtexfile [outputfile]

This is a command line tool for updating the entries in a BibTeX_ file using
mrlookup_. By default bibupdate_ tries to update the entry for each paper
in the BibTeX_ file unless the entry already has an ``mrnumber`` field (you can
disable future checking of an entry by giving it an empty ``mrnumber`` field).

**Options**::

  -a, --all             update or validate ALL BibTeX entries
  -c, --check_all       check all bibtex entries against a database
  -k, --keep_fonts      do NOT replace fonts \Bbb, \germ and \scr in titles
  -h, --help            show this help message and exit
  -i FIELDS, --ignored-fields FIELDS
                        a string of bibtex fields to ignore
  -l LOG, --log LOG     log messages to specified file (defaults to stdout)
  -o  --overwrite       overwrite existing bibtex file
  -q, --quietness       print fewer messages
  -w LEN --wrap LEN     wrap bibtex fields to specified width

  -m, --mrlookup        use mrlookup to update bibtex entries (default)
  -M, --mathscinet      use mathscinet to update bibtex entries (less flexible)

**Note:** 
As described below, you should check the new file for errors before deleting the
original version of your BibTeX_ file.

By default, bibupdate_ does not change your original database file. Instead, it creates a
new file with the name *updated_file.bib*, if your original file was *file.bib*.
It is also possible to have it replace your current file (use carefully!), or to
specify an output file.

BibTeX_ is widely used by the LaTeX_ community to maintain publication databases.
This script attempts to add missing fields to the papers in a BibTeX_ database
file by querying mrlookup_ and getting the missing information from there. This
is not completely routine because to search on mrlookup_ you need either the
authors or the title of the article and both of these can have non-standard
representations. If the article is already published then it is also possible to
use the publication year and its page numbers. To search on mrlookup_ we:

    - use the authors (can be problematic because of accents and names with von etc)
    - use the page numbers, if they exist
    - use the year only if there are no page numbers and this is NOT a preprint
    - use the title if there are no page numbers (or this is a book)

If there is a unique (good, non-fuzzy) match from mrlookup_ then bibupdate_
replaces all of the current fields with those from mrlookup_, except for the
citation key. The values of any fields that are not specified by mrlookup_, such
as ``eprint`` fields, are retained. By default, a message is printed whenever
existing fields in the database are changed. If the title of the retrieved paper
does not (fuzzily) match that of the original article then the entry is NOT
updated and a warning message is printed.

Although some care is taken to make sure that the new BibTeX_ entries correspond
to the same paper that the original entry referred to there is always a (small?)
chance the new entry corresponds to an entirely different paper. In my
experience this happens rarely, and mostly with unpublished manuscripts. In any
case, before you delete your original BibTeX_ file *you are strongly advised to
check the updated file BibTeX file carefully for errors!*

To help the user to compare the updated fields for each entry in the BibTeX_
file the program prints a detailed list of all changes that are made to existing
BibTeX_ fields (any new fields that are added are not printed). Once bibupdate_
has finished running it is recommended that you compare the old and new versions
of your database using programs like *diff* and *tkdiff*.

As bibupdate_ calls mrlookup_ this program will only be useful if you have
papers in your database that are listed in MathSciNet_. As described below it is
also possible to call MathSciNet_ directly, however, this is less flexible
because the ``mrnumber`` field for each paper is required.

I wrote this script because I wanted to automatically add links to journals, the
arXiv_ and DOIs to the bibliographies of my papers using hyperref_. This script
allowed me to add the missing urls and DOI fields to my BibTeX_ database. As a
bonus the script helped me to correct many minor errors that had crept into my
BibTeX_ file over the years (for example, incorrect page numbers and publication
years). Now I use the program to automatically update the preprint entries in my
database when the papers appear in MathSciNet_ after they are published.

Options and defaults
--------------------

-a, --all  Update or validate ALL BibTeX entries

  By default bibupdate_ only checks each BibTeX_ entry with the mrlookup
  database if the entry does *not* have an ``mrnumber`` field. With this switch
  all entries are checked and updated.

-c --check_all  Check/validate all bibtex entries against a database

  Prints a list of entries in the BibTeX file that have fields different from
  those given by the corresponding database. The original BibTeX file is not
  changed.

-k, --keep_fonts      do NOT replace fonts \Bbb, \germ and \scr in titles

  The BibTeX_ entries generated by mrlookup_ use \\Bbb, \\germ and \\scr for the
  \\mathbb, \\mathfrak and \\mathscr fonts. By default, in the *title* fields,
  these fonts specifications are automatically changed to the following more
  LaTeX_ friendly fonts:

        - \\Bbb X  --> \\mathbb{{X}}
        - \\scr X  --> \\mathcal{{X}}
        - \\germ X --> \\mathfrak{{X}}

  By using the -k option the fonts specification used by MathSciNet are used.

-i FIELDS, --ignored-fields=FIELDS  A string of BibTeX_ fields to ignore when writing the updated file

  By default bibupdate_ removes the following fields from each BibTeX_ entry:

      - coden
      - mrreviewer
      - fjournal
      - issn

  This list can be changed using the -i command line option::

     bibupdate -i "coden fjournal" file.bib   # ignore coden and fjournal
     bibupdate -i coden -i fjournal file.bib  # ignore coden and fjournal
     bibupdate -i "" file.bib                 # do not ignore any fields

-l LOG, --log LOG  Log output to file (defaults to stdout)

  Specify a log filename to use for the bibupdate_ messages.

-m --mrlookup     Use mrlookup to update bibtex entries (default)

-M --mathscinet   Use mathscinet to update bibtex entries

  By default mrlookup_ is used to update the BibTeX_ entries in the database.
  This has the advantage of being a free service provided by the American
  Mathematical Society. A second advantage is the more flexible searching is
  possible when mrlookup_ is used. It is also possible to update BibTeX_
  entries using MathSciNet_, however, these searches are currently only possible
  using the ``mrnumber`` field (so this option only does something if combined
  with the --all option or the -check-all-option).

-o  --overwrite  Overwrite the existing bibtex file with the updated version

  Replace the existing BibTeX_ file with the updated file. A backup version of
  the original BibTeX_ is made with a .bak extension. it is also possible to
  specify the output filename as the last argument to bibupdate.

-q, --quietness  Print fewer messages

  There are three levels of verbosity in how bibupdate_ describes the changes that
  it is making. These are determined by the q-option as follows::

     bibupdate     bibfile.bib    (Defalt) Report all changes
     bibupdate -q  bibfile.bib    (Warning mode) Only print entries that are changed
     bibupdate -qq bibfile.bib    (Quiet mode) Only printer error messages

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

  Each bibtex_ entry is identified by the citation key and the (first 50
  characters of the sanitised) document title, as specified by your database. Of
  the three missed entries above, bibupdate_ thinks that the first and third are
  preprints (they are not marked with an !) and  that the final article should
  already have been published. With the entry that bibupdate_ found, only the
  publisher field was changed to include the city of publication.

  In *warning mode*, with the -q option, you are "warned" whenever changes are
  made to an entry or when the paper is not found in the external datbase. That
  is, when papers are found (with changes) or when they are missed and
  bibupdate_ thinks that they are not preprints. In *quiet mode*, with the -qq
  option, the program only reports when something goes wrong.

-w LEN --wrap LEN    Wrap bibtex fields to specified width

  Limits the maximum line length in the output BibTeX_ file. In theory this is
  supposed to make it easier to compare the updated BibTeX_ file with the
  original one, however, in practise this doesn't always work.

Known issues
------------

\bibupdate_ reads BibTeX_ files using a small number of regular expressions so
there may be be some corner cases where it fails to extract all of the field
entries.

There are a small number of cases where bibupdate_ fails to correctly identify
papers that are listed in MathSciNet_. These failures occur for the following
reasons:

* Apostrophes: Searching for a title that contains, for example, "James's Conjecture" 
  confuses mrlookup_.
* Ambiguous spelling: Issues arise when there are multiple ways to spell a
  given author's name. This can often happen if the surname involves accents
  (such as Koenig and K\\"onig). Most of the time accents themselves are not a
  problem because the AMS is LaTeX_ aware.
* Pages numbers: electronic journals, in particular, often have strange page
  numbers (for example "Art. ID rnm032, 24"). bibupdate_ assumes that page
  numbers are always given in the format like 4--42.
* Occasionally MathReviews combines two or more closely related articles. This
  makes it difficult to search for them.

All of these problems are due to idiosyncrasies with mrlookup_ so there is not
much that we can do about them.

Installation
============

You need to have Python_ installed. In principle, this program should work on
any system that supports Python_, however, I only promise that it will work
on an up-to-date mac or Linux system. In the event that it does not install I
may not be able to help you as I will not have access to your system.

From the command line type::

      pip install bibupdate

Instead of pip, you should also be able to use easy_install. The program should
run on python 2.7 and 2.8...I haven't tried python3. You can also clone or
download_ the git repository and work directly with the source.

Support
=======

This program is being made available primarily on the basis that it might be
useful to others. I wrote the program in my spare time and I will support it in
my spare time, to the extent that I will fix what I consider to be serious
problems and I may implement feature requests. 

To do
=====

- More intelligent searches using MathSciNet_.
- Add lookups using MRef and, when an entry is not found, allow additional
  searches
- Add an rc file?
- Fix the wrapping of bibtex fields.
- Interface to the arXiv_? In principle, this is easy to do although,
  ultimately, it would probably not work because the arXiv_ blocks frequent
  requests from the same IP address in order to discourage robots.

Author
======

`Andrew Mathas`_

bibupdate_ Version {__version__}. Copyright (C) 2012,14 

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
.. _bibupdate: {__url__}
.. _download: http://bitbucket.org/AndrewsBucket/bibupdate/downloads/
.. _GPL: http://www.gnu.org/licenses/gpl.html
.. _hyperref: http://www.ctan.org/pkg/hyperref
.. _LaTeX: http://en.wikipedia.org/wiki/LaTeX
.. _MathSciNet: http://www.ams.org/mathscinet/
.. _mrlookup: http://www.ams.org/mrlookup
.. _Python: https://www.python.org/
'''
