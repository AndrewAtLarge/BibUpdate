from setuptools import setup

setup(name='update_bib',
      version='1.1beta',
      description='A script for updating the entries of a bibtex file using mrlookup',
      keywords = 'bibtex, mrlookup, MathSciNet, latex',

      author='Andrew Mathas',
      author_email='andrew.mathas@sydney.edu.au',
      url='https://bitbucket.org/aparticle/update_bib',

      packages=['update_bib'],
      entry_points={'console_scripts': ['update_bib = update_bib:main', ],},

      install_requires = ['fuzzywuzzy >= 0.2'],

      license='GPL',
      long_description=open('README.rst').read(),

      zip_safe=False
)
