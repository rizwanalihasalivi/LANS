"""Research tools share a stable package name across CLI and test imports.

Qualified imports also keep Numba's cached module references loadable by spawned
campaign/runtime workers after pytest has exercised the same kernels.
"""
