"""PIP installer for audfill"""

from setuptools import setup, find_packages


def readme():
    """Get long description from README.md"""
    with open('README.md') as f:
        return f.read()


setup(
    name="Audfill",
    version="1.0.0",
    author="Luke Simmons",
    author_email="Luke5083@live.com",
    description="A script to automatically find a song's info.",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/Skyluker4/Audfill",
    packages=find_packages(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3",
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Topic :: Utilities',
        'Topic :: Multimedia :: Sound/Audio :: Analysis',
    ],
    python_requires='>=3.7',
    platforms=[
        'Linux',
        'MacOS X',
        'Windows'
    ],
    license='MIT License'
)
