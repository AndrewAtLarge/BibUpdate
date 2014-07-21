#!/usr/bin/env python

r"""
==============================================
bibupdate - a script for updating bibtex files
==============================================

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

Andrew Mathas andrew.mathas@sydney.edu.au
Copyright (C) 2012-14 
"""

# Version and license information
__version__=1.1
__license__='GNU General Public License, Version 3, 29 June 2007'
bibupdate_version=r'''
%(prog)s version {version}: update entries in a bibtex file
{license}
'''.format(version=__version__, license=__license__)

######################################################
import argparse, re, sys, urllib
from collections import OrderedDict
from fuzzywuzzy import fuzz
from itertools import chain
from os.path import dirname, basename

# global options, used mainly for printing
global options, verbose, warning, debugging, massage_fonts

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

# exit gracefully after control-C
OriginalExceptHook = sys.excepthook
def NewExceptHook(type, value, traceback):
    r"""
    Exit cleanly when program is killed.
    """
    if type == KeyboardInterrupt:
        bib_error('program killed. Exiting...')
    else:
        OriginalExceptHook(type, value, traceback)

# ...and a hook to grab the exception
sys.excepthook = NewExceptHook

##########################################################

# define a regular expression for extracting papers from BibTeX file
bibtex_entry=re.compile('(@\s*[A-Za-z]*\s*{[^@]*})\s*',re.DOTALL)

# regular expression for cleaning TeX from title etc
remove_tex=re.compile(r'[{}\'"_$]+')
remove_mathematics=re.compile(r'\$[^\$]+\$')  # assume no nesting
# savagely remove all maths from title
clean_title=lambda title: remove_tex.sub('',remove_mathematics.sub('',title))

# to help in checking syntax define recognised/valid types of entries in a bibtex database
bibtex_pub_types=['article', 'book', 'booklet', 'conference', 'inbook', 'incollection', 'inproceedings', 'manual',
                  'mastersthesis', 'misc', 'phdthesis', 'proceedings', 'techreport', 'unpublished']

# need to massage some of the font specifications returned by mrlookup to "standard" latex fonts.
replace_fonts=[ ('mathbb', re.compile(r'\\Bbb (\w)'), re.compile(r'\\Bbb\s*({\w*})')),
                ('mathscr', re.compile(r'\\scr (\w)'), re.compile(r'\\scr\s*({\w*})')),
                ('mathfrak', re.compile(r'\\germ (\w)'), re.compile(r'\\germ\s*{(\w*)}'))
]
def font_replace(string):
    r"""
    Return a new version of `string` with various fonts commands replaced with
    their more standard LaTeX variants.

    Currently::

        - \Bbb X*  --> \mathbb{X*}
        - \scr X*  --> \mathscr{X*}
        - \germ X* --> \mathfrak{X*}
    """
    new_string=''
    last=0
    for rep in replace_fonts:
        string=rep[1].sub(r'\\%s{\1}'%rep[0], string)   # eg. \Bbb C    --> \mathbb{C}
        string=rep[2].sub(r'\\%s{\1}'%rep[0], string)   # eg. \germ{sl} --> \mthfrak{sl}
    return string

