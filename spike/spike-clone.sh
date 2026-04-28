#!/bin/bash

source ${PWD}/share.sh

# =============================================================================

if [ ! -d ${SPIKE_REPO} ] ; then
  git clone https://github.com/riscv/riscv-isa-sim.git ${SPIKE_REPO}
fi

cd ${SPIKE_REPO}
git fetch origin ${SPIKE_COMMIT}:${SPIKE_BRANCH}
git checkout ${SPIKE_BRANCH}

# =============================================================================
