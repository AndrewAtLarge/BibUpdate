# README #

This README would normally document whatever steps are necessary to get your application up and running.

### What is this repository for? ###

Usage: updata_bib <bibtex file>

This script tries to use mrlookup to update all of the entries in a bibtex
file except for the cite key which remains unchanged. Rather than
overwriting the bibtex a new file is created, called new+filename. The user
is advised to check it carefully for any errors in he new file!

On the entries in the bibtex file which do not already have an mrnumber field
are checked.

Although some care is taken to make sure that the new bibtex entries are
correct given the fuzzy nature of the search strings passed to mrlookup, and
possible errors in the existing bibtex file, there are no guarantees so you
are advised to check the updated file carefully!

Andrew Mathas

TODO:
 * add a flag so that the script checks all of the bibtex entries using mr-reference or mrlookup.
 * find the best match when mrlookup returns multiple entries! 
 * add dependencies
 * reconfigure so that the bibtex entries are printed in the same order to make
   it easier to diff the output. If this works then copy the original file to
   *.bak and put the updated file in its place.


* Quick summary
* Version
* [Learn Markdown](https://bitbucket.org/tutorials/markdowndemo)

### How do I get set up? ###

* Summary of set up
* Configuration
* Dependencies
* Database configuration
* How to run tests
* Deployment instructions

### Contribution guidelines ###

* Writing tests
* Code review
* Other guidelines

### Who do I talk to? ###

* Repo owner or admin
* Other community or team contact