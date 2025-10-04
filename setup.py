from setuptools import setup, find_packages

setup(
    name="afterinstall",
    version="1.0.0",
    author="sTershon",
    author_email="gansta252552525@gmail.com",
    description="Приложение для настройки Windows после установки (PyQt6)",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/sTershon/AfterInstall",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.5"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    entry_points={
        "console_scripts": [
            "afterinstall=afterinstall.main:main"
        ]
    },
    include_package_data=True,
    python_requires=">=3.10",
)
