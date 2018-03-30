all: rpm

rpm:
	/bin/bash rpmbuild.sh

clean:
	rm -rf BUILD BUILDROOT RPMS SOURCES SPECS SRPMS
