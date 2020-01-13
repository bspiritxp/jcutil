import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='JC python utils',
    version='0.0.1b',
    author='Jochen.He',
    author_email='thjl@hotmail.com',
    description='some util tools',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: MIT License',
    ]
)
