from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

extensions = [
    Extension(
        "rock_paper_scissors_core",
        ["rock_paper_scissors_core.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=["-O3", "-march=native", "-ffast-math"],
    )
]

setup(
    ext_modules=cythonize(extensions, annotate=True),
)
