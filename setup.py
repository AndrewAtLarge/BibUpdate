from setuptools import setup

setup(name='bibupdate',
      version='1.1',
      description='A script for updating the entries of a bibtex file using mrlookup',
      keywords = 'bibtex, mrlookup, MathSciNet, latex',

      author='Andrew Mathas',
      author_email='andrew.mathas@sydney.edu.au',
      url='https://bitbucket.org/aparticle/bibupdate',

      packages=['bibupdate'],
      entry_points={'console_scripts': ['bibupdate = bibupdate:main', ],},

      install_requires = ['fuzzywuzzy >= 0.2'],

      license='GPL',
      long_description=open('README.rst').read(),

      zip_safe=False
)
