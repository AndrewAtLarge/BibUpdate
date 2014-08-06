from setuptools import setup
import bibupdate, sys

install_requires = ['fuzzywuzzy >= 0.2']
if sys.version_info[:2] < (2, 7):
    install_requires += [
        'argparse',
    ]

# generate the README file
if 'readme' in sys.argv:
    from readme import readme_text
    with open('README.rst','w') as rst_readme:
      rst_readme.write(readme_text.format( **bibupdate.__dict__ ))
    # now create the latex and pdf versions of the documentation in the doc directory
    from subprocess import call
    preamble=r'''\usepackage[a4paper,margin=15mm]{{geometry}}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{{hyperref}}
\hypersetup{{pdfcreator={{ Generated by python + rst2latex + pdfLaTeX }},
            pdfinfo={{Author  ={{ {__author__} }},
                     Keywords={{ {__keywords__} }},
                     License ={{ {__license__} }},
                     Subject ={{ {__description__} }},
                     Title   ={{ Bibupdate - version {__version__} }}
            }},
}}
'''
    # we set --no-doc-title to stop rst2latex from overwriting the document title above
    preamble=' --no-doc-title --latex-preamble="{latex}"'.format(latex=preamble.format( **bibupdate.__dict__ ))
    call('rst2latex.py {opts} README.rst doc/README.tex'.format(opts=preamble), shell=True)
    call('cd doc && pdflatex README && pdflatex README', shell=True)

else:
    setup(name='bibupdate',
          author=bibupdate.__author__,
          author_email=bibupdate.__author_email__,

          description=bibupdate.__description__,
          keywords=bibupdate.__keywords__,
          license=bibupdate.__license__,
          long_description=open('README.rst').read(),
          url=bibupdate.__url__,
          version=bibupdate.__version__,

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
