from setuptools import setup, find_packages

with open('README.rst') as file:
    long_description = file.read()

setup(name='SBIcomm', version='0.1.3',
      description='Python Interface for SBI Securities',
      long_description=long_description,
      author='neka-nat',
      author_email='nekanat.stock@gmail.com',
      packages=find_packages(),
      install_requires=['python-dateutil', 'mechanize', 'lxml'])
