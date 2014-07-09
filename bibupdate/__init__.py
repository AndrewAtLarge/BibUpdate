#!/usr/bin/env python

r"""
#*****************************************************************************
#    bibupdate - a script for updating a bibtex database file using mrlookup
#    Copyright (C) 2012-14 Andrew Mathas andrew.mathas@sydney.edu.au
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#*****************************************************************************

    Usage: bibupdate [options] <bibtex file>

    This script uses mrlookup to try and update the entries in a bibtex file. If
    the paper if found using mrlookup, or mathscient, then the script overwrites
    all of the fields from mrlookup, except for the citation key, retaining any
    other existing fields. Rather than overwriting the bibtex a new file is
    created, called updated_+filename. The user is advised to check the new
    database file carefully for any errors because, even though it is unlikely
    it is potentially for bibupdate to replace a given bibtex entry with the
    details of a completely different paper.

    By default, only the entries in the bibtex file that do not already have an
    mrnumber field are checked.

    Although some care is taken to make sure that the new bibtex entries are
    correct given the fuzzy nature of the search strings passed to mrlookup, and
    possible errors in the existing bibtex file, there are no guarantees so you
    are advised to check the updated file carefully!

    Andrew Mathas
"""

import urllib, re, sys, os
from collections import OrderedDict
from fuzzywuzzy import fuzz
from optparse import OptionParser, SUPPRESS_HELP

# define a regular expression for extracting papers from BibTeX file
bibtex_entry=re.compile('(@\s*[A-Za-z]*\s*{[^@]*})\s*',re.DOTALL)

# regular expression for cleaning TeX from title etc
remove_tex=re.compile(r'[{}"_$]+')
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

def print_to_user(comment):
    r"""
    Print the string `comment' to stdout so that the user knows what is happening.
    """
    sys.stdout.write(comment+'\n')

def good_match(one,two):
    r"""
    Returns True or False depending on whether or not the strings one and two
    are a good (fuzzy) match for each other. First we strip out some latex
    characters.
    """
    return fuzz.ratio(remove_tex.sub('',one).lower(), remove_tex.sub('',two).lower())>90

class Bibtex(OrderedDict):
    r"""
    The bibtex class holds all of the data for one bibtex entry for a paper.  It
    is called with a string <bib_string> that contains a bibtex entry and it
    returns essentially a dictionary with whistles for the bibtex entry.

    The class is called with a string which is known to hold a bibtex entry and
    the class automatically extracts and stores this information.  As the bibtex
    file is a flat text file, to extract the data from it we use a collection of
    regular expressions which pull out the data key by key.

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
    parse_bibtex_entry=re.compile(r"@(?P<pub_type>[A-Za-z]*)\s*\{\s*(?P<cite_key>\S*)\s*,\s*?(?P<keys_and_vals>.*\})[,\s]*\}", re.MULTILINE|re.DOTALL)

    # Regular expression to extract pairs of keys and values from a bibtex string. THe
    # syntax here is very lax: we assume that bibtex fields do not contain the string '=\s+{'.
    # From the AMS the format of a bibtex entry is much more rigid but we cannot
    # assume that an arbitrary bibtex file will respect the AMS conventions.
    bibtex_keys=re.compile('(\w+)\s*=\s*\{([^=(?!\s+\{)]+)\},?$', re.MULTILINE | re.DOTALL )

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
            #print_to_user( 'PARSE ERROR: %s'%(bib_string) )
            self.cite_key=None
            self.bib_string=bib_string
        else:
            self.pub_type=entry.group('pub_type').strip().lower()
            self.cite_key=entry.group('cite_key').strip()
            for (key,val) in self.bibtex_keys.findall(entry.group('keys_and_vals')):
                val=' '.join(val.split()) # remove any internal space from val
                self[key.lower()]=massage_fonts(val)

    def str(self):
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
        Call `url` to search for the bibtex entry as specified by the dictionary `search` 
        and then update `self` if there is a unique good match.

        The url can (currently) point to mrlookup or to mathscinet.
        """
        # query url with the search string
        try:
            debugging('S %s\n%s' % (url, '\n'.join('S %s=%s'%(s[0],s[1]) for s in search.items())))
            lookup = urllib.urlopen(url, urllib.urlencode(search))
            page=lookup.read()
            lookup.close()   # close the url feed
        except IOError:
            print_to_user('%s: unable to connect to %s' % (options.prog, url))
            sys.exit(2)

        # attempt to match self with the bibtex entries returned by mrlookup
        matches=[Bibtex(mr.groups(0)[0]) for mr in bibtex_entry.finditer(page)]
        matches=[mr for mr in matches if mr is not None and mr.has_valid_pub_type()]
        clean_ti=clean_title(self['title'])
        debugging('MR ti=%s.%s' % (clean_ti, ''.join('\nMR -->%s.'%clean_title(mr['title']) for mr in matches)))
        print ''.join('%s\n'%mr.str() for mr in matches)
        if clean_ti<>'':
            matches=[mr for mr in matches if good_match(clean_ti, clean_title(mr['title']))]
        debugging('MR #matches=%d'%len(matches))

        if len(matches)==1:
            match=matches[0]
            differences=[key for key in match if key not in options.ignored_fields and self[key]<>match[key]]
            if differences!=[] and any(self[key]!='' for k in differences):
                warning( '+ %s: updating %s' % (self.cite_key, ' '.join(differences)))
                verbose('\n'.join('+ %s: %s\n %s-> %s'%(key,self[key], ' '*len(key),
                                    match[key]) for key in differences if self[key]!=''))
                for key in differences:
                    self[key]=match[key]
            else:
                debugging('No changes')

        else:  # no good match, or good match not unique
            if not preprint:
                verbose('?%s %s=%s'%(' ' if preprint else '!', self.cite_key, 
                                         self['title'][:40] if self.has_key('title') else '???'))

    def mrlookup(self):
        """
        Use mrlookup to search for a more up-to-date version of this entry. If
        we find one then we update ourself and overwrite all fields with those
        from mrlookup (and keep any other fields).

        To search with mrlookup we look for papers published by the first author in the
        given year with the right page numbers.
        """
        debugging('='*30)
        # only check mathscinet for books or articles for which we don't already have an mrnumber field
        if not options.check_all and (self.has_key('mrnumber')
           or self.pub_type not in ['book','article','inproceedings','incollection']):
            return

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
            # mrlookup is latex aware and it does a far better job of parsing authors than we ever will,
            # however, it only recognises authors in the form: Last Name [, First initial]
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
            search['ti']=clean_title(self['title'].lower())

        self.update_entry('http://www.ams.org/mrlookup', search, preprint)

    def mathscinet(self):
        """
        Use MathSciNet to check/update the entry using the mrnumber field, if it
        exsists.
        """
        if hasattr(self,'mrnumber'):
            search={'fmt': 'bibtex', 'pg1': 'MR', 's1': self['mrnumber']}
            match=self.update_entry('http://www.ams.org/mathscinet/search/publications.html', search, False)

