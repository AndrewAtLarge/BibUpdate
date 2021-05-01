#!/usr/bin/env python

r'''
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

See https://github.com/AndrewAtLarge/BibUpdate for more details
about the bibupdate program.

Andrew Mathas andrew.mathas@gmail.com
Copyright (C) 2012-2021
'''

######################################################
import itertools
import os
import re
import shutil
import sys
import textwrap
import urllib

##########################################################
# Define bibupdate's meta data. Used for global variables, to generate the
# doc-string and README files and in setup.py
class Settings(dict):
    r"""
    A dummy class for hiding meta data and global variables.
    """
    def __init__(self, ini_file):
        super(Settings, self).__init__(self)
        with open(ini_file) as ini:
            for line in ini:
                key, val = [w.strip() for w in line.split('=')]
                if key != '':
                    setattr(self, key.lower().strip(), val.strip())


# The following meta data will be used to generate the __doc__ string below and
# it is used in setup.py.
file = lambda f: os.path.join(os.path.dirname(__file__), f)
bibup=Settings( file('bibupdate.ini') )

# version number of command line help message
bibup.debugging=False # debugging off by default
bibup.startup_warnings=[]

##########################################################
# now try and import the non-standard modules that we use
python_version=sys.version_info[:2]


##########################################################
# We trap system errors so that we can exit cleanly when the program is
# killed and so that we can automatically tap into a debugger when debugging.
def CleanExceptHook(type, value, traceback):
    r"""
    Exit cleanly when program is killed, or jump into pdb if debugging
    """
    if type == KeyboardInterrupt:
        bib_error('program killed. Exiting...')
    elif (not bibup.debugging or hasattr(sys, 'ps1') or not sys.stdin.isatty()
            or not sys.stdout.isatty() or not sys.stderr.isatty()
            or issubclass(type, bdb.BdbQuit) or issubclass(type, SyntaxError)):
        sys.__excepthook__(type, value, traceback)
    else:
        import traceback, pdb
        # we are NOT in interactive mode, print the exception...
        traceback.print_exception(type, value, tb)
        print()
        # ...then start the debugger in post-mortem mode.
        pdb.pm()

# ...and a hook to grab the exception
sys.excepthook = CleanExceptHook

######################################################
import itertools, os, re, shutil, textwrap, urllib

# this will fail with older versions of python so we add our exception hook first
bibup.bibupdate_version='%(prog)s, version {0.version}: {0.description}\n{0.license}'.format(bibup)

##########################################################
# Try and import the (non-standard) modules that we use

# import argparse if possible and quit if we fail
try:
    import argparse
except (ImportError):
    print('bibupdate needs to have the argparse module installed')
    print('Upgrade python or use easy_install or pip and to install argparse')
    sys.exit(1)

# From python 2.7 onwards OrderedDict is in the standard collections library
try:
    from collections import OrderedDict
except(ImportError):
    try:
        # in python 2.6 OrderedDict is in ordereddict
        from  ordereddict import OrderedDict
    except(ImportError):
        # if we can't load Ordered revert to using dict
        print('bibupdate prefers to use the ordered ordered dictionaries')
        print('Upgrade python or use easy_install or pip and to install ordereddict')
        OrderedDict=dict

# finally, try to import and use fuzzywuzzy.fuzz
try:
    from fuzzywuzzy import fuzz
    def good_match(one,two):
        r"""
        Returns True or False depending on whether or not the lower cased strings
        `one` and `two` are a good (fuzzy) match for each other.
        """
        return fuzz.ratio(one.lower(), two.lower())>90
except(ImportError):
    print('# bibupdate prefers to use fuzzy matching to check the titles for any matches but')
    print('# this requires the fuzzywuzzy package, which is not installed on your system')
    print('# For more accurate matching use easy_install/pip to install fuzzywuzzy')
    def good_match(one,two):
        r"""
        Strict matching of `one` and `two`, up to case.
        """
        return one.lower()==two.lower()

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

##########################################################

# define a regular expression for extracting papers from BibTeX file
bibtex_entry=re.compile('(@\s*[A-Za-z]*\s*{[^@]*})\s*',re.DOTALL)

# regular expression for cleaning TeX from title etc
remove_tex=re.compile(r'[{}\'"_$]+')
remove_mathematics=re.compile(r'\$[^\$]+\$')  # assume no nesting

# savagely remove all maths from titles
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

# overkill for "type checking" of the wrap length command line option
class NonnegativeIntegers(list):
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

