from setuptools import setup
setup(
    name='pyled1248',
    version='0.1',
    packages=['pyled1248'],
    install_requires=[
        'Bleak',
        'Pillow',
    ],
    include_package_data=True,
)