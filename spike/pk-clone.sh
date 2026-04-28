#!/bin/bash

source ${PWD}/share.sh

# =============================================================================

if [ ! -d ${PK_REPO} ] ; then
  git clone https://github.com/riscv/riscv-pk.git ${PK_REPO}
fi

cd ${PK_REPO}
git fetch origin ${PK_COMMIT}:${PK_BRANCH}
git checkout ${PK_BRANCH}

# =============================================================================
