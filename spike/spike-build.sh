#!/bin/bash

source ${PWD}/share.sh

# =============================================================================

if [ -d ${SPIKE_BUILD} ] ; then
    rm --force --recursive ${SPIKE_BUILD}
fi

mkdir --parents ${SPIKE_INSTALL}
mkdir --parents ${SPIKE_BUILD}

export PATH="${RISCV}/bin:${PATH}"

cd ${SPIKE_BUILD}
../configure --prefix="${SPIKE_INSTALL}" --target="riscv64-unknown-elf" --with-isa="rv32gcb"
make
make install

# =============================================================================

