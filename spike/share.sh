#!/bin/bash

# =============================================================================

export PK_REPO="${REPO_HOME}/build/riscv-pk"
export PK_BUILD="${PK_REPO}/build"
export PK_COMMIT="9c61d29846d8521d9487a57739330f9682d5b542"
export PK_BRANCH="spike-fi"
export PK_PATCH="${PWD}/pk.patch"
export PK_INSTALL="${REPO_HOME}/build/riscv"

export SPIKE_REPO="${REPO_HOME}/build/riscv-isa-sim"
export SPIKE_BUILD="${SPIKE_REPO}/build"
export SPIKE_COMMIT="770ce31f7543f57472b35e66600085ea81184bb2"
export SPIKE_BRANCH="spike-fi"
export SPIKE_PATCH="${PWD}/spike.patch"
export SPIKE_INSTALL="${REPO_HOME}/build/riscv"

# =============================================================================
