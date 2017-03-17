from setuptools import setup
from subprocess import call
import bibupdate, datetime, sys

install_requires = ['fuzzywuzzy >= 0.2']

# need to do the following properly...there's no point checking the version
# number on the system creating the distribution.
python_version=sys.version_info[:2]
if python_version < (2,6):
    print('bibupdate requires python 2.6 or later. Please upgrade python.')
    sys.exit(1)
elif python_version==(2,6):
    install_requires += [ 'argparse','ordereddict>=1.1' ]
elif python_version>=(3,0):
    print('bibupdate does not yet run under python 3.0 or higher. Please use python 2.')
    sys.exit(1)

# for generating ctan release log
ctan_specs=r'''# Generated: {today}
contribution=bibupdate
version={version}
name={author}
email={author_email}
summary={description}
directory=/support/bibupdate
DoNotAnnounce=0
announce={description}
notes=Requires python
license=free
freeversion=gpl
file=bibupdate.tar.gz
'''

# for creating the latex and pdf versions of the documentation in the doc directory
preamble=r'''\usepackage[a4paper,margin=15mm]{{geometry}}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{{hyperref}}
\hypersetup{{pdfcreator={{ Generated by python + rst2latex + pdfLaTeX }},
            pdfinfo={{Author  ={{ {author} }},
                     Keywords={{ {keywords} }},
                     License ={{ {license} }},
                     Subject ={{ {description} }},
                     Title   ={{ Bibupdate - version {version} }}
            }},
}}
'''

# generate the rst, tex and pdf version of the README file
if 'readme' in sys.argv:
    with open('README.rst','w') as rst_readme:
      rst_readme.write(bibupdate.__doc__)

    # we set --no-doc-title to stop rst2latex from overwriting the document title above
    preamble=' --no-doc-title --latex-preamble="{latex}"'.format(latex=preamble.format( **bibupdate.bibup ))
    call('rst2latex.py {opts} README.rst README.tex'.format(opts=preamble), shell=True)
    call('pdflatex README && pdflatex README', shell=True)

elif 'ctan' in sys.argv:
    bibupdate.bibup['today']='{:%d, %b %Y}'.format(datetime.date.today())
    with open('bibupdate.ctan','w') as ctan:
        ctan.write( ctan_specs.format(**bibupdate.bibup) )
    print('To upload to ctan run: ctanupload -F bibupdate.ctan')

else:
    setup(name=bibupdate.bibup['name'],
          author=bibupdate.bibup['author'],
          author_email=bibupdate.bibup['author_email'],
          description=bibupdate.bibup['description'],
          keywords=bibupdate.bibup['keywords'],
          license=bibupdate.bibup['license'],
          url=bibupdate.bibup['url'],
          version=bibupdate.bibup['version'],

          long_description=bibupdate.__doc__,

          py_modules = ['bibupate'],

          classifiers=[
              'Development Status :: 5 - Production/Stable',
              'Environment :: Console',
              'Intended Audience :: Science/Research',
              'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
              'Natural Language :: English',
              'Programming Language :: Python :: 2.7',
              'Topic :: Text Processing',
              'Topic :: Text Processing :: Markup :: LaTeX',
              'Topic :: Utilities'
          ],

          install_requires=install_requires,

          entry_points={'console_scripts': ['bibupdate = bibupdate:main', ],},
    )
