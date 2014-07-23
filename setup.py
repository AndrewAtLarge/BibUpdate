from setuptools import setup
import bibupdate, sys

install_requires = ['fuzzywuzzy >= 0.2']
if sys.version_info[:2] < (2, 7):
    install_requires += [
        'argparse',
    ]

setup(name='bibupdate',
      author=bibupdate.__author__,
      author_email=bibupdate.__author_email__,

      description=bibupdate.__description__,
      keywords=bibupdate.__keywords__,
      license=bibupdate.__license__,
      long_description=open('README.rst').read(),
      url=bibupdate.__url__,
      version=bibupdate.__version__,

      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Natural Language :: English',
          'Programming Language :: Python :: 2.7',
          'Topic :: Text Processing :: Markup :: LaTeX',
          'Topic :: Utilities'
      ],

      install_requires=install_requires,

      packages=['bibupdate'],
      entry_points={'console_scripts': ['bibupdate = bibupdate:main', ],},
)
