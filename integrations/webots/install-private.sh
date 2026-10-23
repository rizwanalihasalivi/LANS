#!/usr/bin/env bash
set -euo pipefail
setup_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.runtime
mkdir -p "$setup_root" "$setup_root/debs" "$setup_root/runtime" "$setup_root/apt/lists/partial" "$setup_root/apt/cache/archives/partial" "$setup_root/apt/empty"
# This installer writes only beneath this integration's ignored .runtime directory.
archive=webots-R2025a-x86-64.tar.bz2
if [ ! -f "$setup_root/$archive" ]; then
    curl -fL --retry 2 -o "$setup_root/$archive" "https://github.com/cyberbotics/webots/releases/download/R2025a/$archive"
fi
mkdir -p "$setup_root/protos"
upstream=c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b
for proto in Car AckermannVehicle VehicleWheel VehicleLights GenericTireAppearance; do
    if [ ! -f "$setup_root/protos/$proto.proto" ]; then
        curl -fL --retry 2 -o "$setup_root/protos/$proto.proto" \
            "https://raw.githubusercontent.com/cyberbotics/webots/$upstream/projects/vehicles/protos/abstract/$proto.proto"
    fi
done
(cd "$setup_root" && sha256sum -c ../runtime-sha256.txt)
if [ ! -x "$setup_root/webots/bin/webots-bin" ]; then
    tar -xjf "$setup_root/$archive" -C "$setup_root"
fi
cat > "$setup_root/apt/sources.list" <<EOF
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian bookworm main
EOF
cat > "$setup_root/apt/apt.conf" <<EOF
Dir::Etc::sourcelist "${setup_root}/apt/sources.list";
Dir::Etc::sourceparts "${setup_root}/apt/empty";
Dir::Etc::parts "${setup_root}/apt/empty";
Dir::State::lists "${setup_root}/apt/lists";
Dir::Cache "${setup_root}/apt/cache";
APT::Sandbox::User "$(id -un)";
EOF
export APT_CONFIG="$setup_root/apt/apt.conf"
apt-get update
cd "$setup_root/debs"
apt-get download xvfb/trixie xserver-common/trixie libgl1-mesa-dri/trixie libsndio7.0/bookworm libxfont2/trixie libxcvt0/trixie libglx-mesa0/trixie libegl-mesa0/trixie
for pkg in ./*.deb; do dpkg-deb -x "$pkg" "$setup_root/runtime"; done
bash "$(dirname "$setup_root")/run-webots.sh" --version