def good_match(one,two):
    r"""
    Returns True or False depending on whether or not the strings one and two
    are a good (fuzzy) match for each other. First we strip out some latex
    characters.
    """
    return fuzz.ratio(remove_tex.sub('',one).lower(), remove_tex.sub('',two).lower())>90

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
    # Regular expression to extract a bibtex entry from a string. We assume that
    # the pub_type is a word in [A-Za-z]* an allow the citation key and the
    # contents of the bibtex entry to be fairly arbitrary and of the form: {cite_key, *}.
    parse_bibtex_entry=re.compile(r'@(?P<pub_type>[A-Za-z]*)\s*\{\s*(?P<cite_key>\S*)\s*,\s*?(?P<keys_and_vals>.*\})[,\s]*\}', re.MULTILINE|re.DOTALL)

    # To extract the keys and values we need to remove all spaces around equals
    # signs because otherwise we are unable to cope with = inside a bibtex field.
    keys_and_vals=re.compile(r'\s*=\s*')

    # Regular expression to extract pairs of keys and values from a bibtex
    # string. The syntax here is very lax: we assume that bibtex fields do not
    # contain the string '={'.  From the AMS the format of a bibtex entry is
    # much more rigid but we cannot assume that an arbitrary bibtex file will
    # respect the AMS conventions.  There is a small complication in that we
    # allow the value of each field to either be enclosed in braces or to be a
    # single word.
    bibtex_keys=re.compile(r'([A-Za-z]+)=(?:\{((?:[^=]|=(?!\{))+)\}|(\w+)),?$', re.MULTILINE|re.DOTALL)

    # Regular expression for extracting page numbers: <first page>-*<last page>
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
                if val=='': val=word      # val matches {value} whereas word matches word
                val=' '.join(val.split()) # remove any internal space from val
                lkey=key.lower()          # keys always in lower case
                if lkey=='title':
                    self[lkey]=massage_fonts(val)
                else:
                    self[lkey]=val

    def __str__(self):
        r"""
        Return a string for printing the bibtex entry.
        """
        if hasattr(self,'pub_type'):
            return '@%s{%s,\n  %s\n}' % (self.pub_type.upper(), self.cite_key, ',\n  '.join('%s = {%s}'%(key,self[key])
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

    def update_entry(self, url, search, preprint):
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
                    bib_print('%s\nV %s=%s\n%s' % ('='*30, self.cite_key, self['title'][:50],
                                  '\n'.join('V %s: %s\nV%s-> %s'%(key,self[key], ' '*len(key), match[key]) 
                                        for key in differences if self[key]!='')))
                else:
                    warning('%s\n+ Updating %s=%s' % ('+'*30, self.cite_key, self['title'][:50]))
                    verbose('\n'.join('+ %s: %s\n+%s-> %s'%(key,self[key], ' '*len(key),
                                        match[key]) for key in differences if self[key]!=''))
                    for key in differences:
                        self[key]=match[key]
            else:
                debugging('No change')

        else:  # no good match, or more than one good match
            if not preprint:
                verbose("%s\n%s Didn't find %s=%s"%('-'*30, '!' if preprint else '!', self.cite_key, 
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

        # try to guess whether this entry corresponds to a preprint
        preprint=( (self.has_key('pages') and self['pages'].lower() in ['preprint', 'to appear', 'in preparation'])
                  or not (self.has_key('pages') and self.has_key('journal')) )

        if self.has_key('pages') and not preprint:
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

        if self.has_key('title') and len(self['title'])>0 and (not search.has_key('ipage') or preprint):
            search['ti']=clean_title(self['title'])

        self.update_entry('http://www.ams.org/mrlookup', search, preprint)

    def mathscinet(self):
        """
        Use MathSciNet to check/update the entry using the mrnumber field, if it
        exsists.
        """
        if options.all or self.has_key('mrnumber'):
            search={'fmt': 'bibtex', 'pg1': 'MR', 's1': self['mrnumber'].split()[0]}
            self.update_entry('http://www.ams.org/mathscinet/search/publications.html', search, False)

def process_options():
    r"""
    Set up and then parse the options to bibupdate using argparse.
    """
    global options, verbose, warning, debugging, massage_fonts

    parser = argparse.ArgumentParser(description='Update and validate BibTeX files',
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('bibtexfile',type=argparse.FileType('r'),help='bibtex file to update')
    parser.add_argument('outputfile',nargs='?',type=argparse.FileType('w'),help='output file')

    parser.add_argument('-a','--all',action='store_true',default=False,
                        help='update or validate ALL BibTeX entries')
    parser.add_argument('-c','--check-all',action='store_true', default=False,
                        help='check all bibtex entries against a database')
    parser.add_argument('-f','--font_replace',action='store_false', default=False,
                        help='do NOT replace fonts \Bbb, \germ and \scr')
    parser.add_argument('-i','--ignored-fields',type=str,default=['coden','mrreviewer','fjournal','issn'],
                        action='append',help='a string of bibtex fields to ignore')
    parser.add_argument('-l','--log', default=sys.stdout, type=argparse.FileType('w'),
                        help='log output to file (defaults to stdout)')

    # add a mutually exclusive switch for choosing between mrlookup and mathscinet
    lookup=parser.add_mutually_exclusive_group()
    lookup.add_argument('-m','--mrlookup',action='store_const',const='mrlookup',dest='lookup',
                        default='mrlookup',help='use mrlookup to update bibtex entries (default)')
    lookup.add_argument('-M','--mathscinet',action='store_const',const='mathscinet',dest='lookup',
                        help='use mathscinet to update bibtex entries (less flexible)')

    parser.add_argument('-q','--quietness',action='count', default=2,
                        help='printer fewer messages')
    parser.add_argument('-r','--replace',action='store_true', default=False,
                        help='replace existing bibtex file')

    # suppress printing of these two options
    parser.add_argument('--version',action='version', version=bibupdate_version, help=argparse.SUPPRESS)
    parser.add_argument('-d','--debugging',action='store_true', default=False, help=argparse.SUPPRESS)

    # parse the options
    options = parser.parse_args()
    options.prog=parser.prog
    if len(options.ignored_fields)>4:
        # if any fields were added then don't ignore the first 4 fields.
        options.ignored_fields=list(chain.from_iterable([i.lower().split() for i in options.ignored_fields[4:]]))

    # if check_all==True then we want to check everything
    if options.check_all:
        options.all=True

    # define debugging, verbose and warning functions
    if options.debugging:
        options.quietness=2
        debugging=bib_print
    else:
        debugging=lambda *arg: None
    verbose=bib_print if options.quietness==2 else lambda *arg: None
    warning=bib_print if options.quietness>=1 else lambda *arg: None

    # a shortcut function for replacing fonts
    massage_fonts=font_replace if options.font_replace else lambda ti: ti

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
    except IOError,e:
        bib_error('unable to open bibtex file %s' % options.bibtexfile.name)

    # if we are checking for errors then we check EVERYTHING but, in this case,
    # we don't need to create a new bibtex file
    if options.check_all:
        options.check_all=True
    else:
        if options.replace:
            # copy original file to filename+'.bak' and write updates to filename
            try:
                shutil.copyfile(options.filename.name,options.filename.name+'.bak')
                newfile=options.filename.name
            except IOError,e:
                biberror('unable to create backup file')
        elif options.outputfile is None:
            # write updates to 'updated_'+filename
            dir=dirname(options.bibtexfile.name)
            base=basename(options.bibtexfile.name)
            newfile='updated_%s' % base if dir=='' else r'%s/updated_%s' %(dir,base)
        else:
            newfile=options.outputfile.name

        print 'Writing to %s' % newfile
        # open newfile
        try:
            newbibfile=open(newfile,'w')
        except IOError,e:
            bib_error('unable to open new bibtex file %s' % newfile)

        newbibfile.write(papers[:asterisk]) # copy everything up to the first @

    # finally we are ready to start processing the papers from the bibtex file
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
