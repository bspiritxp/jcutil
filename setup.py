import setuptools

with open('README.md', 'r', encoding='utf8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='jcutil',
    version='0.0.6',
    author='Jochen.He',
    author_email='thjl@hotmail.com',
    description='some python util tools in one package',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='',
    python_requires='>=3.8',
    depends=[
        'colorama',
        'joblib',
        'pymongo',
        'pycryptodomex',
        'apscheduler',
        'pyyaml',
        'python-consul',
        'python-redis',
    ],
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        "License :: OSI Approved :: MIT License",
    ]
)