def main():
    # set and parse the options to bibupdate
    global options, verbose, warning, debugging, massage_fonts

    prog=os.path.basename(sys.argv[0])
    usage='Usage: %s [options] <bibtex file>' % prog
    parser = OptionParser(usage=usage)
    parser.add_option('-a','--all',action='store_true',dest='check_all',default=False,
                      help='Check ALL BibTeX entries against mrlookup')
    parser.add_option('-f','--font_replace',dest='font_replace',action='store_false',
                      help='Do NOT replace fonts \Bbb, \germ and \scr', default=True)
    parser.add_option('-i','--ignore',dest='ignore',type='string',default='coden mrreviewer fjournal issn',
                      help='A string of bibtex fields to ignore when printing')
    parser.add_option('-m','--mrlookup',dest='mrlookup',default=True,action='store_true',
                      help='Use mrlookup to update bibtex entries (default)')
    parser.add_option('-M','--mathscinet',dest='lookup',action='store_false',
                      help='Use mathscinet to update bibtex entries (less powerful)')
    parser.add_option('-w','--warnings',action='store_true',dest='warn',default=False,
                      help='Only print warnings when replacing bibtex entries')
    parser.add_option('-q','--quiet',action='store_true', dest='quiet', default=False,
                      help='Only print error messages')
    parser.add_option('-V','--verbose',dest='verbose',default=True,action='store_true',
                      help='Describe all new fields added to bibtex entries')
    parser.add_option('-v','--version',action='store_true', dest='version', default=False,
                      help='Print version number and exit')
    parser.add_option('-d','--debug',action='store_true', dest='debug', default=False,
                      help=SUPPRESS_HELP)
    (options, args) = parser.parse_args()
    if options.version:
        import pkg_resources  # part of setuptools
        print_to_user('bibupdate: update entries in a bibtex database using mrlookup')
        print_to_user('Version %s. Available under GPL 3' % pkg_resources.require("bibupdate")[0].version)
        sys.exit()
    elif len(args)!=1:
        # if no filename then print usage and exit
        print usage
        sys.exit(1)

    # parse the options
    options.prog=prog
    options.ignored_fields=[field for field in options.ignore.split()]
    # set verbose, warn and quiet correctly
    if options.warn:
        options.verbose=False
        if options.quiet:
            print_to_user('%s\nThe options --quiet and --warn are mutually exclusive' % usage)
            sys.exit(1)
    if options.quiet:
        options.verbose=False
        options.warn=False
    if options.verbose:
        options.warn=True

    # shortcut functions so that we don't need to continually check these options
    verbose=print_to_user if options.verbose else lambda *arg, **kw_arg: None
    warning=print_to_user if options.warn else lambda *arg, **kw_arg: None
    debugging=print_to_user if options.debug else lambda *arg, **kw_arg: None
    massage_fonts=font_replace if options.font_replace else lambda ti: ti

    # open the existing BibTeX file
    try:
        bibfile=open(args[0],'r')
        papers=bibfile.read()
        bibfile.close()
    except IOError,e:
        print "%s: unable to open bibtex file %s" % (prog, args[0])
        sys.exit(2)

    # open the replacement BibTeX file
    try:
        newbibfile=open('updated_'+args[0],'w')
    except IOError,e:
        print "%s: unable to open new bibtex file new%s" % (prog, args[0])
        sys.exit(2)

    asterisk=papers.index('@')
    newbibfile.write(papers['asterisk']) # copy everything up to the first @
    for bibentry in bibtex_entry.finditer(papers[asterisk:]):
        if not bibentry is None:
            bt=Bibtex(bibentry.group())
            if bt.has_valid_pub_type():
                getattr(bt, options.lookup)()  # call lookup program`
            else:
                verbose('Unknown pub_type %s for %s' % (bt.pub_type, bt.cite_key))

        # now save the new (and hopefully) improved entry
        newbibfile.write(bt.str()+'\n\n')

    newbibfile.close()

##############################################################################
if __name__ == '__main__':
  main()
