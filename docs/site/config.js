window.RESEARCH_GUIDE_RELEASE = {
  "version": "0.4.1",
  "installCommand": "(\n  installer=$(mktemp) &&\n  trap 'rm -f \"$installer\"' EXIT &&\n  curl -q --proto '=https' --proto-redir '=https' --tlsv1.2 -fLsS \\\n    https://github.com/LWH4Data/research-agent/releases/download/v0.4.1/install-release.sh \\\n    -o \"$installer\" &&\n  bash \"$installer\" --version 0.4.1\n)"
};
