# Env Setup FAQ

## Errors during pip installation

1. Rust Compiler

```
  error: can't find Rust compiler

  If you are using an outdated pip version, it is possible a prebuilt wheel is available for this package but pip is not able to install from it. Installing from the wheel would avoid the need for a Rust compiler.

  To update pip, run:

      pip install --upgrade pip

  and then retry package installation.

  If you did intend to build this package from source, try installing a Rust compiler from your system package manager and ensure it is on the PATH during installation. Alternatively, rustup (available at https://rustup.rs) is the recommended way to download and update the Rust compiler toolchain.

  This package requires Rust >=1.41.0.
  ----------------------------------------
  ERROR: Failed building wheel for cryptography
```

Solution: update pip as it suggests: `pip install --upgrade pip`
