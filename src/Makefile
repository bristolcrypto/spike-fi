export GCC_PREFIX  = ${RISCV}/bin/riscv64-unknown-elf-

export GCC_FLAGS  += -march='rv32imafdc_zicsr_zifencei_zicntr' -mabi='ilp32' -DXLEN='32'
export GCC_PATHS  += 
export GCC_LIBS   += 

${REPO_HOME}/build/test.o    : test.c test.h
	@${GCC_PREFIX}gcc ${GCC_FLAGS} ${GCC_PATHS} $(addprefix -I ,${INCLUDES}) ${CONF} -Wall -std='gnu99' -O3 -c -o ${@} $(filter-out %.h, ${^}) ${GCC_LIBS}
${REPO_HOME}/build/test.elf  : ${REPO_HOME}/build/test.o
	@${GCC_PREFIX}gcc ${GCC_FLAGS} ${GCC_PATHS} $(addprefix -I ,${INCLUDES}) ${CONF} -Wall -std='gnu99' -O3    -o ${@}                   ${^}  ${GCC_LIBS}

${REPO_HOME}/build/test.bin  : ${REPO_HOME}/build/test.elf
	@${GCC_PREFIX}objcopy --output-target='binary' ${<}   ${@}
${REPO_HOME}/build/test.asm  : ${REPO_HOME}/build/test.elf
	@${GCC_PREFIX}objdump --disassemble-all        ${<} > ${@}
${REPO_HOME}/build/test.size : ${REPO_HOME}/build/test.elf
	@${GCC_PREFIX}size -G -d                       ${<} > ${@}

build : ${REPO_HOME}/build/test.elf

run   : ${REPO_HOME}/build/test.elf
	@${RISCV}/bin/spike    --isa='rv32imafdc_zicsr_zifencei_zicntr' ${RISCV}/riscv32-unknown-elf/bin/pk ${<}

debug : ${REPO_HOME}/build/test.elf
	@${RISCV}/bin/spike -d --isa='rv32imafdc_zicsr_zifencei_zicntr' ${RISCV}/riscv32-unknown-elf/bin/pk ${<}

trace : ${REPO_HOME}/build/test.elf
	@${RISCV}/bin/spike -l --isa='rv32imafdc_zicsr_zifencei_zicntr' ${RISCV}/riscv32-unknown-elf/bin/pk ${<}

clean :
	@rm --force ${REPO_HOME}/build/test.o
	@rm --force ${REPO_HOME}/build/test.elf

	@rm --force ${REPO_HOME}/build/test.bin
	@rm --force ${REPO_HOME}/build/test.asm
	@rm --force ${REPO_HOME}/build/test.size
