# `spike-fi`: `spike` with (experimental) fault induction support

<!--- ==================================================================== --->

1. Clone the repo.

   ```sh
   git clone https://github.com/bristolcrypto/spike-fi.git ./spike-fi
   cd ./spike-fi
   git submodule update --init --recursive
   source ./bin/conf.sh
   ```

2. Fix paths, e.g., 
  
   ```sh
   export RISCV="${REPO_HOME}/build/riscv"
   ```

3. Build a multi-architecture 
   [tool-chain](https://github.com/riscv/riscv-gnu-toolchain)
   into `${RISCV}`:
  
   ```sh
   git clone https://github.com/riscv/riscv-gnu-toolchain.git ${REPO_HOME}/build/riscv-gnu-toolchain
   cd ${REPO_HOME}/build/riscv-gnu-toolchain
   sed -i '/shallow = true/d' .gitmodules
   sed -i 's/--depth 1//g' Makefile.in
   ./configure --prefix="${RISCV}" --enable-multilib --with-multilib-generator="rv32gc-ilp32--;rv64gc-lp64--"
   make
   ```

   noting that the `sed` lines are to deal with an
   [issue](https://github.com/riscv-collab/riscv-gnu-toolchain/issues/1669) 
   related to shallow cloning sub-modules.

4. Build `spike` and `pk`
   into `${RISCV}`:

   ```sh
   make --directory="${REPO_HOME}/spike" clone
   make --directory="${REPO_HOME}/spike" apply
   make --directory="${REPO_HOME}/spike" build
   ```

<!--- ==================================================================== --->

${RISCV}/bin/spike --isa='rv32imafdc_zicsr_zifencei_zicntr' --fi-enable --fi-trace --fi-debug --fi-spec='10:1.0:r:5:$:FFFFFFFF' --fi-seed=0 ${RISCV}/riscv32-unknown-elf/bin/pk ${REPO_HOME}/build/test.elf 2>&1 | more

- spike.cc
  - add --fi-enable and --fi-spec arguments

- fi.{h,cc}
  - structure to represent FI specification
  - support for parsing FI specification

- insn_template.cc
  - update PROLOGUE and EPILOGUE macros to insert opportunity for influence of FI

<!--- ==================================================================== --->
