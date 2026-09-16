.PHONY: verify verify-binary build build-wine9 build-wine10 patcher release yaml checksums

verify:
	./scripts/verify-repo.sh

verify-binary:
	./scripts/verify-mciwave.sh binaries/mciwave-wine9-x86-aim.dll --published
	./scripts/verify-mciwave.sh binaries/mciwave-wine10-x86-aim.dll --published

build: build-wine9 build-wine10

build-wine9:
	WINE_VERSION=9.0 ./scripts/build-mciwave.sh

build-wine10:
	WINE_VERSION=10.0 ./scripts/build-mciwave.sh

patcher:
	python3 scripts/build-patcher.py

release: patcher
	python3 scripts/build-release.py
	python3 scripts/verify-release.py --require-published-bundle-checksum

yaml:
	python3 scripts/validate-yaml.py

checksums:
	./scripts/update-checksums.sh
