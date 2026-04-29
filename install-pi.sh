#!/bin/bash

echo "Installing Pi Coding Agent..."
npm install -g @mariozechner/pi-coding-agent

echo "Setting up Pi Agent configuration..."
mkdir -p ~/.pi/agent
cp /workspaces/docs/.pi/models.json.example ~/.pi/agent/models.json