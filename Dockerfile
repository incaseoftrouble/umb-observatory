# Dockerfile for UMB Observatory. One file, two flavors, chosen with --build-arg FLAVOR=...
#
#   fast    (default) prebuilt Storm image (the `stable` release) + released umbi. Builds in minutes; Storm
#           and umbi may lag behind their development branches slightly.
#   source  Storm built from the git master branch and umbi from git main.
#           Everything is the latest version, but expect a long Storm compilation.
#
# Prism is the v4.11 release binary (PRISM_VERSION) in `fast` and built from the
# master branch in `source`. Modest is a downloaded binary (closed source): the
# latest version unless MODEST_VERSION names one, e.g. v3.1.315-g0a0763b35.
#
#   docker build --build-arg FLAVOR=source -t umb-observatory:source .

ARG FLAVOR=fast
ARG FAST_BASE_IMAGE=movesrwth/storm:stable
ARG SOURCE_BASE_IMAGE=movesrwth/storm-dependencies:latest


######################################################################
# Flavor "fast": Storm is a prebuilt binary at /usr/local/bin/storm
FROM $FAST_BASE_IMAGE AS base-fast
# umbi 0.2.12 (the current PyPI release) cannot read valuations with bitstring>=5; drop the pin
# once a release containing the fix (0.2.13) is on PyPI.
ENV UMB_UMBI_SPEC=umbi UMB_UMBI_PIN=bitstring<5


######################################################################
# Flavor "source": build Storm from source, mirroring the Storm Dockerfile
FROM $SOURCE_BASE_IMAGE AS base-source
ARG storm_repo=https://github.com/moves-rwth/storm.git
# storm_ref is a branch, tag or commit SHA (CI passes the SHA of master to pin "latest")
ARG storm_ref=master
ARG no_threads=4
ARG carl_repo="https://github.com/stormchecker/carl-storm.git"
ARG carl_tag="14.36"
COPY .docker/git-checkout.sh /opt/git-checkout.sh
RUN /opt/git-checkout.sh $storm_repo $storm_ref /opt/storm
WORKDIR /opt/storm/build
RUN cmake -DCMAKE_BUILD_TYPE=Release -DSTORM_PORTABLE=ON \
          -DSTORM_CARL_GIT_REPO=$carl_repo -DSTORM_CARL_GIT_TAG=$carl_tag \
          -DSTORM_USE_CLN_RF=ON .. \
 && make -j $no_threads binaries \
 && ln -s /opt/storm/build/bin/storm /usr/local/bin/storm
ENV UMB_UMBI_SPEC="umbi @ git+https://github.com/randriu/umbi.git" UMB_UMBI_PIN=


######################################################################
# Common part
FROM base-${FLAVOR} AS umbobservatory
LABEL org.opencontainers.image.authors="pmctools"

ARG FLAVOR
ENV UMB_FLAVOR=$FLAVOR
EXPOSE 8000

# default-jdk: prism (ninja-build and the JDK are also needed for the source build); unzip, xz-utils: modest
RUN apt-get update -qq \
 && apt-get install -yqq --no-install-recommends \
    python-is-python3 python3-pip python3-venv \
    unzip ninja-build libboost-iostreams-dev default-jdk xz-utils \
 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m pip install --no-cache-dir jupyter jupytext matplotlib scipy pytest

# Prism (see .docker/install-prism.sh): the release binary for `fast`, built from source for `source`
ARG PRISM_VERSION=4.11
ARG PRISM_REPO=https://github.com/prismmodelchecker/prism.git
ARG PRISM_REF=master
ENV PRISM_VERSION=$PRISM_VERSION PRISM_REPO=$PRISM_REPO PRISM_REF=$PRISM_REF
WORKDIR /opt/
COPY .docker/git-checkout.sh .docker/install-prism.sh ./
RUN bash install-prism.sh "$([ "$FLAVOR" = source ] && echo source || echo binary)"

# Modest
WORKDIR /opt/
ARG MODEST_VERSION=LATEST
ENV MODEST_VERSION=$MODEST_VERSION
COPY .docker/install-modest.sh install-modest.sh
RUN bash install-modest.sh

RUN storm --version

# umbi: the default spec and the pin, if any, are set per flavor above. UMBI_SPEC overrides the
# spec (CI passes e.g. umbi==0.2.12 or umbi @ git+...@<sha> so cached layers cannot go stale).
ARG UMBI_SPEC=
RUN python3 -m pip install --no-cache-dir "${UMBI_SPEC:-$UMB_UMBI_SPEC}" $UMB_UMBI_PIN

# Regression models (separate repository)
ARG REGRESSION_REPO=https://github.com/pmc-tools/umb-regression.git
ARG REGRESSION_REF=main
COPY .docker/git-checkout.sh /opt/git-checkout.sh
RUN /opt/git-checkout.sh $REGRESSION_REPO $REGRESSION_REF /opt/umb-regression
ENV UMB_REGRESSION_DIR=/opt/umb-regression

RUN mkdir /opt/umb
WORKDIR /opt/umb
COPY . .
# The notebook sources live in markdown; materialize the .ipynb for the server.
RUN jupytext --to ipynb getting_started.md
COPY .docker/tools.toml tools.toml
RUN chmod +x .docker/start-notebook.sh

# Entrypoint of the base images is cleared so `docker run IMAGE bash` works.
ENTRYPOINT []
CMD ["/opt/umb/.docker/start-notebook.sh"]
