# =============================================================================

COMPONENTS = pk spike

define rule_clone
$(strip ${1})-clone  :
	@${CURDIR}/$(strip ${1})-clone.sh
endef
define rule_apply
$(strip ${1})-apply  :
	@${CURDIR}/$(strip ${1})-apply.sh
endef
define rule_build
$(strip ${1})-build  :
	@${CURDIR}/$(strip ${1})-build.sh
endef
define rule_update
$(strip ${1})-update :
	@${CURDIR}/$(strip ${1})-update.sh
endef
define rule_revert
$(strip ${1})-revert :
	@${CURDIR}/$(strip ${1})-revert.sh
endef
define rule_clean
$(strip ${1})-clean  :
	@${CURDIR}/$(strip ${1})-clean.sh
endef

$(foreach COMPONENT,${COMPONENTS},$(eval $(call rule_clone, ${COMPONENT})))
$(foreach COMPONENT,${COMPONENTS},$(eval $(call rule_apply, ${COMPONENT})))
$(foreach COMPONENT,${COMPONENTS},$(eval $(call rule_build, ${COMPONENT})))
$(foreach COMPONENT,${COMPONENTS},$(eval $(call rule_update,${COMPONENT})))
$(foreach COMPONENT,${COMPONENTS},$(eval $(call rule_revert,${COMPONENT})))
$(foreach COMPONENT,${COMPONENTS},$(eval $(call rule_clean, ${COMPONENT})))

# -----------------------------------------------------------------------------

clone  : $(foreach COMPONENT, ${COMPONENTS}, ${COMPONENT}-clone)

apply  : $(foreach COMPONENT, ${COMPONENTS}, ${COMPONENT}-apply)

build  : $(foreach COMPONENT, ${COMPONENTS}, ${COMPONENT}-build)

update : $(foreach COMPONENT, ${COMPONENTS}, ${COMPONENT}-update)

revert : $(foreach COMPONENT, ${COMPONENTS}, ${COMPONENT}-revert)

clean  : $(foreach COMPONENT, ${COMPONENTS}, ${COMPONENT}-clean)

# =============================================================================
