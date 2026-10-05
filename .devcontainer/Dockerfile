FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

# RE/recon tooling used in phases 1-2 (tshark = wireshark-cli)
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        jq nmap tshark \
    && rm -rf /var/lib/apt/lists/*
