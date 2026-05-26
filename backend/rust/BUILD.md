# Build requires a C toolchain (gcc or clang) and Python dev headers.
#
# Ubuntu / Debian:
#   sudo apt install build-essential python3-dev
#   source "$HOME/.cargo/env"
#   cd backend/rust
#   cargo build --release
#
# The .so lands at  target/release/lib_nexus3d_rust.so
#
# To build a pip-installable wheel:
#   pip install maturin
#   cd backend/rust
#   maturin build --release
