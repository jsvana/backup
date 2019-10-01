from setuptools import setup

setup(
    name="backup",
    version="0.1",
    description="Backup files.",
    url="http://github.com/jsvana/backup",
    author="Jay Vana",
    author_email="jaysvana@gmail.com",
    license="MIT",
    packages=["backup"],
    zip_safe=False,
    entry_points={"console_scripts": ["backup=backup.main:main"]},
)
