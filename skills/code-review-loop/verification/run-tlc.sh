#!/bin/sh
set -eu

verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
java_bin=${JAVA_BIN:-}

if [ -z "$java_bin" ]; then
    if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
        java_bin=$JAVA_HOME/bin/java
    fi
fi

if [ -z "$java_bin" ] && command -v java >/dev/null 2>&1; then
    path_java=$(command -v java)
    if "$path_java" -version >/dev/null 2>&1; then
        java_bin=$path_java
    fi
fi

if [ -z "$java_bin" ] && [ -x /opt/homebrew/opt/openjdk/bin/java ]; then
    java_bin=/opt/homebrew/opt/openjdk/bin/java
fi

if [ -z "$java_bin" ]; then
    echo "Java 11 or newer is required. Set JAVA_BIN to its executable." >&2
    exit 1
fi

data_root=${XDG_DATA_HOME:-${HOME:?}/.local/share}
default_tools_jar=$data_root/tlaplus/2026.08.11.125311-0894c34/tla2tools.jar
pinned_tools_sha=ab323b79802aedc3203b3f9af37c6aca3ed43f4e0225b36f2aa77b26de46c05f
metadata_dir=${TLC_METADIR:-${TMPDIR:-/tmp}/code-review-loop-tlc}
config_name=${TLC_CONFIG:-CodeReviewLoop.cfg}

if [ -n "${TLA2TOOLS_JAR:-}" ]; then
    tools_jar=$TLA2TOOLS_JAR
    expected_tools_sha=${TLA2TOOLS_SHA256:-}
else
    tools_jar=$default_tools_jar
    expected_tools_sha=$pinned_tools_sha
fi

case $config_name in
    /*) config_path=$config_name ;;
    *) config_path=$verification_dir/$config_name ;;
esac

if [ ! -f "$tools_jar" ]; then
    echo "TLA+ tools not found at $tools_jar" >&2
    echo "Set TLA2TOOLS_JAR to a tla2tools.jar location." >&2
    exit 1
fi

if [ ! -f "$config_path" ]; then
    echo "TLC config not found at $config_path" >&2
    exit 1
fi

if [ -n "$expected_tools_sha" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
        actual_tools_sha=$(sha256sum "$tools_jar" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
        actual_tools_sha=$(shasum -a 256 "$tools_jar" | awk '{print $1}')
    else
        echo "sha256sum or shasum is required to verify tla2tools.jar." >&2
        exit 1
    fi

    if [ "$actual_tools_sha" != "$expected_tools_sha" ]; then
        echo "TLA+ tools SHA-256 mismatch." >&2
        echo "Expected: $expected_tools_sha" >&2
        echo "Actual:   $actual_tools_sha" >&2
        exit 1
    fi
elif [ -n "${TLA2TOOLS_JAR:-}" ]; then
    echo "Warning: custom TLA2TOOLS_JAR is not digest-verified; set TLA2TOOLS_SHA256." >&2
fi

case ${TLC_COVERAGE:-0} in
    0|"")
        set --
        ;;
    1)
        set -- -coverage 1
        ;;
    *)
        echo "TLC_COVERAGE must be 0 or 1." >&2
        exit 1
        ;;
esac

exec "$java_bin" \
    -XX:+UseParallelGC \
    -cp "$tools_jar" \
    tlc2.TLC \
    -cleanup \
    -noGenerateSpecTE \
    "$@" \
    -workers auto \
    -metadir "$metadata_dir" \
    -config "$config_path" \
    "$verification_dir/CodeReviewLoop.tla"
