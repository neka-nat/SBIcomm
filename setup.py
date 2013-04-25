from setuptools import setup, find_packages

setup(name='SBIcomm', version='0.1.1',
      description='Python Interface for SBI Securities',
      author='neka-nat',
      author_email='nekanat.stock@gmail.com',
      packages=find_packages(),
      install_requires=['python-dateutil', 'mechanize', 'lxml'])
