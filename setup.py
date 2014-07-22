from setuptools import setup

import bibupdate
setup(name='bibupdate',
      version=bibupdate.__version__,
      description='Automatically update the entries of a bibtex file using mrlookup/MathSciNet',
      keywords = 'bibtex, mrlookup, MathSciNet, latex',

      author='Andrew Mathas',
      author_email='andrew.mathas@gmail.com',
      url='https://bitbucket.org/AndrewsBucket/bibupdate',

      packages=['bibupdate'],
      entry_points={'console_scripts': ['bibupdate = bibupdate:main', ],},

      install_requires = ['fuzzywuzzy >= 0.2'],

      long_description=open('README.rst').read(),
      license=bibupdate.__license__,

      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Programming Language :: Python :: 2.7',
          'Topic :: Text Processing :: Markup :: LaTeX',
          'Topic :: Utilities'
      ],
)