# most of the work is hidden in this class
class Bibtex(OrderedDict):
    r"""
    The bibtex class holds all of the data for a bibtex entry of a manuscript.
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
    parse_bibtex_entry=re.compile(r'@(?P<pub_type>[A-Za-z]*)\s*\{\s*(?P<cite_key>\S*)\s*,\s*?(?P<keys_and_vals>.*)[,\s]*\}',
                                  re.MULTILINE|re.DOTALL)

    # To extract the keys and values we need to remove all spaces around equals
    # signs because otherwise we are unable to cope with = inside a bibtex field.
    despace_equals=re.compile(r'\s*=\s*')

    # A regular expression to extract pairs of keys and values from a bibtex
    # string. The syntax here is very generous: we assume that bibtex fields do not
    # contain the string '={'. The format of a bibtex entry returned by the AMS
    # is much more rigid but we cannot assume that an arbitrary bibtex file will
    # respect the AMS conventions.  There is a small complication in that we
    # allow the value of each field to either be enclosed in braces or to be a
    # single word. For this reason matches to the follow regular expression
    # return triples of the form (key, value, word) corresponding to
    #                 key={value}    OR      key=word
    # In particular, either value=='' or word=''.
    keys_and_vals=re.compile(r'([A-Za-z]+)=(?:\{((?:[^=]|=(?!\{))+)\}|(\w+))', re.MULTILINE|re.DOTALL)

    # A regular expression for extracting page numbers: <first page>-*<last page>
    # or simply <page>.
    page_nums=re.compile('(?P<apage>[0-9]*)-+(?P<zpage>[0-9]*)')

    # For authors we match either "First Last" or "Last, First" with the
    # existence of the comma being the crucial test because we want to allow
    # compound surnames like De Morgan.
    author=re.compile(r'\s+(?P<Au>[\w\s\\\-\'"{}]+),\s[A-Z]|[\w\s\\\-\'"{}]+\s(?P<au>[\w\s\\\-\'"{}]+)',re.DOTALL)

    def __init__(self, bib_string):
        """
        Given a string <bib_string> that contains a bibtex entry return the corresponding Bibtex class.

        EXAMPLES::

        >>> Bibtex.parse_bibtex_entry.search('@article{fred, author={fred}, year={2014}}').groups()
        ('article', 'fred', ' author={fred}, year={2014}')
        >>> Bibtex.parse_bibtex_entry.search('@article{fred, author={fred}, year=2014}').groups()
        ('article', 'fred', ' author={fred}, year=2014')
        >>> Bibtex.bibtex_keys.findall(' author={fred}, year=2014')
        [('author', 'fred', ''), ('year', '', '2014')]
        """
        super(Bibtex, self).__init__()   # initialise as an OrderedDict
        entry=self.parse_bibtex_entry.search(bib_string)
        if entry is None:
            self.cite_key=None
            self.bib_string=bib_string
        else:
            self.pub_type=entry.group('pub_type').strip().lower()
            self.cite_key=entry.group('cite_key').strip()
            keys_and_vals=self.despace_equals.sub('=',entry.group('keys_and_vals'))   # remove spaces around =
            for (key,val,word) in self.keys_and_vals.findall(keys_and_vals):
                if val=='':
                    val=word                  # val matches {value} whereas word matches word
                else:
                    val=' '.join(val.split()) # remove any internal space from val
                lkey=key.lower()              # keys always in lower case
                if lkey=='title':
                    self[lkey]=bibup.fix_fonts(val) # only fix fonts in the title, others assumed OK
                else:
                    self[lkey]=val

            # define the dictionary used for external database lookups
            self.define_search_dictionary()

    def __str__(self):
        r"""
        Return a string for printing the bibtex entry.
        """
        if hasattr(self,'pub_type'):
            return '@%s{%s,\n  %s\n}' % (self.pub_type.upper(), self.cite_key,
                    ',\n  '.join('%s = {%s}'%(key,bibup.wrapped(self[key]))
                     for key in self.keys() if key not in options.remove_fields))
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

    def define_search_dictionary(self):
        r"""
        Define a dictionary for the terms to be used in database lookups.
        This function also sets the preprint flag `self.is_preprint`.
        """
        # guess whether this entry corresponds to a preprint
        self.is_preprint=( ('pages' in self and self['pages'].lower() in ['preprint', 'to appear', 'in preparation'])
                  or not ('pages' in self and 'jounral' in self) )

        self.search={}
        if 'pages' in self and not self.is_preprint:
            pages=self.page_nums.search(self['pages'])
            if not pages is None:
                self.search['ipage']=pages.group('apage')  # first page
                self.search['fpage']=pages.group('zpage')  # last page
            elif self['pages'].isdigit():
                self.search['ipage']=self['pages']  # first page

        # the year is reliable only if we also have page numbers
        if 'year' in self and (self.pub_type=='book' or 'ipage' in self.search):
            self.search['year']=self['year']

        # mrlookup requires either an author or a title
        if 'author' in self:
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
                self.search['au']=authors[5:]

        if 'title' in self and len(self['title'])>0 and (not 'ipage' in self.search or self.is_preprint):
            self.search['ti']=clean_title(self['title'])

        # finally, set the needs_ams flag to True if this is a book or article for which we don't already have an mrnumber field
        if options.all or ('mrnumber' not in self
          and self.pub_type in ['book','article','inproceedings','incollection']):
            self.needs_ams=True
        else:
            self.needs_ams=False


    def update_entry(self, url, search):
        """
        Call `url` to search for the bibtex entry as specified by the dictionary
        `search` and then update `self` if there is a unique good match. If
        there is a good match then we update ourself and overwrite all fields
        with those from mrlookup (and keep any other fields).

        The url can (currently) point to mrlookup or to mathscinet.
        """
        # Query the url with the search string - the python 2/3 version dependency
        # is hidden in the function url_lookup()
        try:
            web_page=url_lookup(url, url_encode(search))
        except IOError:
            bib_error('unable to connect to %s' % url)

        # attempt to match self with the bibtex entries returned by mrlookup
        matches=[Bibtex(mr.groups(0)[0]) for mr in bibtex_entry.finditer(web_page)]
        matches=[mr for mr in matches if mr is not None and mr.has_valid_pub_type()]
        bibup.debug('MR number of matches=%d'%len(matches))
        bibup.debug('MR ti=%s.%s' % (self['title'], ''.join('\nMR -->%s.'%mr['title'] for mr in matches)))
        if 'ti' in self.search:
            matches=[mr for mr in matches if good_match(self.search['ti'], clean_title(mr['title']))]
        bibup.debug('MR number of clean matches=%d'%len(matches))

        if len(matches)==1:
            match=matches[0]
            differences=[key for key in match if key not in options.preserve_fields and self[key]!=match[key]]
            if differences!=[] and any(self[key]!='' for key in differences):
                if options.check:
                    bib_print('%s\n%s=%s\n%s' % ('='*30, self.cite_key, self['title'][:50],
                                  '\n'.join(' %s: %s\n%s-> %s'%(key,self[key], ' '*len(key), match[key])
                                        for key in differences)))
                else:
                    bibup.warning('%s\n+ Updating %s=%s' % ('+'*30, self.cite_key, self['title'][:50]))
                    bibup.verbose('\n'.join('+  %s: %s\n+%s->  %s'%(key,self[key], ' '*len(key),
                                        match[key]) for key in differences))
                    for key in differences:
                        self[key]=match[key]
            else:
                bibup.debug('No change')

            return True # found a match

        else:  # no good match, or more than one good match
            if not self.is_preprint:
                bibup.verbose("%s\n%s Didn't find %s=%s"%('-'*30,
                            '!' if self.is_preprint else '!', self.cite_key,
                            self['title'][:40] if 'title' in self else '???'))
            return False # didn't find a match

    def update_mrlookup(self):
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

        bibup.debug('='*30)
        search={'bibtex':'checked'}   # a dictionary that will contain the parameters for the mrlookup search

        return self.update_entry('http://www.ams.org/mrlookup', self.search)

        # the year is reliable only if we also have page numbers
        if self.has_key('year') and (self.pub_type=='book' or search.has_key('ipage')):
            search['year']=self['year']

    def update_mrref(self):
        r"""
        TODO!!!
        """
        return self.needs_ams

    def mref(self):
        """
        Use Mref to check/update the entry.
        Mref takes a free-form reference so we give it the whole entry to play with.
        """
        # only check mrlookup for books or articles for which we don't already have an mrnumber field
        if not options.all and ('mrnumber' in self or self.pub_type not in ['book','article','inproceedings','incollection']):
            return
        search = {'mref-submit' : "Search", 'dataType': 'bibtex'}
        search['ref'] = ''.join("%s\n"% self[key] for key in self.keys())

        self.update_entry('https://mathscinet.ams.org/mathscinet-mref', search)


    def update_mathscinet(self):
        """
        Use MathSciNet to check/update the entry using the mrnumber field, if it exists.
        """
        if options.all or not 'mrnumber' in self:
            search={'fmt': 'bibtex', 'pg1': 'MR', 's1': self['mrnumber'].split()[0]}
            return self.update_entry('http://www.ams.org/mathscinet/search/publications.html', search)
        else:
            return True

    # extract all entries between <entry>...</entry>
    arxiv=re.compile(r'\<entry>(.*)?\<\/entry>', re.MULTILINE|re.DOTALL)

    # extract all pairs of the form: <key>value</key>
    arxiv_keys_and_vals=re.compile(r'\<(?P<key>[A-Za-z]+)>(?P<val>.*)\<\/(?P=key)>', re.MULTILINE|re.DOTALL)

    def update_arxiv(self):
        r"""
        Use the arXiv's API to find link to the manuscript in the arXiv.

        EXAMPLES::

            >>> entry=r'''  <entry>
            <id>http://arxiv.org/abs/math/0309426v2</id>
            <updated>2004-07-01T14:37:17Z</updated>
            <published>2003-09-26T16:40:30Z</published>
            <title>Elementary divisors of Specht modules</title>
            </entry>'''
            >>> arxiv.findall(entry)[0]
            '\n        <id>http://arxiv.org/abs/math/0309426v2</id>\n        <updated>2004-07-01T14:37:17Z</updated>\n        <published>2003-09-26T16:40:30Z</published>\n        <title>Elementary divisors of Specht modules</title>\n
            >>> arxiv_keys_and_vals.findall(_)[0]
            ('id', 'http://arxiv.org/abs/math/0309426v2'), ('updated', '2004-07-01T14:37:17Z'),
            ('published', '2003-09-26T16:40:30Z'), ('title', 'Elementary divisors of Specht modules')
        """
        search={}
        if 'author' in self.search:
            search['au'] =self.search['author']
        if 'ti' in self.search:
            search['ti']=self.search['ti']
        try:
            web_page=url_lookup('http://export.arxiv.org/api/query?search_query='+url_encode(search).replace('=',':').replace('&','+AND+'))
        except IOError:
            bib_error('unable to connect to %s' % url)

        print(web_page)

        matches=[]
        for match in self.arxiv.findall(web_page):
            m={}
            for (key,val) in arxiv_keys_and_vals.findall(match):
                m[key]=val
            if good_match(self,self.search['title'],m['title']):
                matches.append(m)

        if len(matches)==1:
            arxiv=matches[0]
            bibup.verbose('+ arxiv link for {title}'.format(title=self['title']))
            self['Archiveprefix'] = 'arXiv'
            self['eprint']=arxiv['id'].split('/')[-1]     # http://arxiv.org/abs/math/0309426v2 --> 0309426v2
            if 'abstract' in arxiv and not 'abstract' in self:
                self['abstract']=arxiv['abstact']
        else:
            bibup.verbose('X {links} arxiv links for {title}'.format(links=len(matches),title=self['title']))

    def update_ams(self):
        r"""
        Loop through the list of AMS databases until we either exhaust the list
        or find a match.
        """
        db=0
        while self.needs_ams and db<len(options.ams_databases):
            self.needs_ams=getattr(self, 'update_'+options.ams_databases[db])()  # call next ams database in list
            db+=1

    def update_all(self):
        r"""
        Update both arXiv and mathscinet entries for the publication. The method
        first calls update_arxiv() to update the arXiv entry and then
        calls he sequence of methods
           update_mrlookup, update_mrref and mupdate_mathscinet
        until one of them finds a match.
        """
        bibup.debug('Updating all with needs+ams=%s'%self.needs_ams)
        self.update_arxiv()
        self.update_ams()

# parse rc file and command-line options
def set_user_options():
    r"""
    Set up and then parse the options to bibupdate using argparse.
    """
    global options, bibup

    # bibupdate defaults - can be overridden by the rc file or form the command line
    defaults={'all': False,
              'ams-databases': ['mrlookup', 'mrref', 'mathscinet'],
              'check': False,
              'keep-fonts': False,
              'log': sys.stdout,
              'overwrite': False,
              'preserve-fields': [],
              'quieter': 2,
              'remove-fields': [],
              'wrap':0,
              'update':'all'
    }
    # check for a bibupdaterc file and read if it exists
    if os.path.isfile(os.environ['HOME']+'/.bibupdaterc'):
        try:
            line_num=0 # track line numbers in case of an error
            with open(os.environ['HOME']+'/.bibupdaterc','r') as bibrc:
                for line in bibrc:
                    line_num+=1
                    line=line.split('#')[0]    # anything after "#" is a comment
                    option,value=line.strip().split('=')
                    option=option.strip().lower().replace('_','-')
                    value=value.strip().lower()
                    if not option in defaults:
                        bib_error('illegal option "{option}" on line {line} of .bibupdaterc file'.format(
                                      option=option, line=line_num))
                    elif option in ['ams-databases','preserve-fields','remove-fields']:
                        # these options set a list
                        defaults[option]=[f.strip() for f in value.split(',')]
                    elif option in ['all', 'check', 'keep-fonts','overwrite']:
                        # these options are true or false
                        defaults[option]=False if value=='false' else True
                    elif option in ['quieter','wrap']:
                        # options with integer values
                        defaults['option']=int(value)
                    elif option=='log':
                        # the log must be a writable file
                        defaults[value]=open(value,'w')
                    elif option=='update':
                        if value in ['all','arxiv','mrlookup','mref','mathscinet']:
                            defaults[option]=value
                        else:
                            bib_error('illegal update value "{value}" o line {line} of .bibupdaterc file'.format(
                                      line=line_num, value=value))
                    elif option!='':
                        defaults[option]=value

        except Exception as err:
            bib_error('error on line {line} of .bibupdaterc file'.format(line=line_num))

    # now parse the command line arguments using argparse to define the parser
    parser = argparse.ArgumentParser(description=bibup['description'],
                                     epilog=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('bibtexfile',nargs='?',type=argparse.FileType('r'),help='bibtex file to update')
    parser.add_argument('outputfile',nargs='?',type=str,default=None, help='output file (optional)')

    parser.add_argument('-u','--update',type=str, choices=('all','arxiv','ams', 'mrlookup','mref','mathscinet'),
                        default=defaults['update'], help='update mechanism (default: all)')
    parser.add_argument('-a','--all',action='store_true',default=defaults['all'],
                        help='update or check ALL BibTeX entries')
    parser.add_argument('-c','--check',action='store_true', default=defaults['check'],
                        help='check, but do not update, bibtex entries against databases')
    parser.add_argument('-k','--keep-fonts',action='store_true', default=defaults['keep-fonts'],
                        help='do NOT replace fonts \Bbb, \germ and \scr in titles')
    parser.add_argument('-l','--log', default=defaults['log'], type=argparse.FileType('w'),
                        help='log messages to specified file (defaults to stdout)')
    parser.add_argument('-o','--overwrite',action='store_true', default=defaults['overwrite'],
                        help='overwrite existing bibtex file (use carefully!)')
    parser.add_argument('-p','--preserve-fields',type=str,default=defaults['preserve-fields'],
                        metavar='FIELDS', action='append',help='do not change the values of these bibtex fields')
    parser.add_argument('-r','--remove-fields',type=str,default=defaults['remove-fields'],
                        metavar='FIELDS', action='append',help='delete these bibtex fields')
    parser.add_argument('-q','--quieter',action='count', default=defaults['quieter'],
                        help='printer fewer messages')
    parser.add_argument('-w','--wrap',type=int, default=defaults['wrap'], action='store',
                        choices=NonnegativeIntegers(), metavar='LEN',
                        help='wrap bibtex fields to specified width')

    # suppress printing of these two options
    parser.add_argument('--version',action='version', version=bibup.bibupdate_version, help=argparse.SUPPRESS)
    parser.add_argument('-d','--debugging',action='count', default=0, help=argparse.SUPPRESS)

    # parse the options
    options = parser.parse_args()
    options.prog=parser.prog

    if options.bibtexfile==None:
        bib_error('no bibtex file specified')

    if len(options.preserve_fields)>len(defaults['preserve-fields']):
        pres=len(defaults['preserve_fields'])
        # if any fields were added then don't ignore the first 4 fields.
        options.preserve_fields=list(chain.from_iterable([i.lower().split() for i in options.preserve_fields[pres:]]))

    if len(options.remove_fields)>len(defaults['remove-fields']):
        rem=len(defaults['remove_fields'])
        # if any fields were added then don't ignore the first 4 fields.
        options.remove_fields=list(chain.from_iterable([i.lower().split() for i in options.remove_fields[rem:]]))

    options.ams_databases=defaults['ams-databases'] # can only be changed in .bibupdaterc
    if options.update not in ['all','arxiv']:
        # loop through all databases in options.ams_databases, so overwrite
        # this if user wants to check a single AMS database
        if options.update!='ams':
            options.ams_databases=[options.update]

    # if check==True then we want to check everything
    if options.check:
        options.all=True

    # define word wrapping when requested
    if options.wrap!=0:
        bibup.wrapped=lambda field: '\n'.join(textwrap.wrap(field,options.wrap,subsequent_indent='\t'))
    else:
        bibup.wrapped=lambda field: field

    # define debugging, verbose and warning functions
    if options.debugging>0:
        options.quieter=2
        bibup.debugging=True
        bibup.debug=bib_print
        if options.debugging==4:
            # start pudb
            import pudb
            pu.db
    else:
        bibup.debug=lambda *arg: None
    bibup.verbose=bib_print if options.quieter==2 else lambda *arg: None
    bibup.warning=bib_print if options.quieter>=1 else lambda *arg: None

    # a shorthand for fixed the fonts (to avoid an if-statement when calling it)
    bibup.fix_fonts=replace_fonts if not options.keep_fonts else lambda title: title

def main():
    r"""
    Open the files and the delegate all of the hard work to the BibTeX class.
    """
    global options

    set_user_options()

    # now we are ready to read the BibTeX file and start working
    try:
        papers=options.bibtexfile.read()  # file already opened by argparse
        options.bibtexfile.close()
        asterisk=papers.index('@')
    except IOError:
        bib_error('unable to open bibtex file %s' % options.bibtexfile.name)

    # if we are checking for errors then we check EVERYTHING but, in this case,
    # we don't need to create a new bibtex file
    if not options.check:
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
        if not options.check:
            newbibfile.write('%s\n\n' % bt)

    if not options.check:
        newbibfile.close()

##############################################################################
if __name__ == '__main__':
  main()


# The following __doc__ string is used both to print the documentation and by
# setup.py to automatically generate the README file.
__doc__=r'''
=========
bibupdate
=========

{description}

usage: bibupdate [-h|-H] [-a] [-c] [-f] [-i FIELDS] [-l LOG] [-m | -M] [-q] [-r]
                 [-w LEN] bibtexfile [outputfile]

This is a command line tool for updating the entries in a BibTeX_ file using
mrlookup_. By default bibupdate_ tries to update the entry for each paper
in the BibTeX_ file unless the entry already has an ``mrnumber`` field (you can
disable future checking of an entry by giving it an empty ``mrnumber`` field).

**Options**::

  -a, --all             update or validate ALL BibTeX entries
  -c, --check           check/verify all bibtex entries against a database
  -k, --keep_fonts      do NOT replace fonts \Bbb, \germ and \scr in titles
  -h, --help            show this help message and exit
  -H, --Help            print full program description
  -i FIELDS, --ignored-fields FIELDS
                        a string of bibtex fields to ignore
  -l LOG, --log LOG     log messages to specified file (defaults to stdout)
  -o  --overwrite       overwrite existing bibtex file
  -q, --quieter         print fewer messages
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

-c --check      Check/validate all bibtex entries against a database

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
  with the --all option or the -check option).

-o  --overwrite  Overwrite the existing bibtex file with the updated version

  Replace the existing BibTeX_ file with the updated file. A backup version of
  the original BibTeX_ is made with a .bak extension. it is also possible to
  specify the output filename as the last argument to bibupdate.

-q, --quieter    Print fewer messages

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

- Add interface to the arXiv_ using http://arxiv.org/help/api 
  or http://arxiv.org/help/oa.
- Add flag to stop add list of fields that should not be changed
- More intelligent searches using MathSciNet_
- Add lookup using MRef and, when an entry is not found, allow additional
  searches
- Add an rc file?
- Fix the wrapping of bibtex fields.

Author
======

`Andrew Mathas`_

bibupdate_ Version {version}. Copyright (C) 2012,14 

{license}

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
.. _bibupdate: {url}
.. _download: http://bitbucket.org/AndrewsBucket/bibupdate/downloads/
.. _GPL: http://www.gnu.org/licenses/gpl.html
.. _hyperref: http://www.ctan.org/pkg/hyperref
.. _LaTeX: http://en.wikipedia.org/wiki/LaTeX
.. _MathSciNet: http://www.ams.org/mathscinet/
.. _mrlookup: http://www.ams.org/mrlookup
.. _Python: https://www.python.org/
'''.format(**bibup)

