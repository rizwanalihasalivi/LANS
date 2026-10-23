#!/usr/bin/env bash
set -euo pipefail
setup_root=/workspace/webots-setup
mkdir -p "$setup_root" "$setup_root/debs" "$setup_root/runtime" "$setup_root/apt/lists/partial" "$setup_root/apt/cache/archives/partial" "$setup_root/apt/empty"
if [ ! -x "$setup_root/webots/bin/webots-bin" ]; then
    curl -fL --retry 2 -o "$setup_root/webots-R2025a-x86-64.tar.bz2" https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a-x86-64.tar.bz2
    tar -xjf "$setup_root/webots-R2025a-x86-64.tar.bz2" -C "$setup_root"
fi
cat > "$setup_root/apt/sources.list" <<'EOF'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian bookworm main
EOF
cat > "$setup_root/apt/apt.conf" <<'EOF'
Dir::Etc::sourcelist "/workspace/webots-setup/apt/sources.list";
Dir::Etc::sourceparts "/workspace/webots-setup/apt/empty";
Dir::Etc::parts "/workspace/webots-setup/apt/empty";
Dir::State::lists "/workspace/webots-setup/apt/lists";
Dir::Cache "/workspace/webots-setup/apt/cache";
APT::Sandbox::User "agent";
EOF
export APT_CONFIG="$setup_root/apt/apt.conf"
apt-get update
cd "$setup_root/debs"
apt-get download xvfb/trixie xserver-common/trixie libgl1-mesa-dri/trixie libsndio7.0/bookworm libxfont2/trixie libxcvt0/trixie libglx-mesa0/trixie libegl-mesa0/trixie
for pkg in ./*.deb; do dpkg-deb -x "$pkg" "$setup_root/runtime"; done
bash "$setup_root/run-webots.sh" --version
