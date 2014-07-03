#!/usr/bin/env python

r"""
#*****************************************************************************
#       Copyright (C) 2012 Andrew Mathas andrew.mathas@sydney.edu.au
#
#  Distributed under the terms of the GNU General Public License (GPL)
#                  http://www.gnu.org/licenses/
#*****************************************************************************

    Usage: updata_bib <bibtex file>

    This script tries to use mrlookup to update all of the entries in a bibtex
    file except for the cite key which remains unchanged. Rather than
    overwriting the bibtex a new file is created, called updated+filename. The user
    is advised to check it carefully for any errors in he new file!

    On the entries in the bibtex file which do not already have an mrnumber field
    are checked.

    Although some care is taken to make sure that the new bibtex entries are
    correct given the fuzzy nature of the search strings passed to mrlookup, and
    possible errors in the existing bibtex file, there are no guarantees so you
    are advised to check the updated file carefully!

    Andrew Mathas


TODO:
    - find the best match when mrlookup returns multiple entries!
    - copy the original file to *.bak and put the updated file in its place.
    - add a feature to CHECK the current entries for correctness
    - better output to summarise changes

"""

import urllib, re, sys, os
from collections import OrderedDict
from fuzzywuzzy import fuzz
from optparse import OptionParser

# possible types of entries in a bibtex database
bibtex_pub_types=['article', 'book', 'booklet', 'conference', 'inbook', 'incollection', 'inproceedings', 'manual',
                  'mastersthesis', 'misc', 'phdthesis', 'proceedings', 'techreport', 'unpublished']

def font_replace(string):
    r"""
    Return a new version of `string` with various fonts commands replaced with 
    their more standard LaTeX variants.

    Currently::

        - \scr --> \mathscr
        - \germ -> \mathfrak

    This is not perfect because `\germ O` should be replaced with `\mathfrak{O}`
    and `\germ g\germ l` should be replaced with `\mathfrak{gl}`.
    """
    fonts={r'\scr':r'\mathcal', r'\germ': r'\mathfrak'}
    for word in fonts:
        string=string.replace(word, fonts[word])
    return string

def print_to_user(comment):
    r"""
    Print the string `comment' to stdout so that the user knows what is happening.
    """
    print>>sys.stdout, comment

# regular expression for cleaning TeX from title etc
tex_clean=re.compile(r'[{}\'"_$]')

def bad_match(one,two):
    r"""
    Returns True or False depending on whether or not the strings one and two
    are a good (fuzzy) match for each other. First we strip out some latex
    characters.
    """
    return fuzz.ratio(tex_clean.sub('',one).lower(), tex_clean.sub('',two).lower())<90

