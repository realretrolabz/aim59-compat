.PHONY: verify verify-binary build patcher release yaml checksums

verify:
	./scripts/verify-repo.sh

verify-binary:
	./scripts/verify-mciwave.sh binaries/mciwave-wine9-x86-aim.dll --published

build:
	./scripts/build-mciwave.sh

patcher:
	python3 scripts/build-patcher.py

release: patcher
	python3 scripts/build-release.py
	python3 scripts/verify-release.py

yaml:
	python3 scripts/validate-yaml.py

checksums:
	./scripts/update-checksums.sh