class Bibtex(OrderedDict):
    r"""
    The bibtex class holds all of the data for one bibtex entry. As the bibtex
    file is a flat text file, to extract the data from it we use a collection of
    regular expressions which pull out the data key by key.

    The class is called with a string which is known to hold a bibtex entry and
    the class automatically extracts and stores this information. The class also
    has an mr_update() attribute which, when called, will attempt to find this
    paper in MathSciNet using mrlookup. If it is successful then it will
    overwrite all of the existing bibtex field, except for the cite key, with
    the entries it retrieves from MathSciNet (any entries not in MathSciNet will
    remain).

    Most of he hard work is done by a cunning use of regular expressions to
    extract the data from the bibtex file and from mrlookup...perhaps we should 
    be using pyquery or beautiful soup for the latter, but this regular
    expressions are certainly effective.
    """
    # regular expression to extract a bibtex entry from a string
    parse_bibtex_entry=re.compile(r"(?P<pub_type>@\w*)\s*\{\s*(?P<cite_key>\S*)\s*,\s*?(?P<keys_and_vals>.*\})[,\s]*\}", re.MULTILINE|re.DOTALL)

    # regular expression to extract pairs of keys and values from a bibtex string
    bibtex_keys=re.compile('(\w*)\s*=\s*(\{[^=]*\},?$)', re.MULTILINE | re.DOTALL )

    # regular expression for extracting page numbers
    page_nums=re.compile('(?P<apage>[0-9]*)-+(?P<zpage>[0-9]*)')

    # regular expression for extracting first author.
    # We match either "First Last" or "Last, First"
    author=re.compile(r'(([A-Z][A-Za-z\.]* )*(?P<au>\w*))|(?P<Au>\w*,)',re.DOTALL)

    # only_match_one will find a match if the mrlookup page contains a single match
    only_one_match=re.compile('Retrieved all documents')

    # regular expression to find the bibtex entry on the mrlookup page
    mrlookup_page=re.compile(r"<pre>.*(?P<mr>@.*\})<\/pre>", re.DOTALL)

    """
    A class which contains all of the information in a bibtex entry for a paper.
    It is called with a string <bib_string> that contains a bibtex entry and it returns
    essentially a dictionary with whistles for the bibtex entry.
    """
    def __init__(self, bib_string):
        """
        Given a string <bib_string> that contains a bibtex entry return the corresponding Bibtex class.

        EXAMPLE:
        """
        super(Bibtex, self).__init__()   # initialise as an OrderedDict
        entry=self.parse_bibtex_entry.search(bib_string)
        if entry is None:
            #print_to_user( 'PARSE ERROR: %s'%(bib_string) )
            self.bib_string=bib_string
        else:
            self.pub_type=entry.group('pub_type').strip().lower()
            if self.pub_type[0]=='@': self.pub_type=self.pub_type[1:]
            self.cite_key=entry.group('cite_key').strip()
            for (key,val) in self.bibtex_keys.findall(entry.group('keys_and_vals')):
                # move trailing commas, braces and extra white space from val
                val=val.strip(', ')
                if val[0] =='{': val=val[1:]
                if val[-1]=='}': val=val[:-1]
                val=' '.join(val.strip(',').split())
                if options.replace_fonts:
                    self[key.lower()]=font_replace(val)
                else:
                    self[key.lower()]=val

    def str(self):
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

    def mr_update(self):
        """
        Uses mrlookup to search for a more up-to-date version of this entry. If
        we find one then we update ourself and overwrite all fields with those
        from mrlookup (and keep any other fields).

        To search with mrlookup we look for papers published by the first author in the
        given year with the right page numbers.
        """

        # only check mathscinet for books or articles for which we don't already have it
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
            authors=''
            aulist=re.sub(' and ','&',self['author'])
            aulist=re.sub(r'[\\\'\"{}^]','', aulist)
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
            search['ti']=self['title'].lower()

        # now we query mrlookup with our search string
        try:
            lookup = urllib.urlopen('http://www.ams.org/mrlookup', urllib.urlencode(search))
            page=lookup.read()
            lookup.close()   # close the url feed
        except IOError:
            print "%s: unable to connect to mrlookup" % (options.prog)
            sys.exit(2)

        if self.only_one_match.search(page):
            # only found one matching entry in MathSciNet
            mr_entry = self.mrlookup_page.search(page)
            if not mr_entry is None:
                # We extract the updated entry and use it to update all fields
                new_self=Bibtex(mr_entry.group('mr'))
                differences=[key for key in new_self if key not in options.ignored_fields and self[key]<>new_self[key]]
                if differences!=[] and any(self[key]!='' for k in differences):
                    if options.warn:
                        print_to_user( '-Found updated entry for %s' % self.cite_key )
                        # warn reader of bad title match
                        if bad_match(self['title'],new_self['title']):
                            print_to_user('*Bad title match %s!\n  %s  <-->  %s' % (self.cite_key, self['title'], new_self['title']) )

                    if options.verbose:
                        print '\n'.join('  %s: %s\n %s-> %s'%(key,self[key], ' '*len(key),
                                        new_self[key]) for key in differences if self[key]!='')

                    for key in differences:
                        self[key]=new_self[key]
        else:
            if options.verbose and not preprint:
                print_to_user('%sMissed %s: %s'%(' ' if preprint else '!',
                       self.cite_key, self['title'][:40] if self.has_key('title') else '???'))

def main():
    global options

    # fields from mathscinet that we want to ignore
    prog=os.path.basename(sys.argv[0])
    usage='Usage: %s filename' % prog
    parser = OptionParser(usage=usage)
    parser.add_option('-a','--all',action='store_true',dest='check_all',
                      help='check ALL BibTeX entries against mrlookup')
    parser.add_option('-f','--font',dest='replace_fonts',action='store_false',
                      help='do not replace fonts \germ and \scr')
    parser.add_option('-i','--ignore',dest='ignore',
                      default='coden mrreviewer fjournal issn',
                      help='a string of bibtex fields to ignore when printing')
    parser.add_option('-n','--no_warnings',action='store_true', dest='warn',
                      help='do not print warnings when replacing bibtex entries')
    parser.add_option('-q','--quiet',action='store_false', dest='verbose')
    parser.add_option('-v','--version',action='store_true', dest='version')
    parser.set_defaults(check_all=False,
                        replace_fonts=True,
                        verbose=True,
                        version=False,
                        warn=True,
                       )
    (options, args) = parser.parse_args()
    # if no filename then exit
    if options.version:
        import pkg_resources  # part of setuptools
        print_to_user('bibupdate Version %s' % pkg_resources.require("bibupdate")[0].version)
        sys.exit()
    elif len(args)!=1:
        print usage
        sys.exit(1)
    # parse the options
    options.prog=prog
    options.ignored_fields=[field for field in options.ignore.split()]

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

    # define a regular expression for extracting papers from BibTeX file
    bibtex_entry=re.compile('(@[^@]*})\s*',re.DOTALL)

    for bibentry in bibtex_entry.finditer(papers):
        if not bibentry is None:
            bt=Bibtex(bibentry.group())
            if hasattr(bt, 'pub_type'):
                if bt.pub_type in bibtex_pub_types:
                    bt.mr_update()
                else:
                    print_to_user( 'Unknown pub_type %s for %s'%(bt.pub_type, bt_cite_key) )


            # now save the new improved entry
            newbibfile.write(bt.str()+'\n\n')

    newbibfile.close()

##############################################################################
if __name__ == '__main__':
  main()
